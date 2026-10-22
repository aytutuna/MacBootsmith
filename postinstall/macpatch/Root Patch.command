#!/bin/bash
# Applies the root patches listed in PostInstall/patches.json.
# From Terminal: bash "Root Patch.command" (add --dry-run to only check).
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

/usr/bin/python3 -B . --manifest ../../patches.json "$@"
