# Adapted from OpenCore Legacy Patcher 3.0.0 (sys_patch), BSD-4-Clause, see LICENSE.
import ctypes
import plistlib
import re
from pathlib import Path

import patchsets
import runner

SYSTEM_VERSION_PLIST = "/System/Library/CoreServices/SystemVersion.plist"
OCLP_PLIST = "/System/Library/CoreServices/OpenCore-Legacy-Patcher.plist"
RECORD_PATH = "System/Library/CoreServices/MacPatch.plist"
RECORD_PLIST = "/" + RECORD_PATH
AMFIPASS_COMPATIBILITY_VERSION = (1, 2, 1)

AMFI_ALLOW_INVALID_SIGNATURE = 0x2
AMFI_ALLOW_EVERYTHING = 0x80

UNSUPPORTED_HOST_OS = "Unsupported Host OS"
MISSING_NETWORK_CONNECTION = "Missing Network Connection"
FILEVAULT_ENABLED = "FileVault is enabled"
SIP_ENABLED = "System Integrity Protection is enabled"
AMFI_ENABLED = "AMFI is enabled"
REPATCHING_NOT_SUPPORTED = "Revert first to update or reinstall patches"
ROOT_NOT_SNAPSHOT = "Root volume is not an APFS snapshot"

# Keep in sync with sysvol.write_record
WIRELESS_KEYS = {"Legacy Wireless", "Legacy Wireless Extended", "Modern Wireless Common", "Modern Wireless Extended"}
METADATA_KEYS = {"MacPatch", "PatcherSupportPkg", "Time Patched", "Kernel Debug Kit Used", "OS Version"}


def parse_sw_vers(text):
    values = {}
    for line in text.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            values[key.strip()] = value.strip()
    return values


def system_build():
    # sw_vers reports the Rapid Security Response build (e.g. 22F770820d); the system volume keeps the base build
    with open(SYSTEM_VERSION_PLIST, "rb") as source:
        return plistlib.load(source)["ProductBuildVersion"]


class Host:
    def __init__(self):
        release = runner.run(["/usr/bin/uname", "-r"], merge=False).stdout.strip()
        parts = (release.split(".") + ["0", "0"])[:2]
        self.xnu_major = int(parts[0])
        self.xnu_minor = int(parts[1])
        versions = parse_sw_vers(runner.run(["/usr/bin/sw_vers"], merge=False).stdout)
        self.os_version = versions.get("ProductVersion", "")
        self.os_build = system_build()


def csr_active_config():
    libsystem = ctypes.CDLL("/usr/lib/libSystem.dylib")
    value = ctypes.c_uint32(0)
    if libsystem.csr_get_active_config(ctypes.byref(value)) != 0:
        return 0
    return value.value


def unsupported_host_os(xnu_major):
    return xnu_major < patchsets.BIG_SUR or xnu_major > patchsets.TAHOE


def filevault_enabled(xnu_major):
    if xnu_major < patchsets.BIG_SUR:
        return False
    return "FileVault is Off" not in runner.run(["/usr/bin/fdesetup", "status"]).stdout


def sip_enabled(active, required):
    return active & required != required


def root_volume():
    result = runner.run(["/usr/sbin/diskutil", "info", "-plist", "/"], merge=False)
    try:
        info = plistlib.loads(result.stdout.encode("utf-8"))
    except Exception:
        raise RuntimeError("Failed to parse diskutil output.")
    disk = info["DeviceIdentifier"]
    snapshot = info.get("APFSSnapshot") is True
    if snapshot:
        # disk1s1s1 -> disk1s1
        disk = disk[:-2]
    return disk, snapshot


def nvram_boot_args():
    result = runner.run(["/usr/sbin/nvram", "boot-args"], merge=False)
    if result.returncode != 0 or "\t" not in result.stdout:
        return ""
    return result.stdout.split("\t", 1)[1].strip()


def loaded_kext_version(bundle_id):
    args = ["/usr/sbin/kextstat", "-list-only", "-bundle-id", bundle_id]
    if Path("/usr/bin/kmutil").exists():
        args = ["/usr/bin/kmutil", "showloaded", "--list-only", "--variant-suffix", "release", "--optional-identifier", bundle_id]
    result = runner.run(args)
    if result.returncode != 0:
        return ""
    match = re.search(re.escape(bundle_id) + r"\s+\((?P<version>.+?)\)", result.stdout)
    return match.group("version") if match else ""


def amfi_flags(boot_args):
    flags = {"skip_library_validation": False, "allow_invalid_signature": False, "allow_everything": False}
    args = boot_args.split()
    for arg in args:
        if not arg.startswith("amfi="):
            continue
        try:
            value = arg.split("=")[1]
            value = int(value, 16) if value.startswith("0x") else int(value)
        except (IndexError, ValueError):
            value = 0
        if value & AMFI_ALLOW_INVALID_SIGNATURE:
            flags["allow_invalid_signature"] = True
        if value & AMFI_ALLOW_EVERYTHING:
            flags = {"skip_library_validation": True, "allow_invalid_signature": True, "allow_everything": True}
        break
    for arg in args:
        if arg.startswith("amfi_allow_any_signature=") and arg.split("=")[1] in ("0x1", "1"):
            flags["allow_invalid_signature"] = True
        elif arg.startswith("amfi_get_out_of_my_way=") and arg.split("=")[1] in ("0x1", "1"):
            flags = {"skip_library_validation": True, "allow_invalid_signature": True, "allow_everything": True}
    return flags


def amfi_level_met(level, boot_args, amfipass_version):
    # With a recent AMFIPass loaded the patched binaries run without AMFI boot-args
    if amfipass_version and patchsets.version_tuple(amfipass_version) >= AMFIPASS_COMPATIBILITY_VERSION:
        level = patchsets.AMFI_NO_CHECK
    flags = amfi_flags(boot_args)
    if level == patchsets.AMFI_NO_CHECK:
        return True
    if level == patchsets.AMFI_LIBRARY_VALIDATION:
        return flags["skip_library_validation"]
    if level == patchsets.AMFI_LIBRARY_VALIDATION_AND_SIG:
        return flags["skip_library_validation"] and flags["allow_invalid_signature"]
    return flags["allow_everything"]


def network_available():
    return runner.run(["/usr/bin/curl", "-sI", "--max-time", "5", "-o", "/dev/null", "https://github.com"]).returncode == 0


def repatching_not_supported():
    if Path(OCLP_PLIST).exists():
        # patched by OpenCore Legacy Patcher or a fork of it, which tracks its own files
        return True
    try:
        with open(RECORD_PLIST, "rb") as record:
            existing = set(plistlib.load(record))
    except Exception:
        return False
    return bool(existing - WIRELESS_KEYS - METADATA_KEYS)


def has_networking_patches():
    try:
        with open(RECORD_PLIST, "rb") as record:
            return bool(WIRELESS_KEYS & set(plistlib.load(record)))
    except Exception:
        return False


def validate(host, set_ids, kdk_missing, payload_missing):
    required_sip = patchsets.required_sip(set_ids, host.xnu_major)
    active_sip = csr_active_config()
    _, snapshot = root_volume()
    requires_network = kdk_missing or payload_missing

    checks = [
        (UNSUPPORTED_HOST_OS, unsupported_host_os(host.xnu_major)),
        (MISSING_NETWORK_CONNECTION, requires_network and not network_available()),
        (FILEVAULT_ENABLED, filevault_enabled(host.xnu_major)),
        (SIP_ENABLED, sip_enabled(active_sip, required_sip)),
    ]
    if checks[-1][1]:
        checks.append(("Booted SIP: {} vs expected: {}".format(hex(active_sip), hex(required_sip)), True))
    checks.extend([
        (AMFI_ENABLED, not amfi_level_met(patchsets.required_amfi(set_ids), nvram_boot_args(), loaded_kext_version("com.dhinakg.AMFIPass"))),
        (REPATCHING_NOT_SUPPORTED, repatching_not_supported()),
        (ROOT_NOT_SNAPSHOT, host.xnu_major >= patchsets.BIG_SUR and not snapshot),
    ])
    return [name for name, failed in checks if failed]


def validate_revert(host):
    required_sip = patchsets.root_patch_sip(host.xnu_major)
    active_sip = csr_active_config()
    failures = []
    if unsupported_host_os(host.xnu_major):
        failures.append(UNSUPPORTED_HOST_OS)
    if sip_enabled(active_sip, required_sip):
        failures.append(SIP_ENABLED)
        failures.append("Booted SIP: {} vs expected: {}".format(hex(active_sip), hex(required_sip)))
    return failures
