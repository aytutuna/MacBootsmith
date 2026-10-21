from Scripts.datasets import recovery_boards
from Scripts import macrecovery
from Scripts import utils
import argparse
import json
import os
import socket

class RecoveryFetcher:
    def __init__(self):
        self.utils = utils.Utils()
        self.recovery_folder_name = "com.apple.recovery.boot"
        self.basename = "BaseSystem"
        self.marker_name = "recovery.json"
        self.socket_timeout = 60

    def get_board(self, macos_version_key):
        try:
            return recovery_boards.data.get(int(str(macos_version_key).split(".")[0]))
        except ValueError:
            return None

    def _read_marker(self, marker_path):
        try:
            with open(marker_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else None
        except (OSError, ValueError):
            return None

    def _write_marker(self, marker_path, board, macos_version_key):
        try:
            darwin_major = int(str(macos_version_key).split(".")[0])
        except ValueError:
            darwin_major = None
        with open(marker_path, "w", encoding="utf-8") as f:
            json.dump({
                "board_id": board["board_id"],
                "os_type": board["os_type"],
                "darwin_major": darwin_major,
                "name": board["name"]
            }, f, indent=4)

    def _cleanup(self, recovery_dir):
        for name in (self.basename + ".dmg", self.basename + ".chunklist", self.marker_name):
            path = os.path.join(recovery_dir, name)
            try:
                if os.path.isfile(path):
                    os.remove(path)
            except OSError as e:
                print("Could not remove {}: {}".format(path, e))

    def _is_valid(self, recovery_dir, board):
        dmg_path = os.path.join(recovery_dir, self.basename + ".dmg")
        cnk_path = os.path.join(recovery_dir, self.basename + ".chunklist")
        marker_path = os.path.join(recovery_dir, self.marker_name)

        if not (os.path.isfile(dmg_path) and os.path.isfile(cnk_path) and os.path.isfile(marker_path)):
            return False

        marker = self._read_marker(marker_path)
        if not marker or marker.get("board_id") != board["board_id"] or marker.get("os_type") != board["os_type"]:
            return False

        try:
            macrecovery.verify_image(dmg_path, cnk_path)
            return True
        except (Exception, SystemExit) as e:
            print("")
            print("Existing recovery image is not valid: {}".format(str(e) or "Invalid chunklist"))
            return False

    def download(self, macos_version_key, destination_dir):
        board = self.get_board(macos_version_key)
        if not board:
            print("No recovery board is known for Darwin version {}.".format(macos_version_key))
            return None

        recovery_dir = os.path.join(destination_dir, self.recovery_folder_name)
        dmg_path = os.path.join(recovery_dir, self.basename + ".dmg")
        cnk_path = os.path.join(recovery_dir, self.basename + ".chunklist")
        marker_path = os.path.join(recovery_dir, self.marker_name)

        if self._is_valid(recovery_dir, board):
            print("")
            print("{} recovery image already downloaded and verified.".format(board["name"]))
            return recovery_dir

        previous_timeout = socket.getdefaulttimeout()
        try:
            socket.setdefaulttimeout(self.socket_timeout)
            print("Requesting {} recovery image (board {})...".format(board["name"], board["board_id"]))
            session = macrecovery.get_session(argparse.Namespace(verbose=False))
            info = macrecovery.get_image_info(session, bid=board["board_id"], mlb=macrecovery.MLB_ZERO, os_type=board["os_type"])
            print("Downloading {}...".format(info[macrecovery.INFO_PRODUCT]))
            cnk_path = macrecovery.save_image(info[macrecovery.INFO_SIGN_LINK], info[macrecovery.INFO_SIGN_SESS], self.basename + ".chunklist", recovery_dir)
            dmg_path = macrecovery.save_image(info[macrecovery.INFO_IMAGE_LINK], info[macrecovery.INFO_IMAGE_SESS], self.basename + ".dmg", recovery_dir)
        except KeyboardInterrupt:
            print("")
            print("Download cancelled.")
            self._cleanup(recovery_dir)
            return None
        except (Exception, SystemExit) as e:
            print("")
            print("\033[91mCould not download the macOS recovery image: {}\033[0m".format(str(e) or "network error"))
            print("Please check your internet connection and try again.")
            self._cleanup(recovery_dir)
            return None
        finally:
            socket.setdefaulttimeout(previous_timeout)

        try:
            macrecovery.verify_image(dmg_path, cnk_path)
            self._write_marker(marker_path, board, macos_version_key)
        except KeyboardInterrupt:
            print("")
            print("Download cancelled.")
            self._cleanup(recovery_dir)
            return None
        except (Exception, SystemExit) as e:
            print("")
            print("\033[91mRecovery image verification failed: {}\033[0m".format(str(e) or "Invalid chunklist"))
            self._cleanup(recovery_dir)
            return None

        return recovery_dir
