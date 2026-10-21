#!/usr/bin/env bash
# Boots a built OpenCore EFI folder in QEMU/OVMF and checks that the picker is reached.
#
# Usage: tests/boot/run_qemu.sh <efi-dir>
#   <efi-dir> is the folder that contains BOOT/ and OC/ (for example Results/EFI).
#   The serial log stays at $SERIAL_LOG (default ./serial.log) so a later step can run
#   python OpCore-Simplify.py --analyze-log serial.log on it.
#
# Needs: qemu-system-x86_64, OVMF, mtools, python3, curl.
#
# NOTE: the success and failure markers below are a first guess. Tighten them
# after the first green run on CI, once the real serial log has been inspected.
set -u

# GitHub Actions annotations are visible through the public API even when the
# job log itself needs a login, so every diagnostic worth reading goes through here.
annotate() {
    local kind="$1" title="$2" msg="$3"
    msg="${msg//$''/}"
    msg="${msg//'%'/%25}"
    msg="${msg//$'
'/%0A}"
    echo "::${kind} title=${title}::${msg}"
}
summary() {
    if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
        printf '%s
' "$@" >> "$GITHUB_STEP_SUMMARY"
    fi
}
fail() {
    echo "FAIL: $1" >&2
    annotate error qemu-boot "$1"
    exit 1
}

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

# Any of these means OpenCore got past driver loading and into the boot picker code path.
SUCCESS_REGEXES=(
    "OC: Boot picker"
    "OCB: ShowPicker"
    "OCB: Showing menu"
    "OCB: Processing boot entries"
    "OCB: Found [0-9]+ entries"
    "OCB: Reading boot entries"
    "OCB: ShowMenu"
    "OCB: No bootable entries"
    "OCB: Picker"
    "OCUI:"
)
FAILURE_REGEXES=(
    "ASSERT"
    "!!!! X64 Exception"
)

# 1. Fetch the DEBUG build from the same Dortania build-repo entry the release build came from,
#    unless the EFI was built with the DEBUG option: a DEBUG OpenCore.efi carries its log strings.
if grep -a -q "Ready for takeoff" "$EFI/OC/OpenCore.efi"; then
    url="EFI as built (OpenCore.efi is already DEBUG)"
    echo "OpenCore.efi is already a DEBUG build, keeping the EFI binaries"
else
DL="$WORK/dl"
mkdir -p "$DL"
url=$(curl -fsSL https://raw.githubusercontent.com/dortania/build-repo/builds/latest.json | python3 -c '
import json, sys
print(json.load(sys.stdin)["OpenCorePkg"]["versions"][0]["links"]["debug"])
')
if [ -z "$url" ] || ! curl -fsSL -o "$DL/debug.zip" "$url"; then
    fail "Could not download an OpenCore DEBUG build from ${url:-<no url>}"
fi
echo "Using $url"

python3 - "$DL/debug.zip" "$DL/x" <<'PY'
import sys, zipfile
zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])
PY
DBG="$DL/x/X64/EFI"
for f in BOOT/BOOTx64.efi OC/OpenCore.efi OC/Drivers/OpenRuntime.efi; do
    if [ ! -f "$DBG/$f" ]; then
        fail "DEBUG package is missing $f"
    fi
    mkdir -p "$(dirname "$EFI/$f")"
    cp "$DBG/$f" "$EFI/$f"
done
fi

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
dbg["DisableWatchDog"] = True
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
mformat -i "$IMG" -F -h 64 -s 32 -t 256 :: || fail "mformat failed"
mcopy -s -i "$IMG" "$EFI" ::/EFI || fail "mcopy failed"
mdir -i "$IMG" ::/EFI/BOOT ::/EFI/OC || fail "image does not contain EFI/BOOT and EFI/OC"

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
CODE=$(find_ovmf OVMF_CODE_4M.fd OVMF_CODE.fd) || fail "OVMF_CODE not found; /usr/share/OVMF has: $(ls /usr/share/OVMF 2>/dev/null | tr '
' ' ')"
VARS=$(find_ovmf OVMF_VARS_4M.fd OVMF_VARS.fd) || fail "OVMF_VARS not found; /usr/share/OVMF has: $(ls /usr/share/OVMF 2>/dev/null | tr '
' ' ')"
cp "$VARS" "$WORK/vars.fd"
echo "OVMF code: $CODE"
echo "OVMF vars: $VARS"
annotate notice qemu-env "$(qemu-system-x86_64 --version | head -1); OVMF: $CODE; OpenCore DEBUG: $url"
OVMF_LOG="$WORK/ovmf.log"

# 5. Run QEMU, stop early once a success marker shows up.
: > "$SERIAL_LOG"
# Apple's HfsPlus.efi faults with an invalid opcode on the old Penryn model, so use a
# full-featured CPU: the host CPU under KVM when the runner exposes /dev/kvm, otherwise
# everything TCG can emulate.
if [ -w /dev/kvm ]; then
    ACCEL=(-accel kvm -cpu host)
else
    ACCEL=(-accel tcg -cpu max)
fi
echo "QEMU acceleration: ${ACCEL[*]}"
annotate notice qemu-accel "${ACCEL[*]}"
qemu-system-x86_64 -machine q35 "${ACCEL[@]}" -m 2048 -nographic -monitor none \
    -serial "file:$SERIAL_LOG"     -debugcon "file:$OVMF_LOG" -global isa-debugcon.iobase=0x402 \
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

# Strip CRs, and mask the generated platform identifiers: annotations and summaries
# are public on a public repository.
tr -d '\r' < "$SERIAL_LOG" \
    | sed -E 's/(Setting (SSN|MLB|ROM|system-id|SystemSerialNumber|SystemUUID)) [^ ]+/\1 <masked>/' \
    > "$SERIAL_LOG.clean" && mv "$SERIAL_LOG.clean" "$SERIAL_LOG"
echo "================ serial.log ================"
cat "$SERIAL_LOG"
echo "============================================"
serial_lines=$(wc -l < "$SERIAL_LOG")
if grep -a -q -E "X64 Exception|ASSERT" "$SERIAL_LOG"; then
    annotate error qemu-exception "context around the first exception: $(grep -a -n -m1 -B 25 -A 30 -E 'X64 Exception|ASSERT' "$SERIAL_LOG" | tail -c 3500)"
fi
if [ "$serial_lines" -eq 0 ]; then
    echo "================ ovmf.log (serial log was empty) ================"
    tail -n 80 "$OVMF_LOG" 2>/dev/null
    echo "================================================================"
    annotate warning qemu-boot "serial.log is empty after ${elapsed}s. OVMF debug tail: $(tail -n 40 "$OVMF_LOG" 2>/dev/null | tail -c 2500)"
else
    annotate notice qemu-serial-head "first lines of serial.log (${serial_lines} lines): $(head -n 30 "$SERIAL_LOG" | head -c 2500)"
    annotate notice qemu-serial-tail "last lines of serial.log: $(tail -n 40 "$SERIAL_LOG" | tail -c 3000)"
fi
summary "## QEMU boot" "" '```' "$(tail -n 200 "$SERIAL_LOG")" '```' "" "OVMF debug tail:" '```' "$(tail -n 60 "$OVMF_LOG" 2>/dev/null)" '```'

# 6. Verdict.
for re in "${FAILURE_REGEXES[@]}"; do
    if grep -a -q -E "$re" "$SERIAL_LOG"; then
        fail "found failure marker '$re' in serial.log"
    fi
done
for re in "${SUCCESS_REGEXES[@]}"; do
    if grep -a -q -E "$re" "$SERIAL_LOG"; then
        echo "PASS: found success marker '$re'"
        annotate notice qemu-boot "PASS: found success marker '$re' after ${elapsed}s"
        exit 0
    fi
done
fail "no success marker found within ${BOOT_TIMEOUT}s (${serial_lines} serial lines)"
