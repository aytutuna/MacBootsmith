import contextlib
import importlib.util
import io
import os
import re
import subprocess
import sys
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from repo_path import FIXTURES
from repo_path import REPO_ROOT

from Scripts import utils

try:
    import tkinter
    TK_IMPORT_ERROR = None
except ImportError as error:
    tkinter = None
    TK_IMPORT_ERROR = error

TK_SKIP_REASON = None


def tk_skip_reason():
    global TK_SKIP_REASON
    if TK_SKIP_REASON is not None:
        return TK_SKIP_REASON or None
    if tkinter is None:
        TK_SKIP_REASON = "tkinter is not available: {}".format(TK_IMPORT_ERROR)
        return TK_SKIP_REASON
    try:
        root = tkinter.Tk()
        root.withdraw()
        root.destroy()
        TK_SKIP_REASON = ""
    except tkinter.TclError as error:
        TK_SKIP_REASON = "Tk cannot open a display: {}".format(error)
    return TK_SKIP_REASON or None


class TkTestCase(unittest.TestCase):
    def setUp(self):
        reason = tk_skip_reason()
        if reason:
            self.skipTest(reason)
        from Scripts.gui import app as app_module
        self.app_module = app_module

    def make_app(self, **kwargs):
        kwargs.setdefault("autostart", False)
        app = self.app_module.MacBootsmithApp(**kwargs)
        app.withdraw()
        self.addCleanup(self.destroy, app)
        return app

    def destroy(self, app):
        try:
            if not app.closing:
                app.destroy()
        except tkinter.TclError:
            pass

    def pump(self, app, condition, timeout=20):
        deadline = time.time() + timeout
        while time.time() < deadline:
            app.update()
            if condition():
                return True
            time.sleep(0.02)
        return False


class AppSmokeTest(TkTestCase):
    def test_builds_and_visits_every_page(self):
        from Scripts.gui import pages
        app = self.make_app(install_hooks=False)
        self.assertEqual(len(app.pages), len(pages.PAGE_CLASSES))
        self.assertEqual([page.title for page in app.pages],
                         ["Welcome", "Hardware", "macOS version", "Options", "USB mapping", "Build", "Recovery", "USB", "Post-install", "Finish"])
        for index in range(len(app.pages)):
            app.show_page(index)
            app.update_idletasks()
            self.assertEqual(app.index, index)
            self.assertTrue(str(app.step_labels[index].cget("text")).startswith(">"))
        self.assertEqual(str(app.next_button.cget("text")), "Close")
        self.assertFalse(app.runner.busy())
        app.destroy()
        self.assertTrue(app.closing)

    def test_next_is_gated_until_a_report_is_loaded(self):
        app = self.make_app(install_hooks=False)
        app.show_page(1)
        self.assertTrue(app.next_button.instate(["disabled"]))
        app.show_page(0)
        self.assertFalse(app.next_button.instate(["disabled"]))

    def test_theme_is_vista_or_clam_when_available(self):
        app = self.make_app(install_hooks=False)
        names = app.style.theme_names()
        expected = "vista" if "vista" in names else "clam" if "clam" in names else None
        if expected:
            self.assertEqual(app.style.theme_use(), expected)

    def test_hooks_are_installed_and_removed(self):
        app = self.make_app()
        self.assertIs(utils.Utils.prompt_handler, app.broker)
        self.assertIsInstance(sys.stdout, utils.OutputProxy)
        app.destroy()
        self.assertIsNone(utils.Utils.prompt_handler)
        self.assertIsNone(utils.Utils.output_sink)
        self.assertIsNone(utils.Utils.progress_handler)

    def test_stage_prompt_opens_a_dialog_and_returns_the_answer(self):
        app = self.make_app()
        results = []
        app.run_stage("Asking", lambda: (print("1. First\n2. Second"), utils.Utils().request_input("Select an option (default: 1): "))[1], on_done=results.append)
        self.assertTrue(self.pump(app, lambda: bool(app.dialogs)), "the prompt dialog did not open")
        dialog = app.dialogs[0]
        self.assertEqual(dialog.request.choices, [("1. First", "1"), ("2. Second", "2")])
        dialog.submit("2")
        self.assertTrue(self.pump(app, lambda: bool(results)), "the stage did not finish")
        self.assertEqual(results, ["2"])
        self.assertIn("Select an option (default: 1): 2", app.log.get("1.0", "end"))
        self.assertFalse(app.runner.busy())

    def test_cancel_stops_the_stage_with_gui_exit(self):
        app = self.make_app()
        stopped = []
        app.run_stage("Asking", lambda: utils.Utils().request_input("Type ERASE to continue: "), on_stopped=lambda reason, text: stopped.append(reason))
        self.assertTrue(self.pump(app, lambda: bool(app.dialogs)))
        app.cancel_stage()
        self.assertTrue(self.pump(app, lambda: bool(stopped)))
        self.assertEqual(stopped, ["cancel"])
        self.assertFalse(app.dialogs)

    def test_log_pane_handles_colour_and_carriage_returns(self):
        app = self.make_app(install_hooks=False)
        app.append_log("start\n\033[92mok\033[0m\n10%\r20%\r30%\n")
        content = app.log.get("1.0", "end-1c")
        self.assertEqual(content, "start\nok\n30%\n")
        self.assertIn("green", app.log.tag_names("2.0"))

    def test_hardware_page_loads_a_report_through_the_worker(self):
        app = self.make_app()
        hardware = app.pages[1]
        app.show_page(1)
        done = []
        app.run_stage("Loading", lambda: app.session.load_report(os.path.join(FIXTURES, "desktop", "Report.json")),
                      on_done=lambda verdict: (hardware.show_verdict(verdict), done.append(True)))
        self.assertTrue(self.pump(app, lambda: bool(done), timeout=120), "the report did not load")
        self.assertTrue(hardware.table.get_children())
        self.assertFalse(app.next_button.instate(["disabled"]))
        app.show_page(2)
        self.assertEqual(app.pages[2].selected(), app.session.default_macos())


class SelfTestFlagTest(TkTestCase):
    def test_launcher_self_test_opens_and_closes(self):
        script = os.path.join(REPO_ROOT, "MacBootsmith.py")
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        result = subprocess.run([sys.executable, script, "--self-test"], capture_output=True, text=True, encoding="utf-8", env=env, timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Self-test: visited 10 pages", result.stdout)


class LauncherFilesTest(unittest.TestCase):
    def read(self, name):
        with open(os.path.join(REPO_ROOT, name), "r", encoding="utf-8") as handle:
            return handle.read()

    def test_batch_file_is_well_formed(self):
        text = self.read("MacBootsmith.bat")
        lines = text.splitlines()
        self.assertEqual(lines[0].strip().lower(), "@echo off")
        self.assertIn('set "script=!thisDir!MacBootsmith.py"', text)
        self.assertIn('start "" "!pydir!pythonw.exe" "!script!"', text)
        self.assertIn('"!py3path!" "!script!" %*', text)
        self.assertEqual(text.count("("), text.count(")"))
        labels = {line.strip()[1:].split()[0].lower() for line in lines if line.strip().startswith(":") and not line.strip().startswith("::")}
        targets = {target.lower() for target in re.findall(r"(?:call|goto)\s+:(\w+)", text, re.IGNORECASE)}
        targets.discard("eof")
        self.assertTrue(targets)
        self.assertTrue(targets <= labels, targets - labels)
        for line in lines:
            if line.strip().lower().startswith("rem"):
                continue
            self.assertEqual(line.count('"') % 2, 0, line)

    def test_old_entry_points_are_gone(self):
        for name in ("OpCore-Simplify.py", "OpCore-Simplify.bat", "MacBootsmith.pyw", "MacBootsmith-GUI.bat", "updater.py"):
            self.assertFalse(os.path.exists(os.path.join(REPO_ROOT, name)), name)

    def test_entry_routes_headless_and_never_imports_pyinstaller(self):
        text = self.read("MacBootsmith.py")
        self.assertIn("--headless", text)
        self.assertIn("--self-test", self.read(os.path.join("Scripts", "gui", "app.py")))
        for root, _, files in os.walk(os.path.join(REPO_ROOT, "Scripts")):
            for name in files:
                if name.endswith(".py"):
                    with open(os.path.join(root, name), "r", encoding="utf-8") as handle:
                        self.assertNotIn("import PyInstaller", handle.read(), name)
        self.assertNotIn("PyInstaller", text)

    def test_entry_analyzes_a_log(self):
        script = os.path.join(REPO_ROOT, "MacBootsmith.py")
        sample = os.path.join(FIXTURES, "boot_logs", "ci-serial-sample.txt")
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        result = subprocess.run([sys.executable, script, "--analyze-log", sample], capture_output=True, text=True, encoding="utf-8", env=env, timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Reached the boot picker", result.stdout)

    def test_spec_bundles_the_read_only_data(self):
        text = self.read(os.path.join("packaging", "macbootsmith.spec"))
        self.assertNotIn("OpCore", text)
        self.assertNotIn("updater", text)
        self.assertIn('[os.path.join(ROOT, "MacBootsmith.py")]', text)
        for needle in ('data("MacBootsmith.py", ".")', "usb_enum.cs", "background_picker.icns", "docs", "console=False", 'name="MacBootsmith"', "COLLECT("):
            self.assertIn(needle, text)


class EntryPointTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("macbootsmith_entry_test", os.path.join(REPO_ROOT, "MacBootsmith.py"))
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)

    def route(self, argv):
        with mock.patch.object(self.module, "run_terminal", return_value="menu"):
            with contextlib.redirect_stdout(io.StringIO()) as output:
                return self.module.main(argv), output.getvalue()

    def test_terminal_and_dry_run_flags_open_the_menu(self):
        self.assertEqual(self.route(["--terminal"])[0], "menu")
        self.assertEqual(self.route(["--dry-run-usb"])[0], "menu")

    def test_missing_tkinter_falls_back_to_the_menu(self):
        with mock.patch.dict(sys.modules, {"tkinter": None}):
            result, output = self.route([])
        self.assertEqual(result, "menu")
        self.assertIn("tkinter is not available", output)

    def test_terminal_menu_exits_when_stdin_closes(self):
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        result = subprocess.run([sys.executable, os.path.join(REPO_ROOT, "MacBootsmith.py"), "--terminal"], stdin=subprocess.DEVNULL,
                                capture_output=True, text=True, encoding="utf-8", env=env, timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(" MacBootsmith ", result.stdout)
        self.assertIn("Q. Quit", result.stdout)
        self.assertNotIn("OpCore", result.stdout)


if __name__ == "__main__":
    unittest.main()
