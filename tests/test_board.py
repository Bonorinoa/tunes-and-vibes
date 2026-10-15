"""Board HTML is coverage-first and survives empty / gappy panels."""

from __future__ import annotations

import sqlite3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from schema import DDL  # noqa: E402
import board  # noqa: E402


class BoardTests(unittest.TestCase):
    def _con(self) -> sqlite3.Connection:
        con = sqlite3.connect(":memory:")
        con.executescript(DDL)
        return con

    def test_empty_db_does_not_crash_and_labels_missing_who5(self) -> None:
        html = board.compose(self._con())
        self.assertNotIn("Traceback", html)
        self.assertIn("WHO-5", html)
        self.assertIn("no entries", html.lower())

    def test_cream_page_not_transparent_theme(self) -> None:
        html = board.compose(self._con())
        self.assertIn("#F4EBD8", html)
        self.assertIn("#1C1410", html)

    def test_who5_row_and_test_fire_label(self) -> None:
        con = self._con()
        con.execute(
            """INSERT INTO survey (week_start, responded_at, i1,i2,i3,i4,i5, raw_total, pct, channel, note)
               VALUES ('2026-08-17','t',4,2,2,3,4,15,60,'manual','test-fire reply')"""
        )
        html = board.compose(con)
        self.assertIn("60", html)
        self.assertIn("test-fire", html.lower())

    def test_calendar_marks_gap_between_collected_days(self) -> None:
        con = self._con()
        con.execute(
            "INSERT INTO wellness (date, status, sleep_min, hrv_rmssd, rhr, steps) "
            "VALUES ('2026-08-23','collected',480,80,43,1000)"
        )
        con.execute(
            "INSERT INTO wellness (date, status, rhr, steps) "
            "VALUES ('2026-08-25','collected',44,2000)"
        )
        html = board.compose(con, today="2026-08-25")
        self.assertIn("data-day=\"2026-08-24\"", html)
        self.assertIn("data-kind=\"gap\"", html)

    def test_missing_sleep_is_emdash_not_zero(self) -> None:
        con = self._con()
        con.execute(
            "INSERT INTO wellness (date, status, sleep_min, hrv_rmssd, rhr, steps) "
            "VALUES ('2026-08-28','collected',NULL,NULL,45,10147)"
        )
        html = board.compose(con, today="2026-08-28")
        self.assertNotIn("0h 00m", html)
        self.assertIn("data-day=\"2026-08-28\"", html)


if __name__ == "__main__":
    unittest.main()
