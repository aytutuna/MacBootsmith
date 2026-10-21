import contextlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from Scripts import utils


def load_main_module():
    spec = importlib.util.spec_from_file_location("opcore_simplify_main", os.path.join(REPO_ROOT, "OpCore-Simplify.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class HeadlessUtilsTest(unittest.TestCase):
    def tearDown(self):
        utils.Utils.set_headless(None)

    def ask(self, prompt):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            answer = utils.Utils().request_input(prompt)
        return answer, output.getvalue()

    def test_first_matching_key_wins_case_insensitive(self):
        utils.Utils.set_headless({"prompts": {"AUDIO KEXT": "2", "kext": "9"}, "default": "x"})
        answer, output = self.ask("Select audio kext for your system: ")
        self.assertEqual(answer, "2")
        self.assertIn("Select audio kext for your system: 2", output)

    def test_unmatched_prompt_uses_default_and_logs_it(self):
        utils.Utils.set_headless({"prompts": {"audio": "2"}, "default": "fallback"})
        answer, output = self.ask("Something else: ")
        self.assertEqual(answer, "fallback")
        self.assertIn("Something else: fallback", output)

    def test_missing_default_is_empty_string(self):
        utils.Utils.set_headless({})
        answer, _ = self.ask("Press Enter to continue...")
        self.assertEqual(answer, "")

    def test_repeated_prompt_raises(self):
        utils.Utils.set_headless({"prompts": {}, "default": "bad"})
        with self.assertRaises(utils.HeadlessPromptLoop):
            for _ in range(utils.Utils.headless_repeat_limit + 1):
                self.ask("Select an option: ")

    def test_exit_program_raises_instead_of_exiting(self):
        utils.Utils.set_headless({})
        with self.assertRaises(utils.HeadlessExit):
            utils.Utils().exit_program()

    def test_head_does_not_clear_screen(self):
        utils.Utils.set_headless({})
        with contextlib.redirect_stdout(io.StringIO()) as output:
            utils.Utils().head("Title")
        self.assertIn("== Title ==", output.getvalue())
        self.assertNotIn("\033[8;", output.getvalue())

    def test_interactive_mode_is_default(self):
        self.assertFalse(utils.Utils.is_headless())


class HeadlessRunTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.main = load_main_module()

    def tearDown(self):
        utils.Utils.set_headless(None)

    def run_answers(self, answers):
        with tempfile.TemporaryDirectory() as temp_dir:
            answers_path = os.path.join(temp_dir, "answers.json")
            with open(answers_path, "w", encoding="utf-8") as answers_file:
                json.dump(answers, answers_file)
            with contextlib.redirect_stdout(io.StringIO()) as output:
                exit_code = self.main.run_headless(answers_path)
        return exit_code, output.getvalue()

    def test_marketing_name_resolution(self):
        ocpe = self.main.OCPE.__new__(self.main.OCPE)
        self.assertEqual(ocpe.resolve_headless_macos_version("25.0.0"), "25.0.0")
        self.assertEqual(ocpe.resolve_headless_macos_version("Tahoe"), "25")
        self.assertEqual(ocpe.resolve_headless_macos_version("macOS Sequoia"), "24")
        self.assertEqual(ocpe.resolve_headless_macos_version("Sonoma 14"), "23")
        with self.assertRaises(Exception):
            ocpe.resolve_headless_macos_version("Cheetah")

    def test_missing_answers_file_returns_1(self):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            exit_code = self.main.run_headless(os.path.join(REPO_ROOT, "tests", "fixtures", "does-not-exist.json"))
        self.assertEqual(exit_code, 1)
        self.assertIn("Traceback", output.getvalue())

    def test_unsupported_version_returns_3(self):
        exit_code, output = self.run_answers({
            "report": "tests/fixtures/desktop/Report.json",
            "macos_version": "16.0.0",
            "prompts": {},
            "default": ""
        })
        self.assertEqual(exit_code, 3, output)
        self.assertIn("outside the supported range", output)

    def test_unsupported_gpu_returns_3(self):
        exit_code, output = self.run_answers({
            "report": "tests/fixtures/laptop/Report.json",
            "macos_version": "25.0.0",
            "prompts": {},
            "default": ""
        })
        self.assertEqual(exit_code, 3, output)
        self.assertIn("not compatible with macOS", output)


if __name__ == "__main__":
    unittest.main()
