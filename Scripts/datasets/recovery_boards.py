# Source: https://raw.githubusercontent.com/dortania/OpenCore-Install-Guide/master/installer-guide/windows-install.md
# Keys are the Darwin major version, matching macOSVersionInfo.darwin_version in os_data.py.

data = {
    17: {"board_id": "Mac-7BA5B2D9E42DDD94", "os_type": "default", "name": "macOS High Sierra"},
    18: {"board_id": "Mac-7BA5B2DFE22DDD8C", "os_type": "default", "name": "macOS Mojave"},
    19: {"board_id": "Mac-00BE6ED71E35EB86", "os_type": "default", "name": "macOS Catalina"},
    20: {"board_id": "Mac-42FD25EABCABB274", "os_type": "default", "name": "macOS Big Sur"},
    21: {"board_id": "Mac-FFE5EF870D7BA81A", "os_type": "default", "name": "macOS Monterey"},
    22: {"board_id": "Mac-4B682C642B45593E", "os_type": "default", "name": "macOS Ventura"},
    23: {"board_id": "Mac-226CB3C6A851A671", "os_type": "default", "name": "macOS Sonoma"},
    # Sequoia and Tahoe rows were chosen by probing Apple's catalog on 2026-10-21:
    # iMac19,1 cannot run Tahoe, so "latest" on it is always the newest Sequoia.
    # iMac20,1 supports Tahoe, and "latest" on it returned a Tahoe image.
    # "default" on any Sequoia-capable board returned the same Sequoia 15.4 image.
    24: {"board_id": "Mac-AA95B1DDAB278B95", "os_type": "latest", "name": "macOS Sequoia"},
    25: {"board_id": "Mac-CFF7D910A743CAAF", "os_type": "latest", "name": "macOS Tahoe"},
}
