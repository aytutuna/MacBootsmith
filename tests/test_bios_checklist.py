import unittest

import repo_path  # noqa: F401
from Scripts import bios_checklist


def report(codename, platform="Desktop", name="Intel(R) Core(TM) CPU", **extra):
    data = {
        "Motherboard": {"Name": "Test Board", "Platform": platform},
        "CPU": {"Codename": codename, "Manufacturer": "Intel", "Processor Name": name},
        "GPU": {},
    }
    data.update(extra)
    return data


class ResolveKeyTest(unittest.TestCase):
    def setUp(self):
        self.checklist = bios_checklist.BIOSChecklist()

    def test_comet_lake_desktop(self):
        self.assertEqual(self.checklist.resolve_key(report("Comet Lake-S")), "intel_desktop_skylake_cometlake")

    def test_haswell_laptop(self):
        self.assertEqual(self.checklist.resolve_key(report("Haswell", platform="Laptop")), "intel_laptop_haswell_broadwell")

    def test_kaby_lake_x(self):
        self.assertEqual(self.checklist.resolve_key(report("Kaby Lake-X", name="Intel(R) Core(TM) i7-7740X")), "intel_hedt_skylake_x_cascade_lake")

    def test_bloomfield_non_xeon(self):
        self.assertEqual(self.checklist.resolve_key(report("Bloomfield", name="Intel(R) Core(TM) i7 CPU 920")), "intel_hedt_nehalem_westmere")

    def test_unknown_codename(self):
        self.assertIsNone(self.checklist.resolve_key(report("Totally Unknown Lake")))


class BuildTest(unittest.TestCase):
    def setUp(self):
        self.checklist = bios_checklist.BIOSChecklist()
        self.common = self.checklist.data["common"]

    def test_unknown_codename_returns_common_lists(self):
        result = self.checklist.build(report("Totally Unknown Lake"))
        self.assertIsNone(result["key"])
        for field in ("disable", "enable", "notes"):
            self.assertEqual(result[field], list(self.common.get(field, [])))
        for field in ("disable", "enable", "notes"):
            for item in self.common.get(field, []):
                self.assertIn(item, result[field])

    def test_secure_boot_disabled_removes_entry(self):
        base = self.checklist.build(report("Comet Lake-S"))
        self.assertTrue(any("Secure Boot" in item for item in base["disable"]))
        result = self.checklist.build(report("Comet Lake-S", BIOS={"Secure Boot": "Disabled"}))
        self.assertFalse(any("Secure Boot" in item for item in result["disable"]))
        self.assertEqual(result["notes"], base["notes"])

    def test_resizable_bar_enabled_removes_above_4g(self):
        base = self.checklist.build(report("Comet Lake-S"))
        self.assertTrue(any("Above 4G Decoding" in item for item in base["enable"]))
        result = self.checklist.build(report("Comet Lake-S", GPU={"GPU": {"Resizable BAR": "Enabled"}}))
        self.assertFalse(any("Above 4G Decoding" in item for item in result["enable"]))
        self.assertEqual(result["notes"], base["notes"])


if __name__ == "__main__":
    unittest.main()
