# Gaps: guide advice the app does not implement or surface

Method: each item was checked by reading the named file under `Scripts/` (or `OpCore-Simplify.py`) and searching all `*.py` files for the relevant keys (config keys, kext names, tool names). `Scripts/usb_writer.py` is being changed by another agent; it was searched but not studied. Line numbers refer to the tree on 2026-10-21.

Ranking is by effect on a first successful boot, then on post-install success. Pipeline stages: hardware scan, verdict, USB map, EFI build, ocvalidate, recovery download, USB write, BIOS checklist, first boot, post-install.

## Ranked list

### 1. BIOS checklist is thin and platform-blind

- Guide says: per-family Disable/Enable lists (`bios-settings.md`): Fast Boot, Secure Boot, Serial/Parallel, VT-d/IOMMU, CSM, Thunderbolt, SGX, Platform Trust, CFG Lock; Above 4G, XHCI hand-off, OS type, DVMT (32MB, 64MB or 256MB by family), SATA AHCI. AMD: Above 4G or `npci=0x3000`, IOMMU off.
- Checked: `OpCore-Simplify.py` `check_bios_requirements` (lines 343-361) emits only: enable UEFI/disable CSM if the firmware changed from Legacy, Secure Boot not disabled, and Above 4G plus "Disable Resizable BAR/Smart Access Memory" for Intel desktop chipsets `IntelChipsets[112:]`. `compatibility_checker.py` line 336 separately tells users to turn off Intel VMD. Nothing for AMD, laptops, CFG Lock, VT-d, DVMT, SATA mode, XHCI hand-off.
- Conflict: the guide keeps Resizable BAR allowed and sets `Booter -> Quirks -> ResizeAppleGpuBars` to 0 (the app already sets 0 or -1 at `config_prodigy.py:636` and `npci=0x2000` for HEDT at 515-516); telling users to switch ReBAR off is stricter than the guide.
- Pipeline: BIOS checklist.
- Idea: replace the hard-coded list with `Scripts/datasets/bios_settings.py`, picking the key from codename plus Motherboard platform; show Disable and Enable lists and the family notes; skip options the hardware report already proves correct (Secure Boot, Firmware Type, Resizable BAR).

### 2. No failure-diagnosis loop (DEBUG build, log reading, known-error mapping)

- Guide says: first response to any stall is a DEBUG build (swap `BOOTx64.efi`, `OpenCore.efi`, `OpenRuntime.efi`), `Misc -> Debug` `AppleDebug` YES, `ApplePanic` YES, `DisableWatchdog` YES, `Target` 67, `DisplayLevel` 2147483714, read `opencore-*.txt`; then match the last log line to a documented fix (`install-flow.md` section 7).
- Checked: `gathering_files.py` lines 92-95 download only the `release` OpenCorePkg build; `config_prodigy.py:679` forces `AppleDebug` and `ApplePanic` to False; `DEBUG` appears in `github.py` only to filter kext assets; no search hits for `Target` handling or any log parser.
- Pipeline: first boot (failure branch), after EFI build.
- Idea: "Build debug EFI" toggle that downloads the DEBUG package and sets the Debug keys, plus a Windows "analyse log" step that reads `opencore-*.txt` from the USB and maps known strings (`OCB: LoadImage failed`, `Buffer Too Small`, `OCABC: ...`, `max_cpus_from_firmware`) to the fixes in `install-flow.md`.

### 3. USB mapping advice conflicts with the guide

- Guide says: on macOS 11.3+ `XhciPortLimit` is broken (boot loops); map ports before installing macOS 12+; per-controller limit is 15 (26 ports on Z170+ chipsets); a map is used alone (no `USBInjectAll`, no `SSDT-UIAC`); `XhciUnsupported` only for the listed chipsets.
- Checked: `OpCore-Simplify.py:383` ("enable the XhciPortLimit patch" when more than 15 ports) contradicts the 11.3+ rule; `kext_maestro.py:142` always selects `UTBDefault`; `XHCI-unsupported` selection exists (`kext_maestro.py:425`); no USBToolBox port or per-controller count exists yet (roadmap item 4).
- Pipeline: USB map, EFI build.
- Idea: when the USBToolBox port lands, produce `UTBMap` before the build, cap each controller to 15 and drop the `XhciPortLimit` instruction; for macOS 12+ make mapping a required step before the recovery USB is written.

### 4. CFG Lock is only worked around

- Guide says: preferred fix is unlocking MSR 0xE2 in firmware; test with the DEBUG log (`OCCPU: EIST CFG Lock 1`) or `ControlMsrE2.efi`; quirks `AppleCpuPmCfgLock` / `AppleXcpmCfgLock` are the fallback; Lenovo may not be unlockable; unlock offsets are per BIOS version and are lost on BIOS reset.
- Checked: `config_prodigy.py:654-655` always sets one of the two quirks; no search hit for `ControlMsrE2`; no CFG Lock line in the BIOS checklist.
- Pipeline: BIOS checklist, EFI build (Tools), first boot.
- Idea: optionally copy `ControlMsrE2.efi` into `EFI/OC/Tools` and `Misc -> Tools`, show "boot this entry and read LOCKED/UNLOCKED" in the checklist, and link to the manual unlock procedure; keep the quirks on until the user confirms UNLOCKED.

### 5. Boot-entry persistence, internal-drive install and multiboot

- Guide says: after install move the EFI to the internal ESP; Windows/Linux may overwrite `EFI/BOOT/BOOTx64.efi`; set `Misc -> Boot -> LauncherOption` `Full` (`Short` on Insyde) with `RequestBootVarRouting`; for Windows on the same drive use `Hideself`; ESP should be 200MB (a 100MB Windows ESP gives "MediaKit reports not enough space"); the ESP must be the first partition for Startup Disk.
- Checked: no search hit for `LauncherOption`, `Hideself`, `AllowNvramReset`, `HibernateMode`, `RequestBootVarRouting`, `mountvol`, `MountEFI`; `config_prodigy.py` sets `BlessOverride` to an empty list; the other agent's `usb_writer.py` covers writing the USB.
- Pipeline: EFI build, post-install.
- Idea: set `LauncherOption` from the firmware vendor, add `AllowNvramReset`, and ship a post-install script that copies the EFI to the internal ESP; the Windows method is not in the sources, so it has to be designed separately (for example mounting the ESP from Windows before the first macOS boot).

### 6. ROM and serial generation ignore the iServices guidance

- Guide says: ROM = lowercase MAC without colons, of the real built-in NIC or made up with an Apple OUI; pick a generated serial that Apple's coverage page says it cannot check; `en0` must exist and be built-in; verify NVRAM works first.
- Checked: `smbios.py:51-53` (`generate_random_mac`) creates 6 random bytes with no OUI, `smbios.py:62-71` uses it as ROM; `config_prodigy.py:385-389` sets `built-in` on NICs (covered); no NVRAM self-test, no coverage check, no iServices checklist.
- Pipeline: EFI build (PlatformInfo), post-install.
- Idea: derive ROM from the scan's primary NIC MAC (or use an Apple OUI), and put the NVRAM test (`sudo nvram myvar="$(date)"`, reboot, `nvram myvar`), `en0` check and cache-clean list into the post-install kit.

### 7. Windows-side safety checks before changing BIOS or disks

- Guide says: disabling TPM loses BitLocker keys; macOS and Windows clocks disagree (fix Windows with the registry or BootCamp utilities); Windows must be UEFI/GPT; Windows ESP is 100MB where macOS expects 200MB; Disk Utility must erase the whole device (Show All Devices).
- Checked: no search hit for `BitLocker`, `manage-bde`, `RealTimeIsUniversal`; the BIOS checklist never mentions TPM.
- Pipeline: BIOS checklist, USB write, post-install.
- Idea: Windows-only preflight that detects BitLocker/Device Encryption, GPT vs MBR and ESP size, and warns before the BIOS step; post-install kit entry for the clock fix.

### 8. Tahoe-specific items only partly covered

- Guide says: no AppleHDA on macOS 26, `-ibtcompatbeta` for Intel Bluetooth, `AppleBCMWLANCompanion` for Broadcom Wi-Fi (needs VT-d), OTA updates need `revpatch=sbvmm` and `SecureBootModel` Disabled, WhateverGreen breaks AMD connector patching on 26.
- Checked: covered: AppleHDA note (`kext_maestro.py:159`), `revpatch=sbvmm` and `SecureBootModel` Disabled for Sonoma-and-later (`config_prodigy.py:684`, 716-741), Tahoe Broadcom kext selection (`kext_maestro.py:258`). Not found: `-ibtcompatbeta`, `AppleBCMWLANCompanion`, any WhateverGreen-on-AMD-Tahoe warning, VoodooHDA path.
- Pipeline: verdict, EFI build.
- Idea: add a Tahoe warnings block to the verdict screen and add `-ibtcompatbeta` when an Intel Bluetooth device is present and the target is macOS 26.

### 9. Vendor and chipset quirks from the guide not applied

- Guide says: Surface needs `UEFI -> Quirks -> DisableSecurityPolicy`; B550/A520 need `SSDT-CPUR.aml` (not on X570 or older, else `cckprng_int_gen` panic); Insyde laptops use `LauncherOption` `Short`; ThinkPad NVRAM reset can brick (update BIOS instead); Gigabyte/ASRock AMD may need `npci` instead of Above 4G; 3990X needs hyper-threading off (64-thread limit); `ExitBootServicesDelay` for FileVault on Aptio IV.
- Checked: no search hit for `DisableSecurityPolicy`, `CPUR`, `ExitBootServicesDelay`, 64-thread or `cpus=` handling; HP (`UnblockFsConnect`, `LapicKernelPanic`) and Dell (`CustomSMBIOSGuid`) are covered in `config_prodigy.py` lines 658-707.
- Pipeline: EFI build, BIOS checklist.
- Idea: add a vendor table keyed from the Motherboard name and chipset, applied in the build and echoed in the checklist.

### 10. NVRAM failures: no fallback beyond SSDT-PMC

- Guide says: "Stuck at 2 minutes remaining" and Big Sur stage-2 loops come from broken NVRAM; fixes are SSDT-PMC (300-series), or `LegacyEnable`/`LegacyOverwrite`/`WriteFlash`, or full emulation (`OpenVariableRuntimeDxe.efi` before `OpenRuntime.efi` with `LoadEarly`, `DisableVariableWrite` NO, `ExposeSensitiveData` >= 1, LogoutHook) mainly for X99/X299.
- Checked: SSDT-PMC exists in `acpi_guru.py`; no search hit for `OpenVariableRuntimeDxe`, `LogoutHook`, `LegacyEnable`.
- Pipeline: EFI build for HEDT, first boot.
- Idea: for X99/X299 (the app already has `is_intel_hedt_cpu`) offer an "emulated NVRAM" build option and add the logout-hook install to the post-install kit.

### 11. Post-install kit content

The guide's post-install steps with no counterpart in the repo: `pmset` sleep preparation (`autopoweroff`, `powernap`, `standby`, `proximitywake`, `tcpkeepalive` set to 0), removing the `alcid` boot-arg once `layout-id` is in `DeviceProperties` (the app writes both: `config_prodigy.py:356` and 572), power-management check (`X86PlatformPlugin` attached), SIP reduction after install, RELEASE swap and `Target` 3 for quieter boots, UIScale/resolution settings, OpenCore update procedure (spare USB, `ocvalidate` of the same release), RTC fixes (`DisableRtcChecksum` only for ASUS/HP at `config_prodigy.py:660`; `RTCMemoryFixup` exists in `kext_data.py` but is never selected by `kext_maestro.py`).
Pipeline: post-install. Idea: a generated checklist (`.md` or `.command`) on the USB keyed by the choices made in the build.

### 12. Compatibility surfaces from the hardware limits page

Partly covered: SSE4.2/AVX2 (`compatibility_checker.py:72-86`, 136-159), unsupported NVMe (`compatibility_checker.py:341`), fingerprint (line 249), Intel VMD (333-336). Not found: 64-thread kernel limit (24 threads on OS X 10.10 and older), laptop features the guide calls unsupported (Intel SST microphone, I2C Windows Hello, combo headphone jack input, Thunderbolt hot-plug), Intel RST/RAID SATA mode (only VMD is checked), Intel 600p, Optane acceleration. Pipeline: verdict. Idea: extend the existing per-device compatibility checks.

### 13. SIP value is not among the guide's documented values

- Checked: `config_prodigy.py` `csr_active_config` returns `030A0000` for Big Sur and newer, `FF070000` for Mojave/Catalina, `FF030000` for High Sierra. The guide lists `00000000`, `03000000`, `FF030000`, `FF070000`, `FF0F0000` and warns that unauthenticated-root and Apple-internal flags can break OS updates. The sources do not decode `0x0A03`, so whether it is wise cannot be judged from them (unverified). Flag for review against the intended OCLP/OTA behaviour.

## Covered already (no action)

- ocvalidate after build (`validator.py`), UEFI/Secure Boot check in the BIOS list, `ResizeAppleGpuBars` handling, NIC `built-in` property, USBX/PLUG/AWAC/PMC/RHUB/HPET SSDT generation (`acpi_guru.py`), HfsPlus vs HfsPlusLegacy driver choice (`config_prodigy.py:590`), CFG-lock quirks, `DisableIoMapper`, `ReleaseUsbOwnership`, `UnblockFsConnect` for HP, `CustomSMBIOSGuid`, Cpuid1Data spoof, `DummyPowerManagement`, `alcid`/`layout-id` selection, SecureBootModel and revpatch for OTA, recovery download with board table, ScanPolicy 0.
