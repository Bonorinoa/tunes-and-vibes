"""Garmin ingest: last night + today -> wellness row. Resume-only (non-interactive).

Expired tokens write an api_error row and exit 0 -- never crashes, never hangs
on prompts. Re-auth is a manual `src/garmin_login.py` run.
Night metrics are stored under the wake date (today).

A transient API failure must NOT wipe a substantive row for the same date.
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from schema import DB, init  # noqa: E402

TOKEN_STORE = str(ROOT / "auth" / "garmin")
PROTECTED = frozenset({"collected", "not_worn", "synced_zero"})
STATS_KEEP = (
    "totalSteps",
    "steps",
    "dailyStepGoal",
    "averageStressLevel",
    "bodyBatteryChargedValue",
    "bodyBatteryDrainedValue",
    "activeKilocalories",
    "totalKilocalories",
    "moderateIntensityMinutes",
    "vigorousIntensityMinutes",
    "averageSpo2",
    "highlyActiveSeconds",
    "activeSeconds",
    "restingHeartRate",
)
SLEEP_KEEP = (
    "sleepTimeSeconds",
    "remSleepSeconds",
    "deepSleepSeconds",
    "sleepStartTimestampGMT",
    "sleepEndTimestampGMT",
    "sleepScores",
)


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def num(d: dict, *keys: str) -> float | None:
    """Tolerant numeric getter over nested dicts. None on any gap."""
    cur: object = d
    for k in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
        if cur is None:
            return None
    if isinstance(cur, bool) or not isinstance(cur, (int, float, str)):
        return None
    try:
        return float(cur)  # type: ignore[arg-type]
    except ValueError:
        return None


def per_min(seconds: float | None) -> float | None:
    return seconds / 60.0 if seconds else None


def row_from_payloads(
    sleep: dict | None,
    stats: dict | None,
    hrs: dict | None,
    hrv: dict | None = None,
) -> dict:
    """Map Garmin envelopes onto a wellness row. No I/O."""
    sdto = (sleep or {}).get("dailySleepDTO") or {}
    stats = stats or {}
    hrs = hrs or {}
    steps = num(stats, "totalSteps")
    if steps is None:
        steps = num(stats, "steps")
    row = {
        "status": "collected",
        "sleep_min": per_min(num(sdto, "sleepTimeSeconds")),
        "rem_min": per_min(num(sdto, "remSleepSeconds")),
        "deep_min": per_min(num(sdto, "deepSleepSeconds")),
        "sleep_score": num(sdto, "sleepScores", "overall", "value"),
        "rhr": num(hrs, "restingHeartRate"),
        "rhr_7d": num(hrs, "lastSevenDaysAvgRestingHeartRate"),
        "bb_charged": int(num(stats, "bodyBatteryChargedValue") or 0),
        "bb_drained": int(num(stats, "bodyBatteryDrainedValue") or 0),
        "avg_stress": num(stats, "averageStressLevel"),
        "spo2_avg": num(stats, "averageSpo2"),
        "steps": int(steps or 0),
        "active_kcal": num(stats, "activeKilocalories"),
        "mod_min": num(stats, "moderateIntensityMinutes"),
        "vig_min": num(stats, "vigorousIntensityMinutes"),
        "hrv_rmssd": None,
        "hrv_status": None,
        "note": None,
    }
    substance = [
        row["sleep_min"],
        row["rem_min"],
        row["rhr"],
        row["avg_stress"],
        row["spo2_avg"],
        row["active_kcal"],
        row["bb_charged"],
        row["bb_drained"],
        row["steps"],
    ]
    if all(v is None or v == 0 for v in substance):
        row.update(status="not_worn", note="api ok · all metrics empty (watch off?)")
    if hrv:
        row["hrv_rmssd"] = num(hrv, "hrvSummary", "lastNightAvg")
        row["hrv_status"] = (hrv.get("hrvSummary") or {}).get("status")
    return row


def compact_payload(
    sleep: dict | None,
    stats: dict | None,
    hrs: dict | None,
    hrv: dict | None = None,
) -> dict:
    """Forensic blob small enough to store whole — never the sleep timeseries."""
    sdto = (sleep or {}).get("dailySleepDTO") or {}
    return {
        "sleep": {"dailySleepDTO": {k: sdto.get(k) for k in SLEEP_KEEP}},
        "stats": {k: (stats or {}).get(k) for k in STATS_KEEP},
        "hr": {
            "restingHeartRate": (hrs or {}).get("restingHeartRate"),
            "lastSevenDaysAvgRestingHeartRate": (hrs or {}).get(
                "lastSevenDaysAvgRestingHeartRate"
            ),
        },
        "hrv": hrv,
    }


def merge_wellness_row(existing: dict | None, incoming: dict) -> dict:
    """Keep last-good metrics when a later pull is a transient api_error."""
    if existing is None:
        return incoming
    if incoming.get("status") == "api_error" and existing.get("status") in PROTECTED:
        kept = dict(existing)
        err = incoming.get("note") or "api_error"
        kept["note"] = f"transient {err}; kept {existing['status']}"
        return kept
    return incoming


def collect(client, day: date | None = None) -> tuple[dict, dict]:
    day = day or date.today()
    yday = (day - timedelta(days=1)).isoformat()
    today = day.isoformat()

    sleep = client.get_sleep_data(yday) or {}
    stats = client.get_stats(today) or {}
    hrs = client.get_heart_rates(today) or {}
    hrv = None
    hrv_note = None
    try:
        hrv = client.get_hrv_data(yday) or {}
    except Exception as exc:  # noqa: BLE001 - single optional metric
        hrv_note = f"hrv unavailable: {type(exc).__name__}"

    row = row_from_payloads(sleep, stats, hrs, hrv)
    if hrv_note:
        row["note"] = hrv_note
    return row, compact_payload(sleep, stats, hrs, hrv)


def _load_existing(con: sqlite3.Connection, day: str) -> dict | None:
    cur = con.execute("SELECT * FROM wellness WHERE date=?", (day,))
    got = cur.fetchone()
    if not got:
        return None
    return dict(zip((c[0] for c in cur.description), got))


def main() -> int:
    load_dotenv(ROOT / ".env")
    init()
    today = date.today().isoformat()
    incoming: dict = {"date": today, "status": "api_error", "note": None}
    payload: dict = {}

    try:
        from garminconnect import Garmin

        # Non-interactive: blank password fails fast instead of hanging cron.
        client = Garmin(email=os.getenv("GARMIN_EMAIL") or "", password="", prompt_mfa=lambda: "")
        client.login(TOKEN_STORE)
        data_row, payload = collect(client)
        incoming.update(data_row)
    except Exception as exc:  # noqa: BLE001 - recorded as a row status, never raised
        incoming["note"] = f"{type(exc).__name__}: {exc}"

    cols = [
        "date",
        "status",
        "sleep_min",
        "rem_min",
        "deep_min",
        "sleep_score",
        "rhr",
        "rhr_7d",
        "bb_charged",
        "bb_drained",
        "avg_stress",
        "spo2_avg",
        "steps",
        "active_kcal",
        "mod_min",
        "vig_min",
        "hrv_rmssd",
        "hrv_status",
        "note",
        "raw_json",
        "ingested_at",
    ]

    con = sqlite3.connect(DB)
    existing = _load_existing(con, today)
    row = merge_wellness_row(existing, incoming)
    if row.get("status") != "api_error" or existing is None:
        # Fresh accept: stamp ingest time + (compact) payload.
        if incoming.get("status") != "api_error":
            row["raw_json"] = json.dumps(payload)
            row["ingested_at"] = now()
        elif existing is None:
            row["raw_json"] = None
            row["ingested_at"] = now()
    # preserved last-good: keep existing raw_json + ingested_at

    values = {c: row.get(c) for c in cols}
    placeholders = ",".join(f":{c}" for c in cols)
    updates = ",".join(f"{c}=excluded.{c}" for c in cols[1:])
    con.execute(
        f"INSERT INTO wellness ({', '.join(cols)}) VALUES ({placeholders}) "
        f"ON CONFLICT(date) DO UPDATE SET {updates}",
        values,
    )
    # Log the *attempt* outcome, not the preserved status — forensics live here.
    con.execute(
        "INSERT INTO ingest_log VALUES (?,?,?,?)",
        (now(), "garmin", incoming["status"], incoming.get("note") or row.get("note") or "ok"),
    )
    got = con.execute(
        "SELECT date,status,sleep_min,rem_min,rhr,rhr_7d,hrv_rmssd,hrv_status,"
        "bb_charged,bb_drained,avg_stress,steps FROM wellness WHERE date=?",
        (today,),
    ).fetchone()
    con.commit()
    con.close()

    keys = [
        "date",
        "status",
        "sleep_min",
        "rem_min",
        "rhr",
        "rhr_7d",
        "hrv_rmssd",
        "hrv_status",
        "bb_charged",
        "bb_drained",
        "avg_stress",
        "steps",
    ]
    print("garmin ingest:", dict(zip(keys, got)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
