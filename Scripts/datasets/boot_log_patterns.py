INSTALL_FLOW = "docs/reference/install-flow.md"
TROUBLESHOOTING = INSTALL_FLOW + " section 7"
BOOTER_LIST = INSTALL_FLOW + " section 7, Booter list"
BUILD_SECTION = INSTALL_FLOW + " section 2"
BIOS_SETTINGS = "docs/reference/bios-settings.md"

stages = [
    ("none", "no OpenCore output"),
    ("opencore_started", "OpenCore started"),
    ("config_loaded", "config loaded"),
    ("drivers", "drivers loaded"),
    ("picker_shown", "picker shown"),
    ("entry_chosen", "entry chosen"),
    ("booter_handoff", "booter handoff"),
    ("kernel_started", "kernel started")
]

stage_markers = {
    "opencore_started": [
        r"BS: Starting OpenCore application",
        r"OC: Starting OpenCore"
    ],
    "config_loaded": [
        r"OC: Loaded configuration of \d+ bytes",
        r"OC: OpenCore [A-Z]{3}-\d{3}-\d{4}-\d{2}-\d{2} is loading in"
    ],
    "drivers": [
        r"OC: Got \d+ drivers",
        r"OC: Driver \S+ at \d+ is successfully loaded"
    ],
    "picker_shown": [
        r"OCB: Showing menu",
        r"OCB: ShowPicker",
        r"OC: Boot picker",
        r"OCB: Found \d+ entries",
        r"OCUI:"
    ],
    "entry_chosen": [
        r"OCB: Should boot from \d+\.",
        r"OCB: Perform boot "
    ],
    "booter_handoff": [
        r"AAPL: #\[EB",
        r"EB\|#LOG:EXITBS",
        r"EB\|LD:",
        r"OCAK: Read kernel version"
    ],
    "kernel_started": [
        r"Darwin Kernel Version",
        r"\[ ?PCI configurations? begins?",
        r"Still waiting for root device",
        r"Waiting for [Rr]oot [Dd]evice",
        r"IOConsoleUsers: gIOScreenLock",
        r"kextd stall\[\d+\]",
        r"cckprng_int_gen",
        r"AppleUSBHostPort::createDevice",
        r"panic\(cpu \d+ caller"
    ]
}

banner = r"OC: OpenCore (([A-Z]{3})-(\d)(\d)(\d)-(\d{4}-\d{2}-\d{2})) is loading in (\w+) mode"
build_types = {"DBG": "DEBUG", "REL": "RELEASE", "NPT": "NOOPT", "DEV": "DEVELOPMENT"}

driver_loading = r"OC: Driver (\S+) at \d+ \(.*\) is being loaded"
driver_loaded = r"OC: Driver (\S+) at \d+ is successfully loaded"

mask_rules = [
    (r"(\b(?:HW_)?(?:SSN|MLB)\b[\s=:]+)([A-Z0-9]{8,})", r"\1<masked>"),
    (r"(\b(?:SystemSerialNumber|BoardSerialNumber|ChassisSerialNumber|SerialNumber|MLB)\b[\"'\s=:]+)([A-Za-z0-9]{8,})", r"\1<masked>"),
    (r"(\b(?:system-id|SystemUUID|SmUUID|uuid|UUID)\b[\s=:]+)([0-9A-Fa-f]{8}-?[0-9A-Fa-f]{4}-?[0-9A-Fa-f]{4}-?[0-9A-Fa-f]{4}-?[0-9A-Fa-f]{12})", r"\1<masked>"),
    (r"(\b(?:SSN|MLB) from NVRAM took precedence:\s*)(\S+)", r"\1<masked>"),
    (r"(\b(?:HW_)?ROM\b[\s=:]+)((?:[0-9A-Fa-f]{2}[:-]?){5}[0-9A-Fa-f]{2})\b", r"\1<masked>")
]

# category: crash, config, driver, firmware, picker, security, booter, kernel, noise
# severity: fatal stops the boot, warning may explain a later failure, info is context only
patterns = [
    {
        "id": "x64_exception",
        "regex": r"X64 Exception Type|!!!! X64 Exception",
        "stage": "any",
        "category": "crash",
        "severity": "fatal",
        "cause": "A CPU exception in firmware, a driver or OpenCore itself.",
        "fix": "The lines just before it name the module. Remove or replace that driver; on AMD FX and other older CPUs see kernel-issues in the OpenCore guide.",
        "doc": TROUBLESHOOTING
    },
    {
        "id": "assert",
        "regex": r"\bASSERT\b",
        "stage": "any",
        "category": "crash",
        "severity": "fatal",
        "cause": "An internal check failed in a DEBUG build of OpenCore or a driver.",
        "fix": "The ASSERT line names the source file. Check that every driver comes from the same OpenCore package, then report it to the driver's author.",
        "doc": TROUBLESHOOTING
    },
    {
        "id": "driver_missing",
        "regex": r"OC: Driver (\S+) at \d+ cannot be found",
        "stage": "drivers",
        "category": "config",
        "severity": "fatal",
        "cause": "config.plist lists the driver {0}, but it is not in EFI/OC/Drivers.",
        "fix": "Copy the driver into EFI/OC/Drivers or remove its UEFI -> Drivers entry, then rebuild.",
        "doc": BUILD_SECTION
    },
    {
        "id": "driver_load_failed",
        "regex": r"OC: Driver (\S+) at \d+ cannot be (?:loaded|started) - (.+?)!?$",
        "stage": "drivers",
        "category": "driver",
        "severity": "fatal",
        "cause": "The driver {0} failed to load ({1}): wrong build, damaged file or not meant for this firmware.",
        "fix": "Use the drivers from the same OpenCore package; use HfsPlusLegacy.efi instead of HfsPlus.efi on CPUs without RDRAND.",
        "doc": BUILD_SECTION
    },
    {
        "id": "plist_only_kext",
        "regex": r"Plist only kext has CFBundleExecutable key",
        "stage": "config_loaded",
        "category": "config",
        "severity": "fatal",
        "cause": "A Kernel -> Add entry and the kext on disk disagree about the executable.",
        "fix": "Rebuild so config.plist matches EFI/OC/Kexts exactly.",
        "doc": BUILD_SECTION
    },
    {
        "id": "openruntime_mismatch",
        "regex": r"OCABC: Incompatible OpenRuntime r(\d+), require r(\d+)",
        "stage": "drivers",
        "category": "driver",
        "severity": "fatal",
        "cause": "OpenRuntime.efi (r{0}) comes from a different OpenCore version than OpenCore.efi (needs r{1}).",
        "fix": "Use BOOTx64.efi, OpenCore.efi and OpenRuntime.efi from the same OpenCore build.",
        "doc": TROUBLESHOOTING
    },
    {
        "id": "vault_invalid",
        "regex": r"OC: Invalid Vault mode",
        "stage": "config_loaded",
        "category": "config",
        "severity": "fatal",
        "cause": "Misc -> Security -> Vault has a value OpenCore does not accept.",
        "fix": "Set Vault to Optional (exact case).",
        "doc": TROUBLESHOOTING
    },
    {
        "id": "vault_missing",
        "regex": r"no vault provided",
        "stage": "config_loaded",
        "category": "config",
        "severity": "fatal",
        "cause": "Vault is Basic or Secure but vault.plist or its signature is missing.",
        "fix": "Set Misc -> Security -> Vault to Optional, or restore a clean OpenCore.efi if it was signed.",
        "doc": TROUBLESHOOTING
    },
    {
        "id": "vault_optional",
        "regex": r"OCST: Missing vault data, ignoring",
        "stage": "opencore_started",
        "category": "noise",
        "severity": "info",
        "cause": "Normal with Vault set to Optional.",
        "fix": "Nothing to do.",
        "doc": TROUBLESHOOTING
    },
    {
        "id": "no_schema",
        "regex": r"OCS: No schema for (\S+)",
        "stage": "config_loaded",
        "category": "config",
        "severity": "warning",
        "cause": "config.plist has a key ({0}) this OpenCore version does not know: a Clover config, a configurator edit or a config from another OpenCore version.",
        "fix": "Start from the Sample.plist of this OpenCore version (rebuild with the app) instead of editing an old config.",
        "doc": TROUBLESHOOTING
    },
    {
        "id": "real_field",
        "regex": r"Failed to parse real field of type",
        "stage": "config_loaded",
        "category": "config",
        "severity": "fatal",
        "cause": "A number in config.plist is stored as <real> (usually HaltLevel).",
        "fix": "Change it to <integer>, for HaltLevel <integer>2147483648</integer>.",
        "doc": TROUBLESHOOTING
    },
    {
        "id": "plist_unreadable",
        "regex": r"OCS: Couldn't (?:parse serialized file|get serialized root)",
        "stage": "config_loaded",
        "category": "config",
        "severity": "fatal",
        "cause": "config.plist is not a valid plist.",
        "fix": "Rebuild config.plist, or open it in ProperTree and fix the reported syntax error.",
        "doc": TROUBLESHOOTING
    },
    {
        "id": "memory_pool",
        "regex": r"OCABC: Memory pool allocation failure",
        "stage": "drivers",
        "category": "firmware",
        "severity": "fatal",
        "cause": "The firmware memory layout does not suit OpenCore (Above 4G Decoding or CSM).",
        "fix": "Enable Above 4G Decoding, disable CSM and update the BIOS; some laptops need CSM on.",
        "doc": BIOS_SETTINGS
    },
    {
        "id": "buffer_too_small",
        "regex": r"Buffer Too Small",
        "stage": "any",
        "category": "firmware",
        "severity": "warning",
        "cause": "Often means Above 4G Decoding is off.",
        "fix": "Enable Above 4G Decoding in the BIOS.",
        "doc": BIOS_SETTINGS
    },
    {
        "id": "image_access_denied",
        "regex": r"Failed to open OpenCore image - Access Denied",
        "stage": "opencore_started",
        "category": "firmware",
        "severity": "fatal",
        "cause": "The firmware security policy blocks OpenCore.efi (seen on Surface devices).",
        "fix": "Set UEFI -> Quirks -> DisableSecurityPolicy to true.",
        "doc": TROUBLESHOOTING
    },
    {
        "id": "no_boot_entries",
        "regex": r"OCB: System has no boot entries",
        "stage": "picker_shown",
        "category": "picker",
        "severity": "fatal",
        "cause": "OpenCore found nothing to boot: ScanPolicy, a missing HfsPlus driver, SATA mode or APFS settings.",
        "fix": "ScanPolicy 0, HfsPlus.efi in Drivers, SATA in AHCI mode, UEFI -> APFS EnableJumpstart true.",
        "doc": TROUBLESHOOTING
    },
    {
        "id": "scan_failure",
        "regex": r"OcScanForBootEntries failure - Not Found",
        "stage": "picker_shown",
        "category": "picker",
        "severity": "fatal",
        "cause": "OpenCore found nothing to boot: ScanPolicy, a missing HfsPlus driver, SATA mode or APFS settings.",
        "fix": "ScanPolicy 0, HfsPlus.efi in Drivers, SATA in AHCI mode, UEFI -> APFS EnableJumpstart true.",
        "doc": TROUBLESHOOTING
    },
    {
        "id": "no_default_option",
        "regex": r"failed to match a default boot option",
        "stage": "picker_shown",
        "category": "picker",
        "severity": "warning",
        "cause": "The default boot entry is not visible: ScanPolicy, HfsPlus driver or SATA mode.",
        "fix": "ScanPolicy 0, HfsPlus.efi in Drivers, SATA in AHCI mode.",
        "doc": TROUBLESHOOTING
    },
    {
        "id": "loadimage_security_violation",
        "regex": r"OCB: LoadImage failed - Security Violation",
        "stage": "entry_chosen",
        "category": "security",
        "severity": "fatal",
        "cause": "Apple Secure Boot manifests are missing from the Preboot volume while SecureBootModel is set.",
        "fix": "Set Misc -> Security -> SecureBootModel to Disabled, or reinstall macOS, or copy /usr/standalone/i386 into Preboot System/Library/CoreServices.",
        "doc": TROUBLESHOOTING
    },
    {
        "id": "secure_boot_prohibits",
        "regex": r"OCB: Apple Secure Boot prohibits this boot entry",
        "stage": "entry_chosen",
        "category": "security",
        "severity": "fatal",
        "cause": "Apple Secure Boot rejected the chosen entry (missing or old manifests).",
        "fix": "Set Misc -> Security -> SecureBootModel to Disabled for this install.",
        "doc": TROUBLESHOOTING
    },
    {
        "id": "loadimage_failed",
        "regex": r"OCB: LoadImage failed - (?!Security Violation)(.+)",
        "stage": "entry_chosen",
        "category": "booter",
        "severity": "fatal",
        "cause": "The chosen entry could not be loaded ({0}).",
        "fix": "Check that the installer or macOS volume is intact; recreate the USB installer if it is the recovery entry.",
        "doc": TROUBLESHOOTING
    },
    {
        "id": "startimage_already_started",
        "regex": r"OCB: StartImage failed - Already started",
        "stage": "entry_chosen",
        "category": "booter",
        "severity": "fatal",
        "cause": "Windows Boot Manager on the same drive interferes with the boot.",
        "fix": "Install macOS on a separate drive or use BlessOverride.",
        "doc": "docs/reference/post-install.md"
    },
    {
        "id": "exitbs_failed",
        "regex": r"OCABC: ExitBootServices failed twice",
        "stage": "booter_handoff",
        "category": "booter",
        "severity": "fatal",
        "cause": "The firmware refused to exit boot services; the booter quirks do not suit this firmware.",
        "fix": "Review the Booter quirks (DevirtualiseMmio, SetupVirtualMap, EnableWriteUnprotector, RebuildAppleMemoryMap).",
        "doc": BOOTER_LIST
    },
    {
        "id": "exitbs_start",
        "regex": r"EB\|#LOG:EXITBS:START",
        "stage": "booter_handoff",
        "category": "booter",
        "severity": "info",
        "cause": "boot.efi is exiting boot services to start the kernel. A boot that stops here usually needs other Booter quirks.",
        "fix": "If this is the last line, review the Booter quirks for this firmware.",
        "doc": BOOTER_LIST
    },
    {
        "id": "prelinked_ofs",
        "regex": r"EB\|LD:OFS\] Err\(0xE\)",
        "stage": "booter_handoff",
        "category": "booter",
        "severity": "fatal",
        "cause": "The Preboot volume is out of date.",
        "fix": "Enable UEFI -> APFS JumpstartHotplug, boot Recovery and run diskutil apfs updatePreboot on the Preboot volume.",
        "doc": TROUBLESHOOTING
    },
    {
        "id": "runtime_area",
        "regex": r"Couldn't allocate runtime area",
        "stage": "booter_handoff",
        "category": "booter",
        "severity": "fatal",
        "cause": "Memory layout or KASLR slide problem.",
        "fix": "Apply the KASLR slide fix from the OpenCore guide (extras/kaslr-fix).",
        "doc": TROUBLESHOOTING
    },
    {
        "id": "max_cpus",
        "regex": r"max_cpus_from_firmware not yet initialized",
        "stage": "kernel_started",
        "category": "booter",
        "severity": "fatal",
        "cause": "The kernel could not read the CPU count from firmware memory.",
        "fix": "Enable Booter -> Quirks -> AvoidRuntimeDefrag.",
        "doc": BOOTER_LIST
    },
    {
        "id": "cfg_lock",
        "regex": r"OCCPU: EIST CFG Lock 1",
        "stage": "opencore_started",
        "category": "firmware",
        "severity": "warning",
        "cause": "MSR 0xE2 (CFG Lock) is locked by the firmware.",
        "fix": "Disable CFG Lock in the BIOS, or keep the AppleXcpmCfgLock / AppleCpuPmCfgLock quirks on.",
        "doc": BIOS_SETTINGS
    },
    {
        "id": "mat_support",
        "regex": r"OCABC: MAT support is (\d)",
        "stage": "drivers",
        "category": "booter",
        "severity": "info",
        "cause": "Memory Attributes Table support is {0}; it decides between EnableWriteUnprotector and RebuildAppleMemoryMap plus SyncRuntimePermissions.",
        "fix": "Only relevant if the boot stalls at EXITBS.",
        "doc": BOOTER_LIST
    },
    {
        "id": "kernel_patch_failed",
        "regex": r"OCAK: \[FAIL\] (.+)",
        "stage": "booter_handoff",
        "category": "kernel",
        "severity": "warning",
        "cause": "A kernel patch or quirk did not apply: {0}.",
        "fix": "Check the patch's MinKernel/MaxKernel range against this macOS version; update the patch source.",
        "doc": TROUBLESHOOTING
    },
    {
        "id": "root_device",
        "regex": r"Still waiting for root device|Waiting for [Rr]oot [Dd]evice",
        "stage": "kernel_started",
        "category": "kernel",
        "severity": "fatal",
        "cause": "macOS cannot reach the boot drive: USB port limit or ownership, or SATA mode.",
        "fix": "Map USB ports (option 6), ReleaseUsbOwnership true, XHCI hand-off in BIOS, try a USB 2.0 port, SATA in AHCI mode.",
        "doc": TROUBLESHOOTING
    },
    {
        "id": "usb_create_device",
        "regex": r"AppleUSBHostPort::createDevice: failed to create device",
        "stage": "kernel_started",
        "category": "kernel",
        "severity": "fatal",
        "cause": "XhciPortLimit does not work on macOS 11.3 and newer.",
        "fix": "Map USB ports (option 6) and turn XhciPortLimit off.",
        "doc": TROUBLESHOOTING
    },
    {
        "id": "gio_screen_lock",
        "regex": r"IOConsoleUsers: gIOScreenLock",
        "stage": "kernel_started",
        "category": "kernel",
        "severity": "fatal",
        "cause": "The GPU did not initialise.",
        "fix": "Check ig-platform-id/device-id, CSM off, igfxonln=1 on Coffee Lake; laptops need SSDT-PNLF.",
        "doc": TROUBLESHOOTING
    },
    {
        "id": "kext_summary",
        "regex": r"Cannot perform kext summary|Invalid frame pointer",
        "stage": "kernel_started",
        "category": "kernel",
        "severity": "fatal",
        "cause": "Kext order, a missing or extra executable, or duplicate kexts.",
        "fix": "Lilu first and plugins after it, plist-only kexts without executables, no duplicates.",
        "doc": TROUBLESHOOTING
    },
    {
        "id": "cpu_power_management",
        "regex": r"panic.*AppleIntelCPUPowerManagement",
        "stage": "kernel_started",
        "category": "kernel",
        "severity": "warning",
        "cause": "A panic here usually comes from NullCPUPowerManagement.",
        "fix": "Remove NullCPUPowerManagement and enable Kernel -> Emulate -> DummyPowerManagement.",
        "doc": TROUBLESHOOTING
    },
    {
        "id": "kextd_stall",
        "regex": r"kextd stall\[\d+\]: AppleACPICPU",
        "stage": "kernel_started",
        "category": "kernel",
        "severity": "fatal",
        "cause": "The SMC emulator is missing or broken.",
        "fix": "Lilu and VirtualSMC enabled with Lilu first; never VirtualSMC and FakeSMC together.",
        "doc": TROUBLESHOOTING
    },
    {
        "id": "cckprng",
        "regex": r"cckprng_int_gen: generator has already been sealed",
        "stage": "kernel_started",
        "category": "kernel",
        "severity": "fatal",
        "cause": "VirtualSMC is missing, or SSDT-CPUR is used on a board that is not B550/A520.",
        "fix": "Add VirtualSMC; use SSDT-CPUR only on B550/A520.",
        "doc": TROUBLESHOOTING
    },
    {
        "id": "kernel_panic",
        "regex": r"panic\(cpu \d+ caller",
        "stage": "kernel_started",
        "category": "kernel",
        "severity": "fatal",
        "cause": "macOS panicked; the backtrace names the kext.",
        "fix": "Look for the kext name in the panic lines and compare with the kernel panics in the troubleshooting table.",
        "doc": TROUBLESHOOTING
    },
    {
        "id": "fsb_frequency",
        "regex": r"OCCPU: Failed to get FSBFrequency",
        "stage": "opencore_started",
        "category": "noise",
        "severity": "info",
        "cause": "Normal on non-Apple firmware.",
        "fix": "Nothing to do.",
        "doc": TROUBLESHOOTING
    },
    {
        "id": "partition_info",
        "regex": r"OCPI: (?:Partition table not supported|Failed to retrieve disk info)",
        "stage": "picker_shown",
        "category": "noise",
        "severity": "info",
        "cause": "Normal for MBR and unpartitioned media.",
        "fix": "Nothing to do.",
        "doc": TROUBLESHOOTING
    },
    {
        "id": "bless_missing",
        "regex": r"OCBP: (?:Blessed (?:file|folder) is missing|Predefined .* is missing)",
        "stage": "picker_shown",
        "category": "noise",
        "severity": "info",
        "cause": "OpenCore checks every standard boot path; missing ones are normal.",
        "fix": "Nothing to do.",
        "doc": TROUBLESHOOTING
    },
    {
        "id": "hidden_auxiliary",
        "regex": r"OCB: Not adding hidden auxiliary entry",
        "stage": "picker_shown",
        "category": "noise",
        "severity": "info",
        "cause": "Tools and Reset NVRAM are hidden until Space is pressed in the picker.",
        "fix": "Nothing to do.",
        "doc": INSTALL_FLOW + " section 4"
    },
    {
        "id": "entry_visibility",
        "regex": r"OCB: Get visibility for boot entry .* - Not Found",
        "stage": "picker_shown",
        "category": "noise",
        "severity": "info",
        "cause": "The entry has no .contentVisibility file; normal.",
        "fix": "Nothing to do.",
        "doc": TROUBLESHOOTING
    },
    {
        "id": "hibernation_off",
        "regex": r"OC: Hibernation activation - Invalid Parameter",
        "stage": "opencore_started",
        "category": "noise",
        "severity": "info",
        "cause": "No hibernation image to wake from; normal.",
        "fix": "Nothing to do.",
        "doc": TROUBLESHOOTING
    }
]
