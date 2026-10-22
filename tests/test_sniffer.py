import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from repo_path import REPO_ROOT  # noqa: F401

if "winreg" not in sys.modules:
    try:
        import winreg  # noqa: F401
    except ImportError:
        sys.modules["winreg"] = types.ModuleType("winreg")

from Scripts import report_validator
from Scripts import utils
from Scripts.sniffer import hardware_sniffer
from Scripts.sniffer import wmi
from Scripts.sniffer.platforms import windows

GPU = "PCI\\VEN_8086&DEV_9BC8&SUBSYS_D0001458&REV_03\\3&11583659&0&10"
MONITOR = "DISPLAY\\DEL4321\\4&1A2B3C4D&0&UID4352"
NET = "PCI\\VEN_8086&DEV_0D4D&SUBSYS_E0001458&REV_00\\3&11583659&0&FE"
HDA = "PCI\\VEN_8086&DEV_06C8&SUBSYS_A0C31458&REV_00\\3&11583659&0&FB"
CODEC = "HDAUDIO\\FUNC_01&VEN_10EC&DEV_0897&SUBSYS_1458A0C3&REV_1003\\4&2A3B4C5D&0&0001"
XHCI = "PCI\\VEN_8086&DEV_06ED&SUBSYS_50071458&REV_00\\3&11583659&0&A0"
NVME = "PCI\\VEN_144D&DEV_A808&SUBSYS_A801144D&REV_00\\4&1F2E3D4C&0&00E8"
LPC = "PCI\\VEN_8086&DEV_0685&SUBSYS_50011458&REV_00\\3&11583659&0&F8"

DOCUMENT = {
    "Win32_ComputerSystem": {"Manufacturer": "Contoso Ltd", "Model": "Z490 TEST BOARD", "PCSystemType": 1, "SystemType": "x64-based PC"},
    "Win32_BIOS": [{"SMBIOSBIOSVersion": "F1", "ReleaseDate": "20230510000000.000000+000"}],
    "Win32_BaseBoard": {"Manufacturer": "Contoso", "Product": "Z490 TEST BOARD"},
    "Win32_Processor": {"Manufacturer": "GenuineIntel", "Name": "Intel(R) Core(TM) i5-10400 CPU @ 2.90GHz", "Description": "Intel64 Family 6 Model 165 Stepping 3", "NumberOfCores": 6},
    "Win32_PnPEntity": [
        {"Name": "Intel(R) UHD Graphics 630", "PNPClass": "Display", "PNPDeviceID": GPU, "Service": "igfx", "ConfigManagerErrorCode": 0},
        {"Name": "Generic PnP Monitor", "PNPClass": "Monitor", "PNPDeviceID": MONITOR, "Service": "monitor", "ConfigManagerErrorCode": 0},
        {"Name": "Intel(R) Ethernet Connection (11) I219-V", "PNPClass": "Net", "PNPDeviceID": NET, "Service": "e1dexpress", "ConfigManagerErrorCode": 0},
        {"Name": "High Definition Audio Controller", "PNPClass": "System", "PNPDeviceID": HDA, "Service": "HDAudBus", "ConfigManagerErrorCode": 0},
        {"Name": "Realtek High Definition Audio", "PNPClass": "MEDIA", "PNPDeviceID": CODEC, "Service": "IntcAzAudAddService", "ConfigManagerErrorCode": 0},
        {"Name": "Speakers (Realtek High Definition Audio)", "PNPClass": "AudioEndpoint", "PNPDeviceID": "SWD\\MMDEVAPI\\{0.0.0.00000000}.{1234}", "Service": None, "ConfigManagerErrorCode": 0},
        {"Name": "USB xHCI Compliant Host Controller", "PNPClass": "USB", "PNPDeviceID": XHCI, "Service": "USBXHCI", "ConfigManagerErrorCode": 0},
        {"Name": "HID Keyboard Device", "PNPClass": "Keyboard", "PNPDeviceID": "HID\\VID_046D&PID_C31C&MI_00\\7&1A2B3C4D&0&0000", "Service": "kbdhid", "ConfigManagerErrorCode": 0},
        {"Name": "Standard NVM Express Controller", "PNPClass": "SCSIAdapter", "PNPDeviceID": NVME, "Service": "stornvme", "ConfigManagerErrorCode": 0},
        {"Name": "Contoso SSD 500GB", "PNPClass": "DiskDrive", "PNPDeviceID": "SCSI\\DISK&VEN_NVME&PROD_CONTOSO_SSD\\5&1&0&000000", "Service": "disk", "ConfigManagerErrorCode": 0},
        {"Name": "Intel(R) LPC Controller (Z490) - 0685", "PNPClass": "System", "PNPDeviceID": LPC, "Service": "msisadrv", "ConfigManagerErrorCode": 0},
        {"Name": None, "PNPClass": None, "PNPDeviceID": None, "Service": None, "ConfigManagerErrorCode": 0}
    ],
    "DeviceProperties": [
        {"DeviceID": GPU, "KeyName": "DEVPKEY_Device_Parent", "Data": "PCI\\VEN_8086&DEV_9B63\\3&11583659&0&00"},
        {"DeviceID": GPU, "KeyName": "DEVPKEY_Device_LocationPaths", "Data": ["PCIROOT(0)#PCI(0200)", "ACPI(_SB_)#ACPI(PC00)#ACPI(GFX0)"]},
        {"DeviceID": MONITOR.lower(), "KeyName": "DEVPKEY_Device_Parent", "Data": GPU},
        {"DeviceID": NET, "KeyName": "DEVPKEY_Device_LocationPaths", "Data": "PCIROOT(0)#PCI(1F06)"},
        {"DeviceID": CODEC, "KeyName": "DEVPKEY_Device_Parent", "Data": HDA},
        {"DeviceID": "SWD\\MMDEVAPI\\{0.0.0.00000000}.{1234}", "KeyName": "DEVPKEY_Device_Parent", "Data": CODEC},
        {"DeviceID": XHCI, "KeyName": "DEVPKEY_Device_LocationPaths", "Data": ["PCIROOT(0)#PCI(1400)", "ACPI(_SB_)#ACPI(PC00)#ACPI(XHCI)"]},
        {"DeviceID": NVME, "KeyName": "DEVPKEY_Device_LocationPaths", "Data": ["PCIROOT(0)#PCI(1B00)#PCI(0000)", "ACPI(_SB_)#ACPI(PC00)#ACPI(RP21)#ACPI(PXSX)"]},
        {"DeviceID": "SCSI\\DISK&VEN_NVME&PROD_CONTOSO_SSD\\5&1&0&000000", "KeyName": "DEVPKEY_Device_Parent", "Data": NVME},
        {"DeviceID": LPC, "KeyName": "DEVPKEY_Device_LocationPaths", "Data": ["PCIROOT(0)#PCI(1F00)", "ACPI(_SB_)#ACPI(PC00)#ACPI(LPCB)"]}
    ],
    "WmiMonitorID": {"InstanceName": MONITOR.lower() + "_0", "UserFriendlyName": [67, 79, 78, 84, 79, 83, 79, 32, 50, 55, 0, 0, 0]},
    "WmiMonitorConnectionParams": [{"InstanceName": MONITOR + "_0", "VideoOutputTechnology": 10}],
    "WmiMonitorListedSupportedSourceModes": [{"InstanceName": MONITOR + "_0", "MonitorSourceModes": {"HorizontalActivePixels": 3840, "VerticalActivePixels": 2160}}]
}


def bare_info():
    return windows.WindowsHardwareInfo.__new__(windows.WindowsHardwareInfo)


class ShimTests(unittest.TestCase):
    def setUp(self):
        self.data = wmi.parse(json.dumps(DOCUMENT))

    def test_single_object_becomes_list(self):
        self.assertEqual(len(self.data["Win32_ComputerSystem"]), 1)
        self.assertEqual(self.data["Win32_ComputerSystem"][0].PCSystemType, 1)
        self.assertEqual(len(self.data["WmiMonitorID"]), 1)
        self.assertEqual(len(self.data["Win32_PnPEntity"]), 12)
        self.assertNotIn("DeviceProperties", self.data)

    def test_missing_attribute_is_none(self):
        cpu = self.data["Win32_Processor"][0]
        self.assertIsNone(cpu.NoSuchProperty)
        self.assertEqual(getattr(cpu, "NumberOfCores", 0), 6)

    def test_device_properties(self):
        devices = {d.PNPDeviceID: d for d in self.data["Win32_PnPEntity"]}
        props, ret = devices[MONITOR].GetDeviceProperties(["DEVPKEY_Device_Parent"])
        self.assertEqual(ret, 0)
        self.assertEqual(props[0].Data, GPU)
        self.assertEqual(devices[NET].GetDeviceProperties(["DEVPKEY_Device_LocationPaths"])[0][0].Data, ["PCIROOT(0)#PCI(1F06)"])
        with self.assertRaises(AttributeError):
            devices[NET].GetDeviceProperties(["DEVPKEY_Device_Parent"])[0][0].Data
        with self.assertRaises(AttributeError):
            self.data["Win32_PnPEntity"][-1].GetDeviceProperties(["DEVPKEY_Device_Parent"])[0][0].Data

    def test_monitor_values(self):
        name = bytes(self.data["WmiMonitorID"][0].UserFriendlyName).decode("ascii").rstrip("\x00")
        self.assertEqual(name, "CONTOSO 27")
        modes = self.data["WmiMonitorListedSupportedSourceModes"][0].MonitorSourceModes
        self.assertEqual([(m.HorizontalActivePixels, m.VerticalActivePixels) for m in modes], [(3840, 2160)])

    def test_internal_panel_is_signed(self):
        doc = {"WmiMonitorConnectionParams": [{"InstanceName": "X", "VideoOutputTechnology": 2147483648}]}
        self.assertEqual(wmi.parse(json.dumps(doc))["WmiMonitorConnectionParams"][0].VideoOutputTechnology, -2147483648)

    def test_bios_date_stays_dmtf(self):
        self.assertEqual(self.data["Win32_BIOS"][0].ReleaseDate, "20230510000000.000000+000")

    def test_powershell_failure(self):
        with mock.patch.object(wmi, "_powershell", return_value=("", "Get-CimInstance : Access denied\nmore", 1)):
            with self.assertRaises(Exception) as ctx:
                wmi.snapshot()
        self.assertIn("Access denied", str(ctx.exception))

    def test_stdout_not_json(self):
        with mock.patch.object(wmi, "_powershell", return_value=("WARNING: something odd\n{}", "", 0)):
            with self.assertRaises(Exception) as ctx:
                wmi.snapshot()
        self.assertIn("could not be read", str(ctx.exception))

    def test_powershell_cannot_start(self):
        with mock.patch.object(wmi.subprocess, "run", side_effect=FileNotFoundError(2, "The system cannot find the file specified")):
            with self.assertRaises(Exception) as ctx:
                wmi.snapshot()
        self.assertIn("powershell.exe could not be started", str(ctx.exception))


class ParseDevicePathTests(unittest.TestCase):
    def test_pci(self):
        self.assertEqual(bare_info().parse_device_path(GPU), {"Bus Type": "PCI", "Device ID": "8086-9BC8", "Subsystem ID": "D0001458"})

    def test_usb(self):
        self.assertEqual(bare_info().parse_device_path("USB\\VID_46D&PID_C31C\\5&1"), {"Bus Type": "USB", "Device ID": "046D-C31C"})

    def test_hdaudio(self):
        self.assertEqual(bare_info().parse_device_path(CODEC), {"Bus Type": "HDAUDIO", "Device ID": "10EC-0897", "Subsystem ID": "1458A0C3"})

    def test_acpi(self):
        self.assertEqual(bare_info().parse_device_path("ACPI\\PNP0C0A\\1"), {"Bus Type": "ACPI", "Device": "PNP0C0A"})

    def test_hid_without_vendor(self):
        self.assertEqual(bare_info().parse_device_path("HID\\ELAN0001&COL01\\5&1"), {"Bus Type": "HID", "Device": "ELAN0001"})


class UtilsTests(unittest.TestCase):
    def test_read_ids(self):
        temp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, temp, True)
        path = os.path.join(temp, "test.ids")
        with open(path, "w") as f:
            f.write("# comment\n8086  Intel Corporation\n\t9bc8  CometLake-S GT2\n\t0685  Z490 LPC\n10ec  Realtek\n")
        data = utils.Utils().read_file(path)
        self.assertEqual(data["8086"]["devices"]["9BC8"], "CometLake-S GT2")
        self.assertEqual(data["10EC"]["name"], "Realtek")

    def test_unique_key(self):
        u = utils.Utils()
        self.assertEqual(u.get_unique_key("A", {}), "A")
        self.assertEqual(u.get_unique_key("A", {"A": 1, "A_#1": 2}), "A_#2")


class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.temp, True)
        fake_winreg = types.SimpleNamespace(HKEY_LOCAL_MACHINE=0, OpenKey=mock.Mock(side_effect=FileNotFoundError))
        for patcher in (
            mock.patch.object(wmi, "_powershell", return_value=(json.dumps(DOCUMENT), "", 0)),
            mock.patch.object(windows, "winreg", fake_winreg),
            mock.patch.object(windows.subprocess, "run", side_effect=OSError("no powershell")),
            mock.patch.object(windows.WindowsHardwareInfo, "get_simd_features", return_value="SSE, SSE2, SSE3, SSSE3, SSE4.1, SSE4.2, AVX, AVX2"),
            mock.patch.object(windows.time, "sleep"),
            mock.patch.object(utils.Utils, "head"),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            patcher.__enter__()
            self.addCleanup(patcher.__exit__, None, None, None)

    def test_report_validates(self):
        sniffer = hardware_sniffer.HardwareSniffer(self.temp)
        result = sniffer.collect()
        path = sniffer.export_hardware_report()

        self.assertEqual(result["Motherboard"], {"Name": "CONTOSO Z490 TEST BOARD", "Chipset": "Z490", "Platform": "Desktop"})
        self.assertEqual(result["BIOS"]["Release Date"], "2023-05-10")
        self.assertEqual(result["BIOS"]["Firmware Type"], "UEFI")
        self.assertEqual(result["CPU"]["Codename"], "Comet Lake-S")
        self.assertEqual(result["CPU"]["Core Count"], "06")
        gpu = result["GPU"]["Intel(R) UHD Graphics 630"]
        self.assertEqual((gpu["PCI Path"], gpu["ACPI Path"]), ("PciRoot(0x0)/Pci(0x2,0x0)", "\\_SB.PC00.GFX0"))
        self.assertEqual(result["Monitor"], {"CONTOSO 27": {"Connector Type": "DP", "Resolution": "3840x2160", "Connected GPU": "Intel(R) UHD Graphics 630"}})
        sound = result["Sound"]["Realtek High Definition Audio"]
        self.assertEqual(sound["Audio Endpoints"], ["Speakers"])
        self.assertEqual(sound["Controller Device ID"], "8086-06C8")
        self.assertEqual([c.get("Disk Drives") for c in result["Storage Controllers"].values()], [["Contoso SSD 500GB"]])
        self.assertEqual(result["Network"]["Intel(R) Ethernet Connection (11) I219-V"]["PCI Path"], "PciRoot(0x0)/Pci(0x1f,0x6)")

        is_valid, errors, warnings, data = report_validator.ReportValidator().validate_report(path)
        self.assertTrue(is_valid, errors)
        self.assertEqual(errors, [])
        self.assertEqual(data, result)


class AcpiDumpTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.temp, True)
        self.sniffer = hardware_sniffer.HardwareSniffer(self.temp)
        for patcher in (
            mock.patch.object(self.sniffer, "check_acpidump", return_value=r"C:\tools\acpidump.exe"),
            mock.patch.object(self.sniffer, "is_admin", return_value=False),
            mock.patch.object(utils.Utils, "head"),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            patcher.__enter__()
            self.addCleanup(patcher.__exit__, None, None, None)

    def test_tables_renamed(self):
        def fake_run(args, cwd, **kwargs):
            for name in ("dsdt.dat", "ssdt1.dat"):
                open(os.path.join(cwd, name), "wb").close()
            return subprocess.CompletedProcess(args, 0, stdout="")

        with mock.patch.object(hardware_sniffer.subprocess, "run", side_effect=fake_run):
            acpi_dir = self.sniffer.dump_acpi_tables()
        self.assertEqual(sorted(os.listdir(acpi_dir)), ["dsdt.aml", "ssdt1.aml"])

    def test_failure_removes_dir(self):
        done = subprocess.CompletedProcess(["acpidump"], 1, stdout="Could not get ACPI tables, AE_ACCESS\n")
        with mock.patch.object(hardware_sniffer.subprocess, "run", return_value=done):
            with self.assertRaises(Exception) as ctx:
                self.sniffer.dump_acpi_tables()
        self.assertIn("AE_ACCESS", str(ctx.exception))
        self.assertIn("administrator", str(ctx.exception))
        self.assertFalse(os.path.exists(os.path.join(self.temp, "ACPI")))

    def test_blocked_by_application_control(self):
        err = OSError(22, "An Application Control policy has blocked this file")
        err.winerror = 4551
        with mock.patch.object(hardware_sniffer.subprocess, "run", side_effect=err):
            with self.assertRaises(Exception) as ctx:
                self.sniffer.dump_acpi_tables()
        self.assertIn("Smart App Control", str(ctx.exception))
        self.assertFalse(os.path.exists(os.path.join(self.temp, "ACPI")))

    def test_damaged_exe_downloaded_again(self):
        err = OSError(8, "%1 is not a valid Win32 application")
        err.winerror = 193

        def fake_run(args, cwd, **kwargs):
            open(os.path.join(cwd, "dsdt.dat"), "wb").close()
            return subprocess.CompletedProcess(args, 0, stdout="")

        calls = []

        def run_side_effect(args, cwd, **kwargs):
            calls.append(args)
            if len(calls) == 1:
                raise err
            return fake_run(args, cwd)

        with mock.patch.object(hardware_sniffer.subprocess, "run", side_effect=run_side_effect):
            acpi_dir = self.sniffer.dump_acpi_tables()
        self.assertEqual(os.listdir(acpi_dir), ["dsdt.aml"])
        self.assertEqual(len(calls), 2)
        self.assertEqual(self.sniffer.check_acpidump.call_args_list, [mock.call(), mock.call(redownload=True)])


if __name__ == "__main__":
    unittest.main()
