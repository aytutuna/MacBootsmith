import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))))

from Scripts.report_validator import ReportValidator

# A Hyper-V runner keeps its display, NIC, disks, keyboard and mouse on VMBus and has no USB
# controller; the scan skips VMBus devices exactly as it does on real hardware.
ABSENT_ON_VM = re.compile(r"Root: Missing required key '(GPU|Network|USB Controllers|Storage Controllers|Input)'$")


def main():
    parser = argparse.ArgumentParser(description="Check a hardware report scanned on a CI runner.")
    parser.add_argument("report")
    parser.add_argument("--acpi-dir", help="fail unless this folder holds dumped tables")
    args = parser.parse_args()

    ok, errors, warnings, data = ReportValidator().validate_report(args.report)
    print("valid: {} errors: {} warnings: {}".format(ok, errors, warnings))
    absent = [e for e in errors if ABSENT_ON_VM.match(e)]
    errors = [e for e in errors if e not in absent]

    if data:
        located = [name for name, device in (data.get("System Devices") or {}).items() if device.get("ACPI Path") or device.get("PCI Path")]
        if not located:
            errors.append("no System Devices entry has an ACPI Path or PCI Path, so GetDeviceProperties gave nothing")
    else:
        errors.append("no report data")

    if args.acpi_dir is not None:
        if not os.path.isdir(args.acpi_dir) or not any(name.lower().endswith(".aml") for name in os.listdir(args.acpi_dir)):
            errors.append("no ACPI tables were dumped to {}".format(args.acpi_dir))

    if absent:
        print("::warning::sections the runner VM has no devices for: {}".format("; ".join(absent)))
    if errors:
        print("::error::scanned report check failed: {}".format("; ".join(errors)))
        return 1
    print("::notice::scan ok: {} / {} / sections {}".format(data["Motherboard"]["Name"], data["CPU"]["Processor Name"], ", ".join(data)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
