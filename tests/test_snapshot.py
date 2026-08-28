"""RED tests for the 2026-08-25 digest crash (hrv_status is a string)."""

from __future__ import annotations

import sqlite3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from schema import DDL  # noqa: E402
import snapshot  # noqa: E402


def _db() -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    con.executescript(DDL)
    return con


class FmtTests(unittest.TestCase):
    def test_fmt_does_not_raise_on_vendor_status_string(self) -> None:
        self.assertEqual(snapshot._fmt("NONE"), "NONE")

    def test_fmt_none_is_dash(self) -> None:
        self.assertEqual(snapshot._fmt(None), "—")

    def test_fmt_number_keeps_g(self) -> None:
        self.assertEqual(snapshot._fmt(80.0, "ms"), "80ms")


class DailyPanelTests(unittest.TestCase):
    def test_daily_renders_when_hrv_status_is_none_string(self) -> None:
        con = _db()
        con.execute(
            """INSERT INTO wellness (date, status, sleep_min, rem_min, rhr, rhr_7d,
               hrv_rmssd, hrv_status, bb_charged, bb_drained, avg_stress, steps)
               VALUES ('2026-08-25','collected',547,75,43,44,80,'NONE',81,62,32,0)"""
        )
        text = snapshot.daily(con, "2026-08-25")
        self.assertIn("GARMIN (collected)", text)
        self.assertIn("HRV", text)
        self.assertNotIn("Traceback", text)

    def test_missing_sleep_is_dash_not_zero_hours(self) -> None:
        con = _db()
        con.execute(
            """INSERT INTO wellness (date, status, sleep_min, rem_min, rhr, rhr_7d,
               hrv_rmssd, hrv_status, bb_charged, bb_drained, avg_stress, steps)
               VALUES ('2026-08-24','collected',NULL,NULL,40,45,NULL,NULL,63,81,36,13409)"""
        )
        text = snapshot.daily(con, "2026-08-24")
        self.assertNotIn("0h 00m", text)
        self.assertIn("Sleep     —", text)

    def test_negative_stress_sentinel_is_dash(self) -> None:
        con = _db()
        con.execute(
            """INSERT INTO wellness (date, status, sleep_min, rem_min, rhr, rhr_7d,
               hrv_rmssd, hrv_status, bb_charged, bb_drained, avg_stress, steps)
               VALUES ('2026-08-27','collected',440,67,48,45,88,'NONE',0,0,-1,0)"""
        )
        text = snapshot.daily(con, "2026-08-27")
        self.assertNotIn("stress avg -1", text)
        self.assertIn("stress avg —", text)
        self.assertIn("Steps     —", text)

    def test_daily_valence_prints_join_coverage(self) -> None:
        con = _db()
        con.execute("INSERT INTO tracks VALUES ('a','A','Art','t',180000,0)")
        con.execute("INSERT INTO tracks VALUES ('b','B','Art','t',180000,0)")
        con.execute(
            "INSERT INTO features (rb_uuid, track_id, valence, energy, fetched_at) "
            "VALUES ('u','a',0.2,0.8,'t')"
        )
        con.execute(
            "INSERT INTO plays (played_at, track_id, track_name, artist_names, ingested_at) "
            "VALUES ('2026-08-27T15:00:00Z','a','A','Art','t')"
        )
        con.execute(
            "INSERT INTO plays (played_at, track_id, track_name, artist_names, ingested_at) "
            "VALUES ('2026-08-27T16:00:00Z','b','B','Art','t')"
        )
        text = snapshot.daily(con, "2026-08-27")
        self.assertIn("valence 0.20", text)
        self.assertIn("1/2", text)


if __name__ == "__main__":
    unittest.main()
