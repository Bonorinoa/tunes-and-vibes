"""RED tests: totalSteps parse + transient api_error must not wipe a good day."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import ingest_garmin as g  # noqa: E402


AUG24_STATS = {
    "totalSteps": 13409,
    "dailyStepGoal": 8000,
    "averageStressLevel": 36,
    "bodyBatteryChargedValue": 63,
    "bodyBatteryDrainedValue": 81,
    "activeKilocalories": 791.0,
    "moderateIntensityMinutes": 8,
    "vigorousIntensityMinutes": 22,
}

SLEEP = {
    "dailySleepDTO": {
        "sleepTimeSeconds": 28980,
        "remSleepSeconds": 4860,
        "deepSleepSeconds": 3600,
        "sleepScores": {"overall": {"value": 81}},
    }
}

HRS = {"restingHeartRate": 43, "lastSevenDaysAvgRestingHeartRate": 44}
HRV = {"hrvSummary": {"lastNightAvg": 80, "status": "NONE"}}


class ParseTests(unittest.TestCase):
    def test_row_reads_total_steps_not_missing_steps_key(self) -> None:
        row = g.row_from_payloads(SLEEP, AUG24_STATS, HRS, HRV)
        self.assertEqual(row["steps"], 13409)
        self.assertEqual(row["status"], "collected")
        self.assertEqual(row["sleep_min"], 483.0)
        self.assertEqual(row["mod_min"], 8.0)
        self.assertEqual(row["vig_min"], 22.0)
        self.assertEqual(row["hrv_status"], "NONE")

    def test_legacy_steps_key_still_accepted(self) -> None:
        row = g.row_from_payloads(SLEEP, {"steps": 12}, HRS, None)
        self.assertEqual(row["steps"], 12)


class MergeTests(unittest.TestCase):
    def test_transient_api_error_keeps_collected_metrics(self) -> None:
        existing = {
            "date": "2026-08-26",
            "status": "collected",
            "sleep_min": 483.0,
            "hrv_rmssd": 80.0,
            "rhr": 43.0,
            "steps": 200,
            "note": None,
        }
        incoming = {
            "date": "2026-08-26",
            "status": "api_error",
            "sleep_min": None,
            "hrv_rmssd": None,
            "rhr": None,
            "steps": None,
            "note": "GarminConnectConnectionError: Read timed out",
        }
        kept = g.merge_wellness_row(existing, incoming)
        self.assertEqual(kept["status"], "collected")
        self.assertEqual(kept["sleep_min"], 483.0)
        self.assertEqual(kept["hrv_rmssd"], 80.0)
        self.assertEqual(kept["steps"], 200)
        self.assertIn("timed out", (kept.get("note") or "").lower())

    def test_first_pull_api_error_is_recorded(self) -> None:
        incoming = {"date": "2026-08-26", "status": "api_error", "note": "boom", "sleep_min": None}
        kept = g.merge_wellness_row(None, incoming)
        self.assertEqual(kept["status"], "api_error")

    def test_recovery_overwrites_api_error(self) -> None:
        existing = {"date": "2026-08-26", "status": "api_error", "sleep_min": None, "note": "boom"}
        incoming = {"date": "2026-08-26", "status": "collected", "sleep_min": 483.0, "note": None}
        kept = g.merge_wellness_row(existing, incoming)
        self.assertEqual(kept["status"], "collected")
        self.assertEqual(kept["sleep_min"], 483.0)


if __name__ == "__main__":
    unittest.main()
