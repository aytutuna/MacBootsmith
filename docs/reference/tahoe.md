# macOS 26 Tahoe on OpenCore: what changes and what the app must handle

Status as of 2026-10-21. Tahoe is the last macOS release for Intel hardware, so
it is the final target of this project. Point releases observed in the wild:
Tahoe 26.0.1 through 26.6.2, Sequoia 15.7.9, Sonoma 14.8.9 (tonymacx86 index via
hackintosh.com, 2026-10).

## Supported SMBIOS (Apple models that run Tahoe)

| SMBIOS | Machine | Use for |
| --- | --- | --- |
| iMac20,1 | iMac 27" 2020 | Desktops with UHD 630 iGPU, under 10 cores |
| iMac20,2 | iMac 27" 2020 i9-10910 | Only for i9-10900K class CPUs |
| MacPro7,1 | Mac Pro 2019 | Radeon-only desktops, HEDT, AMD CPUs |
| MacBookPro16,1 / 16,4 | MacBook Pro 16" 2019 | Laptops, 6 cores and up |
| MacBookPro16,2 | MacBook Pro 13" 2020 four TB3 ports | Laptops, 4 cores |

Dropped in Tahoe: iMac19,x, iMacPro1,1, MacBookAir9,1, Macmini8,1,
MacBookPro15,x, MacBookPro16,3. Apple dropped every Mac up to Coffee Lake, so
SMBIOS must be a 2020-or-later model (elitemacx86).

Fork status (Scripts/smbios.py select_smbios_model): the default is chosen by
CPU codename, not by target macOS. On Tahoe that yields models Tahoe dropped:
MacBookPro16,3 and 15,x for laptops, iMac19,1 for Coffee Lake desktops,
MacBookAir9,1 for Ice Lake. The picker UI only greys out unsupported models
(smbios.py:178-199), it does not re-pick. Needed: a Darwin 25 override that
maps laptops to MacBookPro16,2 (4 cores) or 16,1 (6 and up), Coffee Lake and
Comet Lake desktops to iMac20,1, and iGPU-less or AMD systems to MacPro7,1.
Hardware older than Coffee Lake on Tahoe needs OCLP root patches anyway and
should keep the spoofed-model path upstream already has (needs_oclp).

## Hardware ceiling

- CPU: Intel 8th to 10th gen is the comfortable range; Comet Lake recommended.
  11th to 14th gen need extra work, 12th to 14th need hybrid-core topology
  fixes. Core Ultra and Arrow Lake: avoid. AMD Ryzen desktop: AMD Vanilla
  kernel patches, updated for Tahoe.
- GPU working: RX 6600 / 6800 / 6900, RX 5000, RX 570 / 580, Vega 56 / 64,
  Intel UHD 630. Not working: all modern NVIDIA, RX 7000 / 9000, Intel Arc,
  Iris Xe (11th gen and newer iGPU). Polaris had a WhateverGreen regression on
  early Tahoe builds.
- Board: Z490 / Z590 class recommended for a new build.

## Bootloader and kext versions

- OpenCore 1.0.5 or newer (kextcache). elitemacx86 says "v1.5.0 or later",
  which is probably a typo for 1.0.5; treat 1.0.5 as the floor and always
  fetch latest release.
- Lilu 1.7.1 or newer, with `-lilubetaall` if a plugin refuses to load.
- VirtualSMC, WhateverGreen, AppleALC, RestrictEvents, NIC kext
  (IntelMausi, RealtekRTL8111, LucyRTL8125Ethernet) at latest release.
- Early Tahoe builds had a VirtualSMC injection error fixed by a newer
  OpenCore, and an AppleEthernetRL panic from Apple's own RTL8125 driver.

## Analog audio

AppleHDA.kext was removed from macOS 26, so AppleALC alone no longer gives
analog audio. HDMI, DisplayPort and USB audio keep working. Options:

1. AppleALC plus root patches (OCLP-style, reinjects AppleHDA, needs lowered
   SIP, redone after every point release).
2. AppleALC plus SimpleHDA kext injection, no root patches. The fork already
   offers this (kext_maestro.py:158-177).
3. VoodooHDA: `csr-active-config` 03000000, kext in /Library/Extensions.
   Lower quality. Not offered by the fork.
4. USB DAC, or stay on Sequoia.

## Wi-Fi and Bluetooth

- Broadcom: native support ended in Sonoma. Either root patches (OCLP) or
  AppleBCMWLANCompanion (no root patches, needs VT-d enabled, so not on AMD,
  still marked unstable). Not in the fork's kext list; candidate addition.
- Intel Wi-Fi: AirportItlwm (laobamac fork for Tahoe, already in the fork) or
  itlwm plus HeliPort.
- Intel Bluetooth on Tahoe needs boot-arg `-ibtcompatbeta`. Not set by the
  fork (grep of Scripts/ finds no match); add it when IntelBluetoothFirmware
  is selected and Darwin is 25 or newer.
- Early Tahoe: IntelBTPatcher panics were reported; keep it easy to disable.

## OTA updates

On macOS 14.4 and newer OTA updates need RestrictEvents with
`revpatch=sbvmm` and `SecureBootModel` = Disabled, or iBridged to keep secure
boot. The fork already writes revpatch sbvmm (config_prodigy.py:716-741) and
sets SecureBootModel (config_prodigy.py:684). iBridged is not offered.

## WhateverGreen on Tahoe

AMD connector patching panics on some Tahoe builds. Workaround from Dortania:
remove WhateverGreen.kext; if `agdpmod=pikera` was needed, apply the pikera
kext patch manually under Kernel -> Patch. kextcache's install flow disables
WhateverGreen and the USB map kext for the first install and re-enables them
afterwards. The app should offer a "first boot safe mode" toggle that does
exactly that.

## Recovery download for Tahoe

Probed against Apple's catalog on 2026-10-21 (Scripts/datasets/recovery_boards.py):

| Board | os_type | Image date | Size | Meaning |
| --- | --- | --- | --- | --- |
| Mac-AA95B1DDAB278B95 (iMac19,1) | latest | 2025-08-20 | 847 MB | Sequoia 15.6.1, board cannot get Tahoe |
| Mac-CFF7D910A743CAAF (iMac20,1) | latest | 2026-08-17 | 916 MB | Tahoe 26.6.x |
| Mac-27AD2F918AE68F61 (MacPro7,1) | latest | 2026-08-17 | 916 MB | Tahoe, same image |
| any Sequoia-capable board | default | 2025-04-16 | 843 MB | Sequoia 15.4.1 snapshot |
| Mac-226CB3C6A851A671 (MacBookAir8,2) | default | 2024-08-15 | 753 MB | Sonoma |

"default" is a fixed catalog snapshot, "latest" is the newest build for that
board. Pick a board whose maximum OS is the one you want and use "latest".

## First install flow specific to Tahoe

1. BIOS: disable Fast Boot, Secure Boot, CSM, Intel SGX, CFG Lock; enable
   Above 4G Decoding, Resizable BAR, XHCI Hand-off.
2. Build EFI with WhateverGreen and the USB map disabled for the first boot if
   the GPU is AMD (see above).
3. Erase target as APFS, GUID partition map. Some Samsung SSDs refuse to boot.
4. Expect several reboots; pick the "macOS Installer" entry each time until
   it becomes "macOS".
5. Post-install: copy EFI to the internal ESP, map USB ports (15 port limit),
   re-enable WhateverGreen, fix audio per the option chosen, run root patches
   if chosen (OCLP 3.0.0 line from the lzhoang2801 fork for Tahoe), regenerate
   SMBIOS only if iServices fail.

## Sources

- _ref/dortania-install-guide/extras/tahoe.md and extras/smbios-support.md
- https://kextcache.com/macos-tahoe-hackintosh-guide/
- https://www.hackintoshbuilder.com/macos-tahoe-hackintosh-guide/
- https://elitemacx86.com/threads/how-to-update-opencore-efi-for-macos-tahoe.2259/
- https://www.insanelymac.com/forum/topic/361762-installing-macos-tahoe-on-an-imac-181-kabylake-non-retina-2017/
- hackintosh.com index (tonymacx86 thread list; the threads themselves block
  automated access and were not read)
