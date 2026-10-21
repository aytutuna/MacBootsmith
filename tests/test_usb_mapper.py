import contextlib
import copy
import importlib.util
import io
import json
import os
import plistlib
import tempfile
import unittest

from repo_path import FIXTURES, REPO_ROOT
from Scripts import kext_maestro
from Scripts import usb_mapper
from Scripts import utils

HUB_A = "USB#ROOT_HUB30#4&aaaa&0&0#{f18a0e88-c30c-11d0-8815-00a0c906bed8}"
HUB_B = "USB#ROOT_HUB30#4&bbbb&0&0#{f18a0e88-c30c-11d0-8815-00a0c906bed8}"


def raw_port(index, protocols, status=0, properties=1, companion_port=0, companion_hub="", name=None, speed=0, children=None):
    return {
        "Index": index, "Status": status, "Speed": speed, "IsHub": bool(children), "Protocols": protocols,
        "V2Flags": 0, "PortProperties": properties, "CompanionPort": companion_port, "CompanionHub": companion_hub,
        "DeviceName": name, "DeviceId": None, "Vid": 0x1234, "Pid": 0x5678, "Children": children or []
    }


def raw_controller(name, instance_id, acpi, bus, address, hub, ports, compatible="PCI\\CC_0C0330"):
    return {
        "Name": name, "InstanceId": instance_id, "CompatibleIds": [compatible, "PCI\\CC_0C03"], "Service": "USBXHCI",
        "AcpiPath": acpi, "BusNumber": bus, "Address": address, "HubName": hub, "PortCount": len(ports) if isinstance(ports, list) else 1,
        "Error": None, "Ports": ports
    }


CANNED_DUMP = [
    raw_controller(
        "Intel(R) USB 3.20 eXtensible Host Controller", "PCI\\VEN_8086&DEV_7F6E&SUBSYS_3D6C17AA&REV_10\\3&1&0&A0",
        "\\_SB.PC00.XHCI", 0, 0x140000, HUB_A, [
            raw_port(1, 3, status=1, properties=9, companion_port=5, companion_hub=HUB_A, name="Keyboard ", speed=1),
            raw_port(2, 3, properties=1, companion_port=6, companion_hub=HUB_A),
            raw_port(3, 3, status=1, properties=0, name="Integrated Camera", speed=2),
            raw_port(4, 3, status=1, properties=1, name="USB2.1 Hub", speed=2, children=["Monitor Controls"]),
            raw_port(5, 4, properties=9, companion_port=1, companion_hub=HUB_A),
            raw_port(6, 4, properties=1, companion_port=2, companion_hub="\\\\?\\" + HUB_A),
            raw_port(7, 4, properties=2),
            raw_port(8, 3, status=4, properties=1),
        ]),
    raw_controller(
        "ASMedia USB 3.1 eXtensible Host Controller", "PCI\\VEN_1B21&DEV_2142&SUBSYS_50071458&REV_00\\4&2&0&00E4",
        "\\_SB.PC00.RP05.PXSX", 3, 0, HUB_B, [raw_port(1, 3)]),
]


def selection_port(index, cls, guessed, selected=True, type_=None, comment=""):
    return {"index": index, "name": "Port {}".format(index), "class": cls, "type": type_, "guessed": guessed,
            "selected": selected, "comment": comment}


def two_controller_selection():
    return {"version": 1, "controllers": [
        {
            "name": "Intel XHCI", "class": "XHCI",
            "identifiers": {"pci_id": ["8086", "a3af", "1458", "5007"], "acpi_path": "\\_SB.PCI0.XHC_", "bdf": [0, 20, 0]},
            "ports": [
                selection_port(1, "HighSpeed", 3, comment="Rear left"),
                selection_port(2, "HighSpeed", 0),
                selection_port(3, "HighSpeed", 0, selected=False),
                selection_port(10, "HighSpeed", 0, type_=255),
                selection_port(17, "SuperSpeed", 3),
            ]
        },
        {
            "name": "ASMedia XHCI", "class": "XHCI",
            "identifiers": {"pci_id": ["1b21", "2142"], "acpi_path": "\\_SB.PCI0.RP05.PXSX", "bdf": [3, 0, 0]},
            "ports": [
                selection_port(1, "HighSpeed", 9),
                selection_port(3, "SuperSpeed", 9),
            ]
        },
        {
            "name": "Unused EHCI", "class": "EHCI",
            "identifiers": {"pci_id": ["8086", "1e26"], "acpi_path": "\\_SB.PCI0.EH01"},
            "ports": [selection_port(1, "HighSpeed", 0, selected=False)]
        },
    ]}


class BuildKextTest(unittest.TestCase):
    def build(self, selection):
        with tempfile.TemporaryDirectory() as temp_dir:
            kext_path = usb_mapper.build_kext(selection, temp_dir)
            self.assertEqual(os.path.basename(kext_path), "UTBMap.kext")
            files = sorted(os.path.relpath(os.path.join(root, name), kext_path).replace("\\", "/")
                           for root, _, names in os.walk(kext_path) for name in names)
            self.assertEqual(files, ["Contents/Info.plist"])
            with open(os.path.join(kext_path, "Contents", "Info.plist"), "rb") as plist_file:
                return plistlib.load(plist_file)

    def test_plist_layout(self):
        info = self.build(two_controller_selection())
        self.assertEqual(info["CFBundleIdentifier"], "com.dhinakg.USBToolBox.map")
        self.assertEqual(info["CFBundleName"], "UTBMap")
        self.assertEqual(info["OSBundleRequired"], "Root")
        self.assertEqual(info["OSBundleLibraries"], {"com.dhinakg.USBToolBox.kext": "1.0.0"})
        self.assertEqual(sorted(info["IOKitPersonalities"]), ["PXSX", "XHC_"])

        for personality in info["IOKitPersonalities"].values():
            self.assertEqual(personality["CFBundleIdentifier"], "com.dhinakg.USBToolBox.kext")
            self.assertEqual(personality["IOClass"], "USBToolBox")
            self.assertEqual(personality["IOProviderClass"], "IOPCIDevice")
            self.assertEqual(personality["IOMatchCategory"], "USBToolBox")

    def test_intel_ports(self):
        intel = self.build(two_controller_selection())["IOKitPersonalities"]["XHC_"]
        self.assertEqual(intel["IONameMatch"], "XHC")
        merge = intel["IOProviderMergeProperties"]
        self.assertEqual(merge["port-count"], b"\x11\x00\x00\x00")
        self.assertEqual(sorted(merge["ports"]), ["HS01", "HS02", "HS03", "SS01"])
        self.assertEqual(merge["ports"]["HS01"], {"port": b"\x01\x00\x00\x00", "UsbConnector": 3, "#comment": "Rear left"})
        self.assertEqual(merge["ports"]["HS02"]["UsbConnector"], 0)
        self.assertEqual(merge["ports"]["HS03"], {"port": b"\x0a\x00\x00\x00", "UsbConnector": 255})
        self.assertEqual(merge["ports"]["SS01"], {"port": b"\x11\x00\x00\x00", "UsbConnector": 3})

    def test_generic_acpi_name_uses_pci_location(self):
        asmedia = self.build(two_controller_selection())["IOKitPersonalities"]["PXSX"]
        self.assertNotIn("IONameMatch", asmedia)
        self.assertEqual(asmedia["IOPropertyMatch"], {"pcidebug": "3:0:0"})
        merge = asmedia["IOProviderMergeProperties"]
        self.assertEqual(merge["port-count"], b"\x03\x00\x00\x00")
        self.assertEqual({name: entry["UsbConnector"] for name, entry in merge["ports"].items()}, {"HS01": 9, "SS01": 9})

    def test_duplicate_acpi_names_fall_back(self):
        selection = two_controller_selection()
        selection["controllers"][1]["identifiers"] = {"pci_id": ["1b21", "2142", "1458", "5007"], "acpi_path": "\\_SB.PCI1.XHC_"}
        info = self.build(selection)
        self.assertEqual(sorted(info["IOKitPersonalities"]), ["_SB.PCI0.XHC_", "_SB.PCI1.XHC_"])
        intel = info["IOKitPersonalities"]["_SB.PCI0.XHC_"]
        self.assertEqual(intel["IOPropertyMatch"], {"pcidebug": "0:20:0"})
        asmedia = info["IOKitPersonalities"]["_SB.PCI1.XHC_"]
        self.assertEqual(asmedia["IOPCIPrimaryMatch"], "0x21421b21")
        self.assertEqual(asmedia["IOPCISecondaryMatch"], "0x50071458")

    def test_port_data_is_little_endian(self):
        self.assertEqual(usb_mapper.port_data(3), b"\x03\x00\x00\x00")
        self.assertEqual(usb_mapper.port_data(0x1A), b"\x1a\x00\x00\x00")
        self.assertEqual(usb_mapper.port_data(0x0102), b"\x02\x01\x00\x00")

    def test_missing_connector_type_is_rejected(self):
        selection = two_controller_selection()
        selection["controllers"][0]["ports"][1]["guessed"] = None
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(ValueError):
                usb_mapper.build_kext(selection, temp_dir)

    def test_ci_fixture_builds(self):
        with open(os.path.join(FIXTURES, "desktop", "USBMap.json"), encoding="utf-8") as fixture:
            selection = json.load(fixture)
        self.assertEqual(usb_mapper.validate_selection(selection), [])
        info = self.build(selection)
        self.assertEqual(len(info["IOKitPersonalities"]), 2)
        for personality in info["IOKitPersonalities"].values():
            self.assertLessEqual(len(personality["IOProviderMergeProperties"]["ports"]), usb_mapper.MAX_PORTS_PER_CONTROLLER)


class PortLimitTest(unittest.TestCase):
    def controllers(self, count, selected):
        ports = [selection_port(index, "HighSpeed", 0, selected=index <= selected) for index in range(1, count + 1)]
        return [{"name": "Big XHCI", "class": "XHCI", "identifiers": {"acpi_path": "\\_SB.PCI0.XHCI"}, "ports": ports}]

    def test_toggle_refuses_sixteenth_port(self):
        controllers = self.controllers(20, 15)
        ok, message = usb_mapper.toggle_port(controllers, 16)
        self.assertFalse(ok)
        self.assertIn("at most 15", message)
        self.assertFalse(controllers[0]["ports"][15]["selected"])

    def test_toggle_allows_after_deselect(self):
        controllers = self.controllers(20, 15)
        self.assertTrue(usb_mapper.toggle_port(controllers, 1)[0])
        self.assertTrue(usb_mapper.toggle_port(controllers, 16)[0])
        self.assertEqual(usb_mapper.selected_count(controllers[0]), 15)

    def test_toggle_out_of_range(self):
        self.assertFalse(usb_mapper.toggle_port(self.controllers(3, 0), 4)[0])

    def test_validate_flags_too_many(self):
        errors = usb_mapper.validate_selection(self.controllers(20, 17))
        self.assertTrue(any("Deselect 2" in error for error in errors), errors)
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(ValueError):
                usb_mapper.build_kext({"controllers": self.controllers(20, 17)}, temp_dir)

    def test_set_port_type(self):
        controllers = self.controllers(3, 3)
        self.assertTrue(usb_mapper.set_port_type(controllers, 2, 255)[0])
        self.assertEqual(controllers[0]["ports"][1]["type"], 255)
        self.assertFalse(usb_mapper.set_port_type(controllers, 2, 42)[0])

    def test_headless_selection_flow(self):
        mapper = usb_mapper.USBMapper()
        controllers = self.controllers(18, 0)
        for port in controllers[0]["ports"]:
            port["selected"] = None
            port["seen"] = ["Stick"] if port["index"] <= 16 else []
        utils.Utils.set_headless({"prompts": {}, "default": ""})
        answers = iter(["s", "16", "t 1 3", "s"])
        mapper.utils.request_input = lambda prompt="": next(answers)
        try:
            with contextlib.redirect_stdout(io.StringIO()) as output:
                result = mapper.select_ports(controllers)
        finally:
            utils.Utils.set_headless(None)
        self.assertIs(result, controllers)
        self.assertIn("Deselect 1", output.getvalue())
        self.assertEqual(usb_mapper.selected_count(controllers[0]), 15)
        self.assertEqual(controllers[0]["ports"][0]["type"], 3)


class EnumerateTest(unittest.TestCase):
    def mapper_with_output(self, stdout, stderr="", code=0):
        mapper = usb_mapper.USBMapper()
        mapper._supported = lambda: True
        calls = []

        def fake_powershell(command):
            calls.append(command)
            return stdout, stderr, code
        mapper._powershell = fake_powershell
        return mapper, calls

    def test_parses_controllers_and_guesses(self):
        mapper, calls = self.mapper_with_output(json.dumps(CANNED_DUMP))
        controllers = mapper.enumerate()
        self.assertIn("Add-Type", calls[0])
        self.assertIn("usb_enum.cs", calls[0])
        self.assertEqual(len(controllers), 2)

        intel = controllers[0]
        self.assertEqual(intel["class"], "XHCI")
        self.assertEqual(intel["identifiers"]["pci_id"], ["8086", "7f6e", "17aa", "3d6c"])
        self.assertEqual(intel["identifiers"]["bdf"], [0, 20, 0])
        self.assertEqual(intel["identifiers"]["acpi_path"], "\\_SB.PC00.XHCI")
        ports = {port["index"]: port for port in intel["ports"]}
        self.assertEqual(ports[1]["class"], "HighSpeed")
        self.assertEqual(ports[5]["class"], "SuperSpeed")
        self.assertEqual(ports[1]["devices"], [{"name": "Keyboard", "speed": "USB 1.1", "children": []}])
        self.assertEqual(ports[4]["devices"][0]["children"], ["Monitor Controls"])
        self.assertEqual(ports[1]["guessed"], 9)
        self.assertEqual(ports[5]["guessed"], 9)
        self.assertEqual(ports[2]["guessed"], 3)
        self.assertEqual(ports[6]["guessed"], 3)
        self.assertEqual(ports[3]["guessed"], 255)
        self.assertEqual(ports[4]["guessed"], 0)
        self.assertEqual(ports[7]["guessed"], 255)
        self.assertIsNone(ports[8]["guessed"])
        self.assertEqual(ports[8]["status"], "DeviceCausedOvercurrent")

        asmedia = controllers[1]
        self.assertEqual(asmedia["identifiers"]["pci_id"], ["1b21", "2142", "1458", "5007"])
        self.assertEqual(asmedia["identifiers"]["bdf"], [3, 0, 0])

    def test_single_object_output(self):
        single = copy.deepcopy(CANNED_DUMP[1])
        single["Ports"] = raw_port(1, 4, properties=1)
        mapper, _ = self.mapper_with_output(json.dumps(single))
        controllers = mapper.enumerate()
        self.assertEqual(len(controllers), 1)
        self.assertEqual(len(controllers[0]["ports"]), 1)
        self.assertEqual(controllers[0]["ports"][0]["class"], "SuperSpeed")
        self.assertEqual(controllers[0]["ports"][0]["guessed"], 255)

    def test_failure_returns_none(self):
        mapper, _ = self.mapper_with_output("", "Add-Type : compiler error", 1)
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertIsNone(mapper.enumerate())
        self.assertIn("compiler error", output.getvalue())

    def test_bad_json_returns_none(self):
        mapper, _ = self.mapper_with_output("not json", "warning text")
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertIsNone(mapper.enumerate())
        self.assertIn("warning text", output.getvalue())

    def test_unsupported_os(self):
        mapper = usb_mapper.USBMapper()
        original = usb_mapper.os.name
        usb_mapper.os.name = "posix"
        try:
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertIsNone(mapper.enumerate())
                self.assertIsNone(mapper.discover())
        finally:
            usb_mapper.os.name = original
        self.assertEqual(output.getvalue().count("only supported on Windows"), 2)


class PersistenceTest(unittest.TestCase):
    def test_save_and_load_round_trip(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            mapper = usb_mapper.USBMapper(report_dir=temp_dir)
            controllers = usb_mapper.merge_history([], usb_mapper.parse_controllers(json.dumps(CANNED_DUMP)))
            usb_mapper.preselect(controllers)
            path = mapper.save({"controllers": controllers})
            self.assertEqual(path, os.path.join(temp_dir, "USBMap.json"))
            loaded = mapper.load_saved()
            self.assertEqual(loaded["version"], 1)
            selected = [port["index"] for port in loaded["controllers"][0]["ports"] if port["selected"]]
            self.assertEqual(selected, [1, 3, 4])
            kext_path = mapper.build_kext(None, temp_dir)
            self.assertTrue(os.path.isfile(os.path.join(kext_path, "Contents", "Info.plist")))

    def test_merge_accumulates_seen(self):
        first = usb_mapper.parse_controllers(json.dumps(CANNED_DUMP))
        history = usb_mapper.merge_history([], first)
        moved = copy.deepcopy(CANNED_DUMP)
        moved[0]["Ports"][0] = raw_port(1, 3, properties=9, companion_port=5, companion_hub=HUB_A)
        moved[0]["Ports"][1] = raw_port(2, 3, status=1, properties=1, companion_port=6, companion_hub=HUB_A, name="Stick", speed=2)
        history = usb_mapper.merge_history(history, usb_mapper.parse_controllers(json.dumps(moved)))
        ports = {port["index"]: port for port in history[0]["ports"]}
        self.assertEqual(ports[1]["seen"], ["Keyboard"])
        self.assertEqual(ports[1]["devices"], [])
        self.assertEqual(ports[2]["seen"], ["Stick"])
        usb_mapper.preselect(history)
        self.assertTrue(ports[1]["selected"])
        self.assertTrue(ports[2]["selected"])
        self.assertFalse(ports[5]["selected"])

    def test_missing_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            self.assertIsNone(usb_mapper.USBMapper(report_dir=temp_dir).load_saved())

    def test_report_matching(self):
        with open(os.path.join(FIXTURES, "desktop", "Report.json"), encoding="utf-8") as report_file:
            report = json.load(report_file)
        with open(os.path.join(FIXTURES, "desktop", "USBMap.json"), encoding="utf-8") as map_file:
            selection = json.load(map_file)
        matched, unmatched = usb_mapper.report_matches(selection, report)
        self.assertEqual([controller["name"] for controller in matched], ["Intel(R) USB 3.1 eXtensible Host Controller - 1.10 (Microsoft)"])
        self.assertEqual(len(unmatched), 1)
        with open(os.path.join(FIXTURES, "laptop", "Report.json"), encoding="utf-8") as report_file:
            laptop = json.load(report_file)
        self.assertEqual(usb_mapper.report_matches(selection, laptop)[0], [])


class KextSelectionTest(unittest.TestCase):
    version = "24.0.0"

    def setUp(self):
        self.k = kext_maestro.KextMaestro()
        self.reset()

    def tearDown(self):
        self.reset()
        utils.Utils.set_headless(None)

    def reset(self):
        for kext in self.k.kexts:
            kext.checked = kext.required
        self.k.usb_map_replaced_default = False

    def checked(self, name):
        return self.k.kexts[kext_maestro.kext_data.kext_index_by_name[name]].checked

    def select(self, **kwargs):
        with open(os.path.join(FIXTURES, "desktop", "Report.json"), encoding="utf-8") as report_file:
            report = json.load(report_file)
        utils.Utils.set_headless({"prompts": {"Select audio kext": "2"}, "default": ""})
        with contextlib.redirect_stdout(io.StringIO()):
            self.k.select_required_kexts(report, self.version, False, [], **kwargs)

    def test_default_without_map(self):
        self.select()
        self.assertTrue(self.checked("UTBDefault"))
        self.assertTrue(self.checked("USBToolBox"))

    def test_map_flag_drops_default(self):
        self.select(usb_map=True)
        self.assertFalse(self.checked("UTBDefault"))
        self.assertTrue(self.checked("USBToolBox"))

    def test_apply_usb_map_swaps_and_restores(self):
        self.select()
        self.k.apply_usb_map(self.version, True)
        self.assertFalse(self.checked("UTBDefault"))
        self.assertTrue(self.checked("USBToolBox"))
        self.k.apply_usb_map(self.version, False)
        self.assertTrue(self.checked("UTBDefault"))
        self.assertTrue(self.checked("USBToolBox"))

    def test_apply_without_map_keeps_user_choice(self):
        self.select()
        self.k.uncheck_kext(kext_maestro.kext_data.kext_index_by_name["UTBDefault"])
        self.k.apply_usb_map(self.version, False)
        self.assertFalse(self.checked("UTBDefault"))


class BuildIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("opcore_simplify_main_usb", os.path.join(REPO_ROOT, "OpCore-Simplify.py"))
        cls.main = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.main)

    def setUp(self):
        self.ocpe = self.main.OCPE.__new__(self.main.OCPE)
        self.ocpe.u = utils.Utils()
        self.ocpe.k = kext_maestro.KextMaestro()
        self.temp = tempfile.TemporaryDirectory()
        self.ocpe.usb_mapper = usb_mapper.USBMapper(report_dir=self.temp.name)
        self.ocpe.usb_map_override = None
        self.ocpe.usb_map_source = None
        with open(os.path.join(FIXTURES, "desktop", "Report.json"), encoding="utf-8") as report_file:
            self.report = json.load(report_file)
        for kext in self.ocpe.k.kexts:
            kext.checked = kext.required

    def tearDown(self):
        for kext in self.ocpe.k.kexts:
            kext.checked = kext.required
        self.temp.cleanup()

    def quiet(self, function, *args, **kwargs):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            result = function(*args, **kwargs)
        return result, output.getvalue()

    def test_no_saved_map(self):
        source, _ = self.quiet(self.ocpe.prepare_usb_map, self.report, "24.0.0")
        self.assertIsNone(source)

    def test_saved_map_is_built_into_kexts(self):
        with open(os.path.join(FIXTURES, "desktop", "USBMap.json"), encoding="utf-8") as map_file:
            self.ocpe.usb_mapper.save(json.load(map_file))
        source, output = self.quiet(self.ocpe.prepare_usb_map, self.report, "24.0.0")
        self.assertEqual(source["kind"], "json")
        self.assertIn("not listed in the hardware report", output)
        kexts_dir = os.path.join(self.temp.name, "Kexts")
        kext_path = self.ocpe.install_usb_map(kexts_dir)
        self.assertEqual(kext_path, os.path.join(kexts_dir, "UTBMap.kext"))
        self.assertTrue(self.ocpe.k.kexts[kext_maestro.kext_data.kext_index_by_name["USBToolBox"]].checked)
        self.assertFalse(self.ocpe.k.kexts[kext_maestro.kext_data.kext_index_by_name["UTBDefault"]].checked)

    def test_saved_map_from_other_machine_is_ignored(self):
        with open(os.path.join(FIXTURES, "desktop", "USBMap.json"), encoding="utf-8") as map_file:
            self.ocpe.usb_mapper.save(json.load(map_file))
        with open(os.path.join(FIXTURES, "laptop", "Report.json"), encoding="utf-8") as report_file:
            laptop = json.load(report_file)
        source, output = self.quiet(self.ocpe.prepare_usb_map, laptop, "24.0.0")
        self.assertIsNone(source)
        self.assertIn("does not match", output)

    def test_explicit_kext_is_copied(self):
        with open(os.path.join(FIXTURES, "desktop", "USBMap.json"), encoding="utf-8") as map_file:
            kext_source = usb_mapper.build_kext(json.load(map_file), self.temp.name)
        self.ocpe.usb_map_override = kext_source
        source, _ = self.quiet(self.ocpe.prepare_usb_map, self.report, "24.0.0")
        self.assertEqual(source["kind"], "kext")
        kexts_dir = os.path.join(self.temp.name, "EFI", "Kexts")
        copied = self.ocpe.install_usb_map(kexts_dir)
        self.assertTrue(os.path.isfile(os.path.join(copied, "Contents", "Info.plist")))

    def test_explicit_missing_map_raises(self):
        self.ocpe.usb_map_override = os.path.join(self.temp.name, "missing.json")
        with self.assertRaises(Exception):
            self.quiet(self.ocpe.prepare_usb_map, self.report, "24.0.0")

    def test_load_kexts_lists_map_after_usbtoolbox(self):
        kexts_dir = os.path.join(self.temp.name, "Kexts")
        os.makedirs(kexts_dir)
        toolbox_dir = os.path.join(kexts_dir, "USBToolBox.kext", "Contents")
        os.makedirs(toolbox_dir)
        with open(os.path.join(toolbox_dir, "Info.plist"), "wb") as plist_file:
            plistlib.dump({"CFBundleIdentifier": "com.dhinakg.USBToolBox.kext", "CFBundleVersion": "1.2.0", "OSBundleLibraries": {}}, plist_file)
        usb_mapper.build_kext(two_controller_selection(), kexts_dir)
        kernel_add = self.ocpe.k.load_kexts(self.report, "24.0.0", kexts_dir)
        bundles = [entry["BundlePath"] for entry in kernel_add]
        self.assertIn("UTBMap.kext", bundles)
        self.assertLess(bundles.index("USBToolBox.kext"), bundles.index("UTBMap.kext"))
        entry = kernel_add[bundles.index("UTBMap.kext")]
        self.assertEqual(entry["ExecutablePath"], "")
        self.assertEqual(entry["PlistPath"], "Contents/Info.plist")


if __name__ == "__main__":
    unittest.main()
