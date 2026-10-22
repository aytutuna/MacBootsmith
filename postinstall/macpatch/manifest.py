import json
import re

import patchsets

VERSION = 1
NOT_COVERED = ("graphics",)


class ManifestError(Exception):
    pass


def validate(data):
    if not isinstance(data, dict):
        raise ManifestError("patches.json must hold a JSON object")
    if data.get("version") != VERSION:
        raise ManifestError("patches.json version {!r} is not supported (expected {})".format(data.get("version"), VERSION))
    entries = data.get("root_patches")
    if not isinstance(entries, list):
        raise ManifestError("root_patches must be a list")
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("set"), str):
            raise ManifestError("every root_patches entry needs a \"set\" name: {!r}".format(entry))
        if entry["set"] not in patchsets.SETS and entry["set"] not in NOT_COVERED:
            raise ManifestError("unknown patch set {!r}".format(entry["set"]))
    pin = data.get("payload")
    if pin is not None:
        if not isinstance(pin, dict):
            raise ManifestError("payload must be an object")
        if not str(pin.get("url", "")).startswith("https://"):
            raise ManifestError("payload url must be https")
        if not re.match(r"^[0-9a-fA-F]{64}$", str(pin.get("sha256", ""))):
            raise ManifestError("payload sha256 must be 64 hex digits")
        if not isinstance(pin.get("size"), int) or pin["size"] <= 0:
            raise ManifestError("payload size must be a positive integer")
        if not pin.get("psp_version"):
            raise ManifestError("payload psp_version is missing")
    return data


def load(path):
    try:
        with open(path, "r", encoding="utf-8") as source:
            data = json.load(source)
    except OSError as e:
        raise ManifestError("cannot read {}: {}".format(path, e))
    except ValueError as e:
        raise ManifestError("{} is not valid JSON: {}".format(path, e))
    return validate(data)


def covered(entry):
    return entry["set"] in patchsets.SETS and entry.get("supported", True) is not False


def patch_sets(data):
    listed = set(entry["set"] for entry in data["root_patches"] if covered(entry))
    return [set_id for set_id in patchsets.SETS if set_id in listed]


def unsupported(data):
    return [entry for entry in data["root_patches"] if not covered(entry)]
