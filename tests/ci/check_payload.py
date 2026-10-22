# Downloads the pinned PatcherSupportPkg payload and checks that every file MacPatch would install is in it.
# macOS only (hdiutil): python3 tests/ci/check_payload.py --dest <folder>
import argparse
import os
import subprocess
import sys

TOOL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))), "postinstall", "macpatch")
sys.path.insert(0, TOOL_DIR)

import patchsets  # noqa: E402
import payload  # noqa: E402
import sysvol  # noqa: E402

# xnu major, xnu minor, build, version: each side of the version-string switches in the three sets
CASES = [
    (21, 6, "21H1015", "12.7.3"),
    (21, 6, "21H1123", "12.7.4"),
    (22, 6, "22G513", "13.6.4"),
    (22, 6, "22G621", "13.6.5"),
    (23, 3, "23D60", "14.3.1"),
    (23, 4, "23E214", "14.4"),
    (24, 6, "24G84", "15.6"),
    (25, 0, "25A362", "26.0.1"),
]


def check_case(root, xnu_major, xnu_minor, build, version):
    sets = patchsets.needed(list(patchsets.SETS), xnu_major, build)
    patches = patchsets.merged_patches(sets, xnu_major, xnu_minor, build, version)
    errors = []
    for step in sysvol.file_plan(patches, root, ""):
        name = step["file"]
        if step["method"] == patchsets.OVERWRITE_SYSTEM_VOLUME and name.endswith(".framework"):
            errors.append("{} used with overwrite".format(name))
        if step["method"] == patchsets.MERGE_SYSTEM_VOLUME and not name.endswith(".framework"):
            errors.append("{} used with merge".format(name))
        source = os.path.join(step["source"], name)
        if not os.path.exists(source):
            errors.append("missing {}".format(source))
        if name == "AppleHDA.kext" and not os.path.isfile(os.path.join(source, "Contents", "MacOS", "AppleHDA")):
            errors.append("{} has no Contents/MacOS/AppleHDA".format(source))
    print("Darwin {}.{} {} ({}): {} -> {} files, {}".format(
        xnu_major, xnu_minor, build, version, ", ".join(sets) or "nothing", len(sysvol.file_plan(patches, root, "")), "ok" if not errors else "FAILED"))
    for error in errors:
        print("  " + error)
    return not errors


def main():
    parser = argparse.ArgumentParser(description="Check the PatcherSupportPkg payload against MacPatch's patch sets.")
    parser.add_argument("--dest", required=True, help="folder for the download and the mount point")
    args = parser.parse_args()

    os.makedirs(args.dest, exist_ok=True)
    dmg = os.path.join(args.dest, payload.NAME)
    if not payload.matches(dmg, payload.PIN):
        print("Downloading {}".format(payload.PIN["url"]))
        subprocess.run(["/usr/bin/curl", "-L", "--fail", "-sS", "-o", dmg, payload.PIN["url"]], check=True)
        if not payload.matches(dmg, payload.PIN):
            print("{} does not match the pinned size {} and SHA-256 {}".format(dmg, payload.PIN["size"], payload.PIN["sha256"]), file=sys.stderr)
            return 1
    print("{} matches PatcherSupportPkg {} (size and SHA-256)".format(dmg, payload.PIN["psp_version"]))

    root = os.path.join(args.dest, "Universal-Binaries")
    os.makedirs(root, exist_ok=True)
    subprocess.run(["/usr/bin/hdiutil", "attach", "-noverify", "-nobrowse", "-readonly", "-stdinpass", "-mountpoint", root, dmg],
                   input=b"password", check=True)
    try:
        results = [check_case(root, *case) for case in CASES]
    finally:
        subprocess.run(["/usr/bin/hdiutil", "detach", root, "-force"])
    # job logs need a login, annotations do not
    print("::{}::payload {}: {} of {} builds ok".format("notice" if all(results) else "error", payload.PIN["psp_version"], sum(results), len(results)))
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
