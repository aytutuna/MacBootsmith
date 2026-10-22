# Adapted from OpenCore Legacy Patcher 3.0.0 (sys_patch), BSD-4-Clause, see LICENSE.
import re

OVERWRITE_SYSTEM_VOLUME = "Overwrite System Volume"
MERGE_SYSTEM_VOLUME = "Merge System Volume"
REMOVE_SYSTEM_VOLUME = "Remove System Volume"
EXECUTE = "Execute"
INSTALL_TYPES = (OVERWRITE_SYSTEM_VOLUME, MERGE_SYSTEM_VOLUME)

CATALINA = 19
BIG_SUR = 20
MONTEREY = 21
VENTURA = 22
SONOMA = 23
SEQUOIA = 24
TAHOE = 25

CSR_ALLOW_UNTRUSTED_KEXTS = 0x1
CSR_ALLOW_UNRESTRICTED_FS = 0x2
CSR_ALLOW_UNAPPROVED_KEXTS = 0x200
CSR_ALLOW_UNAUTHENTICATED_ROOT = 0x800

AMFI_NO_CHECK = 0
AMFI_LIBRARY_VALIDATION = 1
AMFI_LIBRARY_VALIDATION_AND_SIG = 2
AMFI_ALLOW_ALL = 3


def version_tuple(version):
    parts = [int(part) for part in re.findall(r"\d+", str(version))[:3]]
    return tuple((parts + [0, 0, 0])[:3])


def root_patch_sip(xnu_major):
    if xnu_major >= VENTURA:
        return CSR_ALLOW_UNTRUSTED_KEXTS | CSR_ALLOW_UNRESTRICTED_FS | CSR_ALLOW_UNAUTHENTICATED_ROOT
    if xnu_major >= BIG_SUR:
        return CSR_ALLOW_UNRESTRICTED_FS | CSR_ALLOW_UNAUTHENTICATED_ROOT
    return CSR_ALLOW_UNTRUSTED_KEXTS | CSR_ALLOW_UNRESTRICTED_FS | CSR_ALLOW_UNAPPROVED_KEXTS


def _modern_audio_native(xnu_major, os_build):
    if xnu_major < TAHOE:
        return True
    # Tahoe Beta 1 still shipped AppleHDA
    return os_build == "25A5279m"


def _modern_audio_patches(xnu_major, xnu_minor, os_build, os_version):
    return {
        "Modern Audio": {
            OVERWRITE_SYSTEM_VOLUME: {
                "/System/Library/Extensions": {
                    "AppleHDA.kext": "26.0 Beta 1",
                },
            },
        },
    }


def _modern_wireless_patches(xnu_major, xnu_minor, os_build, os_version):
    patches = {
        "Modern Wireless Common": {
            OVERWRITE_SYSTEM_VOLUME: {
                "/usr/libexec": {
                    "wifip2pd": "13.7.2-{}".format(xnu_major),
                },
            },
            MERGE_SYSTEM_VOLUME: {
                "/System/Library/PrivateFrameworks": {
                    "IO80211.framework": "13.7.2-{}".format(xnu_major),
                    "WiFiPeerToPeer.framework": "13.7.2-{}".format(xnu_major),
                },
            },
        },
    }
    if xnu_major <= SONOMA:
        patches["Modern Wireless Extended"] = {
            OVERWRITE_SYSTEM_VOLUME: {
                "/usr/libexec": {
                    "airportd": "13.7.2-{}".format(xnu_major),
                },
            },
            MERGE_SYSTEM_VOLUME: {
                "/System/Library/Frameworks": {
                    "CoreWLAN.framework": "13.7.2-{}".format(xnu_major),
                },
                "/System/Library/PrivateFrameworks": {
                    "CoreWiFi.framework": "13.7.2-{}".format(xnu_major),
                },
            },
        }
    return patches


def _affected_by_cve_2024_23227(xnu_major, os_version):
    # 12.7.4, 13.6.5 and 14.4 broke the old airportd; the security patch level is not in the XNU version
    if xnu_major > SONOMA:
        return True
    version = version_tuple(os_version)
    if os_version.startswith("12"):
        return version >= (12, 7, 4)
    if os_version.startswith("13"):
        return version >= (13, 6, 5)
    if os_version.startswith("14"):
        return version >= (14, 4, 0)
    return False


def _legacy_wireless_patches(xnu_major, xnu_minor, os_build, os_version):
    patches = {
        "Legacy Wireless": {
            OVERWRITE_SYSTEM_VOLUME: {
                "/usr/libexec": {
                    "airportd": "11.7.10-Sandbox" if _affected_by_cve_2024_23227(xnu_major, os_version) else "11.7.10",
                },
                "/System/Library/CoreServices": {
                    "WiFiAgent.app": "11.7.10",
                },
            },
        },
    }
    if xnu_major < VENTURA:
        return patches

    binary_version = "12.7.2" if xnu_major < SEQUOIA or xnu_major >= TAHOE else "12.7.2-{}".format(xnu_major)
    framework_version = "12.7.2" if xnu_major < SEQUOIA else "12.7.2-{}".format(xnu_major)
    patches["Legacy Wireless Extended"] = {
        OVERWRITE_SYSTEM_VOLUME: {
            "/usr/libexec": {
                "wps": binary_version,
                "wifip2pd": binary_version,
            },
        },
        MERGE_SYSTEM_VOLUME: {
            "/System/Library/Frameworks": {
                "CoreWLAN.framework": framework_version,
            },
            "/System/Library/PrivateFrameworks": {
                "CoreWiFi.framework": framework_version,
                "IO80211.framework": framework_version,
                "WiFiPeerToPeer.framework": framework_version,
            },
        },
    }
    return patches


def _no_kdk(xnu_major):
    return False


# Same order as OCLP's detection list, which is the order the patches are applied in.
SETS = {
    "legacy_wireless": {
        "name": "Networking: Legacy Wireless",
        "networking": True,
        "native_os": lambda xnu_major, os_build: xnu_major < MONTEREY,
        "requires_kdk": _no_kdk,
        "required_sip": root_patch_sip,
        "required_amfi": AMFI_ALLOW_ALL,
        "patches": _legacy_wireless_patches,
    },
    "modern_wireless": {
        "name": "Networking: Modern Wireless",
        "networking": True,
        "native_os": lambda xnu_major, os_build: xnu_major < SONOMA,
        "requires_kdk": _no_kdk,
        "required_sip": root_patch_sip,
        "required_amfi": AMFI_ALLOW_ALL,
        "patches": _modern_wireless_patches,
    },
    "modern_audio": {
        "name": "Miscellaneous: Modern Audio",
        "networking": False,
        "native_os": _modern_audio_native,
        "requires_kdk": lambda xnu_major: xnu_major >= TAHOE,
        "required_sip": root_patch_sip,
        "required_amfi": AMFI_ALLOW_ALL,
        "patches": _modern_audio_patches,
    },
}


def needed(set_ids, xnu_major, os_build):
    return [set_id for set_id in SETS if set_id in set_ids and not SETS[set_id]["native_os"](xnu_major, os_build)]


def merged_patches(set_ids, xnu_major, xnu_minor, os_build, os_version):
    patches = {}
    for set_id in set_ids:
        patches.update(SETS[set_id]["patches"](xnu_major, xnu_minor, os_build, os_version))
    return patches


def requires_kdk(set_ids, xnu_major):
    return xnu_major >= VENTURA and any(SETS[set_id]["requires_kdk"](xnu_major) for set_id in set_ids)


def required_sip(set_ids, xnu_major):
    mask = 0
    for set_id in set_ids:
        mask |= SETS[set_id]["required_sip"](xnu_major)
    return mask


def required_amfi(set_ids):
    return max([SETS[set_id]["required_amfi"] for set_id in set_ids] or [AMFI_NO_CHECK])
