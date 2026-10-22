from Scripts.datasets import codec_layouts
from Scripts.datasets import os_data
from Scripts.datasets import postinstall_tools
from Scripts import app_paths
from Scripts import integrity_checker
from Scripts import resource_fetcher
from Scripts import utils
import datetime
import fnmatch
import json
import os
import plistlib
import re
import shutil

SUMMARY_NAME = "build_summary.json"
SUMMARY_VERSION = 1
KIT_FOLDER = "PostInstall"
TOOLS_FOLDER = "Tools"
MANIFEST_NAME = "manifest.json"
CHECKLIST_NAME = "POST-INSTALL.md"
COMMAND_NAME = "post-install.command"
SMBIOS_NAME = "smbios.txt"
GENERATED_FILES = (CHECKLIST_NAME, COMMAND_NAME, SMBIOS_NAME)
MODES = ("full", "docs-only")

APPLE_NVRAM_GUID = "7C436110-AB2A-4BBB-A880-FE41995C9F82"
LILU_NVRAM_GUID = "4D1FDA02-38C7-4A6A-9CC6-4BCCA8B30102"
FIRMWARE_DIR = "/usr/local/share/firmware/wifi"
USB_VOLUME = "/Volumes/OPENCORE/PostInstall"
DOCS_FOLDER = "Docs"
DOCS_FILES = ("post-install.md", "install-flow.md")
PMSET_LINES = (
    "sudo pmset autopoweroff 0",
    "sudo pmset powernap 0",
    "sudo pmset standby 0",
    "sudo pmset proximitywake 0",
    "sudo pmset tcpkeepalive 0"
)
SMBIOS_FIELDS = ("SystemProductName", "SystemSerialNumber", "MLB", "SystemUUID", "ROM")


def _darwin_tuple(version):
    try:
        parts = [int(part) for part in str(version).split(".")]
    except ValueError:
        return (0, 0, 0)
    return tuple((parts + [0, 0, 0])[:3])


def _layout_value(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, (bytes, bytearray)) and value:
        return int.from_bytes(bytes(value[:4]), "little")
    return None


def _hex(value):
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).hex()
    return str(value or "")


def make_build_summary(hardware_report, config, smbios_model, macos_version, needs_oclp, ocvalidate="unavailable",
                       whatevergreen_first_boot=None, applealc=False, simplehda=False, bcmc=False, usb_map_kext=None, debug=False):
    hardware_report = hardware_report or {}
    config = config or {}
    motherboard = hardware_report.get("Motherboard") or {}
    bios_vendor = str((hardware_report.get("BIOS") or {}).get("Vendor") or "")
    nvram_add = (config.get("NVRAM") or {}).get("Add") or {}
    apple_nvram = nvram_add.get(APPLE_NVRAM_GUID) or {}
    lilu_nvram = nvram_add.get(LILU_NVRAM_GUID) or {}
    boot_args = str(apple_nvram.get("boot-args") or "")
    security = ((config.get("Misc") or {}).get("Security") or {})

    audio = None
    if applealc:
        for codec_name, codec_props in (hardware_report.get("Sound") or {}).items():
            codec_id = codec_props.get("Device ID")
            if codec_id not in codec_layouts.data:
                continue
            layout_id = None
            for properties in ((config.get("DeviceProperties") or {}).get("Add") or {}).values():
                layout_id = _layout_value(properties.get("layout-id"))
                if layout_id is not None:
                    break
            alcid_match = re.search(r"(?:^|\s)alcid=(\d+)", boot_args)
            alcid = int(alcid_match.group(1)) if alcid_match else None
            chosen = layout_id if layout_id is not None else alcid
            audio = {
                "codec": codec_name,
                "codec_id": codec_id,
                "layout_id": layout_id,
                "alcid": alcid,
                "simplehda": bool(simplehda),
                "alternatives": [{"id": layout.id, "comment": layout.comment.strip()} for layout in codec_layouts.data[codec_id] if layout.id != chosen]
            }
            break

    broadcom = []
    if bcmc:
        firmware_by_device = {}
        for tool in postinstall_tools.tools:
            if tool["when"] == "broadcom_companion":
                for device_id in tool.get("device_ids", []):
                    firmware_by_device[device_id] = tool["dest"]
        for network_name, network_props in (hardware_report.get("Network") or {}).items():
            device_id = network_props.get("Device ID")
            if device_id in firmware_by_device and network_props.get("PCI Path"):
                broadcom.append({"device": network_name, "device_id": device_id, "firmware": firmware_by_device[device_id]})

    revpatch = [item for item in str(lilu_nvram.get("revpatch") or "").split(",") if item]

    return {
        "version": SUMMARY_VERSION,
        "created": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "motherboard": motherboard.get("Name") or "Unknown",
        "platform": motherboard.get("Platform") or "Unknown",
        "bios_vendor": bios_vendor,
        "insyde": bool(re.search(r"insyde", bios_vendor, re.IGNORECASE)),
        "macos_version": macos_version,
        "macos_name": os_data.get_macos_name_by_darwin(macos_version) if macos_version else "Unknown",
        "smbios_model": smbios_model,
        "needs_oclp": bool(needs_oclp),
        "ocvalidate": ocvalidate,
        "debug": bool(debug),
        "whatevergreen_first_boot": {"agdp_patch": bool(whatevergreen_first_boot.get("agdp_patch"))} if whatevergreen_first_boot else None,
        "audio": audio,
        "broadcom_companion": broadcom,
        "usb_map": {"custom": bool(usb_map_kext), "kext": usb_map_kext or "UTBDefault.kext"},
        "secure_boot_model": security.get("SecureBootModel"),
        "sip": _hex(apple_nvram.get("csr-active-config")).upper(),
        "revpatch": revpatch,
        "boot_args": boot_args,
        "config_path": "EFI/OC/config.plist"
    }


class PostInstallKit:
    def __init__(self, fetcher=None):
        self.utils = utils.Utils()
        self._fetcher = fetcher
        self.integrity_checker = integrity_checker.IntegrityChecker()
        self.tools = postinstall_tools.tools

    @property
    def fetcher(self):
        if self._fetcher is None:
            self._fetcher = resource_fetcher.ResourceFetcher()
        return self._fetcher

    @fetcher.setter
    def fetcher(self, value):
        self._fetcher = value

    def save_summary(self, summary, path):
        with open(path, "w", encoding="utf-8") as summary_file:
            json.dump(summary, summary_file, indent=4)
        return path

    def load_summary(self, path):
        try:
            with open(path, "r", encoding="utf-8") as summary_file:
                summary = json.load(summary_file)
        except (OSError, ValueError):
            return None
        if not isinstance(summary, dict) or summary.get("version") != SUMMARY_VERSION:
            return None
        return summary

    def invalidate(self, dest_dir):
        removed = []
        for name in GENERATED_FILES:
            path = os.path.join(dest_dir, name)
            if os.path.isfile(path):
                try:
                    os.remove(path)
                    removed.append(path)
                except OSError as e:
                    print("Could not remove {}: {}".format(path, e))
        docs_path = os.path.join(dest_dir, DOCS_FOLDER)
        if os.path.isdir(docs_path):
            shutil.rmtree(docs_path, ignore_errors=True)
        return removed

    def applicable_tools(self, summary):
        device_ids = set(item.get("device_id") for item in summary.get("broadcom_companion") or [])
        selected = []
        for tool in self.tools:
            when = tool["when"]
            if when == "needs_oclp" and not summary.get("needs_oclp"):
                continue
            if when == "broadcom_companion" and not device_ids.intersection(tool.get("device_ids", [])):
                continue
            selected.append(tool)
        return selected

    def tool_ref(self, tool):
        return tool.get("tag") or tool.get("commit") or tool.get("branch")

    def resolve_download(self, tool):
        if tool.get("url"):
            return tool["url"], tool.get("sha256")
        repo = tool["repo"]
        if not tool.get("tag"):
            return "https://github.com/{}/archive/{}.zip".format(repo, tool["commit"]), tool.get("sha256")
        asset = tool["asset"]
        if not any(char in asset for char in "*?["):
            return "https://github.com/{}/releases/download/{}/{}".format(repo, tool["tag"], asset), tool.get("sha256")
        release = self.fetcher.fetch_and_parse_content("https://api.github.com/repos/{}/releases/tags/{}".format(repo, tool["tag"]), "json")
        for item in (release or {}).get("assets", []):
            if fnmatch.fnmatch(item.get("name", ""), asset):
                digest = str(item.get("digest") or "")
                sha256 = tool.get("sha256") or (digest.split(":", 1)[1] if digest.startswith("sha256:") else None)
                return item.get("browser_download_url"), sha256
        raise ValueError("no asset matching {} in {} {}".format(asset, repo, tool["tag"]))

    def load_manifest(self, path):
        try:
            with open(path, "r", encoding="utf-8") as manifest_file:
                data = json.load(manifest_file)
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def manifest_entry(self, tool, url, path):
        return {
            "name": tool["name"],
            "repo": tool["repo"],
            "ref": self.tool_ref(tool),
            "url": url,
            "sha256": self.integrity_checker.get_sha256(path),
            "size": os.path.getsize(path)
        }

    def collect_tools(self, summary, tools_dir, download=True):
        status = {}
        tools = self.applicable_tools(summary)
        manifest_path = os.path.join(tools_dir, MANIFEST_NAME)
        manifest = self.load_manifest(manifest_path)
        changed = False

        for tool in tools:
            name = tool["name"]
            if not tool.get("download", True):
                status[name] = "link"
                continue

            dest = os.path.join(tools_dir, tool["dest"])
            entry = manifest.get(tool["dest"]) or {}
            expected = tool.get("sha256")
            if not expected and entry.get("repo") == tool["repo"] and entry.get("ref") == self.tool_ref(tool):
                expected = entry.get("sha256")

            if os.path.isfile(dest) and expected and self.integrity_checker.get_sha256(dest).lower() == expected.lower():
                if download:
                    print("{} is already in the kit and its SHA-256 matches.".format(name))
                status[name] = "present"
                continue

            if not download:
                status[name] = "missing"
                continue

            try:
                url, sha256 = self.resolve_download(tool)
            except Exception as e:
                print("\033[1;93mWarning: could not find the download for {}: {}\033[0m".format(name, e))
                status[name] = "failed"
                continue

            self.utils.create_folder(tools_dir)
            print("")
            print("Downloading {} ({})...".format(name, self.tool_ref(tool)))
            partial = dest + ".part"
            ok = False
            try:
                ok = self.fetcher.download_and_save_file(url, partial, sha256)
                if ok:
                    os.replace(partial, dest)
            except Exception as e:
                print("Download error: {}".format(e))
                ok = False
            if not ok:
                if os.path.exists(partial):
                    try:
                        os.remove(partial)
                    except OSError:
                        pass
                print("\033[1;93mWarning: {} could not be downloaded; POST-INSTALL.md links to it instead.\033[0m".format(name))
                status[name] = "failed"
                continue

            manifest[tool["dest"]] = self.manifest_entry(tool, url, dest)
            changed = True
            status[name] = "downloaded"

        if changed:
            with open(manifest_path, "w", encoding="utf-8") as manifest_file:
                json.dump(manifest, manifest_file, indent=4)
        return status

    def read_smbios(self, config_path):
        try:
            with open(config_path, "rb") as config_file:
                config = plistlib.load(config_file)
        except Exception:
            return None
        generic = (config.get("PlatformInfo") or {}).get("Generic") or {}
        values = {}
        for field in SMBIOS_FIELDS:
            value = generic.get(field)
            values[field] = _hex(value) if field == "ROM" else str(value or "")
        return values

    def render_smbios(self, values):
        lines = ["Keep these values private: anyone who has them can present this machine to Apple's services as their own.", ""]
        if not values:
            lines.append("config.plist could not be read, so the values are not listed here. They are under PlatformInfo -> Generic in EFI/OC/config.plist.")
        else:
            for field in SMBIOS_FIELDS:
                lines.append("{}: {}".format(field, values.get(field, "")))
        return "\n".join(lines) + "\n"

    def has_file(self, tool, status):
        return status.get(tool["name"]) in ("downloaded", "present")

    def tool_mention(self, name, summary, status):
        for tool in self.applicable_tools(summary):
            if tool["name"] == name:
                if self.has_file(tool, status):
                    return "{} (`{}/{}` in this folder)".format(name, TOOLS_FOLDER, tool["dest"])
                return "{} ({})".format(name, tool["page"])
        return name

    def unzip_step(self, name, summary, status):
        for tool in self.applicable_tools(summary):
            if tool["name"] == name:
                if self.has_file(tool, status):
                    return "Unzip `{}/{}` from this folder".format(TOOLS_FOLDER, tool["dest"])
                return "Download {} from {} (Code -> Download ZIP), unzip it".format(name, tool["page"])
        return "Get {}".format(name)

    def firmware_tools(self, summary):
        return [tool for tool in self.applicable_tools(summary) if tool["when"] == "broadcom_companion"]

    def render_checklist(self, summary, status=None):
        status = status or {}
        darwin = _darwin_tuple(summary.get("macos_version"))
        is_tahoe = darwin >= (25, 0, 0)
        audio = summary.get("audio")
        broadcom = summary.get("broadcom_companion") or []
        usb_map = summary.get("usb_map") or {}
        first_boot = summary.get("whatevergreen_first_boot")
        sbvmm = "sbvmm" in (summary.get("revpatch") or [])
        hackintool = self.tool_mention("Hackintool", summary, status)
        propertree = self.tool_mention("ProperTree", summary, status)
        mountefi = self.tool_mention("MountEFI", summary, status)
        sections = []

        def section(title, body):
            sections.append((title, body.strip("\n")))

        if darwin >= (20, 0, 0):
            kext_check = "kmutil showloaded | grep -E \"Lilu|VirtualSMC\""
        else:
            kext_check = "kextstat | grep -E \"Lilu|VirtualSMC\""
        section("First boot checks", "\n".join([
            "The EFI is still on the USB drive at this point, so keep the drive plugged in.",
            "",
            "1. Boot from the USB drive. After each restart of the installer pick the macOS entry on the internal disk, not the USB installer entry, until the setup screens appear. Press Space in the picker if an entry is hidden.",
            "2. Finish the setup screens but skip signing in with an Apple Account for now (see \"Before signing in with an Apple Account\" below)." + (" Leave FileVault off on the setup screens; root patching needs it off and turning it off later means waiting for a full decryption." if summary.get("needs_oclp") else ""),
            "3. In Terminal, check that the core kexts loaded and that the SMBIOS model is in place:",
            "",
            "   ```",
            "   " + kext_check,
            "   sysctl hw.model",
            "   ```",
            "",
            "   The first command lists Lilu and VirtualSMC; the second prints `hw.model: {}`.".format(summary.get("smbios_model") or "the chosen model"),
            "4. Check networking and that the display runs at its native resolution with smooth animations (graphics acceleration).",
            "5. On Windows or here, copy the EFI folder from the USB drive somewhere safe before changing anything. It is your way back if a later step breaks booting."
        ]))

        if first_boot:
            lines = [
                "This build kept WhateverGreen.kext in EFI/OC/Kexts but disabled it for the first boot, because its AMD connector patching can panic on macOS 26.",
                "",
                "1. Open EFI/OC/config.plist on the USB drive with {}. A USB drive made by this app mounts by itself in macOS (as OPENCORE); otherwise mount its EFI partition with {}.".format(propertree, mountefi),
                "2. Set Kernel -> Add -> WhateverGreen.kext -> Enabled to True."
            ]
            step = 3
            if first_boot.get("agdp_patch"):
                lines.append("3. Delete the Kernel -> Patch entry \"AGDP board-id patch (pikera) for first boot without WhateverGreen\", then add `agdpmod=pikera` back to NVRAM -> Add -> {} -> boot-args.".format(APPLE_NVRAM_GUID))
                step = 4
            lines.append("{}. Save and reboot from the USB drive.".format(step))
            lines.append("{}. If it panics, set Enabled back to False (the USB drive's config.plist can be edited from Windows) and boot again. The GPU then runs without WhateverGreen until a fixed release is out.".format(step + 1))
            lines.append("")
            lines.append("Do this before moving the EFI to the internal disk, so the copy you move is the one that works.")
            section("Re-enable WhateverGreen", "\n".join(lines))

        if summary.get("insyde"):
            launcher = "Short (this firmware is Insyde, which often cannot handle full device paths in boot entries)"
        else:
            launcher = "Full (use Short instead on Insyde firmware)"
        section("Move the EFI to the internal disk", "\n".join([
            "1. {} and run MountEFI.command (Control-click, Open, the first time).".format(self.unzip_step("MountEFI", summary, status)),
            "2. Copy the EFI folder from the USB drive to the Desktop as a backup. A USB drive made by this app mounts by itself (as OPENCORE); otherwise mount its EFI partition with MountEFI and unmount it afterwards. Keep only one EFI partition mounted at a time.",
            "3. Mount the internal macOS disk's EFI partition. Several diskXsY entries can belong to one disk; they share one EFI partition. A folder named APPLE there can be deleted.",
            "4. Copy the EFI folder onto it. If Windows shares this disk, keep EFI/Microsoft and copy only EFI/BOOT and EFI/OC.",
            "5. Open EFI/OC/config.plist on the internal EFI partition with {} and set Misc -> Boot -> LauncherOption to {}. RequestBootVarRouting is already on in this build. Save.".format(propertree, launcher),
            "6. Shut down, remove the USB drive and boot. If the PC does not find OpenCore, pick the disk once in the firmware boot menu; OpenCore then registers its own boot entry."
        ]))

        if summary.get("needs_oclp"):
            oclp = next((tool for tool in self.applicable_tools(summary) if tool["name"] == "OCLP-Mod"), None)
            reason = "This build targets {} on hardware whose drivers macOS no longer ships".format(summary.get("macos_name"))
            if audio and is_tahoe and not audio.get("simplehda"):
                reason += ", including AppleHDA for analog audio on macOS 26"
            lines = [
                reason + ". Root patches put them back on the system volume.",
                "",
                "Unverified: the settings in this build (-amfipassbeta, AMFIPass, the Tahoe AirPortBrcmNIC kext, the AppleHDA rollback) follow the OpenCore Legacy Patcher fork used by OpCore Simplify, and this build has not been tested with OCLP-Mod. An incompatible root patch can leave a system that does not boot, and the EFI backup does not undo it. Back up the data first and read \"If it does not boot\" before patching.",
                "",
                "1. FileVault must be off before patching. Check with `fdesetup status` and turn it off in System Settings -> Privacy & Security -> FileVault.",
                "2. Turn off System Settings -> General -> Software Update -> Automatic Updates -> \"Download new updates when available\". A staged update breaks patching.",
                "3. Connect to the internet, Ethernet if possible; the patcher downloads support packages while patching."
            ]
            if oclp:
                if self.has_file(oclp, status):
                    lines.append("4. Install `{}/{}` from this folder.".format(TOOLS_FOLDER, oclp["dest"]))
                else:
                    lines.append("4. On the Mac, download {} from {} (about 770 MB; the kit does not include it). Check it before installing:".format(oclp["asset"], oclp["page"]))
                    lines.append("")
                    lines.append("   ```")
                    lines.append("   shasum -a 256 ~/Downloads/{}".format(oclp["asset"]))
                    lines.append("   ```")
                    lines.append("")
                    lines.append("   It must print `{}`.".format(oclp["sha256"]))
            else:
                lines.append("4. Download and install OCLP-Mod.")
            lines.extend([
                "5. Open OCLP-Mod, choose Post-Install Root Patch, start root patching and reboot when it finishes. Do not use its Build and Install OpenCore: this EFI was built for this PC.",
                "   OCLP-Mod was archived by its author in June 2026. Release 3.1.9 still works, but its download servers (SimpleHacAPI) are being shut down, so turn SimpleHacAPI off in OCLP-Mod settings first. If patching fails, the mainline OpenCore Legacy Patcher from dortania.github.io patches the same drivers; it has not been tested with this build.",
                "6. Run the root patches again after every macOS update. Updates remove them, and with a patched system volume macOS downloads full installers instead of small updates.",
                "7. SIP (csr-active-config {}) and SecureBootModel ({}) are already set by this build. Leave them as they are and do not change SIP from recoveryOS.".format(summary.get("sip") or "as built", summary.get("secure_boot_model") or "as built")
            ])
            section("Root patches with OCLP-Mod", "\n".join(lines))

        if audio:
            layout_id = audio.get("layout_id")
            alcid = audio.get("alcid")
            chosen = layout_id if layout_id is not None else alcid
            if layout_id is not None and alcid is not None:
                where = "set as layout-id in DeviceProperties and as `alcid={}` in boot-args".format(alcid)
            elif layout_id is not None:
                where = "set as layout-id in DeviceProperties"
            elif alcid is not None:
                where = "set as `alcid={}` in boot-args".format(alcid)
            else:
                where = "not set by this build"
            lines = [
                "- Codec: {} ({})".format(audio.get("codec"), audio.get("codec_id")),
                "- Layout ID in this build: {} ({})".format(chosen if chosen is not None else "none", where)
            ]
            if is_tahoe:
                if audio.get("simplehda"):
                    lines.append("- macOS 26 has no AppleHDA; this build restores it with AppleALC and SimpleHDA, without a root patch.")
                else:
                    lines.append("- macOS 26 has no AppleHDA; analog audio works only after the OCLP-Mod root patch above.")
            lines.extend([
                "",
                "If there is no sound from the speakers or the headphone jack:",
                "",
                "1. Open {}, Sound tab, and confirm the codec. Then try the other layout IDs for this codec one at a time:".format(hackintool),
                ""
            ])
            alternatives = audio.get("alternatives") or []
            if alternatives:
                lines.append("   | Layout ID | Notes |")
                lines.append("   | --- | --- |")
                for item in alternatives:
                    lines.append("   | {} | {} |".format(item.get("id"), str(item.get("comment") or "").replace("|", "/")))
            else:
                lines.append("   AppleALC lists no other layout for this codec.")
            lines.extend([
                "",
                "2. To try a layout, open config.plist with {} and add `alcid=<id>` to NVRAM -> Add -> {} -> boot-args, or change the number if alcid is already there (only one alcid value), save and reboot.".format(propertree, APPLE_NVRAM_GUID),
                "3. When one works, put the same number in DeviceProperties -> Add -> (the audio controller's PciRoot path) -> layout-id as a Number, and remove `alcid=` from boot-args, because alcid overrides layout-id.",
                "4. Pick the output device in System Settings -> Sound."
            ])
            section("Audio", "\n".join(lines))

        if broadcom:
            lines = ["Wi-Fi stays off until the firmware file is in place. VT-d must stay enabled in the BIOS for AppleBCMWLANCompanion.", ""]
            firmware = {tool["dest"]: tool for tool in self.firmware_tools(summary)}
            for item in broadcom:
                tool = firmware.get(item["firmware"])
                lines.append("For {} ({}) the file is `{}`.".format(item["device"], item["device_id"], item["firmware"]))
                if tool and not self.has_file(tool, status):
                    lines.append("It is not in this kit yet: download {} into the Tools folder and check that `shasum -a 256` prints `{}`.".format(tool["url"], tool["sha256"]))
                lines.append("")
                lines.append("```")
                lines.append("cd \"{}\"".format(USB_VOLUME))
                lines.append("sudo mkdir -p {} && sudo cp \"{}/{}\" {}/".format(FIRMWARE_DIR, TOOLS_FOLDER, item["firmware"], FIRMWARE_DIR))
                lines.append("```")
                lines.append("")
            lines.extend([
                "The first line assumes the USB drive is named OPENCORE; adjust it if yours has another name. post-install.command offers the same copy after checking the file's SHA-256. Reboot afterwards.",
                "",
                "Updates: AppleBCMWLANCompanion panics during macOS updates. Before installing one, set Kernel -> Add -> AppleBCMWLANCompanion.kext -> Enabled to False, update, then set it back to True. The firmware file in {} survives updates. The driver is still marked unstable upstream.".format(FIRMWARE_DIR)
            ])
            section("Broadcom Wi-Fi firmware", "\n".join(lines))

        if usb_map.get("custom"):
            lines = [
                "This build uses your USB map ({}) in place of UTBDefault.kext.".format(usb_map.get("kext")),
                "",
                "1. Open {}, USB tab. Plug a USB 2 and a USB 3 device into every port you mapped and check that each port shows the device, USB 3 devices at USB 3 speed.".format(hackintool),
                "2. Check that Bluetooth and devices on internal headers still work; they use USB ports too.",
                "3. If a port is missing or slow, boot Windows, map again with option 6 (USB Port Mapping), rebuild with option 7 and replace the EFI on the internal disk with the new one."
            ]
        else:
            lines = [
                "This build still uses UTBDefault.kext, which enables every port and can go past macOS's limit of 15 ports per controller (ports stuck at USB 2 speed, missing ports, sleep problems).",
                "",
                "1. Boot Windows on this PC, run option 6 (USB Port Mapping), plug a USB 2 and a USB 3 device into every port you use and save the map.",
                "2. Keep at most 15 ports per controller; a USB 3 port counts twice. XhciPortLimit does not work on macOS 11.3 and newer.",
                "3. Rebuild with option 7, replace the EFI on the internal disk with the new one, then check every port in {}, USB tab.".format(hackintool)
            ]
        section("USB ports", "\n".join(lines))

        section("Before signing in with an Apple Account", "\n".join([
            "1. en0 must exist and be marked built-in:",
            "",
            "   ```",
            "   ioreg -rd1 -c IONetworkInterface | grep -E '\"BSD Name\"|\"IOBuiltin\"'",
            "   ```",
            "",
            "   The entry with `\"BSD Name\" = \"en0\"` must show `\"IOBuiltin\" = Yes`. {} shows the same under System -> Peripherals. If en0 is missing, delete /Library/Preferences/SystemConfiguration/NetworkInterfaces.plist and preferences.plist, then reboot.".format(hackintool),
            "2. NVRAM must keep a value across a reboot:",
            "",
            "   ```",
            "   sudo nvram myvar=test",
            "   ```",
            "",
            "   Reboot, then run `nvram myvar`; it must print `myvar test`. Remove it with `sudo nvram -d myvar`. If nothing is printed, NVRAM is not working; see section 5 of {}/post-install.md before signing in.".format(DOCS_FOLDER),
            "3. The SMBIOS values this build generated (serial, MLB, UUID, ROM) are in {} next to this file. Keep them private and keep using them; do not generate new ones unless signing in fails.".format(SMBIOS_NAME),
            "4. Prefer an Apple Account that already has Apple hardware or purchases; new accounts are the ones usually refused. Remove old devices from the account and turn on two-factor authentication first."
        ]))

        section("Sleep", "\n".join(
            ["Before testing sleep, apply the post-install guide's power settings (post-install.command offers to run them):", "", "```"] +
            list(PMSET_LINES) +
            ["```", "", "Then test sleep and wake. Most sleep problems come from the USB map, so finish the USB ports section first."]
        ))

        if sbvmm:
            lines = [
                "RestrictEvents with `revpatch=sbvmm` and SecureBootModel {} are already set in this build, so System Settings -> General -> Software Update offers updates.".format(summary.get("secure_boot_model") or "Disabled"),
                "",
                "- Before each update keep a copy of the working EFI, update OpenCore and the kexts first if the new release needs it, and read reports about the new build."
            ]
            if summary.get("needs_oclp"):
                lines.append("- After each update run the OCLP-Mod root patches again.")
            if broadcom:
                lines.append("- Disable AppleBCMWLANCompanion before updating (see Broadcom Wi-Fi firmware).")
            section("macOS updates", "\n".join(lines))

        boot_lines = [
            "1. Boot from the USB drive again, or put the EFI backup back. That is why the copies above matter.",
            "2. Add `-v` to boot-args if it is not there, boot, and note the last lines on screen before it stops.",
            "3. Look the message up in the troubleshooting table, section 7 of {}/install-flow.md.".format(DOCS_FOLDER),
            "4. For problems before the macOS kernel starts, a DEBUG build of OpenCore writes a log file to the EFI partition (section 8 of the same page). A debug-build option in this app is the next planned step; until then follow that recipe by hand."
        ]
        if summary.get("needs_oclp"):
            boot_lines.append("5. If macOS stopped booting after root patching, an EFI backup does not help. Boot recoveryOS from the USB drive, open Terminal, mount the system volume read-write (`mount -uw \"/Volumes/Macintosh HD\"`) and revert the root patches or the system snapshot with the patcher's revert-patches function. If macOS still starts, open the patcher and choose Revert Root Patches, then reboot.")
        section("If it does not boot", "\n".join(boot_lines))

        header = [
            "# Post-install checklist",
            "",
            "Made by MacBootsmith on {} for {} ({}).".format(summary.get("created") or "unknown date", summary.get("motherboard") or "Unknown", summary.get("platform") or "Unknown"),
            "",
            "- macOS: {} (Darwin {})".format(summary.get("macos_name") or "Unknown", summary.get("macos_version") or "unknown"),
            "- SMBIOS: {}".format(summary.get("smbios_model") or "Unknown"),
            "- ocvalidate: {}".format(summary.get("ocvalidate") or "not run"),
            "- Root patches: {}".format("needed (OCLP-Mod)" if summary.get("needs_oclp") else "not needed"),
            "",
            "Work through the sections in order. Steps that do not apply to this build are left out. post-install.command in this folder runs the safe mechanical steps (bash post-install.command in Terminal)."
        ]
        body = []
        for number, (title, text) in enumerate(sections, 1):
            body.extend(["", "## {}. {}".format(number, title), "", text])

        tools = self.applicable_tools(summary)
        if tools:
            body.extend(["", "## Tools", "", "| Tool | Purpose | Where |", "| --- | --- | --- |"])
            for tool in tools:
                where = "`{}/{}`".format(TOOLS_FOLDER, tool["dest"]) if self.has_file(tool, status) else tool["page"]
                body.append("| {} ({}) | {} | {} |".format(tool["name"], self.tool_ref(tool), tool["purpose"], where))

        return "\n".join(header + body) + "\n"

    def render_command(self, summary):
        lines = [
            "#!/bin/bash",
            "# Post-install helper for {} ({}).".format(summary.get("smbios_model") or "this build", summary.get("macos_name") or "macOS"),
            "# Run it in Terminal with: bash post-install.command",
            "# To double-click it instead, make it executable once: chmod +x post-install.command",
            "# It asks before every action and never touches an EFI partition.",
            "",
            "cd \"$(dirname \"$0\")\" || exit 1",
            "",
            "confirm() {",
            "    local answer",
            "    read -r -p \"$1 [y/N] \" answer",
            "    case \"$answer\" in",
            "        y|Y|yes|Yes|YES) return 0 ;;",
            "    esac",
            "    return 1",
            "}",
            "",
            "if [ \"$(uname -s)\" != \"Darwin\" ]; then",
            "    echo \"Run this script on the installed macOS system.\"",
            "    exit 1",
            "fi",
            "",
            "echo \"Checklist: $(pwd)/{}\"".format(CHECKLIST_NAME),
            "echo \"Work through it in order; this script only does the mechanical steps.\"",
            "echo \"\"",
            "",
            "echo \"Sleep settings from the post-install guide:\""
        ]
        for line in PMSET_LINES:
            lines.append("echo \"  {}\"".format(line))
        lines.extend([
            "if confirm \"Apply these pmset settings now?\"; then",
            "    failed=0"
        ])
        for line in PMSET_LINES:
            lines.append("    {} || {{ echo \"Failed: {}\"; failed=1; }}".format(line, line))
        lines.extend([
            "    if [ \"$failed\" = 0 ]; then echo \"Applied.\"; else echo \"Some settings failed; see the lines above.\"; fi",
            "else",
            "    echo \"Skipped.\"",
            "fi",
            "echo \"\""
        ])

        firmware = {tool["dest"]: tool for tool in self.firmware_tools(summary)}
        for item in summary.get("broadcom_companion") or []:
            tool = firmware.get(item["firmware"])
            if not tool:
                continue
            lines.extend([
                "fw=\"{}/{}\"".format(TOOLS_FOLDER, tool["dest"]),
                "if [ -f \"$fw\" ]; then",
                "    actual=$(shasum -a 256 \"$fw\" | awk '{print $1}')",
                "    if [ \"$actual\" != \"{}\" ]; then".format(tool["sha256"]),
                "        echo \"$fw does not have the expected SHA-256; not copying it.\"",
                "    elif confirm \"Copy $fw to {} for AppleBCMWLANCompanion?\"; then".format(FIRMWARE_DIR),
                "        sudo mkdir -p {} && sudo cp \"$fw\" {}/ && echo \"Copied. Reboot to bring up Wi-Fi.\"".format(FIRMWARE_DIR, FIRMWARE_DIR),
                "    else",
                "        echo \"Skipped.\"",
                "    fi",
                "else",
                "    echo \"$fw is not in this kit. Download {} into the {} folder and run this script again.\"".format(tool["url"], TOOLS_FOLDER),
                "fi",
                "echo \"\""
            ])

        lines.extend([
            "echo \"Next: follow {} to move the EFI to the internal disk with MountEFI.\"".format(CHECKLIST_NAME),
            "echo \"This script does not touch EFI partitions.\""
        ])
        return "\n".join(lines) + "\n"

    def copy_docs(self, dest_dir):
        source_dir = os.path.join(app_paths.bundle_dir(), "docs", "reference")
        docs_dir = os.path.join(dest_dir, DOCS_FOLDER)
        for name in DOCS_FILES:
            source = os.path.join(source_dir, name)
            if not os.path.isfile(source):
                print("\033[1;93mWarning: {} was not found; it is not in the kit.\033[0m".format(source))
                continue
            self.utils.create_folder(docs_dir)
            shutil.copyfile(source, os.path.join(docs_dir, name))

    def write_text(self, path, text):
        with open(path, "w", encoding="utf-8", newline="\n") as output:
            output.write(text)
        return path

    def build(self, build_summary, dest_dir, mode="full", config_path=None):
        if mode not in MODES:
            raise ValueError("Unknown post-install kit mode '{}'; use one of: {}.".format(mode, ", ".join(MODES)))
        if not build_summary:
            raise ValueError("A build summary is needed to prepare the post-install kit.")

        self.utils.create_folder(dest_dir)
        tools_dir = os.path.join(dest_dir, TOOLS_FOLDER)

        if mode == "full":
            print("Collecting post-install tools into {}...".format(tools_dir))
        status = self.collect_tools(build_summary, tools_dir, download=(mode == "full"))
        failed = [name for name, state in status.items() if state == "failed"]

        if mode == "full":
            print("")
        print("Writing {}...".format(CHECKLIST_NAME))
        checklist_path = self.write_text(os.path.join(dest_dir, CHECKLIST_NAME), self.render_checklist(build_summary, status))

        print("Writing {}...".format(COMMAND_NAME))
        command_path = self.write_text(os.path.join(dest_dir, COMMAND_NAME), self.render_command(build_summary))
        try:
            os.chmod(command_path, 0o755)
        except OSError:
            pass

        print("Writing {}...".format(SMBIOS_NAME))
        if not config_path:
            relative = str(build_summary.get("config_path") or "EFI/OC/config.plist")
            config_path = os.path.join(os.path.dirname(os.path.abspath(dest_dir)), *relative.split("/"))
        values = self.read_smbios(config_path)
        if values is None:
            print("\033[1;93mWarning: could not read {}; {} has no values.\033[0m".format(config_path, SMBIOS_NAME))
        smbios_path = self.write_text(os.path.join(dest_dir, SMBIOS_NAME), self.render_smbios(values))

        self.copy_docs(dest_dir)

        print("")
        if failed:
            print("\033[1;93m{} tool(s) could not be downloaded: {}. The checklist links to them instead.\033[0m".format(len(failed), ", ".join(failed)))
        print("Post-install kit ready at {}".format(dest_dir))
        return {
            "dest_dir": dest_dir,
            "mode": mode,
            "files": [checklist_path, command_path, smbios_path],
            "tools": status
        }
