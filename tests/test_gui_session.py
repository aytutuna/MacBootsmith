import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from repo_path import FIXTURES

from Scripts import utils
from Scripts.gui import broker
from Scripts.gui import session as session_module


class ScriptedPrompts:
    def __init__(self, answers):
        self.answers = answers
        self.prompts = []
        self.log = []

    def post(self, message):
        if message[0] == "log":
            self.log.append(message[1])
        elif message[0] == "prompt":
            request = message[1]
            self.prompts.append(request.prompt)
            lowered = request.prompt.lower()
            answer = next((value for key, value in self.answers.items() if key.lower() in lowered), "")
            request.reply(answer)


class SessionPipelineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(FIXTURES, "answers-desktop.json"), encoding="utf-8") as handle:
            cls.answers = json.load(handle)["prompts"]

    def setUp(self):
        self.script = ScriptedPrompts(self.answers)
        self.broker = broker.PromptBroker(self.script.post)
        self.session = session_module.Session(preset_hook=self.broker.set_presets)
        self.restore = utils.Utils.install_output_proxy()
        utils.Utils.set_output_sink(self.broker.sink)
        utils.Utils.set_prompt_handler(self.broker)

    def tearDown(self):
        utils.Utils.set_prompt_handler(None)
        utils.Utils.set_output_sink(None)
        self.restore()

    def test_desktop_report_verdict_and_configuration(self):
        verdict = self.session.load_report(os.path.join(FIXTURES, "desktop", "Report.json"))
        self.assertIsNone(verdict["acpi"])
        self.assertTrue(self.session.ocpe.ac.skip_acpi_tables)
        sections = {row["section"] for row in verdict["rows"]}
        self.assertTrue({"CPU", "GPU", "Network"} <= sections)
        self.assertTrue(all(row["status"] in ("supported", "unsupported", "oclp", "unchecked") for row in verdict["rows"]))
        self.assertTrue(all("\033[" not in row["support"] for row in verdict["rows"]))
        self.assertIsNotNone(verdict["native"])

        choices = self.session.macos_choices()
        darwins = [choice["darwin"] for choice in choices]
        self.assertIn(25, darwins)
        self.assertEqual(darwins, sorted(darwins))
        default = self.session.default_macos()
        self.assertIn(default, darwins)
        self.assertTrue(next(choice for choice in choices if choice["darwin"] == default)["suggested"])
        self.assertEqual(self.broker.presets, [])

        options = {"audio": "2", "broadcom": "1", "whatevergreen": "yes", "debug": True}
        config = self.session.configure(25, options)
        self.assertTrue(config["macos_version"].startswith("25."))
        self.assertEqual(config["smbios_model"], "iMac20,1")
        self.assertTrue(config["debug"])
        self.assertTrue(self.session.ocpe.debug_build)
        self.assertIn("Lilu", config["kexts"])
        self.assertEqual(self.broker.presets, [])
        self.assertFalse(any(prompt.lower().startswith("please enter the macos version") for prompt in self.script.prompts))
        self.assertTrue(self.session.option_relevance(25)["audio"])

        bios = self.session.bios_requirements()
        self.assertEqual(set(bios), {"disable", "enable", "notes"})

    def test_incompatible_report_raises_stage_error(self):
        with self.assertRaises(session_module.StageError) as raised:
            self.session.load_report(os.path.join(FIXTURES, "laptop", "Report.json"))
        self.assertIn("not compatible", str(raised.exception))
        self.assertIsNone(self.session.hardware_report)

    def test_invalid_report_lists_the_errors(self):
        with self.assertRaises(session_module.StageError) as raised:
            self.session.load_report(os.path.join(FIXTURES, "no-such-report.json"))
        self.assertTrue(raised.exception.details)

    def test_configure_needs_a_report(self):
        with self.assertRaises(session_module.StageError):
            self.session.configure(25)


class SessionHelpersTest(unittest.TestCase):
    def test_option_presets_only_include_chosen_answers(self):
        session = session_module.Session()
        presets = session.option_presets(24, {"audio": None, "broadcom": "2", "whatevergreen": "no", "debug": False})
        self.assertEqual(presets, {
            "Please enter the macOS version": "24",
            "Select Broadcom Wi-Fi option": "2",
            "Disable WhateverGreen for the first boot": "no"
        })

    def test_answering_clears_presets_even_on_error(self):
        seen = []
        session = session_module.Session(preset_hook=seen.append)
        with self.assertRaises(RuntimeError):
            with session.answering({"Type ERASE": "ERASE"}):
                raise RuntimeError("boom")
        self.assertEqual(seen, [{"Type ERASE": "ERASE"}, {}])

    def test_macos_choices_mark_oclp_and_suggested(self):
        session = session_module.Session()
        session.native_macos_version = ("17.0.0", "23.99.99")
        session.ocl_patched_macos_version = ("25.99.99", "24.0.0")
        session.suggested_macos_version = "23.99.99"
        choices = session.macos_choices()
        self.assertEqual([choice["darwin"] for choice in choices], list(range(17, 26)))
        self.assertEqual([choice["darwin"] for choice in choices if choice["oclp"]], [24, 25])
        self.assertEqual(session.default_macos(), 23)

    def test_usb_map_disable_flag_reaches_the_build(self):
        session = session_module.Session()
        session.set_usb_map_disabled(True)
        self.assertTrue(session.usb_map_disabled)
        session.set_usb_map_disabled(False)
        self.assertFalse(session.usb_map_disabled)

    def test_write_installer_passes_the_selected_disk(self):
        session = session_module.Session()
        seen = {}

        class Usb:
            def create_installer(self, *args, **kwargs):
                seen.update(kwargs)

        class Ocpe:
            usb = Usb()
            result_dir = "Results"

        session.ensure_ocpe = lambda: Ocpe()
        disk = {"number": 3, "size_bytes": 16, "identity": "A"}
        session.write_installer(disk, "ERASE", dry_run=True)
        self.assertEqual(seen["expected_disk"], disk)

    def test_paths_are_under_the_app_folder(self):
        paths = session_module.Session().paths()
        self.assertTrue(paths["recovery"].endswith(os.path.join("Results", "com.apple.recovery.boot")))
        self.assertTrue(paths["usbmap"].endswith(os.path.join("SysReport", "USBMap.json")))


if __name__ == "__main__":
    unittest.main()
