# Prompts and what to answer

Most prompts have a default; pressing Enter takes it. This lists the ones where the choice is not obvious.

## Tahoe audio kext

| Option | Pick it when |
|---|---|
| 2. AppleALC + SimpleHDA (default) | Nothing else in the build needs OpenCore Legacy Patcher root patches. Keeps SIP intact and survives macOS updates. |
| 1. AppleALC + OCLP | Root patches are needed anyway (GPU or Broadcom Wi-Fi). Reuses Apple's AppleHDA, so jack and input support is the most complete. |

The default is 1 when the hardware list already requires root patches, otherwise 2. SimpleHDA is the younger project and some codecs lose a jack or the internal mic with it.

## Codec layout ID

The ID tells AppleALC which pin configuration to use for the codec. Each entry was contributed for a specific board, and the green default comes from a well known author. If sound is missing or a jack does not work after install, change only `DeviceProperties -> PciRoot(...)/Pci(...) -> layout-id` (or `alcid=` in boot-args) and reboot. No rebuild is needed.

## AMD Navi 21/23 GPU kext

| Option | Notes |
|---|---|
| 2. WhateverGreen (default) | Uses the firmware macOS ships; what most guides assume. |
| 1. NootRX | Loads newer GPU firmware. Can fix black screens or missing outputs on some RX 6600/6800 cards. Cannot coexist with an Intel iGPU. |

Try the other one post-install if the display misbehaves.

## Broadcom Wi-Fi

| Option | Pick it when |
|---|---|
| 1. Root patches (default) | You already accepted root patches for the GPU or audio. |
| 2. AppleBCMWLANCompanion | Intel system with VT-d enabled and you want to keep SIP and update normally. Fall back to 1 if Wi-Fi does not appear. |

## Intel Wi-Fi

The default is the option that gives the native Wi-Fi menu without root patches when one exists. itlwm is the fallback when AirportItlwm misbehaves; it works with the HeliPort app instead of the native menu.

## Device combinations

Devices left out of the chosen combination are disabled for macOS (hidden via ACPI or device properties). Windows is unaffected. Pick the combination with the newest macOS range. For a laptop with an NVIDIA dGPU that means the Intel iGPU alone.

## macOS version

Enter accepts the suggested version. Versions marked Requires OpenCore Legacy Patcher install fine but need root patches inside macOS for full graphics or Wi-Fi; prefer an unmarked version for a first install.

## Other prompts

| Prompt | Answer |
|---|---|
| OpenCore Legacy Patcher warning | Yes only if the hardware list said a device requires it. |
| DEBUG EFI | No, unless the boot fails and you need the log. |
| Post-install kit, full or docs-only | Full when you are online now; it downloads the tools. Docs-only writes the checklist without them. |
| Recovery, default or latest | Default is the known-good Sequoia 15.4 snapshot. Latest is the newest version for the board. |
| USB mapping | Map on the machine you install on. Skip only if you accept the 15-port default. |
| Type ERASE | Typed before the USB writer wipes the stick. Check the disk number and size first; everything on it is lost. |
