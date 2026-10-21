# Board- and vendor-specific exceptions from the OpenCore install guide that the generic build does not apply.
# "match" fields are lists of case-insensitive regular expressions searched in the hardware report:
#   motherboard -> Motherboard.Name, chipset -> Motherboard.Chipset, bios_vendor -> BIOS.Vendor,
#   cpu -> CPU.Processor Name. A rule applies when every listed field has at least one matching pattern.
# "config" maps dotted config.plist keys to values; "drop_drivers" removes UEFI drivers by Path;
# "acpi" maps prebuilt tables to their download page; a table is added to ACPI -> Add when present in EFI/OC/ACPI.
# HP and Dell handling stays in config_prodigy.genarate.

ssdt_cpur_url = "https://github.com/dortania/Getting-Started-With-ACPI/raw/master/extra-files/compiled/SSDT-CPUR.aml"

rules = [
    {
        "name": "Microsoft Surface",
        "match": {"motherboard": ["SURFACE"]},
        "config": {"UEFI.Quirks.DisableSecurityPolicy": True},
        "notes": [
            "Microsoft Surface: UEFI -> Quirks -> DisableSecurityPolicy is on so the firmware lets OpenCore load its drivers; keep Secure Boot disabled."
        ]
    },
    {
        "name": "AMD B550/A520",
        "match": {"chipset": ["^B550$", "^A520$"]},
        "acpi": {"SSDT-CPUR.aml": ssdt_cpur_url},
        "unless_acpi": "SSDT-PLUG-ALT.aml",
        "unless_notes": [
            "AMD B550/A520: the processor objects are already redefined by SSDT-PLUG-ALT.aml in this build; do not add SSDT-CPUR.aml next to it."
        ],
        "notes": [
            "Needs SSDT-CPUR.aml (not on X570 or older) or boot panics in cckprng_int_gen"
        ]
    },
    {
        "name": "Insyde firmware",
        "match": {"bios_vendor": ["Insyde"]},
        "notes": [
            "Insyde firmware: after copying the EFI to the internal disk, set Misc -> Boot -> LauncherOption to Short instead of Full, because Insyde firmware often cannot handle full device paths in boot entries."
        ]
    },
    {
        "name": "Lenovo ThinkPad",
        "match": {"motherboard": ["THINKPAD", r"^LENOVO\s+2[01][0-9A-Z]{2}"]},
        "drop_drivers": ["ResetNvramEntry.efi"],
        "notes": [
            "Do not use Reset NVRAM from the picker on ThinkPads; it can brick the firmware. Update the BIOS instead. The match also covers ThinkBook machine types, which get the same precaution.",
            "ResetNvramEntry.efi is left out of this build, so the picker has no Reset NVRAM entry."
        ]
    },
    {
        "name": "AMD Threadripper over 64 threads",
        "match": {"cpu": ["3990X", r"[3579]995WX", "7985WX", "9985WX", r"[79]980X"]},
        "notes": [
            "macOS supports at most 64 threads: disable SMT in BIOS"
        ]
    }
]
