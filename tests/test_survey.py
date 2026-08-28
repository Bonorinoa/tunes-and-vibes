"""WHO-5 parser + store. Never touches the live panel DB."""

from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import survey  # noqa: E402
from schema import init  # noqa: E402


class ParseTests(unittest.TestCase):
    def test_valid_spaces(self) -> None:
        items, issue = survey.parse_reply("4 4 3 4 5")
        self.assertEqual(items, [4, 4, 3, 4, 5])
        self.assertEqual(issue, "")

    def test_valid_commas(self) -> None:
        items, _ = survey.parse_reply("4,4,3,4,5")
        self.assertEqual(items, [4, 4, 3, 4, 5])

    def test_mixed_separators(self) -> None:
        items, _ = survey.parse_reply("4, 4 3;4|5")
        self.assertEqual(items, [4, 4, 3, 4, 5])

    def test_out_of_range(self) -> None:
        items, issue = survey.parse_reply("6 4 3 4 5")
        self.assertIsNone(items)
        self.assertIn("out of range", issue)

    def test_wrong_count(self) -> None:
        items, _ = survey.parse_reply("4 4 3 4")
        self.assertIsNone(items)

    def test_non_numeric(self) -> None:
        items, _ = survey.parse_reply("4 4 x 4 5")
        self.assertIsNone(items)

    def test_week_start_is_monday(self) -> None:
        self.assertEqual(survey.week_start(date(2026, 8, 27)), "2026-08-24")

    def test_sunday_official_lands_on_that_iso_week(self) -> None:
        self.assertEqual(survey.week_start(date(2026, 8, 30)), "2026-08-24")

    def test_monday_grace_stays_on_sundays_week(self) -> None:
        self.assertEqual(survey.week_start(date(2026, 8, 31)), "2026-08-24")

    def test_tuesday_is_the_new_iso_week(self) -> None:
        self.assertEqual(survey.week_start(date(2026, 9, 1)), "2026-08-31")


class StoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp()) / "t.sqlite"
        init(self.tmp)

    def test_upsert_last_valid_wins(self) -> None:
        on = date(2026, 8, 27)
        survey.store([4, 4, 3, 4, 5], channel="test", db_path=self.tmp, on=on)
        survey.store([5, 5, 5, 5, 5], channel="test", db_path=self.tmp, on=on)
        con = sqlite3.connect(self.tmp)
        got = con.execute(
            "SELECT i1,i2,i3,i4,i5,pct,channel FROM survey WHERE week_start='2026-08-24'"
        ).fetchone()
        con.close()
        self.assertEqual(got, (5, 5, 5, 5, 5, 100.0, "test"))

    def test_monday_store_writes_sundays_week(self) -> None:
        survey.store([4, 4, 3, 4, 5], channel="test", db_path=self.tmp, on=date(2026, 8, 31))
        con = sqlite3.connect(self.tmp)
        weeks = [r[0] for r in con.execute("SELECT week_start FROM survey")]
        con.close()
        self.assertEqual(weeks, ["2026-08-24"])

    def test_store_reply_rejects_garbage(self) -> None:
        self.assertIsNone(survey.store_reply("hello", db_path=self.tmp))


if __name__ == "__main__":
    unittest.main()
