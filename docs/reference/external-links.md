# External links worth keeping

Only links that appear in the source set and still matter for macOS 11 to 26 on Intel/AMD hardware. Skipped on purpose: Clover and its builders, UniBeast/MultiBeast and other tonymacx86-era tools, Niresh and other pre-built distros, anything older than OpenCore-era guides (pre-2018), VM-on-Windows guides, shop and affiliate links, per-point-release tonymacx86 update threads.

Context from `_ref/hackintosh-com/index.html`: macOS 26 Tahoe is described as the last macOS that supports Intel Macs (and therefore Hackintosh); macOS 27 "Golden Gate" is Apple Silicon only. The page lists guides back to Mac OS X 10.5, most of which are out of scope here.

## 1. Official tool repositories

| Tool | URL | Used for |
| :--- | :--- | :--- |
| OpenCorePkg (releases, `Utilities/macrecovery`, `ocvalidate`, `macserial`, `ControlMsrE2`, `ocpasswordgen`, LogoutHook, Docs: `Sample.plist`, `Configuration.pdf`, `Differences.pdf`) | https://github.com/acidanthera/OpenCorePkg | Core of the EFI, recovery download, validation, serials |
| OcBinaryData (HfsPlus.efi, HfsPlusLegacy.efi, Resources for OpenCanopy) | https://github.com/acidanthera/OcBinaryData | Drivers, GUI assets |
| Lilu | https://github.com/acidanthera/Lilu | Plugin host |
| VirtualSMC | https://github.com/acidanthera/VirtualSMC | SMC emulation |
| WhateverGreen (FAQ for Intel HD: `Manual/FAQ.IntelHD.en.md`) | https://github.com/acidanthera/WhateverGreen | GPU patching |
| AppleALC (supported codecs wiki) | https://github.com/acidanthera/AppleALC | Audio |
| RestrictEvents | https://github.com/acidanthera/RestrictEvents | `revpatch`, OTA updates |
| CryptexFixup | https://github.com/acidanthera/CryptexFixup | Non-AVX2 cryptex on Ventura+ |
| NVMeFix | https://github.com/acidanthera/NVMeFix | NVMe power management and fixes |
| CPUFriend | https://github.com/acidanthera/CPUFriend | Power management data injection |
| RTCMemoryFixup | https://github.com/acidanthera/RTCMemoryFixup | RTC region exclusion |
| BrcmPatchRAM / BlueToolFixup | https://github.com/acidanthera/BrcmPatchRAM | Broadcom Bluetooth |
| AirportBrcmFixup | https://github.com/acidanthera/AirportBrcmFixup | Broadcom Wi-Fi |
| BrightnessKeys | https://github.com/acidanthera/BrightnessKeys | Laptop brightness keys |
| VoodooPS2 | https://github.com/acidanthera/VoodooPS2 | PS/2 keyboard and trackpad |
| IntelMausi | https://github.com/acidanthera/IntelMausi | Intel Ethernet |
| gfxutil | https://github.com/acidanthera/gfxutil | PciRoot lookup |
| MaciASL | https://github.com/acidanthera/MaciASL | SSDT editing |
| Acidanthera bug tracker | https://github.com/acidanthera/bugtracker | Report ASSERTs and OpenCore bugs |
| USBToolBox tool | https://github.com/USBToolBox/tool | USB mapping from Windows or macOS |
| USBToolBox kext | https://github.com/USBToolBox/kext | USB map kext |
| AMD vanilla kernel patches | https://github.com/AMD-OSX/AMD_Vanilla | Required for all AMD CPUs, update per macOS release and core count |
| SMCAMDProcessor | https://github.com/trulyspinach/SMCAMDProcessor | AMD power management |
| CpuTscSync | https://github.com/lvs1974/CpuTscSync | TSC sync on laptops |
| TSCAdjustReset | https://github.com/interferenc/TSCAdjustReset | Skylake-X and Cascade Lake TSC |
| ECEnabler | https://github.com/1Revenger1/ECEnabler | Embedded controller fields in battery readouts |
| VoodooI2C | https://github.com/VoodooI2C/VoodooI2C | I2C trackpads |
| VoodooRMI, VoodooSMBus | https://github.com/VoodooSMBus/VoodooRMI, https://github.com/VoodooSMBus/VoodooSMBus | Synaptics/Elan SMBus trackpads |
| itlwm / AirportItlwm / HeliPort / IntelBluetoothFirmware | https://github.com/OpenIntelWireless/itlwm, https://github.com/OpenIntelWireless/HeliPort, https://github.com/OpenIntelWireless/IntelBluetoothFirmware | Intel Wi-Fi and Bluetooth |
| LucyRTL8125Ethernet, RTL8111, AtherosE2200 | https://github.com/Mieze/LucyRTL8125Ethernet, https://github.com/Mieze/RTL8111_driver_for_OS_X, https://github.com/Mieze/AtherosE2200Ethernet | Realtek 2.5G / 1G, Atheros E2200 Ethernet |
| AppleIGC, AppleIGB | https://github.com/SongXiaoXi/AppleIGC, https://github.com/donatengit/AppleIGB | Intel I225 / I210-class NICs |
| AppleBCMWLANCompanion | https://github.com/0xFireWolf/AppleBCMWLANCompanion | Broadcom Wi-Fi on macOS 15 and 26 without root patching |
| iBridged | https://github.com/Carnations-Botanica/iBridged | Keep secure boot on with OTA updates on 14.4+ |
| VoodooHDA | https://github.com/CloverHackyColor/VoodooHDA | Fallback audio on Tahoe (lower quality) |
| UEFITool, Universal-IFR-Extractor | https://github.com/LongSoft/UEFITool, https://github.com/LongSoft/Universal-IFR-Extractor | CFG Lock unlock |
| Modified GRUB shell | https://github.com/datasone/grub-mod-setup_var | `setup_var_cv` for the CFG Lock unlock |
| OpenCore Legacy Patcher | https://github.com/dortania/OpenCore-Legacy-Patcher | Root patching (see `oclp.md`) |
| KdkSupportPkg, MetallibSupportPkg | https://github.com/dortania/KdkSupportPkg, https://github.com/dortania/MetallibSupportPkg | Packages OCLP root patching needs |

Referenced by the guides but hosted on RehabMan's bitbucket or unmaintained forks: USBInjectAll (`os-x-usb-inject-all`), FakeSMC, NullEthernet, iASL builds, VoodooTSCSync. The guides themselves warn that RehabMan's MaciASL "no longer maintain their repos" and recommend Acidanthera's MaciASL. Check availability before depending on them.

## 2. Helper tools by CorpNewt and others (macOS/Windows/Linux Python)

| Tool | URL | Used for |
| :--- | :--- | :--- |
| ProperTree | https://github.com/corpnewt/ProperTree | plist editing, OC Snapshot (Cmd/Ctrl+R) |
| GenSMBIOS | https://github.com/corpnewt/GenSMBIOS | Serial generation |
| SSDTTime | https://github.com/corpnewt/SSDTTime | FixHPET, USB reset (SSDT-RHUB), PLUG and others |
| USBMap | https://github.com/corpnewt/USBMap | Intel USB mapping on macOS |
| MountEFI | https://github.com/corpnewt/MountEFI | Mount ESPs (post-install guide's method) |
| OCConfigCompare | https://github.com/corpnewt/OCConfigCompare | Compare config.plist with the new sample |
| Lilu-and-Friends, KextExtractor | https://github.com/corpnewt/Lilu-and-Friends, https://github.com/corpnewt/KextExtractor | Kext build and merge |
| CPUFriendFriend | https://github.com/corpnewt/CPUFriendFriend | Power management data |
| BitmaskDecode | https://github.com/corpnewt/BitmaskDecode | Decode SIP values |
| brigadier | https://github.com/corpnewt/brigadier | BootCamp driver download for Windows on a hack |
| Hackintool | https://github.com/headkaze/Hackintool | `en0` / PCI export checks |

## 3. Current guides

| Guide | URL | Notes |
| :--- | :--- | :--- |
| OpenCore Install Guide | https://dortania.github.io/OpenCore-Install-Guide/ | Primary source; header names the supported OpenCore release |
| Extras for Tahoe | https://dortania.github.io/OpenCore-Install-Guide/extras/tahoe.html | The only guide page with macOS 26 specifics |
| Extras for Ventura, Monterey, Big Sur | https://dortania.github.io/OpenCore-Install-Guide/extras/ventura.html, `.../monterey.html`, `.../big-sur/` | Version-specific |
| OpenCore Post-Install | https://dortania.github.io/OpenCore-Post-Install/ | Audio, USB, iServices, security, sleep |
| Getting Started With ACPI | https://dortania.github.io/Getting-Started-With-ACPI/ | SSDT recipes referenced in nearly every config page |
| OpenCore Multiboot | https://dortania.github.io/OpenCore-Multiboot/ | Windows/Linux on the same machine |
| GPU Buyers Guide, Wireless Buyers Guide, Anti-Hackintosh Buyers Guide | https://dortania.github.io/GPU-Buyers-Guide/, https://dortania.github.io/Wireless-Buyers-Guide/, https://dortania.github.io/Anti-Hackintosh-Buyers-Guide/ | Hardware verdict references |
| OCLP documentation | https://dortania.github.io/OpenCore-Legacy-Patcher/ | Root patches, updates |
| Getting Started With OpenCore (InsanelyMac Discord) | https://insanelymacdiscord.github.io/Getting-Started-With-OpenCore/ | Community fork of the install guide, listed on hackintosh.com |
| tonymacx86: macOS Tahoe installation USB | https://www.tonymacx86.com/threads/how-to-create-a-macos-tahoe-installation-usb.332208/ | Lists update threads through 26.6.2 |
| kextcache: final Tahoe build; making a bootable USB with Mist | https://kextcache.com/macos-tahoe-hackintosh-guide/, https://kextcache.com/guide-making-bootable-macos-usb-using-mist/ | Tahoe and installer creation |
| Mac Observer: upgrading a Hackintosh to Tahoe | https://www.macobserver.com/tips/round-ups/i-updated-my-hackintosh-to-macos-tahoe-heres-how-it-went/ | Field report |
| InsanelyMac: X299 final cut for Tahoe | https://www.insanelymac.com/forum/topic/361935-the-final-cut-x299-support-for-all-macos-versions-including-tahoe-last-macos-release-for-intel/ | Skylake-X on Tahoe |
| EliteMacx86 Sequoia threads (web.archive copies) | https://web.archive.org/web/20251128050005/https://elitemacx86.com/threads/how-to-install-macos-sequoia-on-pc-intel-amd.1877/, https://web.archive.org/web/20251128050013/https://elitemacx86.com/threads/common-problems-in-macos-sequoia-15-0-and-workarounds.1873/, https://web.archive.org/web/20251014074502/https://elitemacx86.com/threads/how-to-fix-broadcom-wifi-on-macos-sonoma-and-later.1415/ | Install, common problems and Broadcom Wi-Fi |
| EveryMac compatibility lists (Tahoe, Sequoia, Sonoma) | https://everymac.com/mac-answers/macos-26-tahoe-faq/macos-tahoe-macos-26-compatbility-list-system-requirements.html and the macOS 15 / 14 equivalents | Which real Mac models each macOS supports (SMBIOS choice) |

## 4. Communities

| Community | URL |
| :--- | :--- |
| r/hackintosh | https://www.reddit.com/r/hackintosh |
| tonymacx86 | https://www.tonymacx86.com |
| InsanelyMac forum | https://www.insanelymac.com/forum/ |
| Hackintosh-Forum.de | https://www.hackintosh-forum.de/ |
| AMD-OSX forum | https://forum.amd-osx.com/index.php |

## 5. Video

hackintosh.com lists an iSolution video covering macOS Tahoe and Sequoia installation with OpenCore Simplify (channel https://www.youtube.com/@iSolutional); the specific video URL is embedded in the page, not given as a link.

## 6. Not covered by the sources

No source gives a URL for Hardware Sniffer, gibMacOS (named in the post-install guide only), or the OpenCore Simplify upstream repository. `https://rufus.ie/` appears in `windows-install.md` and is the only Windows-side USB tool URL in the install guide.
