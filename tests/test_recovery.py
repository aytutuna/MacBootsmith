import contextlib
import io
import json
import os
import tempfile
import unittest

import repo_path  # noqa: F401
from Scripts import macrecovery
from Scripts import recovery_fetcher
from Scripts.datasets import recovery_boards


class BoardDataTest(unittest.TestCase):
    def test_entries_are_well_formed(self):
        self.assertTrue(recovery_boards.data)
        for key, board in recovery_boards.data.items():
            self.assertIsInstance(key, int)
            self.assertTrue(17 <= key <= 25, key)
            self.assertRegex(board["board_id"], r"^Mac-[0-9A-F]{16}$")
            self.assertIn(board["os_type"], ("default", "latest"))

    def test_get_board(self):
        fetcher = recovery_fetcher.RecoveryFetcher()
        self.assertEqual(fetcher.get_board("24.99.99"), recovery_boards.data[24])
        self.assertEqual(fetcher.get_board("24.99.99")["name"], "macOS Sequoia")
        self.assertIsNone(fetcher.get_board("garbage"))


class MarkerTest(unittest.TestCase):
    def setUp(self):
        self.fetcher = recovery_fetcher.RecoveryFetcher()
        self.board = recovery_boards.data[24]
        self.original_verify = macrecovery.verify_image
        self.original_session = macrecovery.get_session
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = os.path.join(self.tmp.name, self.fetcher.recovery_folder_name)
        os.makedirs(self.dir)

    def tearDown(self):
        macrecovery.verify_image = self.original_verify
        macrecovery.get_session = self.original_session
        self.tmp.cleanup()

    def populate(self, board_id=None):
        for name in ("BaseSystem.dmg", "BaseSystem.chunklist"):
            with open(os.path.join(self.dir, name), "wb") as f:
                f.write(b"x")
        with open(os.path.join(self.dir, "recovery.json"), "w") as f:
            json.dump({"board_id": board_id or self.board["board_id"], "os_type": self.board["os_type"]}, f)

    def is_valid(self):
        with contextlib.redirect_stdout(io.StringIO()):
            return self.fetcher._is_valid(self.dir, self.board)

    def test_matching_marker_is_valid(self):
        macrecovery.verify_image = lambda dmg, cnk: None
        self.populate()
        self.assertTrue(self.is_valid())

    def test_different_board_is_invalid(self):
        macrecovery.verify_image = lambda dmg, cnk: None
        self.populate(board_id="Mac-0000000000000000")
        self.assertFalse(self.is_valid())

    def test_failing_verify_is_invalid(self):
        def fail(dmg, cnk):
            raise ValueError("bad chunklist")
        macrecovery.verify_image = fail
        self.populate()
        self.assertFalse(self.is_valid())

    def test_missing_files_are_invalid(self):
        macrecovery.verify_image = lambda dmg, cnk: None
        self.assertFalse(self.is_valid())

    def test_download_failure_returns_none_and_leaves_no_files(self):
        def boom(args):
            raise OSError("no network")
        macrecovery.get_session = boom
        with contextlib.redirect_stdout(io.StringIO()):
            result = self.fetcher.download("24.0.0", self.tmp.name)
        self.assertIsNone(result)
        for name in ("BaseSystem.dmg", "BaseSystem.chunklist", "recovery.json"):
            self.assertFalse(os.path.exists(os.path.join(self.dir, name)), name)


if __name__ == "__main__":
    unittest.main()
