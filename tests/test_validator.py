import os
import subprocess
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from repo_path import REPO_ROOT  # noqa: F401

from Scripts import validator


class ValidateTests(unittest.TestCase):
    def setUp(self):
        self.val = validator.ConfigValidator()
        patcher = mock.patch.object(self.val, "check_ocvalidate", return_value=r"C:\tools\ocvalidate.exe")
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_passes_when_exit_zero(self):
        done = subprocess.CompletedProcess(["ocvalidate"], 0, stdout="Completed validating config.plist in 1 ms. No issues found.\n")
        with mock.patch.object(validator.subprocess, "run", return_value=done):
            ok, text = self.val.validate("config.plist")
        self.assertTrue(ok)
        self.assertIn("No issues found", text)

    def test_errors_when_exit_nonzero(self):
        done = subprocess.CompletedProcess(["ocvalidate"], 1, stdout="Kernel->Quirks->DisableIoMapper is invalid\n")
        with mock.patch.object(validator.subprocess, "run", return_value=done):
            ok, text = self.val.validate("config.plist")
        self.assertFalse(ok)
        self.assertIn("DisableIoMapper", text)

    def test_blocked_by_application_control(self):
        err = OSError(22, "An Application Control policy has blocked this file")
        err.winerror = 4551
        with mock.patch.object(validator.subprocess, "run", side_effect=err):
            ok, text = self.val.validate("config.plist")
        self.assertIsNone(ok)
        self.assertIn("Smart App Control", text)
        self.assertIn("ocvalidate.exe", text)

    def test_other_launch_error(self):
        with mock.patch.object(validator.subprocess, "run", side_effect=OSError(13, "Permission denied")):
            ok, text = self.val.validate("config.plist")
        self.assertIsNone(ok)
        self.assertIn("Permission denied", text)


if __name__ == "__main__":
    unittest.main()
