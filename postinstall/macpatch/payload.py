# Adapted from OpenCore Legacy Patcher 3.0.0 (sys_patch), BSD-4-Clause, see LICENSE.
import hashlib
import logging
import os

import runner

NAME = "Universal-Binaries.dmg"
PIN = {
    "psp_version": "2.0.3",
    "url": "https://github.com/dortania/PatcherSupportPkg/releases/download/2.0.3/Universal-Binaries.dmg",
    "sha256": "cf2a80deafe153ed4a9aa32c63463032e02718f32713e9b3f0a6e09f9a6ffbab",
    "size": 790749184,
}


def pin_from_manifest(data):
    pin = data.get("payload")
    return dict(pin) if pin else dict(PIN)


def sha256_of(path):
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def matches(path, pin):
    if not os.path.isfile(path) or os.path.getsize(path) != pin["size"]:
        return False
    return sha256_of(path) == pin["sha256"].lower()


def find(pin, folders):
    for folder in folders:
        path = os.path.join(folder, NAME)
        if os.path.isfile(path):
            logging.info("- Checking %s", path)
            if matches(path, pin):
                return path
            logging.info("  - Size or SHA-256 does not match PatcherSupportPkg %s, ignoring it", pin["psp_version"])
    return None


def download(pin, cache_dir):
    os.makedirs(cache_dir, exist_ok=True)
    path = os.path.join(cache_dir, NAME)
    partial = path + ".part"
    logging.info("- Downloading %s (PatcherSupportPkg %s, %d MB)", NAME, pin["psp_version"], pin["size"] // (1024 * 1024))
    runner.check(["/usr/bin/curl", "-L", "--fail", "--progress-bar", "-o", partial, pin["url"]], capture=False)
    if not matches(partial, pin):
        os.remove(partial)
        raise RuntimeError("{} does not match the pinned size and SHA-256".format(NAME))
    os.replace(partial, path)
    return path


def mountpoint(cache_dir):
    return os.path.join(cache_dir, "Universal-Binaries")


def attach_args(dmg, cache_dir):
    return [
        "/usr/bin/hdiutil", "attach", "-noverify", dmg,
        "-mountpoint", mountpoint(cache_dir),
        "-nobrowse",
        "-shadow", os.path.join(cache_dir, "Universal-Binaries_overlay"),
        "-passphrase", "password",
    ]


def mount(dmg, cache_dir):
    root = mountpoint(cache_dir)
    if os.path.ismount(root):
        logging.info("- Universal-Binaries.dmg already mounted")
        return root
    # the dmg may come from the USB drive, so the cache folder for the mount point may not exist yet
    os.makedirs(cache_dir, exist_ok=True)
    runner.check(attach_args(dmg, cache_dir))
    logging.info("- Mounted Universal-Binaries.dmg")
    return root


def unmount(cache_dir):
    root = mountpoint(cache_dir)
    if not os.path.ismount(root):
        return
    if runner.run(["/usr/bin/hdiutil", "detach", root, "-force"]).returncode != 0:
        logging.info("- Failed to unmount Universal-Binaries.dmg")
    overlay = os.path.join(cache_dir, "Universal-Binaries_overlay")
    if os.path.isfile(overlay):
        os.remove(overlay)
