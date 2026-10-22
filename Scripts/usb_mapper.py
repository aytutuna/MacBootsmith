# The port type guessing rules and the UTBMap.kext layout follow USBToolBox
# (https://github.com/USBToolBox/tool), used under the MIT License:
#
# Copyright (c) 2021-2022 Dhinak G
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from Scripts import app_paths
from Scripts import explain
from Scripts import run
from Scripts import utils
import copy
import json
import os
import plistlib
import re
import shutil
import struct

MAX_PORTS_PER_CONTROLLER = 15
MAP_VERSION = 1
KEXT_NAME = "UTBMap.kext"
USBTOOLBOX_IDENTIFIER = "com.dhinakg.USBToolBox.kext"

PORT_TYPES = {
    0: "Type A",
    1: "Type Mini-AB",
    2: "ExpressCard",
    3: "USB 3 Type A",
    4: "USB 3 Type B",
    5: "USB 3 Type Micro-B",
    6: "USB 3 Type Micro-AB",
    7: "USB 3 Type Power-B",
    8: "Type C - USB 2 only",
    9: "Type C - with switch",
    10: "Type C - without switch",
    255: "Internal"
}
TYPE_USB2_A = 0
TYPE_USB3_A = 3
TYPE_C_WITH_SWITCH = 9
TYPE_INTERNAL = 255

CONNECTION_STATUS = [
    "NoDeviceConnected",
    "DeviceConnected",
    "DeviceFailedEnumeration",
    "DeviceGeneralFailure",
    "DeviceCausedOvercurrent",
    "DeviceNotEnoughPower",
    "DeviceNotEnoughBandwidth",
    "DeviceHubNestedTooDeeply",
    "DeviceInLegacyHub",
    "DeviceEnumerating",
    "DeviceReset"
]
USABLE_STATUS = ("NoDeviceConnected", "DeviceConnected")

SUPER_SPEED = "SuperSpeed"
HIGH_SPEED = "HighSpeed"
FULL_SPEED = "FullSpeed"
UNKNOWN_SPEED = "Unknown"
PORT_CLASS_LABELS = {SUPER_SPEED: "USB 3", HIGH_SPEED: "USB 2", FULL_SPEED: "USB 1.1", UNKNOWN_SPEED: "?"}
DEVICE_SPEEDS = {0: "USB 1.1", 1: "USB 1.1", 2: "USB 2.0", 3: "USB 3.0"}

CONTROLLER_CLASSES = {0x00: "UHCI", 0x10: "OHCI", 0x20: "EHCI", 0x30: "XHCI"}
CONTROLLER_SERVICES = {"usbxhci": "XHCI", "usbehci": "EHCI", "usbohci": "OHCI", "usbuhci": "UHCI"}

GENERIC_ACPI_NAMES = ("PXSX",)

INFO_PLIST_TEMPLATE = {
    "CFBundleDevelopmentRegion": "English",
    "CFBundleGetInfoString": "v1.1",
    "CFBundleIdentifier": "com.dhinakg.USBToolBox.map",
    "CFBundleInfoDictionaryVersion": "6.0",
    "CFBundleName": "UTBMap",
    "CFBundlePackageType": "KEXT",
    "CFBundleShortVersionString": "1.1",
    "CFBundleSignature": "????",
    "CFBundleVersion": "1.1",
    "IOKitPersonalities": {},
    "OSBundleRequired": "Root"
}


def as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def normalize_hub_name(name):
    name = str(name or "").strip()
    for prefix in ("\\\\?\\", "\\\\.\\", "\\??\\"):
        if name.startswith(prefix):
            name = name[len(prefix):]
    return name.lower()


def port_data(index):
    return struct.pack("<I", int(index))


def port_class_from_protocols(protocols):
    try:
        protocols = int(protocols)
    except (TypeError, ValueError):
        return UNKNOWN_SPEED
    if protocols < 0:
        return UNKNOWN_SPEED
    if protocols & 0x4:
        return SUPER_SPEED
    if protocols & 0x2 and protocols & 0x1:
        return HIGH_SPEED
    if protocols & 0x1:
        return FULL_SPEED
    return UNKNOWN_SPEED


def device_speed(speed, v2_flags):
    try:
        speed = int(speed)
        v2_flags = int(v2_flags or 0)
    except (TypeError, ValueError):
        return "Unknown"
    if speed == 3 and v2_flags & 0x4:
        return "USB 3.1 Gen 2"
    return DEVICE_SPEEDS.get(speed, "Unknown")


def controller_class(compatible_ids, service):
    for compatible_id in as_list(compatible_ids):
        match = re.search(r"CC_0C03([0-9A-F]{2})", str(compatible_id), re.IGNORECASE)
        if match:
            return CONTROLLER_CLASSES.get(int(match.group(1), 16), "Unknown")
    return CONTROLLER_SERVICES.get(str(service or "").lower(), "Unknown")


def parse_pci_id(instance_id):
    match = re.search(r"VEN_([0-9A-F]{4})&DEV_([0-9A-F]{4})(?:&SUBSYS_([0-9A-F]{4})([0-9A-F]{4}))?", str(instance_id or ""), re.IGNORECASE)
    if not match:
        return None
    pci_id = [match.group(1).lower(), match.group(2).lower()]
    if match.group(3) and match.group(3).upper() + match.group(4).upper() not in ("00000000", "FFFFFFFF"):
        pci_id += [match.group(4).lower(), match.group(3).lower()]
    return pci_id


def _int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def parse_port(raw):
    status_code = _int(raw.get("Status"), -1)
    status = CONNECTION_STATUS[status_code] if 0 <= status_code < len(CONNECTION_STATUS) else "Unknown"
    properties = _int(raw.get("PortProperties"), -1)
    index = _int(raw.get("Index"))
    port = {
        "index": index,
        "name": "Port {}".format(index),
        "class": port_class_from_protocols(raw.get("Protocols")),
        "status": status,
        "type_c": properties >= 0 and bool(properties & 0x8),
        "user_connectable": properties < 0 or bool(properties & 0x1),
        "companion": {
            "hub": normalize_hub_name(raw.get("CompanionHub")),
            "port": _int(raw.get("CompanionPort"))
        },
        "guessed": None,
        "devices": []
    }
    if status == "DeviceConnected":
        name = str(raw.get("DeviceName") or "").strip()
        if not name:
            name = "USB device {:04X}:{:04X}".format(_int(raw.get("Vid")), _int(raw.get("Pid")))
        port["devices"].append({
            "name": name,
            "speed": device_speed(raw.get("Speed"), raw.get("V2Flags")),
            "children": [str(child).strip() for child in as_list(raw.get("Children")) if str(child or "").strip()]
        })
    return port


def parse_controller(raw):
    identifiers = {}
    instance_id = str(raw.get("InstanceId") or "")
    if instance_id:
        identifiers["instance_id"] = instance_id
    pci_id = parse_pci_id(instance_id)
    if pci_id:
        identifiers["pci_id"] = pci_id
    acpi_path = str(raw.get("AcpiPath") or "").strip()
    if acpi_path:
        identifiers["acpi_path"] = acpi_path
    bus = _int(raw.get("BusNumber"), -1)
    address = _int(raw.get("Address"), -1)
    if bus >= 0 and address >= 0:
        identifiers["bdf"] = [bus, (address >> 16) & 0xFFFF, address & 0xFFFF]

    controller = {
        "name": str(raw.get("Name") or "USB controller").strip(),
        "class": controller_class(raw.get("CompatibleIds"), raw.get("Service")),
        "identifiers": identifiers,
        "hub_name": normalize_hub_name(raw.get("HubName")),
        "port_count": _int(raw.get("PortCount")),
        "ports": []
    }
    if raw.get("Error"):
        controller["error"] = str(raw.get("Error"))
    for raw_port in as_list(raw.get("Ports")):
        if isinstance(raw_port, dict):
            controller["ports"].append(parse_port(raw_port))
    controller["ports"].sort(key=lambda port: port["index"])
    return controller


def guess_ports(controllers):
    hubs = {controller.get("hub_name"): controller for controller in controllers if controller.get("hub_name")}

    def companion_of(port):
        companion = port.get("companion") or {}
        if not companion.get("port"):
            return None
        hub = hubs.get(companion.get("hub"))
        if not hub:
            return None
        return next((other for other in hub["ports"] if other["index"] == companion["port"]), None)

    for controller in controllers:
        for port in controller["ports"]:
            if port.get("status") not in USABLE_STATUS:
                port["guessed"] = None
                continue
            companion = companion_of(port)
            has_companion = bool((port.get("companion") or {}).get("port"))
            if port.get("type_c") or (companion and companion.get("type_c")):
                port["guessed"] = TYPE_C_WITH_SWITCH
            elif not port.get("user_connectable", True):
                port["guessed"] = TYPE_INTERNAL
            elif companion and {port.get("class"), companion.get("class")} == {SUPER_SPEED, HIGH_SPEED}:
                port["guessed"] = TYPE_USB3_A
            elif port.get("class") == SUPER_SPEED and not has_companion:
                port["guessed"] = TYPE_INTERNAL
            else:
                port["guessed"] = TYPE_USB2_A
    return controllers


def parse_controllers(text):
    data = json.loads(text) if str(text or "").strip() else []
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        raise ValueError("unexpected data from the port enumerator")
    controllers = [parse_controller(item) for item in data if isinstance(item, dict)]
    return guess_ports(controllers)


def controller_key(controller):
    identifiers = controller.get("identifiers") or {}
    if identifiers.get("instance_id"):
        return ("instance", identifiers["instance_id"].lower())
    return ("pci", tuple(identifiers.get("pci_id") or ()), tuple(identifiers.get("bdf") or ()), identifiers.get("acpi_path"))


def get_controllers(selection):
    if isinstance(selection, dict):
        return selection.get("controllers") or []
    return selection or []


def connector_type(port):
    value = port.get("type")
    if value is None:
        value = port.get("guessed")
    return value


def numbered_ports(controllers):
    numbered = []
    for controller in controllers:
        for port in controller.get("ports", []):
            numbered.append((controller, port))
    return numbered


def selected_count(controller):
    return sum(1 for port in controller.get("ports", []) if port.get("selected"))


def toggle_port(controllers, number):
    numbered = numbered_ports(controllers)
    if not 1 <= number <= len(numbered):
        return False, "Port {} is not in the list.".format(number)
    controller, port = numbered[number - 1]
    if port.get("selected"):
        port["selected"] = False
        return True, "{} deselected.".format(port["name"])
    if selected_count(controller) >= MAX_PORTS_PER_CONTROLLER:
        return False, "{} already has {} ports selected. macOS allows at most {} per controller; deselect one first.".format(
            controller["name"], MAX_PORTS_PER_CONTROLLER, MAX_PORTS_PER_CONTROLLER)
    port["selected"] = True
    return True, "{} selected.".format(port["name"])


def set_port_type(controllers, number, code):
    numbered = numbered_ports(controllers)
    if not 1 <= number <= len(numbered):
        return False, "Port {} is not in the list.".format(number)
    if code not in PORT_TYPES:
        return False, "Unknown connector type {}.".format(code)
    port = numbered[number - 1][1]
    port["type"] = code
    return True, "{} set to {}.".format(port["name"], PORT_TYPES[code])


def validate_selection(selection):
    errors = []
    controllers = get_controllers(selection)
    total = 0
    for controller in controllers:
        count = selected_count(controller)
        total += count
        if count > MAX_PORTS_PER_CONTROLLER:
            errors.append("{} has {} ports selected; macOS allows at most {} per controller. Deselect {}.".format(
                controller.get("name"), count, MAX_PORTS_PER_CONTROLLER, count - MAX_PORTS_PER_CONTROLLER))
        for port in controller.get("ports", []):
            if port.get("selected") and connector_type(port) not in PORT_TYPES:
                errors.append("{} on {} has no connector type; set one with \"t <port> <code>\".".format(port.get("name"), controller.get("name")))
        if count:
            try:
                choose_matching_key(controller, controllers)
            except ValueError as error:
                errors.append(str(error))
    if not total:
        errors.append("No ports are selected.")
    return errors


def acpi_leaf(controller):
    acpi_path = (controller.get("identifiers") or {}).get("acpi_path")
    if not acpi_path:
        return None
    return acpi_path.rpartition(".")[2].lstrip("\\") or None


def acpi_match_name(controller):
    leaf = acpi_leaf(controller)
    if not leaf:
        return None
    return leaf.rstrip("_") or leaf


def _unique(controllers, controller, value_of):
    value = value_of(controller)
    if not value:
        return False
    return [value_of(other) for other in controllers].count(value) == 1


def choose_matching_key(controller, controllers):
    identifiers = controller.get("identifiers") or {}
    name = acpi_match_name(controller)
    if name and name.upper() not in GENERIC_ACPI_NAMES and _unique(controllers, controller, acpi_match_name):
        return {"IONameMatch": name}
    if identifiers.get("bdf"):
        return {"IOPropertyMatch": {"pcidebug": ":".join(str(part) for part in identifiers["bdf"])}}
    pci_value = lambda item: tuple((item.get("identifiers") or {}).get("pci_id") or ())
    if identifiers.get("pci_id") and _unique(controllers, controller, pci_value):
        pci_id = identifiers["pci_id"]
        key = {"IOPCIPrimaryMatch": "0x{}{}".format(pci_id[1], pci_id[0])}
        if len(pci_id) > 3:
            key["IOPCISecondaryMatch"] = "0x{}{}".format(pci_id[3], pci_id[2])
        return key
    raise ValueError("No way to match {} in macOS (no unique ACPI name, PCI location or PCI ID).".format(controller.get("name")))


def personality_name(controller, controllers):
    identifiers = controller.get("identifiers") or {}
    if identifiers.get("acpi_path"):
        if _unique(controllers, controller, acpi_match_name):
            return acpi_leaf(controller)
        return identifiers["acpi_path"].lstrip("\\")
    if identifiers.get("bdf"):
        return ":".join(str(part) for part in identifiers["bdf"])
    return controller.get("name") or "Controller"


def port_prefix(controller, port):
    if controller.get("class") == "XHCI" and port.get("class") == SUPER_SPEED:
        return "SS"
    if controller.get("class") == "XHCI" and port.get("class") == HIGH_SPEED:
        return "HS"
    return "PRT"


def port_names(controller):
    names = {}
    counters = {}
    for port in sorted(controller.get("ports", []), key=lambda item: item["index"]):
        if not port.get("selected"):
            continue
        prefix = port_prefix(controller, port)
        counters[prefix] = counters.get(prefix, 0) + 1
        names[port["index"]] = prefix + str(counters[prefix]).zfill(4 - len(prefix))
    return names


def build_info_plist(selection):
    errors = validate_selection(selection)
    if errors:
        raise ValueError(" ".join(errors))

    controllers = get_controllers(selection)
    info = copy.deepcopy(INFO_PLIST_TEMPLATE)
    for controller in controllers:
        ports = sorted((port for port in controller.get("ports", []) if port.get("selected")), key=lambda item: item["index"])
        if not ports:
            continue

        personality = {
            "CFBundleIdentifier": USBTOOLBOX_IDENTIFIER,
            "IOClass": "USBToolBox",
            "IOProviderClass": "IOPCIDevice",
            "IOMatchCategory": "USBToolBox"
        }
        personality.update(choose_matching_key(controller, controllers))

        names = port_names(controller)
        merge_ports = {}
        for port in ports:
            entry = {
                "port": port_data(port["index"]),
                "UsbConnector": int(connector_type(port))
            }
            if port.get("comment"):
                entry["#comment"] = str(port["comment"])
            merge_ports[names[port["index"]]] = entry

        personality["IOProviderMergeProperties"] = {
            "ports": merge_ports,
            "port-count": port_data(max(port["index"] for port in ports))
        }

        name = personality_name(controller, controllers)
        unique_name = name
        suffix = 2
        while unique_name in info["IOKitPersonalities"]:
            unique_name = "{}-{}".format(name, suffix)
            suffix += 1
        info["IOKitPersonalities"][unique_name] = personality

    info["OSBundleLibraries"] = {USBTOOLBOX_IDENTIFIER: "1.0.0"}
    return info


def build_kext(selection, dest_dir):
    info = build_info_plist(selection)
    kext_path = os.path.join(dest_dir, KEXT_NAME)
    if os.path.exists(kext_path):
        shutil.rmtree(kext_path)
    os.makedirs(os.path.join(kext_path, "Contents"))
    with open(os.path.join(kext_path, "Contents", "Info.plist"), "wb") as plist_file:
        plistlib.dump(info, plist_file, sort_keys=True)
    return kext_path


def report_matches(selection, hardware_report):
    report_ids = []
    for props in (hardware_report or {}).get("USB Controllers", {}).values():
        device_id = str(props.get("Device ID") or "").upper()
        subsystem = str(props.get("Subsystem ID") or "").upper()
        locations = set(str(props.get(key)).upper() for key in ("ACPI Path", "PCI Path") if props.get(key))
        report_ids.append((device_id, subsystem, locations))

    matched = []
    unmatched = []
    for controller in get_controllers(selection):
        if not any(port.get("selected") for port in controller.get("ports", [])):
            continue
        pci_id = (controller.get("identifiers") or {}).get("pci_id") or []
        found = False
        identifiers = controller.get("identifiers") or {}
        if len(pci_id) >= 2:
            device_id = "{}-{}".format(pci_id[0], pci_id[1]).upper()
            subsystem = "{}{}".format(pci_id[3], pci_id[2]).upper() if len(pci_id) > 3 else ""
            own_locations = set(str(value).upper() for value in (identifiers.get("acpi_path"),) if value)
            for report_device, report_subsystem, locations in report_ids:
                if report_device != device_id:
                    continue
                if subsystem and report_subsystem:
                    found = subsystem == report_subsystem
                elif not report_subsystem and own_locations and locations:
                    found = bool(own_locations & locations)
                else:
                    found = True
                if found:
                    break
        (matched if found else unmatched).append(controller)
    return matched, unmatched


def merge_history(history, current):
    history = history or []
    for controller in current:
        key = controller_key(controller)
        known = next((item for item in history if controller_key(item) == key), None)
        if known is None:
            controller = copy.deepcopy(controller)
            for port in controller["ports"]:
                port["seen"] = [device["name"] for device in port.get("devices", [])]
                port.setdefault("selected", None)
                port.setdefault("type", None)
                port.setdefault("comment", "")
            history.append(controller)
            continue

        for field in ("name", "class", "identifiers", "hub_name", "port_count"):
            if controller.get(field):
                known[field] = controller[field]
        if controller.get("error"):
            known["error"] = controller["error"]
        else:
            known.pop("error", None)
        known_ports = {port["index"]: port for port in known.get("ports", [])}
        for port in controller["ports"]:
            old = known_ports.get(port["index"])
            if old is None:
                port = copy.deepcopy(port)
                port["seen"] = [device["name"] for device in port.get("devices", [])]
                port.setdefault("selected", None)
                port.setdefault("type", None)
                port.setdefault("comment", "")
                known["ports"].append(port)
                continue
            for field in ("class", "status", "type_c", "user_connectable", "companion", "devices"):
                if field in port:
                    old[field] = copy.deepcopy(port[field])
            if port.get("guessed") is not None or old.get("guessed") is None:
                old["guessed"] = port.get("guessed")
            seen = old.setdefault("seen", [])
            for device in port.get("devices", []):
                if device["name"] not in seen:
                    seen.append(device["name"])
        known["ports"].sort(key=lambda item: item["index"])
    return history


def preselect(controllers):
    for controller in controllers:
        for port in controller.get("ports", []):
            if port.get("selected") is None:
                port["selected"] = bool(port.get("seen") or port.get("devices"))
    return controllers


def strip_selection(controllers):
    stored = []
    for controller in controllers:
        item = {field: copy.deepcopy(controller.get(field)) for field in ("name", "class", "identifiers", "hub_name", "port_count")}
        item["ports"] = []
        for port in controller.get("ports", []):
            item["ports"].append({
                "index": port["index"],
                "name": port.get("name") or "Port {}".format(port["index"]),
                "class": port.get("class", UNKNOWN_SPEED),
                "type": port.get("type"),
                "guessed": port.get("guessed"),
                "selected": bool(port.get("selected")),
                "comment": port.get("comment") or "",
                "type_c": bool(port.get("type_c")),
                "user_connectable": bool(port.get("user_connectable", True)),
                "companion": copy.deepcopy(port.get("companion") or {"hub": "", "port": 0}),
                "seen": list(port.get("seen") or [])
            })
        stored.append(item)
    return {"version": MAP_VERSION, "controllers": stored}


class USBMapper:
    def __init__(self, report_dir=None):
        self.utils = utils.Utils()
        self.r = run.Run()
        self.report_dir = report_dir or os.path.join(app_paths.app_dir(), "SysReport")
        self.map_path = os.path.join(self.report_dir, "USBMap.json")
        self.enum_source = os.path.join(app_paths.data_dir(), "usb_enum.cs")
        self.unsupported_message = "USB port mapping is only supported on Windows for now."
        system_root = os.environ.get("SystemRoot", r"C:\Windows")
        self.powershell_exe = os.path.join(system_root, "System32", "WindowsPowerShell", "v1.0", "powershell.exe")
        self.ps_prefix = "[Console]::OutputEncoding=[Text.Encoding]::UTF8; "

    def _supported(self):
        if os.name != "nt":
            print(self.unsupported_message)
            return False
        return True

    def _powershell(self, command):
        return self.r.run({"args": [self.powershell_exe, "-NoProfile", "-NonInteractive", "-Command", self.ps_prefix + command]})

    def enumerate(self):
        if not self._supported():
            return None
        if not os.path.exists(self.enum_source):
            print("The port enumerator {} is missing.".format(self.enum_source))
            return None
        command = "$ErrorActionPreference='Stop'; Add-Type -TypeDefinition ([IO.File]::ReadAllText('{}')); ConvertTo-Json -InputObject @([UsbPortDump.UsbEnum]::Dump()) -Depth 8 -Compress".format(
            self.enum_source.replace("'", "''"))
        out = self._powershell(command)
        if out[2] != 0:
            print("Could not list the USB ports (code {}):".format(out[2]))
            print(out[1].strip() or out[0].strip())
            return None
        try:
            return parse_controllers(out[0])
        except Exception as e:
            print("Could not read the USB port list: {}".format(e))
            if out[1].strip():
                print(out[1].strip())
            return None

    def load_saved(self, path=None):
        path = path or self.map_path
        if not os.path.isfile(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as map_file:
                data = json.load(map_file)
        except Exception as e:
            print("Could not read the USB map {}: {}".format(path, e))
            return None
        if isinstance(data, list):
            data = {"version": MAP_VERSION, "controllers": data}
        if not isinstance(data, dict) or not isinstance(data.get("controllers"), list):
            print("The USB map {} has no controller list.".format(path))
            return None
        for controller in data["controllers"]:
            controller.setdefault("identifiers", {})
            controller.setdefault("ports", [])
            for port in controller["ports"]:
                port.setdefault("name", "Port {}".format(port.get("index")))
        return data

    def save(self, selection, path=None):
        path = path or self.map_path
        data = strip_selection(get_controllers(selection))
        folder = os.path.dirname(path)
        if folder and not os.path.isdir(folder):
            os.makedirs(folder)
        with open(path, "w", encoding="utf-8") as map_file:
            json.dump(data, map_file, indent=4)
        return path

    def build_kext(self, selection, dest_dir):
        if selection is None:
            selection = self.load_saved()
        if selection is None:
            return None
        return build_kext(selection, dest_dir)

    def _type_label(self, port):
        value = connector_type(port)
        label = PORT_TYPES.get(value, "Unknown") if value is not None else "Unknown"
        if port.get("type") is None and value is not None:
            label += " (guess)"
        return label

    def _device_text(self, port):
        parts = []
        for device in port.get("devices", []):
            text = "{} ({})".format(device.get("name"), device.get("speed"))
            if device.get("children"):
                text += " + " + ", ".join(device["children"])
            parts.append(text)
        return "; ".join(parts) or "-"

    def _controller_header(self, controller):
        identifiers = controller.get("identifiers") or {}
        details = [controller.get("class", "Unknown")]
        pci_id = identifiers.get("pci_id")
        if pci_id:
            details.append("PCI {}:{}".format(pci_id[0], pci_id[1]).upper())
        if identifiers.get("bdf"):
            details.append("at {}".format(":".join(str(part) for part in identifiers["bdf"])))
        if identifiers.get("acpi_path"):
            details.append(identifiers["acpi_path"])
        return "{} [{}]".format(controller.get("name"), ", ".join(details))

    def show_discovery(self, controllers):
        self.utils.head("USB Port Mapping: Discover Ports")
        print("")
        print(explain.wrap(explain.stages["usb_map"], 68))
        print("")
        print("Plug a USB 2.0 device and then a USB 3.0 device into every port you use,")
        print("including front-panel and Type-C ports. Ports that see a device stay marked.")
        for controller in controllers:
            print("")
            print(self._controller_header(controller))
            if controller.get("error"):
                print("    {}".format(controller["error"]))
                continue
            print("    {:>4}  {:<6}  {:<30}  {:<32}  {}".format("Port", "Speed", "Type", "Connected now", "Seen"))
            for port in controller.get("ports", []):
                seen = ", ".join(port.get("seen") or []) or "-"
                print("    {:>4}  {:<6}  {:<30}  {:<32}  {}".format(
                    port["index"], PORT_CLASS_LABELS.get(port.get("class"), "?"), self._type_label(port)[:30],
                    self._device_text(port)[:32], seen[:40]))
        print("")

    def show_selection(self, controllers, message=None):
        self.utils.head("USB Port Mapping: Select Ports")
        print("")
        number = 0
        for controller in controllers:
            names = port_names(controller)
            count = selected_count(controller)
            print("{}  ({} of {} selected)".format(self._controller_header(controller), count, MAX_PORTS_PER_CONTROLLER))
            for port in controller.get("ports", []):
                number += 1
                mark = "x" if port.get("selected") else " "
                seen = ", ".join(port.get("seen") or []) or "-"
                print("  [{}] {:>3}. {:<8} {:<6} {:<6} {:<30} {}".format(
                    mark, number, port.get("name"), names.get(port["index"], ""), PORT_CLASS_LABELS.get(port.get("class"), "?"),
                    self._type_label(port)[:30], seen[:40]))
            if count > MAX_PORTS_PER_CONTROLLER:
                print("  \033[1;93m{} ports selected; deselect {} to stay within the {}-port limit.\033[0m".format(
                    count, count - MAX_PORTS_PER_CONTROLLER, MAX_PORTS_PER_CONTROLLER))
            print("")
        print("Connector types: " + ", ".join("{}={}".format(code, label) for code, label in sorted(PORT_TYPES.items()) if code in (0, 3, 8, 9, 10, 255)))
        print("")
        print("Commands:")
        print("  <number>[,<number>...] or <from>-<to>   toggle ports")
        print("  t <number> <code>                        set the connector type")
        print("  i <number>                               mark a port internal (Bluetooth, webcam, card reader)")
        print("  S save and finish   B back to discovery   Q cancel")
        if message:
            print("")
            print(message)
        print("")

    def _parse_numbers(self, text):
        numbers = []
        for part in text.replace(" ", "").split(","):
            if not part:
                continue
            if "-" in part:
                start, _, end = part.partition("-")
                if not (start.isdigit() and end.isdigit()):
                    return None
                start, end = int(start), int(end)
                if start > end:
                    start, end = end, start
                numbers.extend(range(start, end + 1))
            elif part.isdigit():
                numbers.append(int(part))
            else:
                return None
        return numbers or None

    def select_ports(self, controllers):
        preselect(controllers)
        message = None
        while True:
            self.show_selection(controllers, message)
            message = None
            answer = self.utils.request_input("Select an option: ").strip()
            lowered = answer.lower()
            if lowered == "q":
                return None
            if lowered == "b":
                return "back"
            if lowered == "s":
                errors = validate_selection(controllers)
                if errors:
                    message = "\033[91m" + "\n".join(errors) + "\033[0m"
                    continue
                return controllers
            parts = lowered.split()
            if parts and parts[0] in ("t", "i"):
                if parts[0] == "t" and len(parts) == 3 and parts[1].isdigit() and parts[2].isdigit():
                    ok, message = set_port_type(controllers, int(parts[1]), int(parts[2]))
                elif parts[0] == "i" and len(parts) == 2 and parts[1].isdigit():
                    ok, message = set_port_type(controllers, int(parts[1]), TYPE_INTERNAL)
                else:
                    message = "Usage: t <number> <code> or i <number>."
                continue
            numbers = self._parse_numbers(answer)
            if numbers is None:
                message = "\033[91mInvalid option.\033[0m"
                continue
            messages = []
            for number in numbers:
                ok, text = toggle_port(controllers, number)
                if not ok:
                    messages.append("\033[91m{}\033[0m".format(text))
            message = "\n".join(messages) or None

    def show_final(self, controllers):
        self.utils.head("USB Port Mapping: Final Map")
        print("")
        for controller in controllers:
            names = port_names(controller)
            if not names:
                continue
            print("{}  ({} ports)".format(self._controller_header(controller), len(names)))
            for port in controller.get("ports", []):
                if port.get("selected"):
                    print("    {:<6} Port {:>2}  {:<6} {}".format(names[port["index"]], port["index"], PORT_CLASS_LABELS.get(port.get("class"), "?"), PORT_TYPES.get(connector_type(port))))
            print("")
        skipped = [controller.get("name") for controller in controllers if not selected_count(controller)]
        if skipped:
            print("Controllers with no selected ports are left out of the map: {}".format(", ".join(skipped)))
            print("")

    def discover(self):
        if not self._supported():
            return None

        saved = self.load_saved()
        history = copy.deepcopy(get_controllers(saved)) if saved else []
        while True:
            while True:
                controllers = self.enumerate()
                if controllers is None:
                    print("")
                    self.utils.request_input("Press Enter to go back...")
                    return None
                present = set(controller_key(controller) for controller in controllers)
                dropped = [item.get("name") for item in history if controller_key(item) not in present]
                if dropped:
                    print("Left out of the map because they are not present in this machine: {}".format(", ".join(str(name) for name in dropped)))
                    history = [item for item in history if controller_key(item) in present]
                history = merge_history(history, controllers)
                self.show_discovery(history)
                answer = self.utils.request_input("Press Enter to refresh after plugging a device, D when done, Q to cancel: ").strip().lower()
                if answer == "q":
                    return None
                if answer == "d":
                    break

            result = self.select_ports(history)
            if result is None:
                return None
            if result == "back":
                continue

            selection = strip_selection(result)
            path = self.save(selection)
            self.show_final(result)
            print("USB map saved to {}".format(path))
            print("It is used for every build from now on. Run USB Port Mapping again to change it.")
            print("")
            return selection
