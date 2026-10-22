import contextlib
import io
import os
import queue
import sys
import threading
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import repo_path  # noqa: F401

from Scripts import utils
from Scripts.gui import broker


class SeamTestCase(unittest.TestCase):
    def setUp(self):
        self.restore = utils.Utils.install_output_proxy()
        self.output = []
        utils.Utils.set_output_sink(self.output.append)

    def tearDown(self):
        utils.Utils.set_prompt_handler(None)
        utils.Utils.set_progress_handler(None)
        utils.Utils.set_output_sink(None)
        utils.Utils.set_headless(None)
        self.restore()

    def text(self):
        return "".join(self.output)


class PromptHandlerSeamTest(SeamTestCase):
    def test_handler_gets_prompt_and_captured_text_and_its_answer_is_returned(self):
        calls = []

        def handler(prompt, captured):
            calls.append((prompt, captured))
            return "2"

        utils.Utils.set_prompt_handler(handler)
        print("Choose a kext:")
        print("\033[1m1. AppleALC + OCLP\033[0m")
        print("2. AppleALC + SimpleHDA")
        answer = utils.Utils().request_input("Select audio kext for your system: ")

        self.assertEqual(answer, "2")
        self.assertEqual(len(calls), 1)
        prompt, captured = calls[0]
        self.assertEqual(prompt, "Select audio kext for your system: ")
        self.assertIn("1. AppleALC + OCLP", captured)
        self.assertIn("2. AppleALC + SimpleHDA", captured)
        self.assertNotIn("\033[", captured)
        self.assertIn("Select audio kext for your system: 2", self.text())

    def test_captured_text_only_covers_output_since_the_previous_prompt(self):
        seen = []
        utils.Utils.set_prompt_handler(lambda prompt, captured: seen.append(captured) or "")
        print("first screen")
        utils.Utils().request_input("One: ")
        print("second screen")
        utils.Utils().request_input("Two: ")
        self.assertIn("first screen", seen[0])
        self.assertIn("second screen", seen[1])
        self.assertNotIn("first screen", seen[1])
        self.assertNotIn("One: ", seen[1])

    def test_none_answer_becomes_empty_string(self):
        utils.Utils.set_prompt_handler(lambda prompt, captured: None)
        self.assertEqual(utils.Utils().request_input("Anything: "), "")
        self.assertIn("Anything: [Enter]", self.text())

    def test_head_prints_plain_heading_and_starts_a_new_screen(self):
        seen = []
        utils.Utils.set_prompt_handler(lambda prompt, captured: seen.append(captured) or "")
        print("stale text")
        with mock.patch.object(utils.os, "system", side_effect=AssertionError("screen must not be cleared")):
            utils.Utils().head("Select macOS Version")
        utils.Utils().request_input("Version: ")
        self.assertIn("== Select macOS Version ==", self.text())
        self.assertNotIn("\033[8;", self.text())
        self.assertNotIn("stale text", seen[0])
        self.assertIn("== Select macOS Version ==", seen[0])

    def test_window_and_folder_calls_are_no_ops(self):
        utils.Utils.set_prompt_handler(lambda prompt, captured: "")
        with mock.patch.object(utils.subprocess, "run", side_effect=AssertionError("no folder opening")):
            utils.Utils().open_folder(os.getcwd())
            utils.Utils().adjust_window_size("text")
        self.assertNotIn("\033[8;", self.text())

    def test_exit_program_raises_gui_exit(self):
        utils.Utils.set_prompt_handler(lambda prompt, captured: "")
        with self.assertRaises(utils.GuiExit) as raised:
            utils.Utils().exit_program()
        self.assertEqual(raised.exception.reason, "exit")
        self.assertTrue(issubclass(utils.GuiExit, BaseException))
        self.assertFalse(issubclass(utils.GuiExit, Exception))

    def test_handler_raising_gui_exit_propagates_through_request_input(self):
        def handler(prompt, captured):
            raise utils.GuiExit("Cancelled", reason="cancel")

        utils.Utils.set_prompt_handler(handler)
        with self.assertRaises(utils.GuiExit) as raised:
            utils.Utils().request_input("Select: ")
        self.assertEqual(raised.exception.reason, "cancel")

    def test_headless_answers_take_precedence_over_the_handler(self):
        utils.Utils.set_prompt_handler(lambda prompt, captured: self.fail("handler must not be used in headless mode"))
        utils.Utils.set_headless({"prompts": {"audio": "2"}, "default": ""})
        self.assertEqual(utils.Utils().request_input("Select audio kext: "), "2")
        with self.assertRaises(utils.HeadlessExit):
            utils.Utils().exit_program()

    def test_progress_handler_receives_steps_without_clearing_the_screen(self):
        events = []
        utils.Utils.set_progress_handler(lambda *args: events.append(args))
        with mock.patch.object(utils.os, "system", side_effect=AssertionError("screen must not be cleared")):
            utils.Utils().progress_bar("Building", ["One", "Two"], 1)
            utils.Utils().progress_bar("Building", ["One", "Two"], 2, done=True)
        self.assertEqual(events[0], ("Building", ["One", "Two"], 1, False))
        self.assertTrue(events[1][3])
        self.assertIn("[2/2] Two...", self.text())


class InteractiveModeUnchangedTest(unittest.TestCase):
    def test_request_input_uses_input_when_no_handler_is_set(self):
        self.assertIsNone(utils.Utils.prompt_handler)
        self.assertFalse(utils.Utils.is_gui())
        with mock.patch("builtins.input", return_value="typed") as typed:
            self.assertEqual(utils.Utils().request_input("Select: "), "typed")
        typed.assert_called_once_with("Select: ")

    def test_head_still_clears_the_console_and_draws_the_box(self):
        with mock.patch.object(utils.os, "system") as system, contextlib.redirect_stdout(io.StringIO()) as output:
            utils.Utils().head("Title")
        system.assert_called_once()
        self.assertIn("╔", output.getvalue())
        self.assertIn("\033[8;", output.getvalue())

    def test_exit_program_still_exits(self):
        with mock.patch("builtins.input", return_value=""), mock.patch.object(utils.os, "system"), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit):
                utils.Utils().exit_program()


class OutputProxyTest(unittest.TestCase):
    def tearDown(self):
        utils.Utils.set_output_sink(None)
        utils.Utils.set_prompt_handler(None)

    def test_writes_go_to_the_console_when_no_sink_is_set(self):
        console = io.StringIO()
        proxy = utils.OutputProxy(console)
        proxy.write("hello\n")
        proxy.flush()
        self.assertEqual(console.getvalue(), "hello\n")

    def test_writes_go_to_the_sink_when_set(self):
        console = io.StringIO()
        received = []
        utils.Utils.set_output_sink(received.append)
        proxy = utils.OutputProxy(console)
        proxy.write("to the window\n")
        proxy.write(b"bytes too\n")
        self.assertEqual(console.getvalue(), "")
        self.assertEqual("".join(received), "to the window\nbytes too\n")
        self.assertFalse(proxy.isatty())

    def test_works_without_a_console_stream(self):
        proxy = utils.OutputProxy(None)
        self.assertEqual(proxy.write("ignored"), len("ignored"))
        proxy.flush()
        self.assertFalse(proxy.isatty())

    def test_capture_only_happens_while_a_handler_is_set(self):
        proxy = utils.OutputProxy(io.StringIO())
        proxy.write("before")
        utils.Utils.set_prompt_handler(lambda prompt, captured: "")
        proxy.write("during")
        self.assertEqual(utils.Utils.take_captured(), "during")

    def test_install_is_idempotent_and_restores(self):
        original = sys.stdout, sys.stderr
        restore = utils.Utils.install_output_proxy()
        try:
            self.assertIsInstance(sys.stdout, utils.OutputProxy)
            self.assertIsInstance(sys.stderr, utils.OutputProxy)
            first = sys.stdout
            inner = utils.Utils.install_output_proxy()
            self.assertIs(sys.stdout, first)
            inner()
            self.assertIs(sys.stdout, first)
        finally:
            restore()
        self.assertEqual((sys.stdout, sys.stderr), original)

    def test_print_reaches_sink_through_installed_proxy(self):
        received = []
        restore = utils.Utils.install_output_proxy()
        try:
            utils.Utils.set_output_sink(received.append)
            print("line one")
        finally:
            utils.Utils.set_output_sink(None)
            restore()
        self.assertEqual("".join(received), "line one\n")


class ChoiceParserTest(unittest.TestCase):
    def test_yes_no_variants(self):
        self.assertEqual(broker.parse_choices("Continue with OpenCore Legacy Patcher? (yes/No): "), [("Yes", "yes"), ("No", "no")])
        self.assertEqual(broker.parse_choices("Build EFI for UEFI? (Yes/no): "), [("Yes", "yes"), ("No", "no")])
        self.assertEqual(broker.parse_choices("Continue anyway? (y/N): "), [("Yes", "y"), ("No", "n")])

    def test_numbered_menu_lines_become_buttons(self):
        captured = "\n".join([
            "== Select macOS Version ==",
            "Available macOS versions:",
            "",
            "   24. macOS Sequoia 15",
            "   25. macOS Tahoe 26 (Requires OpenCore Legacy Patcher)",
            "",
            "Q. Quit",
        ])
        choices = broker.parse_choices("Please enter the macOS version you want to use (default: macOS Tahoe 26): ", captured)
        self.assertEqual([value for _, value in choices], ["24", "25", "Q"])
        self.assertTrue(choices[0][0].startswith("24. macOS Sequoia"))

    def test_menu_parsing_ignores_ansi_and_keeps_last_duplicate(self):
        captured = "\033[1m1.\033[0m Old\n1. New\n2. Other\n"
        choices = broker.parse_choices("Select an option: ", captured)
        self.assertEqual(choices, [("1. New", "1"), ("2. Other", "2")])

    def test_plain_prompt_has_no_buttons(self):
        self.assertEqual(broker.parse_choices("Enter the USB drive letter (for example E): ", "Some text\n"), [])

    def test_defaults_and_press_enter(self):
        self.assertEqual(broker.default_answer("Select Broadcom Wi-Fi option (default: 1): "), "1")
        self.assertIsNone(broker.default_answer("Select: "))
        self.assertTrue(broker.is_press_enter("Press Enter to continue..."))
        self.assertTrue(broker.is_press_enter("   Press Enter to go back..."))
        self.assertFalse(broker.is_press_enter("Type ERASE to continue: "))


class AnsiStreamTest(unittest.TestCase):
    def test_colours_and_split_escape_sequences(self):
        stream = broker.AnsiStream()
        segments = stream.feed("plain \033[92mgreen")
        segments += stream.feed(" still\033")
        segments += stream.feed("[0m back\033[8;30;100t")
        self.assertEqual("".join(text for text, _ in segments), "plain green still back")
        self.assertIn(("green", "green"), segments)
        self.assertIn((" still", "green"), segments)
        self.assertEqual(segments[-1], (" back", None))

    def test_last_percent(self):
        self.assertEqual(broker.last_percent("120.0/800.0 MB |===   | 15.0% downloaded"), 15.0)
        self.assertEqual(broker.last_percent("2.1 MB/s [####] 100% 3.0/3.0MB"), 100.0)
        self.assertIsNone(broker.last_percent("no progress here"))


class PromptBrokerTest(unittest.TestCase):
    def setUp(self):
        self.messages = queue.Queue()
        self.broker = broker.PromptBroker(self.messages.put)
        # automatic answers print their explanation; keep it out of the test output
        quiet = contextlib.redirect_stdout(io.StringIO())
        quiet.__enter__()
        self.addCleanup(quiet.__exit__, None, None, None)

    def test_press_enter_is_acknowledged_without_a_dialog(self):
        self.assertEqual(self.broker("Press Enter to continue...", "text"), "")
        self.assertTrue(self.messages.empty())

    def test_presets_answer_without_a_dialog_until_they_repeat(self):
        self.broker.set_presets({"Select audio kext": "2"})
        for _ in range(broker.PRESET_REPEAT_LIMIT):
            self.assertEqual(self.broker("Select audio kext for your system: ", ""), "2")
        self.assertTrue(self.messages.empty())

        def reply():
            kind, request = self.messages.get(timeout=5)
            self.assertEqual(kind, "prompt")
            request.reply("1")

        thread = threading.Thread(target=reply)
        thread.start()
        self.assertEqual(self.broker("Select audio kext for your system: ", "1. A\n2. B\n"), "1")
        thread.join(5)

    def test_prompt_request_carries_choices_and_waits_for_the_reply(self):
        def reply():
            kind, request = self.messages.get(timeout=5)
            self.assertEqual(request.choices, [("1. First", "1"), ("2. Second", "2")])
            self.assertEqual(request.default, "1")
            request.reply("2")

        thread = threading.Thread(target=reply)
        thread.start()
        self.assertEqual(self.broker("Pick one (default: 1): ", "1. First\n2. Second\n"), "2")
        thread.join(5)

    def test_cancel_while_waiting_raises_gui_exit(self):
        def cancel():
            self.messages.get(timeout=5)
            self.broker.cancel()

        thread = threading.Thread(target=cancel)
        thread.start()
        with self.assertRaises(utils.GuiExit) as raised:
            self.broker("Select an option: ", "1. A\n")
        thread.join(5)
        self.assertEqual(raised.exception.reason, "cancel")

    def test_cancel_stops_the_worker_at_its_next_output_only(self):
        self.broker.cancel()
        self.broker.sink("main thread output is never interrupted\n")
        errors = []

        def worker():
            self.broker.worker_ident = threading.get_ident()
            try:
                self.broker.sink("worker output\n")
            except utils.GuiExit as e:
                errors.append(e.reason)

        thread = threading.Thread(target=worker)
        thread.start()
        thread.join(5)
        self.assertEqual(errors, ["cancel"])

    def test_repeated_prompt_keeps_the_earlier_menu(self):
        requests = []

        def reply(count):
            for _ in range(count):
                kind, request = self.messages.get(timeout=5)
                requests.append(request)
                request.reply("x")

        thread = threading.Thread(target=reply, args=(2,))
        thread.start()
        self.broker("Select audio kext: ", "1. A\n2. B\n")
        self.broker("Select audio kext: ", "Invalid selection, please try again.\n")
        thread.join(5)
        self.assertIn("1. A", requests[1].captured)
        self.assertIn("Invalid selection", requests[1].captured)


class StageRunnerTest(unittest.TestCase):
    def run_stage(self, func):
        messages = queue.Queue()
        runner = broker.StageRunner(broker.PromptBroker(messages.put), messages.put)
        runner.start("stage", func)
        runner.thread.join(10)
        return messages.get(timeout=5)

    def test_done(self):
        message = self.run_stage(lambda: 42)
        self.assertEqual((message[0], message[2], message[3]), ("done", "stage", 42))

    def test_busy_until_the_result_is_consumed(self):
        messages = queue.Queue()
        runner = broker.StageRunner(broker.PromptBroker(messages.put), messages.put)
        token = runner.start("first", lambda: 1)
        runner.thread.join(10)
        self.assertTrue(runner.busy())
        self.assertIsNone(runner.start("second", lambda: 2))
        message = messages.get(timeout=5)
        runner.finish(message[1])
        self.assertEqual(message[1], token)
        self.assertFalse(runner.busy())
        self.assertIsNotNone(runner.start("second", lambda: 2))

    def test_error_carries_the_exception(self):
        def fail():
            raise ValueError("broken")
        message = self.run_stage(fail)
        self.assertEqual(message[0], "error")
        self.assertIsInstance(message[3], ValueError)
        self.assertIn("Traceback", message[4])

    def test_gui_exit_is_reported_as_stopped(self):
        def stop():
            raise utils.GuiExit("Cancelled", reason="cancel")
        message = self.run_stage(stop)
        self.assertEqual((message[0], message[3]), ("stopped", "cancel"))

    def test_worker_prompt_is_answered_from_another_thread(self):
        messages = queue.Queue()
        prompt_broker = broker.PromptBroker(messages.put)
        runner = broker.StageRunner(prompt_broker, messages.put)
        restore = utils.Utils.install_output_proxy()
        utils.Utils.set_output_sink(prompt_broker.sink)
        utils.Utils.set_prompt_handler(prompt_broker)
        try:
            runner.start("ask", lambda: utils.Utils().request_input("Continue? (yes/No): "))
            result = None
            while result is None:
                message = messages.get(timeout=10)
                if message[0] == "prompt":
                    message[1].reply("yes")
                elif message[0] == "done":
                    result = message[3]
            self.assertEqual(result, "yes")
        finally:
            utils.Utils.set_prompt_handler(None)
            utils.Utils.set_output_sink(None)
            restore()


if __name__ == "__main__":
    unittest.main()
