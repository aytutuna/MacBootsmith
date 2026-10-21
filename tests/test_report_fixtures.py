import contextlib
import io
import os
import unittest

import repo_path
from Scripts import report_validator


class FixtureReportTest(unittest.TestCase):
    def check(self, name):
        path = os.path.join(repo_path.FIXTURES, name, "Report.json")
        validator = report_validator.ReportValidator()
        with contextlib.redirect_stdout(io.StringIO()):
            is_valid, errors, _, _ = validator.validate_report(path)
        self.assertTrue(is_valid, errors)
        self.assertEqual(errors, [])

    def test_desktop(self):
        self.check("desktop")

    def test_laptop(self):
        self.check("laptop")


if __name__ == "__main__":
    unittest.main()
