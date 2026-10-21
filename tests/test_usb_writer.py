import contextlib
import io
import json
import unittest
from unittest import mock

import repo_path  # noqa: F401
from Scripts import usb_writer

GB = 1000 ** 3
IS_WINDOWS = usb_writer.os.name == "nt"


def disk(number, size=16 * GB, **overrides):
    item = {"Number": number, "FriendlyName": "Disk {}".format(number), "Size": size, "BusType": "USB",
            "PartitionStyle": "RAW", "IsBoot": False, "IsSystem": False, "IsOffline": False,
            "IsReadOnly": False, "UniqueId": "ID{}".format(number), "SerialNumber": "SN{}".format(number)}
    item.update(overrides)
    return item


class DiskpartScriptTest(unittest.TestCase):
    def setUp(self):
        self.writer = usb_writer.USBWriter()

    def test_small_disk_has_no_size(self):
        script = self.writer.build_diskpart_script(2, 16 * 1024)
        self.assertNotIn("size=", script)
        self.assertIn("select disk 2", script)

    def test_large_disk_capped(self):
        script = self.writer.build_diskpart_script(2, 64 * 1024)
        self.assertIn("size=32000", script)

    def test_script_commands(self):
        script = self.writer.build_diskpart_script(3, 16 * 1024)
        for line in ("clean", "convert gpt", "format fs=fat32 quick"):
            self.assertIn(line, script)


@unittest.skipUnless(IS_WINDOWS, "Windows only")
class CopyPayloadTest(unittest.TestCase):
    def setUp(self):
        self.writer = usb_writer.USBWriter()

    def run_copy(self, drive):
        with mock.patch.object(usb_writer.shutil, "copytree") as copytree, \
                mock.patch.object(usb_writer.shutil, "rmtree") as rmtree, \
                contextlib.redirect_stdout(io.StringIO()):
            result = self.writer.copy_payload(drive, "no-such-efi")
        copytree.assert_not_called()
        rmtree.assert_not_called()
        return result

    def test_empty_drive_rejected(self):
        ok, problems = self.run_copy("")
        self.assertFalse(ok)
        self.assertTrue(problems)

    def test_root_path_rejected(self):
        ok, problems = self.run_copy("C:\\")
        self.assertFalse(ok)
        self.assertTrue(problems)


@unittest.skipUnless(IS_WINDOWS, "Windows only")
class PowerShellParsingTest(unittest.TestCase):
    def setUp(self):
        self.writer = usb_writer.USBWriter()

    def test_drive_letter_ignores_noise(self):
        output = ("WARNING: something happened\n", "", 0)
        with mock.patch.object(self.writer, "_powershell", return_value=output):
            self.assertIsNone(self.writer.wait_for_drive_letter(2, timeout_s=0))

    def test_drive_letter_accepts_letter(self):
        output = ("WARNING: something happened\nE\n", "", 0)
        with mock.patch.object(self.writer, "_powershell", return_value=output):
            self.assertEqual(self.writer.wait_for_drive_letter(2, timeout_s=0), "E:")

    def list_disks(self, payload):
        with mock.patch.object(self.writer, "_powershell", return_value=(json.dumps(payload), "", 0)), \
                contextlib.redirect_stdout(io.StringIO()):
            return self.writer.list_usb_disks()

    def test_filter_drops_unsafe_disks(self):
        payload = [
            disk(0, BusType="NVMe", IsBoot=True),
            disk(1, BusType="NVMe"),
            disk(2, IsBoot=True),
            disk(3, size=GB // 2),
            disk(4, IsOffline=True),
            disk(5),
        ]
        result = self.list_disks(payload)
        self.assertEqual([d["number"] for d in result], [5])

    def test_single_object_output(self):
        result = self.list_disks(disk(7))
        self.assertEqual([d["number"] for d in result], [7])
        self.assertEqual(self.list_disks(disk(8, BusType="NVMe")), [])


if __name__ == "__main__":
    unittest.main()
