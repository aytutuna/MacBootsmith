from Scripts import app_paths
from Scripts import gathering_files
from Scripts import utils
import os
import platform
import subprocess

os_name = platform.system()

class ConfigValidator:
    def __init__(self):
        self.g = None
        self.utils = utils.Utils()
        self.script_dir = app_paths.tools_dir()

    def _find_ocvalidate(self):
        if os_name == "Windows":
            ocvalidate_binary = ["ocvalidate.exe"]
        elif os_name == "Linux":
            ocvalidate_binary = ["ocvalidate.linux", "ocvalidate"]
        elif os_name == "Darwin":
            ocvalidate_binary = ["ocvalidate"]
        else:
            raise Exception("Unknown OS for ocvalidate")

        for binary in ocvalidate_binary:
            ocvalidate_path = os.path.join(self.script_dir, binary)
            if os.path.exists(ocvalidate_path):
                return ocvalidate_path
        return None

    def check_ocvalidate(self):
        ocvalidate_path = self._find_ocvalidate()
        if ocvalidate_path:
            return ocvalidate_path

        if self.g is None:
            self.g = gathering_files.gatheringFiles()

        history_file = self.g.download_history_file
        current_history = self.utils.read_file(history_file)
        snapshot = list(current_history) if isinstance(current_history, list) else None

        # The gatherer skips OpenCorePkg while it is recorded as up to date,
        # so the entry has to be dropped to force a fetch. Restore it if the
        # fetch does not produce the binary.
        if snapshot:
            new_history = [item for item in snapshot if item.get("product_name") != "OpenCorePkg"]
            if len(new_history) != len(snapshot):
                self.utils.write_file(history_file, new_history)

        try:
            self.g.gather_bootloader_kexts([], "")
            ocvalidate_path = self._find_ocvalidate()
        except BaseException:
            if snapshot:
                self.utils.write_file(history_file, snapshot)
            raise

        if not ocvalidate_path:
            if snapshot:
                self.utils.write_file(history_file, snapshot)
            raise Exception("Failed to find ocvalidate after downloading OpenCorePkg")
        return ocvalidate_path

    def validate(self, config_path):
        ocvalidate = self.check_ocvalidate()

        try:
            proc = subprocess.run([ocvalidate, config_path], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
        except OSError as e:
            # 4551: Smart App Control, 1260: AppLocker / software restriction policy
            if getattr(e, "winerror", None) in (1260, 4551):
                return None, ("Windows blocked {} (Smart App Control or an application control policy), so config.plist was not checked.\n"
                              "Smart App Control cannot be set to allow one file; it can only be turned off under Windows Security > App & browser control,\n"
                              "and once off it stays off. Alternatively run the same check on the CI build or on another PC.").format(os.path.basename(ocvalidate))
            return None, "ocvalidate could not be run: {}".format(e)

        return proc.returncode == 0, proc.stdout.strip()
