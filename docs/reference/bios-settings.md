# BIOS/UEFI settings for macOS (OpenCore install guide)

Distilled from the Dortania OpenCore Install Guide. Machine-readable copy: `Scripts/datasets/bios_settings.py` (`data`, keyed by the family names used below).

General rules stated by the guide:

- Most options may not exist in a given firmware. Match as closely as possible and skip what is missing; laptops in particular often lack many of them.
- Run the latest BIOS. The one documented exception (MSI 500-series AMD boards, struck through in the guide) is marked fixed by newer AMD vanilla patches.
- Sources are listed per section; "unverified" marks statements the sources do not make.

Sources: `_ref/dortania-install-guide/prerequisites.md`, `_ref/dortania-install-guide/macos-limits.md`, `_ref/dortania-install-guide/config.plist/README.md`.

## 1. Platform families

The install guide has one config page per family; each ends with an "Intel BIOS settings" or "AMD BIOS Settings" section. The app's `cpu_data.IntelCPUGenerations` names are listed so a codename can be mapped to a family. Platform (desktop/laptop) comes from the hardware report's Motherboard platform.

| Key in `bios_settings.data` | Guide page(s) | App codenames |
| :--- | :--- | :--- |
| `intel_desktop_penryn` | config.plist/penryn.md | Yonah, Conroe, Penryn (not in app list) |
| `intel_desktop_lynnfield_clarkdale` | config.plist/clarkdale.md | Lynnfield, Clarkdale |
| `intel_desktop_sandy_ivy` | config.plist/sandy-bridge.md, ivy-bridge.md | Sandy Bridge, Ivy Bridge |
| `intel_desktop_haswell` | config.plist/haswell.md | Haswell |
| `intel_desktop_skylake_cometlake` | config.plist/skylake.md, kaby-lake.md, coffee-lake.md, comet-lake.md | Skylake, Kaby Lake, Coffee Lake-S, Comet Lake-S, Rocket Lake-S (assumed) |
| `intel_laptop_arrandale_sandy_ivy` | config-laptop.plist/arrandale.md, sandy-bridge.md, ivy-bridge.md | Arrandale, Clarksfield, Sandy Bridge, Ivy Bridge |
| `intel_laptop_haswell_broadwell` | config-laptop.plist/haswell.md, broadwell.md | Haswell-ULT/ULX/H, Broadwell-U/Y/H |
| `intel_laptop_skylake_cometlake` | config-laptop.plist/skylake.md, kaby-lake.md, coffee-lake.md, coffee-lake-plus.md | Skylake, Kaby Lake(-H), Amber Lake-Y, Coffee Lake-H/U, Whiskey Lake-U, Comet Lake-H/U |
| `intel_laptop_icelake` | config-laptop.plist/icelake.md | Ice Lake-U |
| `intel_hedt_nehalem_westmere` | config-HEDT/nehalem.md | Bloomfield, Gulftown, Gainestown, Westmere-EP/EX, Beckton, Jasper Forest |
| `intel_hedt_ivy_bridge_e` | config-HEDT/ivy-bridge-e.md | Sandy Bridge-E, Ivy Bridge-E |
| `intel_hedt_haswell_broadwell_e` | config-HEDT/haswell-e.md, broadwell-e.md | Haswell-E/EP/EX, Broadwell-E |
| `intel_hedt_skylake_x_cascade_lake` | config-HEDT/skylake-x.md | Skylake-X, Cascade Lake-X/P/W |
| `amd_bulldozer_jaguar` | AMD/fx.md | not in app list |
| `amd_zen` | AMD/zen.md | all names in `AMDCPUGenerations` (assumed for Zen 4+) |
| `common` | all | options shared by every family |

Not covered by the guide's BIOS pages: Intel newer than Comet Lake (desktop) or Ice Lake (laptop) (Tiger Lake, Alder Lake and later), Mobile Atom/Celeron/Pentium, AMD laptops. The sources are silent on BIOS options for these; treat any lookup as "closest family, unverified".

## 2. Baseline lists

### Common to every family

| Disable | Enable |
| :--- | :--- |
| Fast Boot | Above 4G Decoding |
| Secure Boot | EHCI/XHCI Hand-off |
| Serial/COM Port | OS type: Windows 8.1/10 UEFI Mode (some boards need "Other OS") |
| Parallel Port | SATA Mode: AHCI |
| Compatibility Support Module (CSM) | |

### Intel (all desktop, laptop and HEDT pages)

| Disable | Enable |
| :--- | :--- |
| Fast Boot | VT-x |
| Secure Boot | Above 4G Decoding |
| Serial/COM Port | Hyper-Threading |
| Parallel Port | Execute Disable Bit |
| VT-d (may stay on if `Kernel -> Quirks -> DisableIoMapper` is YES) | EHCI/XHCI Hand-off |
| Compatibility Support Module (CSM) | OS type: Windows 8.1/10 UEFI Mode |
| Thunderbolt (for the initial install) | DVMT Pre-Allocated (iGPU Memory): see table below |
| Intel SGX | SATA Mode: AHCI |
| Intel Platform Trust | |
| CFG Lock (MSR 0xE2 write protection) | |

Sources: `_ref/dortania-install-guide/config.plist/comet-lake.md` ("Intel BIOS settings"), same section in every other config page listed in section 1.

### AMD (Zen and Bulldozer/Jaguar)

| Disable | Enable |
| :--- | :--- |
| Fast Boot | Above 4G Decoding (must be on; if missing add `npci=0x3000` to boot-args; never both) |
| Secure Boot | EHCI/XHCI Hand-off |
| Serial/COM Port | OS type: Windows 8.1/10 UEFI Mode |
| Parallel Port | SATA Mode: AHCI |
| Compatibility Support Module (CSM) | |
| IOMMU | |

No VT-x, Hyper-Threading, XD, DVMT, CFG Lock, SGX or Platform Trust entries exist for AMD (the guide: AMD has no CFG Lock). Zen only: 3990X users must disable hyper-threading (macOS supports at most 64 threads; the 3990X has 128); Gigabyte/Aorus and ASRock boards may break drivers (for example Ethernet) or other OSes when Above 4G is on, in which case disable it and use `npci`; on X570 and newer, Resizable BAR Support may appear once Above 4G is on and `Booter -> Quirks -> ResizeAppleGpuBars` must then be `0`.

Sources: `_ref/dortania-install-guide/AMD/zen.md`, `_ref/dortania-install-guide/AMD/fx.md` ("AMD BIOS Settings"), `_ref/dortania-install-guide/troubleshooting/extended/kernel-issues.md` (npci).

## 3. Differences by family

Deltas against the Intel baseline. "CFG fallback" is the kernel quirk to enable when the option cannot be turned off.

| Family | DVMT | CFG Lock entry / fallback quirk | Other differences |
| :--- | :--- | :--- | :--- |
| Intel desktop Penryn | 32MB or higher | No CFG Lock or Thunderbolt entry (Penryn need not unlock MSR 0xE2) | none |
| Intel desktop Lynnfield/Clarkdale | 32MB or higher | `AppleCpuPmCfgLock` | none |
| Intel desktop Sandy/Ivy Bridge | 32MB or higher | `AppleCpuPmCfgLock` | none |
| Intel desktop Haswell | 64MB or higher | `AppleXcpmCfgLock` (+ `AppleCpuPmCfgLock` on OS X 10.10 and older) | none |
| Intel desktop Skylake/Kaby/Coffee/Comet Lake | 64MB or higher | `AppleXcpmCfgLock` | Comet Lake page adds: Above 4G may expose Resizable BAR on Z490+; keep `ResizeAppleGpuBars` = 0 |
| Intel laptop Arrandale/Sandy/Ivy | 32MB or higher | `AppleCpuPmCfgLock` | CSM may be called Legacy Support or Hybrid Boot; Thunderbolt only "if available"; VT-x = Virtualization Support |
| Intel laptop Haswell/Broadwell | 64MB or higher | `AppleXcpmCfgLock` (+ `AppleCpuPmCfgLock` for 10.10 and older) | none |
| Intel laptop Skylake to Comet Lake | 64MB or higher | `AppleXcpmCfgLock` | none |
| Intel laptop Ice Lake | 256MB (exact) | `AppleXcpmCfgLock` | none |
| Intel HEDT Nehalem/Westmere | none listed | `AppleCpuPmCfgLock` | none |
| Intel HEDT Sandy/Ivy-E | none listed | `AppleXcpmCfgLock` (+ `AppleCpuPmCfgLock` for 10.10 and older) | none |
| Intel HEDT Haswell-E/Broadwell-E | none listed | `AppleXcpmCfgLock` (+ `AppleCpuPmCfgLock` for 10.10 and older) | If Above 4G misbehaves, "MMIOH Base" must be 12 TB or lower |
| Intel HEDT Skylake-X/Cascade Lake | none listed | `AppleXcpmCfgLock` | "MMIOH Base" 12 TB or lower; X299 needs Above 4G or USB breaks |

Sources: the BIOS sections of the config pages in section 1; `_ref/dortania-install-guide/troubleshooting/extended/kernel-issues.md` ("Stuck on `[EB|#LOG:EXITBS:START]`", "Kernel Patch Issues"); `_ref/dortania-post-install/misc/msr-lock.md`.

Quirk rule from the kernel-issues page: Haswell and newer only need `AppleXcpmCfgLock`; Ivy Bridge and older only need `AppleCpuPmCfgLock`; Broadwell and older also need `AppleCpuPmCfgLock` on 10.10 and older.

## 4. Vendor-specific notes

None of these are BIOS toggles unless stated; they are vendor behaviours the guide ties to firmware.

| Vendor / firmware | Note | Source |
| :--- | :--- | :--- |
| ASUS | UEFITool can open ASUS, MSI and ASRock firmware directly (needed for the CFG Lock unlock). Newer ASUS BIOS (v3006+) will not boot with `SetupVirtualMap` on (Skylake-X page). Comet Lake: ASUS, Gigabyte and ASRock boards will not boot with `SetupVirtualMap` on. Z97 and HEDT: Big Sur stage-2 install loops without working native NVRAM (Z97 mainly). SSDT-RHUB is needed on ASUS and possibly MSI, not on Gigabyte/ASRock. Skylake-X: ASUS and EVGA firmware do not write TSC to all cores (TSCAdjustReset). | config-HEDT/skylake-x.md, config.plist/comet-lake.md, extras/big-sur/README.md, ktext.md |
| MSI | MSI Navi (5700XT) installer needed the `ATY,rom` / `-wegnoegpu` patch before Big Sur; no longer required on Big Sur and newer. 500-series AMD board warning is struck through; fixed in current AMD vanilla patches. UEFITool can open MSI firmware. | troubleshooting, macos-limits.md |
| Gigabyte / Aorus | Some firmware still requires `SetupVirtualMap` (early kernel panic otherwise). AMD Zen: Above 4G Decoding may break Ethernet and other OSes; use `npci`. Comet Lake I225-V default PciRoot is `PciRoot(0x0)/Pci(0x1C,0x1)/Pci(0x0,0x0)` for ASUS and Gigabyte. | config pages, AMD/zen.md, kernel-issues.md |
| ASRock | Same Above 4G caveat as Gigabyte on AMD. Intel ASRock boards need XHCI-unsupported (B460/Z490+ do not). X399 USB controller is named PTCP. | AMD/zen.md, ktext.md, usb/manual |
| Dell | Needs `CustomSMBIOSGuid` YES and `UpdateSMBIOSMode` Custom (also VAIO). Some Dell laptops need the old quirk set (EnableWriteUnprotector) even with MAT support (Inspiron 5370 example). Dell firmware cannot be opened directly by UEFITool; see dreamwhite's extraction guide. Dell breakless PS2 keys have a dedicated fix. | kernel-issues.md, userspace-issues.md, post-issues.md, msr-lock.md |
| HP | `UnblockFsConnect` YES when no drives are listed; `LapicKernelPanic` for HP systems; RTC disabled with no way to re-enable on HP 250 G6 and HP 15-DA0014dx (needs a fake RTC SSDT); random key spam on Skylake+ HP laptops after lid wake (SSDT-HP-FixLidSleep). | config pages, kernel-issues.md, sleep.md |
| Lenovo / ThinkPad | CFG Lock variable may be set but not unlockable without physically modifying the BIOS (RU tool is an alternative route). ThinkPads can be "semi-bricked" after a NVRAM reset in OpenCore; the guide recommends resetting NVRAM by updating the BIOS instead. | msr-lock.md, userspace-issues.md |
| Microsoft Surface | Firmware blocks OpenCore even with Secure Boot off ("Failed to open OpenCore image - Access Denied"): enable `UEFI -> Quirks -> DisableSecurityPolicy`. Surface battery needs device-specific kexts. | opencore-issues.md, battery.md |
| Insyde | `Misc -> Boot -> LauncherOption` = `Short` (commonly laptops); `Booter -> ProtectSecureBoot` YES to fix secure boot keys when Vault is used. | multiboot/bootstrap.md, security/vault.md |
| Aptio IV (Broadwell and older) | `UEFI -> Quirks -> ExitBootServicesDelay` 3000-5000 if "Still waiting for root device" with FileVault; `HashServices` YES for Broadwell and older. | security/filevault.md |
| Intel NUC | Treated as laptop hardware: follow the Intel Laptop pages. | config.plist/README.md |

Sources: `_ref/dortania-install-guide/{config-HEDT/skylake-x.md,config.plist/comet-lake.md,extras/big-sur/README.md,ktext.md,macos-limits.md,troubleshooting/extended/*.md}`, `_ref/dortania-post-install/{misc/msr-lock.md,multiboot/bootstrap.md,universal/security/filevault.md,universal/security/vault.md,universal/sleep.md,laptop-specific/battery.md}`.

## 5. Option-by-option gotchas

### CFG Lock (MSR 0xE2)

- Intel only. AMD has none; Penryn does not need it unlocked.
- macOS (XNU and AppleIntelPowerManagement) wants to write MSR 0xE2. With the lock on the hack does not boot unless the patch quirks are enabled.
- Preferred fix is unlocking in firmware (no patching, more stable across OS updates). Fallback: `Kernel -> Quirks -> AppleCpuPmCfgLock` and/or `AppleXcpmCfgLock` (which one depends on the family, see section 3).
- Check method 1: DEBUG OpenCore with `Misc -> Debug -> Target` = 67; search the log for `OCCPU: EIST CFG Lock` (1 = locked, 0 = unlocked).
- Check method 2: add `ControlMsrE2.efi` (from OpenCorePkg) to `EFI/OC/Tools` and `config.plist`, boot it from the picker. Output "This firmware has LOCKED MSR 0xE2 register!" or "UNLOCKED".
- If unlocked, set both quirks to NO. If locked and the BIOS hides the option: find `CFG Lock` in the firmware with UEFITool, export the Setup section, run Universal-IFR-Extractor, read the VarStore name and VarOffset, then in the modified GRUB shell run `setup_var_cv <VarStoreName> <offset> 0x01 0x00`. Offsets are unique per board and firmware version; never reuse an offset without checking.
- A BIOS reset restores the lock; write down the offset and BIOS version.
- Lenovo may be impossible without hardware modification.

Sources: `_ref/dortania-post-install/misc/msr-lock.md`, `_ref/dortania-install-guide/troubleshooting/extended/kernel-issues.md`.

### Above 4G Decoding and Resizable BAR

- Above 4G Decoding must be on (stalls: "Buffer Too Small", "OCABC: Memory pool allocation failure - Not Found", PCI allocation stalls near `apfs_module_start`/`Waiting for Root device`).
- If the BIOS has no such option: boot-arg `npci=0x2000` or `npci=0x3000` (try one at a time). Never both the option and `npci`.
- 2020+ BIOS (Z490, X570 and newer): enabling Above 4G may expose Resizable BAR Support. The guide's instruction is to keep `Booter -> Quirks -> ResizeAppleGpuBars` at `0` while it is enabled. It does not tell the user to turn Resizable BAR off. (The app's pre-boot checklist currently says to disable Resizable BAR/Smart Access Memory; see gaps.md.)
- X299 needs Above 4G or USB breaks; X99/X299 (for example GA-X299-UD4) may need both the option and `npci`, a contradiction with the rule above that the sources leave unresolved.

Sources: `_ref/dortania-install-guide/troubleshooting/extended/kernel-issues.md`, `config.plist/comet-lake.md`, `AMD/zen.md`.

### Secure Boot, CSM, OS type

- Disable Secure Boot. CSM must be off in most cases (gIO errors, stalls). Setting "OS type: Windows 8.1/10 UEFI Mode" (sometimes called WHQL mode) can substitute on some boards; some boards want "Other OS".
- Laptop exception: scrambled screen in the installer means CSM (Boot legacy ROMs / legacy support) must be on; "Stuck on IOConsoleUsers" notes say CSM may need to be on for laptops.
- Surface and some firmwares keep blocking OpenCore with Secure Boot off (DisableSecurityPolicy, see section 4).
- Do not confuse with OpenCore `SecureBootModel` (Apple Secure Boot); that is a separate setting in config.plist (post-install.md).

Sources: `_ref/dortania-install-guide/troubleshooting/extended/{kernel-issues,userspace-issues,opencore-issues}.md`.

### VT-d / IOMMU

- Intel: disable VT-d. If it cannot be disabled (or is needed for another OS), set `Kernel -> Quirks -> DisableIoMapper` YES, which the guide prefers over `dart=0` because SIP can stay on. `DisableIoMapperMapping` is needed only if network/Thunderbolt problems appear with VT-d on and more than 16GB RAM; it requires a patched DMAR table.
- AMD: disable IOMMU.
- Exception: `AppleBCMWLANCompanion` (Tahoe Broadwell Wi-Fi workaround) requires VT-d on, so AMD cannot use it (tahoe.md).

Sources: `_ref/dortania-install-guide/config.plist/comet-lake.md`, `extras/tahoe.md`.

### Fast Boot, Serial/COM port, Parallel port, Intel SGX, Intel Platform Trust

- All listed under Disable. The guide gives no per-option rationale beyond the list; Serial is only mentioned elsewhere as the channel for kernel debugging (so it matters if the user will use serial logging).
- Intel Platform Trust is Intel's firmware TPM (PTT); the sleep page separately says to disable "Trusted Platform Module" and warns that BitLocker keys are lost if TPM is disabled.

Sources: `_ref/dortania-install-guide/config.plist/comet-lake.md`, `_ref/dortania-post-install/universal/sleep.md`, `troubleshooting/kernel-debugging.md`.

### Thunderbolt

- Disable for the initial install; Thunderbolt can cause issues if not set up correctly.
- Post-install: Thunderbolt 3/USB-C combined ports are unreliable; keeping the controller powered gives hot-plug at the cost of panics or USB-C breaking after sleep. Disabling Thunderbolt in the BIOS resolves it and is one of two paths for sleep (the other is patching).

Sources: `_ref/dortania-install-guide/macos-limits.md`, `_ref/dortania-post-install/universal/sleep.md`.

### Legacy USB, XHCI/EHCI hand-off

- Enable EHCI/XHCI Hand-off. If macOS does not receive USB ownership ("Waiting for Root Device", stop sign), the BIOS option helps, and `UEFI -> Quirks -> ReleaseUsbOwnership` YES is the config equivalent. Try a USB 2.0 port instead of 3.x if the installer fails.
- The guide has no "Legacy USB Support" toggle recommendation; it is silent on it.

Sources: `_ref/dortania-install-guide/troubleshooting/extended/kernel-issues.md`.

### DVMT (laptops and iGPU desktops)

- Set DVMT Pre-Allocated (iGPU Memory) to the value in section 3. The post-install VRAM page covers the case where the BIOS cannot raise DVMT above 32MB: lower the framebuffer's `framebuffer-stolenmem` and `framebuffer-fbmem` values so the total stays under the 32MB pre-allocation.

Sources: BIOS sections in config pages; `_ref/dortania-post-install/gpu-patching/intel-patching/` for the patching route.

### SATA, NVMe, RAID

- AHCI only. RAID/IDE is unsupported and Intel RST volumes are invisible to macOS. NVMe drives must be set to NVMe mode (a BIOS bug lets NVMe be set as SATA). Disable SATA hot-plug (AMD stalls) and note Disk Utility failures can come from SATA hot-plug.
- Problem SSDs: Samsung PM981/PM991, Micron 2200S (need NVMeFix, may still fail), Samsung 970 EVO Plus before its firmware fix, Intel 600p. Optane acceleration setups are unsupported; Optane H10/H20 work if the Optane part is disabled.

Sources: `_ref/dortania-install-guide/macos-limits.md`, `troubleshooting/extended/kernel-issues.md`, `userspace-issues.md`.

### Windows 11 and TPM relevance

- The sources never discuss Windows 11 on the same machine. The only facts: (1) disabling Intel Platform Trust / TPM is in the Disable list and in the sleep checklist; (2) disabling TPM loses BitLocker keys; (3) OCLP's Windows page says Windows 11 needs the TPM 2.0 requirement bypassed to install on unsupported (Mac) machines (`_ref/oclp/docs/WINDOWS.md`, Windows 11 install box).
- Anything beyond that, for example whether an existing Windows 11 install keeps working with TPM off, is not covered (unverified). A safe checklist step is to detect BitLocker/Device Encryption on Windows before asking the user to touch TPM settings.

Sources: `_ref/dortania-post-install/universal/sleep.md`, `_ref/oclp/docs/WINDOWS.md`.

### Sleep-related BIOS items

- Disable: Wake on LAN, Trusted Platform Module, Wake on USB (some boards need it on to wake; most get random wake-ups with it on).
- Enable: Wake on Bluetooth only if a Bluetooth keyboard wakes the machine.
- Disable unused audio devices in the BIOS if they cause sleep issues.
- Physical limits from the same page: avoid CPU, RAM and factory GPU overclocks (AVX overclocks break iGPUs).

Sources: `_ref/dortania-post-install/universal/sleep.md`.

### Items the sources do not give

- A rule for "Intel VMD" (the app already warns about it in `compatibility_checker.py`; the guide's sources do not mention VMD).
- Per-vendor menu paths (where the options live in AMI, Insyde or Phoenix setup screens).
- BIOS guidance for Intel 11th gen and newer, or for AMD Zen 4 and later.
