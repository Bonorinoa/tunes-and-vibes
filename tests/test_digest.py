"""Digest compose never raises; includes Garmin strip even on empty music."""

from __future__ import annotations

import sqlite3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from schema import DDL  # noqa: E402
import digest  # noqa: E402


class DigestTests(unittest.TestCase):
    def test_compose_empty_db(self) -> None:
        con = sqlite3.connect(":memory:")
        con.executescript(DDL)
        text = digest.compose(con)
        self.assertNotIn("Traceback", text)
        self.assertIn("WHO-5", text)
        self.assertIn("Last Garmin ingest", text)

    def test_compose_with_collected_hrv_none_string(self) -> None:
        con = sqlite3.connect(":memory:")
        con.executescript(DDL)
        con.execute(
            """INSERT INTO wellness (date, status, sleep_min, rem_min, rhr, rhr_7d,
               hrv_rmssd, hrv_status, bb_charged, bb_drained, avg_stress, steps)
               VALUES ('2099-01-01','collected',480,60,50,50,80,'NONE',10,10,20,100)"""
        )
        text = digest.compose(con)
        self.assertNotIn("Traceback", text)
        # row is in 2099, outside today's daily/trailing window — renderer must still ship
        self.assertIn("WHO-5", text)
        self.assertIn("Last Garmin ingest", text)


if __name__ == "__main__":
    unittest.main()
