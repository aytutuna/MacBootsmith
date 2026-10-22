# Adapted from OpenCore Legacy Patcher 3.0.0 (sys_patch), BSD-4-Clause, see LICENSE.
import json
import logging
import os
import plistlib
import tempfile
from pathlib import Path

import patchsets
import payload
import runner

KDK_INSTALL_PATH = "/Library/Developer/KDKs"
KDK_API_LINK = "https://dortania.github.io/KdkSupportPkg/manifest.json"
KEXT_CATALOG = [
    "System.kext/PlugIns/Libkern.kext/Libkern",
    "apfs.kext/Contents/MacOS/apfs",
    "IOUSBHostFamily.kext/Contents/MacOS/IOUSBHostFamily",
    "AMDRadeonX6000.kext/Contents/MacOS/AMDRadeonX6000",
]


def valid(kdk_path):
    version_plist = Path(kdk_path) / "System/Library/CoreServices/SystemVersion.plist"
    if not version_plist.exists():
        logging.info("- Corrupted KDK found (%s), missing SystemVersion.plist", Path(kdk_path).name)
        return False
    try:
        with open(version_plist, "rb") as source:
            kdk_build = plistlib.load(source)["ProductBuildVersion"]
    except Exception:
        logging.info("- Corrupted KDK found (%s), missing ProductBuildVersion", Path(kdk_path).name)
        return False

    # macOS updates delete files from KDKs; the pkg receipt lists what should be there
    result = runner.run(["/usr/sbin/pkgutil", "--files", "com.apple.pkg.KDK.{}".format(kdk_build)], merge=False)
    if result.returncode != 0:
        for kext in KEXT_CATALOG:
            if not (Path(kdk_path) / "System/Library/Extensions" / kext).exists():
                logging.info("- Corrupted KDK found (%s), missing %s", Path(kdk_path).name, kext)
                return False
        return True
    for line in result.stdout.splitlines():
        if line.startswith("System/Library/Extensions") and not (Path(kdk_path) / line).exists():
            logging.info("- Corrupted KDK found (%s), missing %s", Path(kdk_path).name, line)
            return False
    return True


def installed(match, check_version=False):
    if not Path(KDK_INSTALL_PATH).is_dir():
        return None
    for folder in sorted(Path(KDK_INSTALL_PATH).iterdir()):
        if not folder.is_dir():
            continue
        if check_version:
            if match not in folder.name:
                continue
        elif not folder.name.endswith("{}.kdk".format(match)):
            continue
        if valid(folder):
            return str(folder)
    return None


def fetch_list():
    logging.info("- Pulling KDK list from KdkSupportPkg API")
    result = runner.run(["/usr/bin/curl", "-sL", "--fail", "--max-time", "10", KDK_API_LINK], merge=False)
    if result.returncode != 0:
        logging.info("- Could not contact KDK API")
        return None
    try:
        return json.loads(result.stdout)
    except ValueError:
        logging.info("- Could not parse the KDK list")
        return None


def pick(kdk_list, host_build, host_version):
    for kdk in kdk_list:
        if kdk["build"] == host_build:
            return kdk, True

    host = patchsets.version_tuple(host_version)
    for kdk in kdk_list:
        version = patchsets.version_tuple(kdk["version"])
        if version > host or version[0] != host[0]:
            continue
        if version[1] not in (host[1] - 1, host[1]):
            continue
        # the list is sorted by version then date, so the first hit is the closest
        return kdk, False
    return None, False


def resolve(host_build, host_version, kdk_list=None):
    if patchsets.version_tuple(host_version)[0] < 13:
        return {"error": "KDKs are not required for macOS Monterey or older"}

    path = installed(host_build)
    if path:
        return {"path": path}

    if kdk_list is None:
        major, minor = patchsets.version_tuple(host_version)[:2]
        loose = "{}.{}".format(major, minor)
        older = "{}.{}".format(major, minor - 1 if minor > 0 else 0)
        for match in (loose, older):
            path = installed(match, check_version=True)
            if path:
                return {"path": path}
        return {"error": "Could not contact KdkSupportPkg API, and no KDK matching {} ({}) or {} was installed.".format(host_version, host_build, older)}

    kdk, exact = pick(kdk_list, host_build, host_version)
    if kdk is None:
        return {"error": "No KDKs found for {} ({})".format(host_build, host_version)}
    if not exact:
        logging.info("- No direct KDK match for %s, closest match: %s (%s)", host_build, kdk["build"], kdk["version"])

    path = installed(kdk["build"])
    if path:
        return {"path": path, "kdk": kdk}
    return {"kdk": kdk}


def verified(kdk, path):
    expected = str(kdk.get("sha256sum") or "").lower()
    if expected:
        if payload.sha256_of(path) != expected:
            return False
    elif runner.run(["/usr/bin/hdiutil", "verify", path]).returncode != 0:
        # the KdkSupportPkg entry has no hash, so fall back to the image's own checksum as OCLP does
        return False
    logging.info("- Kernel Debug Kit checksum verified")
    return True


def download_args(kdk, path):
    return ["/usr/bin/curl", "-L", "--fail", "--progress-bar", "-o", path, kdk["url"]]


def download(kdk, cache_dir):
    os.makedirs(cache_dir, exist_ok=True)
    path = os.path.join(cache_dir, "KDK_{}.dmg".format(kdk["build"]))
    size = int(kdk.get("fileSize") or 0)
    if size and os.path.isfile(path) and os.path.getsize(path) == size and verified(kdk, path):
        logging.info("- Reusing %s", path)
        return path
    logging.info("- Downloading %s (%d MB)", kdk.get("name") or kdk["build"], size // (1024 * 1024))
    try:
        runner.check(download_args(kdk, path), capture=False)
        if size and os.path.getsize(path) != size:
            raise RuntimeError("Kernel Debug Kit download has the wrong size")
        if not verified(kdk, path):
            raise RuntimeError("Kernel Debug Kit checksum verification failed, please try again")
    except BaseException:
        if os.path.exists(path):
            os.remove(path)
        raise
    return path


def install_dmg(dmg):
    logging.info("- Extracting downloaded KDK disk image")
    mount_point = tempfile.mkdtemp()
    try:
        runner.check(["/usr/bin/hdiutil", "attach", dmg, "-mountpoint", mount_point, "-nobrowse"])
        try:
            pkg = os.path.join(mount_point, "KernelDebugKit.pkg")
            if not os.path.exists(pkg):
                raise RuntimeError("Failed to find KDK package in DMG, likely corrupted")
            logging.info("- Installing KDK package, this may take a while")
            runner.check(["/usr/sbin/installer", "-pkg", pkg, "-target", "/"])
        finally:
            runner.run(["/usr/bin/hdiutil", "detach", mount_point])
    finally:
        try:
            os.rmdir(mount_point)
        except OSError:
            pass
    logging.info("- Successfully installed KDK")


def merge_args(kdk_path, mount_location):
    # only System/Library/Extensions; Kernels and KernelSupport are not needed for root patching
    return ["/usr/bin/rsync", "-r", "-i", "-a", "{}/System/Library/Extensions/".format(kdk_path), "{}/System/Library/Extensions".format(mount_location)]


def merge(kdk_path, mount_location):
    logging.info("- Merging KDK with Root Volume: %s", Path(kdk_path).name)
    runner.run(merge_args(kdk_path, mount_location))
    if not (Path(mount_location) / "System/Library/Extensions/System.kext/PlugIns/Libkern.kext/Libkern").exists():
        raise RuntimeError("Failed to merge KDK with Root Volume")
    logging.info("- Successfully merged KDK with Root Volume")


def ensure(host_build, host_version, cache_dir, mount_location):
    found = resolve(host_build, host_version, fetch_list())
    if "error" in found:
        raise RuntimeError(found["error"])
    if "path" not in found:
        dmg = download(found["kdk"], cache_dir)
        install_dmg(dmg)
        # kept until the install succeeds so a failed install can retry without downloading again
        os.remove(dmg)
        path = installed(found["kdk"]["build"])
        if not path:
            raise RuntimeError("KDK was not installed, but should have been")
        found["path"] = path
    logging.info("- Found KDK at: %s", found["path"])
    merge(found["path"], mount_location)
    return found["path"]
