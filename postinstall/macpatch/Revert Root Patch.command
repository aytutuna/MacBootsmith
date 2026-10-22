#!/bin/bash
# Returns the system volume to the last sealed snapshot, undoing the root patches.
# From Terminal: bash "Revert Root Patch.command". It does not need patches.json.
cd "$(dirname "$0")" || exit 1

if ! xcode-select -p >/dev/null 2>&1; then
    echo "MacPatch needs Python 3 from Apple's Command Line Tools. Their installer opens now;"
    echo "run this script again when it has finished."
    xcode-select --install
    exit 1
fi

if ! /usr/bin/python3 -c 'import sys; sys.exit(sys.version_info < (3, 9))' >/dev/null 2>&1; then
    echo "MacPatch needs Python 3.9 or newer; found: $(/usr/bin/python3 --version 2>&1)"
    exit 1
fi

/usr/bin/python3 -B . --revert --log ../../macpatch.log "$@"
