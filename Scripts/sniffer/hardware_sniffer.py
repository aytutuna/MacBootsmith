# Adapted from HardwareSniffer.py in lzhoang2801/Hardware-Sniffer (BSD-3-Clause), commit 2e0fa16.
from Scripts import app_paths
from Scripts import resource_fetcher
from Scripts import utils
from . import wmi
import ctypes
import os
import shutil
import subprocess

ACPIDUMP_URL = "https://github.com/acpica/acpica/releases/download/R2024_12_12/acpidump.exe"
ACPIDUMP_SHA256 = "9f54227f9f7dccbf1fbc652f05d342e7525d5de0861905bfef05254064a07fd4"

class HardwareSniffer:
    def __init__(self, result_dir):
        self.fetcher = resource_fetcher.ResourceFetcher()
        self.u = utils.Utils()
        self.result_dir = result_dir
        self.report_path = os.path.join(result_dir, "Report.json")
        self.acpi_dir = os.path.join(result_dir, "ACPI")

    def collect(self):
        from .platforms.windows import WindowsHardwareInfo

        wmi.snapshot()
        self.hardware_info = WindowsHardwareInfo()
        self.hardware_info.hardware_collector()
        return self.hardware_info.result

    def export_hardware_report(self):
        self.u.head("Exporting Hardware Report")
        print("")
        self.u.create_folder(self.result_dir)
        self.u.write_file(self.report_path, self.hardware_info.result)
        print("Report saved to `{}`".format(self.report_path))
        print("")
        return self.report_path

    def check_acpidump(self, redownload=False):
        # iasl-win zips fetched by dsdt.py also carry acpidump.exe, so it is usually here already
        acpidump_path = os.path.join(app_paths.tools_dir(), "acpidump.exe")

        if redownload and os.path.exists(acpidump_path):
            os.remove(acpidump_path)
        elif os.path.exists(acpidump_path):
            return acpidump_path

        self.u.head("Gathering Files")
        print("")
        print("Please wait for download acpidump...")

        if not self.fetcher.download_and_save_file(ACPIDUMP_URL, acpidump_path, ACPIDUMP_SHA256):
            raise Exception("Could not download acpidump.exe. Download it from https://github.com/acpica/acpica/releases and place it in {}.".format(app_paths.tools_dir()))

        return acpidump_path

    def is_admin(self):
        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False

    def run_acpidump(self, acpidump_path):
        try:
            return subprocess.run([acpidump_path, "-b"], cwd=self.acpi_dir, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
        except OSError as e:
            # 4551: Smart App Control, 1260: AppLocker / software restriction policy
            if getattr(e, "winerror", None) in (1260, 4551):
                raise Exception("Windows blocked acpidump.exe (Smart App Control or an application control policy).\n"
                                "Smart App Control cannot be set to allow one file; it can only be turned off under Windows Security > App & browser control,\n"
                                "and once off it stays off. Alternatively boot this PC from a Linux USB and copy /sys/firmware/acpi/tables, then point the ACPI prompt at that folder.")
            if getattr(e, "winerror", None) in (193, 216):
                raise
            raise Exception("acpidump could not be run: {}".format(e))

    def dump_acpi_tables(self):
        self.u.create_folder(self.acpi_dir, remove_content=True)
        try:
            acpidump_path = self.check_acpidump()

            self.u.head("Dumping ACPI Tables")
            print("")
            print("Dumping tables to {}...".format(self.acpi_dir))

            try:
                out = self.run_acpidump(acpidump_path)
            except OSError as e:
                # 193/216: truncated or wrong-architecture exe, so fetch a clean copy once
                if getattr(e, "winerror", None) not in (193, 216):
                    raise
                print("acpidump.exe is damaged, downloading it again...")
                out = self.run_acpidump(self.check_acpidump(redownload=True))

            if out.returncode != 0:
                reason = next((line.strip() for line in out.stdout.splitlines() if line.strip()), "exit code {}".format(out.returncode))
                if not self.is_admin():
                    reason += " (dumping ACPI tables may need administrator rights)"
                raise Exception("acpidump failed: {}".format(reason))

            print("Updating names...")

            for name in os.listdir(self.acpi_dir):
                if name.lower().endswith(".dat"):
                    try:
                        os.rename(os.path.join(self.acpi_dir, name), os.path.join(self.acpi_dir, name[:-4] + ".aml"))
                    except Exception as e:
                        print(" - {} -> {} failed: {}".format(name, name[:-4] + ".aml", e))

            if not any(name.lower().endswith(".aml") for name in os.listdir(self.acpi_dir)):
                raise Exception("acpidump did not write any tables.")
        except Exception:
            shutil.rmtree(self.acpi_dir, ignore_errors=True)
            raise

        print("")
        print("ACPI tables dumped successfully.")
        print("")
        return self.acpi_dir
