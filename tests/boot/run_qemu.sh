#!/usr/bin/env bash
# Boots a built OpenCore EFI folder in QEMU/OVMF and checks that the picker is reached.
#
# Usage: tests/boot/run_qemu.sh <efi-dir>
#   <efi-dir> is the folder that contains BOOT/ and OC/ (for example Results/EFI).
#
# Needs: qemu-system-x86_64, OVMF, mtools, python3, curl.
#
# NOTE: the success and failure markers below are a first guess. Tighten them
# after the first green run on CI, once the real serial log has been inspected.
set -u

if [ $# -ne 1 ] || [ ! -d "$1/OC" ] || [ ! -d "$1/BOOT" ]; then
    echo "usage: $0 <efi-dir containing BOOT and OC>" >&2
    exit 2
fi

SRC_EFI=$(cd "$1" && pwd)
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
EFI="$WORK/EFI"
cp -r "$SRC_EFI" "$EFI"
SERIAL_LOG="${SERIAL_LOG:-$PWD/serial.log}"
BOOT_TIMEOUT="${BOOT_TIMEOUT:-120}"

SUCCESS_REGEXES=(
    "OC: Boot picker"
    "OCB: ShowPicker"
)
FAILURE_REGEXES=(
    "ASSERT"
    "!!!! X64 Exception"
)

# 1. Fetch the DEBUG build from the same Dortania build-repo entry the release build came from.
DL="$WORK/dl"
mkdir -p "$DL"
url=$(curl -fsSL https://raw.githubusercontent.com/dortania/build-repo/builds/latest.json | python3 -c '
import json, sys
print(json.load(sys.stdin)["OpenCorePkg"]["versions"][0]["links"]["debug"])
')
if [ -z "$url" ] || ! curl -fsSL -o "$DL/debug.zip" "$url"; then
    echo "Could not download an OpenCore DEBUG build" >&2
    exit 1
fi
echo "Using $url"

python3 - "$DL/debug.zip" "$DL/x" <<'PY'
import sys, zipfile
zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])
PY
DBG="$DL/x/X64/EFI"
for f in BOOT/BOOTx64.efi OC/OpenCore.efi OC/Drivers/OpenRuntime.efi; do
    if [ ! -f "$DBG/$f" ]; then
        echo "DEBUG package is missing $f" >&2
        exit 1
    fi
    mkdir -p "$(dirname "$EFI/$f")"
    cp "$DBG/$f" "$EFI/$f"
done

# 2. Patch config.plist for logging and a visible picker.
python3 - "$EFI/OC/config.plist" <<'PY'
import plistlib, sys
path = sys.argv[1]
with open(path, "rb") as f:
    cfg = plistlib.load(f)
misc = cfg.setdefault("Misc", {})
dbg = misc.setdefault("Debug", {})
boot = misc.setdefault("Boot", {})
sec = misc.setdefault("Security", {})
# 75 = enable (1) + onscreen (2) + serial (8) + file (64); 67 would have no serial output
dbg["Target"] = 75
dbg["DisplayLevel"] = 2147483714
dbg["DisableWatchdog"] = True
boot["PickerMode"] = "Builtin"
boot["ShowPicker"] = True
boot["Timeout"] = 0
misc.setdefault("Serial", {})["Init"] = True
sec["ScanPolicy"] = 0
with open(path, "wb") as f:
    plistlib.dump(cfg, f)
PY

# 3. Build a FAT32 disk image without root.
IMG="$WORK/disk.img"
truncate -s 256M "$IMG"
mformat -i "$IMG" -F -h 64 -s 32 -t 256 ::
mcopy -s -i "$IMG" "$EFI" ::/EFI

# 4. Locate OVMF.
find_ovmf() {
    local d name
    for d in /usr/share/OVMF /usr/share/edk2/ovmf /usr/share/qemu; do
        for name in "$@"; do
            if [ -f "$d/$name" ]; then echo "$d/$name"; return 0; fi
        done
    done
    return 1
}
CODE=$(find_ovmf OVMF_CODE_4M.fd OVMF_CODE.fd) || { echo "OVMF_CODE not found" >&2; exit 1; }
VARS=$(find_ovmf OVMF_VARS_4M.fd OVMF_VARS.fd) || { echo "OVMF_VARS not found" >&2; exit 1; }
cp "$VARS" "$WORK/vars.fd"
echo "OVMF code: $CODE"
echo "OVMF vars: $VARS"

# 5. Run QEMU, stop early once a success marker shows up.
: > "$SERIAL_LOG"
qemu-system-x86_64 -machine q35 -cpu Penryn -m 2048 -nographic -monitor none \
    -serial "file:$SERIAL_LOG" \
    -drive if=pflash,format=raw,readonly=on,file="$CODE" \
    -drive if=pflash,format=raw,file="$WORK/vars.fd" \
    -drive format=raw,file="$IMG" &
QPID=$!

has_marker() {
    local re
    for re in "$@"; do
        if grep -a -q -E "$re" "$SERIAL_LOG"; then return 0; fi
    done
    return 1
}

elapsed=0
while [ "$elapsed" -lt "$BOOT_TIMEOUT" ] && kill -0 "$QPID" 2>/dev/null; do
    sleep 3
    elapsed=$((elapsed + 3))
    if has_marker "${SUCCESS_REGEXES[@]}"; then break; fi
    if has_marker "${FAILURE_REGEXES[@]}"; then break; fi
done
kill "$QPID" 2>/dev/null
wait "$QPID" 2>/dev/null

echo "================ serial.log ================"
cat "$SERIAL_LOG"
echo "============================================"

# 6. Verdict.
for re in "${FAILURE_REGEXES[@]}"; do
    if grep -a -q -E "$re" "$SERIAL_LOG"; then
        echo "FAIL: found failure marker '$re'"
        exit 1
    fi
done
for re in "${SUCCESS_REGEXES[@]}"; do
    if grep -a -q -E "$re" "$SERIAL_LOG"; then
        echo "PASS: found success marker '$re'"
        exit 0
    fi
done
echo "FAIL: no success marker found within ${BOOT_TIMEOUT}s"
exit 1
