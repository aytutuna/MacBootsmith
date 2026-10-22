# MacBootsmith

MacBootsmith is a Windows tool that takes a PC from hardware scan to a bootable OpenCore USB installer for macOS. It is a fork of OpCore-Simplify with the stages that project leaves to the user (validation, recovery download, USB creation, BIOS guidance) added on top.

macOS 26 Tahoe is the last macOS release for Intel hardware, so the supported range is macOS High Sierra through Tahoe.

## Status

Early development. Every push is tested in CI: unit tests, a headless EFI build against hardware report fixtures, and a QEMU boot of the generated EFI to the OpenCore picker. The maintainers have not yet verified a full install on real hardware, and the USB writer in particular has not been run against a real stick. Expect rough edges and read the prompts carefully.

CI runs: https://github.com/aytutuna/MacBootsmith/actions

## What it does

1. Hardware scan with Hardware Sniffer, producing a hardware report.
2. Compatibility verdict: which macOS versions each device supports, and which need OpenCore Legacy Patcher.
3. EFI build using the OpCore-Simplify engine (ACPI patches, kexts, SMBIOS, config.plist).
4. Config validation of the built EFI with ocvalidate.
5. macOS recovery download from Apple's servers using macrecovery.
6. USB installer creation with diskpart: FAT32 partition, EFI and recovery copied and verified with SHA-256. Only USB-bus disks are offered, and you must confirm the erase.
7. BIOS checklist for the detected platform: the firmware settings to disable and enable before booting the installer.
8. USB port mapping on the target machine: every controller and root-hub port is listed through Windows' USB hub interface, you plug a device into each port you want, and the build turns the selection into a UTBMap kext in place of the placeholder map.
9. Post-install kit: a checklist for the installed system made from the build's choices (EFI move, root patches, audio layouts, Broadcom firmware, USB checks, Apple Account prerequisites, sleep, updates), a macOS helper script, the generated SMBIOS values and optionally the tools (Hackintool, ProperTree, MountEFI), copied to the USB drive with the installer.
10. Graphical interface: a step-by-step window over the same stages (see below). The terminal menu remains.

Open work is tracked in `docs/reference/gaps.md`.

## What it does not do

- Install macOS for you. You still boot the USB, partition the target disk and run the installer.
- Bypass hardware limits. Common blockers: Intel 11th generation and newer integrated graphics, modern NVIDIA GPUs, AMD RX 7000 series and newer, and most Intel laptop Wi-Fi cards without extra work (Broadcom or a supported replacement is the usual answer).
- Fix Apple account services (iMessage, FaceTime, iCloud) beyond generating the SMBIOS values they need.
- Make running macOS on non-Apple hardware licence-compliant. That is your responsibility (see Legal).

## Requirements

- Windows 10 or 11.
- Python 3.8 or newer. The `.bat` launcher offers to install it if missing.
- Administrator rights for the USB step.
- A USB drive of 4 GB or more. Its contents will be erased.
- An internet connection. OpenCore, kexts and the recovery image are downloaded at run time; nothing from Apple is bundled.

## How to use

### Graphical interface

Double-click `MacBootsmith-GUI.bat` (or run `pythonw MacBootsmith.pyw`). The window walks through the stages in order, with a step list on the left and a log at the bottom:

1. Welcome: requirements and the Windows preflight (BitLocker, partition style, EFI partition size).
2. Hardware: scan this PC with Hardware Sniffer or open an existing report, then read the compatibility verdict per device.
3. macOS version: the versions this hardware supports; the suggested one is preselected.
4. Options: audio method on macOS 26, Broadcom Wi-Fi method, WhateverGreen on the first boot, RELEASE or DEBUG build. Next configures the build (SMBIOS, ACPI patches, kexts).
5. USB mapping: list the ports, plug devices in and refresh, tick at most 15 ports per controller, set connector types, save the map.
6. Build: gathers OpenCore and the kexts, builds the EFI and shows the ocvalidate result.
7. Recovery: downloads and verifies the recovery image.
8. USB: lists USB disks only; you must select the disk and type ERASE before Write is enabled. A dry run changes nothing. Copying only the EFI to an existing drive is the second mode. Writing needs administrator rights; the page offers a restart as administrator.
9. Post-install: prepares the kit (full or docs-only) and shows the checklist and the BIOS Disable, Enable and Notes lists.
10. Finish: where every output is, and the boot log analyser for a DEBUG log.

The window drives the same OpenCore engine stages as the terminal menu and headless mode; nothing is decided differently. When a stage needs an answer that has no control on the page (for example which of two GPUs to keep), a dialog shows the stage's own text and options. Cancel stops the running stage at its next output or question.

`python MacBootsmith.pyw --self-test` opens the window, visits every page and closes after two seconds (used by CI).

### Terminal menu

Run `OpCore-Simplify.bat` as administrator. The main menu offers:

1. Select Hardware Report: scan this PC or load an existing report, then check compatibility.
2. Select macOS Version: choose the target release.
3. Customize ACPI Patch: review or change the ACPI patches.
4. Customize Kexts: review or change the kext selection.
5. Customize SMBIOS Model: pick the Mac model to present.
6. USB Port Mapping: discover the ports on this machine and choose which ones macOS gets (at most 15 per controller).
7. Build OpenCore EFI: write the EFI and run ocvalidate on it. Answer yes to the DEBUG question only to diagnose a boot that fails: the EFI then uses the DEBUG OpenCore build and writes a log file to the EFI partition on every boot.
8. Download macOS Recovery: fetch the recovery image for the chosen release.
9. Prepare Post-Install Kit: write the post-install checklist, helper script and SMBIOS values to `Results\PostInstall`, with or without the tools.
10. Create USB Installer: format a USB drive and write the installer, or copy only the EFI to an existing drive. The post-install kit is copied too when it exists.
11. Analyze Boot Log: read the newest `opencore-*.txt` from a drive letter, folder or file (a QEMU `serial.log` works too) and report how far the boot got, the known errors it contains with their fixes, and the last lines. Serial numbers, MLB and system-id are masked. No hardware report is needed.

Then boot from the USB and work through the on-screen BIOS checklist.

Headless mode builds an EFI without prompts, from a JSON answers file (used by CI and for scripting):

```
python OpCore-Simplify.py --headless <answers.json>
```

Add `"debug": true` to the answers file for a DEBUG EFI (see `tests/fixtures/answers-desktop-debug.json`).

The boot log analyser also runs on its own; it exits 1 when no log is found:

```
python OpCore-Simplify.py --analyze-log <log file, folder or drive>
```

## Development

Run the tests:

```
python -m unittest discover -s tests
```

The CI workflow (`.github/workflows/ci.yml`) has five jobs:

- test: the unit tests.
- build: headless EFI build per hardware report fixture (desktop, desktop-debug, laptop), with an ocvalidate check, a DEBUG settings check for desktop-debug and, for the desktop fixture, a docs-only post-install kit check; the EFI is uploaded as an artifact.
- boot: boots the desktop and desktop-debug EFIs in QEMU, checks that the OpenCore picker appears, and runs the boot log analyser on the serial log.
- package: builds the Windows app with PyInstaller (`packaging/macbootsmith.spec`), runs a headless desktop build and the window self-test with the packaged app, and uploads it as the MacBootsmith-windows artifact. See `packaging/README.md`.
- recovery-download: downloads and verifies a macOS 26 recovery image.

Design notes live in `docs/reference/` (BIOS settings, install flow, post-install, OCLP, Tahoe, prompt choices, gaps, external links).

Contributions are welcome. The rule that matters: nothing from Apple is ever committed to this repository, whether binaries, images or logos.

## Legal

No Apple software is included. The recovery image is downloaded by you, from Apple's servers. macOS's licence restricts installation to Apple-branded hardware, and you are responsible for your own compliance. This project is not affiliated with Apple or with the authors of the tools it builds on.

## Credits

- [OpCore-Simplify](https://github.com/lzhoang2801/OpCore-Simplify) by lzhoang2801: the engine this project forks.
- [OpenCorePkg and macrecovery](https://github.com/acidanthera/OpenCorePkg) by Acidanthera: bootloader, ocvalidate, macserial, recovery download.
- Hardware Sniffer by lzhoang2801: hardware scan (https://github.com/lzhoang2801/Hardware-Sniffer).
- [USBToolBox](https://github.com/USBToolBox/tool): USB mapping tooling and kext.
- [SSDTTime](https://github.com/corpnewt/SSDTTime) and [ProperTree](https://github.com/corpnewt/ProperTree) by corpnewt.
- [Dortania guides](https://dortania.github.io/OpenCore-Install-Guide/): the reference for OpenCore setup.
- [OpenCore Legacy Patcher](https://github.com/dortania/OpenCore-Legacy-Patcher): root patching for unsupported hardware.

## License

BSD-3-Clause, inherited from OpCore-Simplify. The `LICENSE` file keeps the original notice: Copyright (c) 2024, lzhoang2601.
