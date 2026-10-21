from Scripts.datasets import bios_settings
from Scripts.datasets import cpu_data

class BIOSChecklist:
    def __init__(self):
        self.data = bios_settings.data

    def is_intel_hedt_cpu(self, processor_name, cpu_codename):
        if cpu_codename in cpu_data.IntelCPUGenerations[45:66]:
            return cpu_codename.endswith(("-X", "-P", "-W", "-E", "-EP", "-EX"))

        if cpu_codename in cpu_data.IntelCPUGenerations[66:]:
            return "Xeon" in processor_name

        return False

    def resolve_key(self, hardware_report):
        cpu = hardware_report.get("CPU", {})
        motherboard = hardware_report.get("Motherboard", {})
        codename = cpu.get("Codename", "")
        processor_name = cpu.get("Processor Name", "")
        platform = "Laptop" if "NUC" in motherboard.get("Name", "") else motherboard.get("Platform", "")
        platform = "Laptop" if platform == "NUC" else platform

        if "AMD" in cpu.get("Manufacturer", "") or "AMD" in processor_name:
            prefix = "amd"
        elif self.is_intel_hedt_cpu(processor_name, codename):
            prefix = "intel_hedt"
        elif "Laptop" in platform:
            prefix = "intel_laptop"
        else:
            prefix = "intel_desktop"

        if not codename:
            return None

        keys = [key for key in self.data if key != "common"]

        def in_family(key):
            return key == prefix or key.startswith(prefix + "_")

        def pick(matches):
            if not matches:
                return None
            for key in matches:
                if in_family(key):
                    return key
            return matches[0]

        exact = [key for key in keys if codename in self.data[key].get("codenames", [])]
        if exact:
            return pick(exact)

        if prefix == "intel_hedt" or codename.endswith("-X"):
            keys = [key for key in keys if key.startswith("intel_hedt")]

        partial = [key for key in keys if any(name in codename or codename in name for name in self.data[key].get("codenames", []))]
        return pick(partial)

    def merge(self, field, key):
        merged = []
        entries = [self.data.get("common", {})]
        if key:
            entries.append(self.data[key])
        for entry in entries:
            for item in entry.get(field, []):
                if item not in merged:
                    merged.append(item)
        return merged

    def build(self, hardware_report):
        key = self.resolve_key(hardware_report)
        disable = self.merge("disable", key)
        enable = self.merge("enable", key)
        notes = self.merge("notes", key)

        bios = hardware_report.get("BIOS", {})
        if bios.get("Secure Boot") == "Disabled":
            disable = [item for item in disable if "Secure Boot" not in item]
        if any(gpu.get("Resizable BAR") == "Enabled" for gpu in hardware_report.get("GPU", {}).values()):
            enable = [item for item in enable if "Above 4G Decoding" not in item]

        return {"key": key, "disable": disable, "enable": enable, "notes": notes}
