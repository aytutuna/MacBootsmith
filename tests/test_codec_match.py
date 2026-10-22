import contextlib
import copy
import io
import json
import os
import unittest
from unittest import mock

from repo_path import FIXTURES
from Scripts import codec_match
from Scripts import config_prodigy
from Scripts import utils
from Scripts.datasets import codec_layouts
from Scripts.gui import session as session_module

Layout = codec_layouts.Layout


class TokenTest(unittest.TestCase):
    def test_vendor_prefixes_are_dropped(self):
        self.assertEqual(codec_match.board_tokens("ASUS PRIME Z490-A"), ["PRIME", "Z490", "A"])
        self.assertEqual(codec_match.model_token("ASUS PRIME Z490-A"), "Z490")
        self.assertEqual(codec_match.board_tokens("Micro-Star MS-7C75"), ["MS", "7C75"])
        self.assertEqual(codec_match.model_token("Micro-Star MS-7C75"), "7C75")
        self.assertEqual(codec_match.board_tokens("Dell Inc. Latitude 7490"), ["LATITUDE", "7490"])
        self.assertEqual(codec_match.model_token("Dell Inc. Latitude 7490"), "7490")
        self.assertEqual(codec_match.model_token("ASUSTeK COMPUTER INC. ZenBook UX430UA"), "UX430UA")
        self.assertIsNone(codec_match.model_token("PRIME A"))
        self.assertIsNone(codec_match.model_token(None))

    def test_sub_brands_stay_in_the_board_tokens(self):
        self.assertEqual(codec_match.board_tokens("Z490 AORUS ELITE"), ["Z490", "AORUS", "ELITE"])

    def test_vendors_in_names_and_comments(self):
        self.assertEqual(codec_match.vendors("Micro-Star MS-7C75"), {"MSI"})
        self.assertEqual(codec_match.vendors("Dell Inc. Latitude 7490"), {"Dell"})
        self.assertEqual(codec_match.vendors("MacPeet- ALC1220 for Z390 Aorus Ultra - Output SP/HP Manualmode"), {"Gigabyte"})
        self.assertEqual(codec_match.vendors("Creative CA0132, 2.0 front HP + Mic"), set())
        self.assertEqual(codec_match.vendors("Damon - Realtek ALC 295 for HP Envy x360"), {"HP"})

    def test_vendor_glued_to_the_model(self):
        self.assertIn("7570", codec_match.tokens("DalianSky - Realtek ALC295/ALC3254 Dell7570"))
        self.assertNotIn("TEK", codec_match.tokens("ASUSTeK"))

    def test_vendor_from_subsystem(self):
        self.assertEqual(codec_match.subsystem_vendor("1458A0C3"), "Gigabyte")
        self.assertEqual(codec_match.subsystem_vendor("17aa3907"), "Lenovo")
        self.assertIsNone(codec_match.subsystem_vendor("10DE0000"))
        self.assertIsNone(codec_match.subsystem_vendor(None))
        self.assertEqual(codec_match.board_vendors("Z490 AORUS ELITE", "1458A0C3"), {"Gigabyte"})
        self.assertEqual(codec_match.board_vendors("ASUS PRIME Z490-A", "1458A0C3"), {"ASUS", "Gigabyte"})


class RankTest(unittest.TestCase):
    def test_exact_board_is_made_for_it(self):
        ranked = codec_match.rank_layouts(codec_layouts.data["10EC-0897"], "Z590M", "1458A194")
        layout, score, reason = ranked[0]
        self.assertEqual((layout.id, score), (11, 4))
        self.assertEqual(reason, "made for GIGABYTE Z590M")
        self.assertEqual(ranked[1][1], 2)

    def test_comment_naming_every_board_word_is_exact(self):
        layouts = [Layout(1, "Toleda - Realtek ALC1220"), Layout(17, "NIBLIZE - ALC1220 for Gigabyte Z490 Vision G"),
                   Layout(40, "Custom ALC1220 for Gigabyte Z490 Aorus Elite")]
        layout, score, reason = codec_match.rank_layouts(layouts, "Z490 AORUS ELITE", "1458A0C3")[0]
        self.assertEqual((layout.id, score, reason), (40, 4, "made for Gigabyte Z490 Aorus Elite"))

    def test_laptop_model_number_is_exact(self):
        layout, score, reason = codec_match.rank_layouts(codec_layouts.data["10EC-0295"], "ASUSTeK COMPUTER INC. UX430UA", "10431234")[0]
        self.assertEqual((layout.id, score, reason), (14, 4, "made for ASUS UX430UA"))

    def test_same_chipset_is_only_similar(self):
        ranked = codec_match.rank_layouts(codec_layouts.data["10EC-1220"], "Z490 AORUS ELITE", "1458A0C3")
        self.assertEqual([(layout.id, score) for layout, score, _ in ranked[:3]], [(18, 3), (1, 1), (17, 3)])
        self.assertEqual(ranked[0][2], "made for Gigabyte Z490 Aorus Master, a similar Gigabyte Z490 board; try the others if a jack is dead")
        self.assertEqual(ranked[1][2], "a trusted general layout")

    def test_another_vendors_board_is_not_similar(self):
        layouts = [Layout(1, "Toleda - Realtek ALC1220"), Layout(2, "ALC1220 for ASUS Z490 Hero")]
        ranked = codec_match.rank_layouts(layouts, "Z490 AORUS ELITE", "1458A0C3")
        self.assertEqual([(layout.id, score) for layout, score, _ in ranked], [(1, 1), (2, 0)])

    def test_single_letter_suffix_counts(self):
        layouts = [Layout(1, "Toleda - Realtek ALC1220"), Layout(2, "ALC1220 for ASUS Prime Z490-P")]
        self.assertEqual(codec_match.rank_layouts(layouts, "ASUS PRIME Z490-A", "10431234")[0][1], 3)
        layouts.append(Layout(3, "ALC1220 for ASUS Prime Z490-A"))
        self.assertEqual(codec_match.rank_layouts(layouts, "ASUS PRIME Z490-A", "10431234")[0][:2], (layouts[2], 4))

    def test_laptop_model_that_looks_like_a_chipset(self):
        board = "LENOVO ThinkPad T480"
        layout, score, reason = codec_match.rank_layouts([Layout(1, "Mirone - ALC257"), Layout(2, "ALC257 for Lenovo T480")], board, "17AA1234", "Laptop")[0]
        self.assertEqual((layout.id, score, reason), (2, 4, "made for Lenovo T480"))
        ranked = codec_match.rank_layouts([Layout(2, "ALC257 for Lenovo T480 and T580")], board, "17AA1234", "Laptop")
        self.assertEqual(ranked[0][1], 3)
        self.assertEqual(codec_match.rank_layouts([Layout(2, "ALC257 for Lenovo T480")], board, "17AA1234", "Desktop")[0][1], 3)

    def test_same_maker_laptop_ranks_below_the_trusted_layout(self):
        ranked = codec_match.rank_layouts(codec_layouts.data["10EC-0295"], "Dell Inc. 0XYZ12", "10280000", "Laptop")
        self.assertEqual((ranked[0][0].id, ranked[0][1]), (3, 1))
        self.assertEqual(ranked[0][2], "a trusted general layout; no layout names your board")
        laptop = next(reason for _, score, reason in ranked if score == 2)
        self.assertEqual(laptop, "made for another Dell laptop; no layout names your model")

    def test_subsystem_alone_does_not_pick_a_maker_layout(self):
        ranked = codec_match.rank_layouts(codec_layouts.data["10EC-1220"], None, "1458A0C3", "Desktop")
        self.assertEqual((ranked[0][0].id, ranked[0][1]), (1, 1))

    def test_no_match_keeps_the_trusted_default(self):
        layouts = codec_layouts.data["10EC-1220"]
        ranked = codec_match.rank_layouts(layouts, "X570 TAICHI", "18491220")
        self.assertEqual(ranked[0][0].id, 1)
        self.assertEqual(ranked[0][2], "a trusted general layout; no layout names your board")

    def test_same_maker_without_the_model(self):
        ranked = codec_match.rank_layouts(codec_layouts.data["10EC-0295"], "Dell Inc. 0XYZ12", "10280000")
        self.assertEqual(ranked[0][1], 2)
        self.assertEqual(ranked[0][2], "made for another Dell board; no layout names your model")

    def test_sort_is_stable(self):
        layouts = [Layout(5, "Generic"), Layout(2, "Toleda one"), Layout(9, "Other"), Layout(1, "Mirone two"), Layout(3, "Plain")]
        ranked = codec_match.rank_layouts(layouts, "", None)
        self.assertEqual([layout.id for layout, _, _ in ranked], [2, 1, 5, 9, 3])
        ranked = codec_match.rank_layouts([Layout(4, "A"), Layout(2, "B")], "", None)
        self.assertEqual([layout.id for layout, _, _ in ranked], [4, 2])
        self.assertTrue(ranked[0][2].startswith("the first layout listed"))
        self.assertEqual(ranked[1][2], "")


class SelectLayoutTest(unittest.TestCase):
    def select(self, report, answer=""):
        prodigy = config_prodigy.ConfigProdigy()
        with mock.patch.object(utils.Utils, "request_input", return_value=answer), \
             mock.patch.object(utils.Utils, "adjust_window_size"), mock.patch.object(utils.Utils, "head"):
            with contextlib.redirect_stdout(io.StringIO()) as output:
                layout_id, _ = prodigy.select_audio_codec_layout(report)
        return prodigy, layout_id, output.getvalue()

    def report(self, board):
        return {"Motherboard": {"Name": board}, "Sound": {"Realtek": {"Device ID": "10EC-0897", "Subsystem ID": "1458A194"}}}

    def test_default_follows_the_board(self):
        prodigy, layout_id, output = self.select(self.report("Z590M"))
        self.assertEqual(layout_id, 11)
        self.assertIn("Default layout 11: made for GIGABYTE Z590M", output)
        self.assertEqual(prodigy.layout_reason, "made for GIGABYTE Z590M")

    def test_similar_board_wording_reaches_the_summary(self):
        report = {"Motherboard": {"Name": "Z490 AORUS ELITE"}, "Sound": {"Realtek": {"Device ID": "10EC-1220", "Subsystem ID": "1458A0C3"}}}
        prodigy, layout_id, output = self.select(report)
        similar = "made for Gigabyte Z490 Aorus Master, a similar Gigabyte Z490 board; try the others if a jack is dead"
        self.assertEqual(layout_id, 18)
        self.assertIn("Default layout 18: " + similar, output)
        utils.Utils.decisions = [("codec_layout", "", "Enter the ID of the codec layout you want to use (default: 18): ")]
        self.addCleanup(setattr, utils.Utils, "decisions", [])
        self.assertEqual(utils.Utils.decision_lines({"codec_layout": prodigy.layout_reason}),
                         ["Codec layout ID: the default layout (18). M" + similar[1:] + "."])

    def test_desktop_fixture_without_a_board_name_keeps_layout_1(self):
        with open(os.path.join(FIXTURES, "desktop", "Report.json"), encoding="utf-8") as handle:
            report = json.load(handle)
        report = copy.deepcopy(report)
        del report["Motherboard"]["Name"]
        prodigy, layout_id, output = self.select(report)
        self.assertEqual(layout_id, 1)
        self.assertIn("Default layout 1: a trusted general layout; no layout names your board", output)

    def test_picked_layout_keeps_its_own_reason(self):
        prodigy, layout_id, _ = self.select(self.report("Z590M"), "13")
        self.assertEqual(layout_id, 13)
        self.assertIsNone(prodigy.layout_reason)


class ExpressReasonTest(unittest.TestCase):
    def test_summary_line_carries_the_reason(self):
        from test_gui_session import ExpressTest
        case = ExpressTest("test_full_chain_order_and_summary")
        case.setUp()
        self.addCleanup(case.doCleanups)
        session = case.session
        session.defaults_hook = utils.Utils.set_accept_defaults

        def configure():
            utils.Utils().request_input("Enter the ID of the codec layout you want to use (default: 11): ")
            case.ocpe.co.layout_reason = "made for GIGABYTE Z590M"

        case.configure_hook = configure
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                summary = session.express("report.json")
        finally:
            utils.Utils.set_accept_defaults(False)
        self.assertEqual(summary["decisions"], ["Codec layout ID: the default layout (11). Made for GIGABYTE Z590M."])
        self.assertIn("  - Codec layout ID: the default layout (11). Made for GIGABYTE Z590M.", session_module.summary_lines(summary))

    def test_without_a_reason_the_generic_text_stays(self):
        utils.Utils.decisions = [("codec_layout", "", "Enter the ID of the codec layout you want to use (default: 3): ")]
        self.addCleanup(setattr, utils.Utils, "decisions", [])
        self.assertEqual(utils.Utils.decision_lines({"codec_layout": None}),
                         ["Codec layout ID: the default layout (3). First install. It is right most of the time."])


if __name__ == "__main__":
    unittest.main()
