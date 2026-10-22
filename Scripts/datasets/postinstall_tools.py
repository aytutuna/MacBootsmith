# Tools the post-install kit offers, checked against the GitHub release pages on 2026-10-21.
# Fields:
#   name, purpose: shown in POST-INSTALL.md.
#   repo: GitHub "owner/name".
#   tag: pinned release tag, or None when the tool has no releases.
#   commit: pinned commit whose source archive is downloaded when tag is None (never a moving branch head).
#   branch: informational branch name for tools fetched through a raw "url" pinned to a commit.
#   asset: release asset name; fnmatch wildcards are resolved through the GitHub API for the pinned tag.
#          For commit and raw-file tools it is only a label.
#   url: direct download URL; None means it is built from repo, tag or commit and asset.
#   sha256: expected SHA-256. Taken from the digest the GitHub API reports for the release asset.
#           For commit archives and raw files it is the hash of the pinned content.
#   dest: file name inside the kit's Tools folder.
#   when: "always", "needs_oclp" (root patches are needed) or "broadcom_companion" (AppleBCMWLANCompanion chosen).
#   download: False keeps the tool as a link with its hash in POST-INSTALL.md. OCLP-Mod.pkg carries
#             root-patch payloads taken from older macOS releases, so the kit never fetches it itself.
#   device_ids: for firmware files, the Wi-Fi device IDs the file belongs to.
#   page: where a user can read about or download the tool by hand.

allowed_when = ("always", "needs_oclp", "broadcom_companion")

# Payload MacPatch (postinstall/macpatch) installs root patches from. Hash and size taken from the
# GitHub release digest and a download on 2026-10-21; keep in sync with payload.PIN in the tool.
patcher_support_pkg = {
    "psp_version": "2.0.3",
    "url": "https://github.com/dortania/PatcherSupportPkg/releases/download/2.0.3/Universal-Binaries.dmg",
    "sha256": "cf2a80deafe153ed4a9aa32c63463032e02718f32713e9b3f0a6e09f9a6ffbab",
    "size": 790749184
}

tools = [
    {
        "name": "OCLP-Mod",
        "purpose": "OpenCore Legacy Patcher fork with Tahoe root patches (graphics, Wi-Fi, AppleHDA audio); fallback when MacPatch fails. Archived in June 2026.",
        "repo": "laobamac/OCLP-Mod",
        "tag": "3.1.9",
        "branch": None,
        "asset": "OCLP-Mod.pkg",
        "url": None,
        "sha256": "ba95c1efda777ca745e477dd2ec0f7d7a38bf9cd5ddccf06c055d41da4ce27ec",
        "dest": "OCLP-Mod.pkg",
        "when": "needs_oclp",
        "download": False,
        "page": "https://github.com/laobamac/OCLP-Mod/releases/tag/3.1.9"
    },
    {
        "name": "Hackintool",
        "purpose": "Checks en0, USB ports, audio codec and layout IDs from inside macOS.",
        "repo": "benbaker76/Hackintool",
        "tag": "4.1.5",
        "branch": None,
        "asset": "Hackintool.zip",
        "url": None,
        "sha256": "fdec76c80626e93388f7af40c68e567dc4f8752116cbab22a9f2874045072e13",
        "dest": "Hackintool.zip",
        "when": "always",
        "download": True,
        "page": "https://github.com/benbaker76/Hackintool/releases/tag/4.1.5"
    },
    {
        "name": "ProperTree",
        "purpose": "Cross-platform plist editor for config.plist (needs Python 3 on macOS).",
        "repo": "corpnewt/ProperTree",
        "tag": None,
        "branch": None,
        "commit": "51ed53dbe3c96a81686ae1fc47f6d2a92f668159",
        "asset": "ProperTree.zip",
        "url": None,
        "sha256": "964273c86006f750785e810cfdf79bdc93ec0c93650daf54121d3712b734c9ac",
        "dest": "ProperTree.zip",
        "when": "always",
        "download": True,
        "page": "https://github.com/corpnewt/ProperTree"
    },
    {
        "name": "MountEFI",
        "purpose": "Mounts EFI partitions in macOS so the EFI folder can be copied to the internal disk.",
        "repo": "corpnewt/MountEFI",
        "tag": None,
        "branch": None,
        "commit": "5310a71c9a46ab053afb9588cf2abc4d44fccb49",
        "asset": "MountEFI.zip",
        "url": None,
        "sha256": "23aee8dd51c5956f7237fc070f7e991c2b90d9e91066601f60c1e82d97fcc9e5",
        "dest": "MountEFI.zip",
        "when": "always",
        "download": True,
        "page": "https://github.com/corpnewt/MountEFI"
    },
    {
        "name": "BCM4350 firmware for AppleBCMWLANCompanion",
        "purpose": "Wi-Fi firmware AppleBCMWLANCompanion loads from /usr/local/share/firmware/wifi.",
        "repo": "0xFireWolf/AppleBCMWLANCompanion",
        "tag": None,
        "branch": "main",
        "asset": "Firmwares/BCM4350/brcmfmac4350-pcie_7.35.180.119.bin",
        "url": "https://raw.githubusercontent.com/0xFireWolf/AppleBCMWLANCompanion/493e08a15bde93aa4a658032976dff66e0fd1d56/Firmwares/BCM4350/brcmfmac4350-pcie_7.35.180.119.bin",
        "sha256": "5691d1e0ceb70baf18efb7a0ec6cb84feb9edd2d0700c525b42930c4e7e4b845",
        "dest": "brcmfmac4350-pcie_7.35.180.119.bin",
        "when": "broadcom_companion",
        "download": True,
        "device_ids": ["14E4-43A3"],
        "page": "https://github.com/0xFireWolf/AppleBCMWLANCompanion/tree/main/Firmwares/BCM4350"
    },
    {
        "name": "BCM43602 firmware for AppleBCMWLANCompanion",
        "purpose": "Wi-Fi firmware AppleBCMWLANCompanion loads from /usr/local/share/firmware/wifi.",
        "repo": "0xFireWolf/AppleBCMWLANCompanion",
        "tag": None,
        "branch": "main",
        "asset": "Firmwares/BCM43602/brcmfmac43602-pcie_7.35.177.61.bin",
        "url": "https://raw.githubusercontent.com/0xFireWolf/AppleBCMWLANCompanion/493e08a15bde93aa4a658032976dff66e0fd1d56/Firmwares/BCM43602/brcmfmac43602-pcie_7.35.177.61.bin",
        "sha256": "bf4cfc23ee952a3d82ef33a0f5f87853201c98f1bed034876a910f354f37862d",
        "dest": "brcmfmac43602-pcie_7.35.177.61.bin",
        "when": "broadcom_companion",
        "download": True,
        "device_ids": ["14E4-43BA"],
        "page": "https://github.com/0xFireWolf/AppleBCMWLANCompanion/tree/main/Firmwares/BCM43602"
    }
]
