from Scripts import gathering_files
from Scripts import run
from Scripts import utils
import os
import platform

os_name = platform.system()

class ConfigValidator:
    def __init__(self):
        self.g = None
        self.run = run.Run().run
        self.utils = utils.Utils()
        self.script_dir = os.path.dirname(os.path.realpath(__file__))

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

        output = self.run({
            "args": [ocvalidate, config_path]
        })

        if not output or output[1] == "Command not found!" or not os.path.exists(ocvalidate):
            return None, "ocvalidate could not be run"

        text = (output[0] or "") + (output[1] or "")
        return output[2] == 0, text.strip()
