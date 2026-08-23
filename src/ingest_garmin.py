"""Garmin ingest: last night + today -> wellness row. Resume-only (non-interactive).

Expired tokens write an api_error row and exit 0 -- never crashes, never hangs
on prompts. Re-auth is a manual `src/garmin_login.py` run.
Night metrics are stored under the wake date (today).
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


def collect(client) -> tuple[dict, dict]:
    yday = (date.today() - timedelta(days=1)).isoformat()
    today = date.today().isoformat()

    sleep = client.get_sleep_data(yday) or {}
    sdto = sleep.get("dailySleepDTO") or {}
    stats = client.get_stats(today) or {}
    hrs = client.get_heart_rates(today) or {}

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
        "steps": int(num(stats, "steps") or 0),
        "active_kcal": num(stats, "activeKilocalories"),
        "note": None,
    }

    # Status contract: API success with NO substantive metrics = not_worn.
    # (Watch off for the day/month. Distinguishes from synced_zero, which
    # requires steps>0 or some signal proving wear with zero activity.)
    substance = [
        row["sleep_min"], row["rem_min"], row["rhr"], row["avg_stress"],
        row["spo2_avg"], row["active_kcal"], row["bb_charged"], row["bb_drained"],
    ]
    if all(v is None or v == 0 for v in substance):
        row.update(status="not_worn", note="api ok · all metrics empty (watch off?)")
    try:
        hrv = client.get_hrv_data(yday) or {}
        row["hrv_rmssd"] = num(hrv, "hrvSummary", "lastNightAvg")
        row["hrv_status"] = (hrv.get("hrvSummary") or {}).get("status")
    except Exception as exc:  # noqa: BLE001 - single optional metric
        row["note"] = f"hrv unavailable: {type(exc).__name__}"
    return row, {"sleep": sleep, "stats": stats, "hr": hrs}


def main() -> int:
    load_dotenv(ROOT / ".env")
    init()
    today = date.today().isoformat()
    row: dict = {"date": today, "status": "api_error", "note": None}
    payload: dict = {}

    try:
        from garminconnect import Garmin

        # Non-interactive: blank password fails fast instead of hanging cron.
        client = Garmin(email=os.getenv("GARMIN_EMAIL") or "", password="", prompt_mfa=lambda: "")
        client.login(TOKEN_STORE)
        data_row, payload = collect(client)
        row.update(data_row)
    except Exception as exc:  # noqa: BLE001 - recorded as a row status, never raised
        row["note"] = f"{type(exc).__name__}: {exc}"

    cols = [
        "date", "status", "sleep_min", "rem_min", "deep_min", "sleep_score", "rhr", "rhr_7d",
        "bb_charged", "bb_drained", "avg_stress", "spo2_avg", "steps", "active_kcal",
        "hrv_rmssd", "hrv_status", "note", "raw_json", "ingested_at",
    ]
    values = {c: row.get(c) for c in cols}
    values["raw_json"] = (json.dumps(payload)[:20000] if payload else None)
    values["ingested_at"] = now()

    con = sqlite3.connect(DB)
    placeholders = ",".join(f":{c}" for c in cols)
    updates = ",".join(f"{c}=excluded.{c}" for c in cols[1:])
    con.execute(
        f"INSERT INTO wellness ({', '.join(cols)}) VALUES ({placeholders}) "
        f"ON CONFLICT(date) DO UPDATE SET {updates}",
        values,
    )
    con.execute(
        "INSERT INTO ingest_log VALUES (?,?,?,?)",
        (now(), "garmin", row["status"], row.get("note") or "ok"),
    )
    got = con.execute(
        "SELECT date,status,sleep_min,rem_min,rhr,rhr_7d,hrv_rmssd,hrv_status,"
        "bb_charged,bb_drained,avg_stress,steps FROM wellness WHERE date=?",
        (today,),
    ).fetchone()
    con.commit()
    con.close()

    keys = ["date", "status", "sleep_min", "rem_min", "rhr", "rhr_7d", "hrv_rmssd",
            "hrv_status", "bb_charged", "bb_drained", "avg_stress", "steps"]
    print("garmin ingest:", dict(zip(keys, got)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
