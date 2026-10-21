import contextlib
import io
import unittest

import repo_path  # noqa: F401
from Scripts import smbios


def make_report(codename, cores, name, platform="Desktop", gpu_type="Integrated GPU", manufacturer="Intel"):
    return {
        "Motherboard": {"Name": "Test Board", "Platform": platform},
        "CPU": {"Codename": codename, "Core Count": str(cores), "Manufacturer": manufacturer, "Processor Name": name},
        "GPU": {"Test GPU": {"Device Type": gpu_type}},
    }


class TahoeOverrideTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.smbios = smbios.SMBIOS()

    def select(self, report, version):
        with contextlib.redirect_stdout(io.StringIO()):
            return self.smbios.select_smbios_model(report, version)

    def test_comet_lake_desktop_with_igpu(self):
        report = make_report("Comet Lake-S", 6, "Intel(R) Core(TM) i5-10400 CPU @ 2.90GHz")
        self.assertEqual(self.select(report, "25.0.0"), "iMac20,1")

    def test_comet_lake_desktop_unchanged_before_tahoe(self):
        report = make_report("Comet Lake-S", 6, "Intel(R) Core(TM) i5-10400 CPU @ 2.90GHz")
        default = self.smbios.select_default_smbios_model(report, "24.6.0")
        self.assertEqual(self.select(report, "24.6.0"), default)
        self.assertEqual(default, "iMac20,1")

    def test_coffee_lake_h_laptop_six_cores(self):
        report = make_report("Coffee Lake-H", 6, "Intel(R) Core(TM) i7-8750H CPU @ 2.20GHz", platform="Laptop")
        self.assertEqual(self.select(report, "25.0.0"), "MacBookPro16,1")

    def test_coffee_lake_u_laptop_four_cores(self):
        report = make_report("Coffee Lake-U", 4, "Intel(R) Core(TM) i5-8250U CPU @ 1.60GHz", platform="Laptop")
        self.assertEqual(self.select(report, "25.0.0"), "MacBookPro16,2")

    def test_haswell_laptop_unchanged(self):
        report = make_report("Haswell-H", 4, "Intel(R) Core(TM) i7-4710HQ CPU @ 2.50GHz", platform="Laptop")
        default = self.smbios.select_default_smbios_model(report, "25.0.0")
        self.assertEqual(self.select(report, "25.0.0"), default)
        self.assertTrue(default.startswith("MacBookPro11"))

    def test_skylake_desktop_with_igpu_unchanged(self):
        report = make_report("Skylake", 4, "Intel(R) Core(TM) i7-6700 CPU @ 3.40GHz")
        self.assertEqual(self.select(report, "25.0.0"), "iMac17,1")

    def test_amd_matisse_with_dgpu(self):
        report = make_report("Matisse", 12, "AMD Ryzen 9 3900X 12-Core Processor", gpu_type="Discrete GPU", manufacturer="AuthenticAMD")
        self.assertEqual(self.select(report, "25.0.0"), "MacPro7,1")

    def test_bloomfield_without_igpu_unchanged(self):
        report = make_report("Bloomfield", 4, "Intel(R) Core(TM) i7 CPU 920 @ 2.67GHz", gpu_type="Discrete GPU")
        self.assertEqual(self.select(report, "25.0.0"), "MacPro6,1")

    def test_haswell_e_without_igpu(self):
        report = make_report("Haswell-E", 8, "Intel(R) Core(TM) i7-5960X CPU @ 3.00GHz", gpu_type="Discrete GPU")
        self.assertEqual(self.select(report, "25.0.0"), "MacPro7,1")


if __name__ == "__main__":
    unittest.main()
