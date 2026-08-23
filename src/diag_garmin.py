"""One-off: inspect what Garmin actually returned for 2026-08-23."""

import json
import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parents[1] / "data" / "panel.sqlite"

con = sqlite3.connect(DB)
row = con.execute("SELECT raw_json, note FROM wellness WHERE date=?", ("2026-08-23",)).fetchone()
con.close()

if not row:
    print("no row")
    raise SystemExit(0)

raw, note = row
print("note:", note)
if not raw:
    print("raw_json is NULL")
    raise SystemExit(0)

d = json.loads(raw)
for key, val in d.items():
    print(f"\n== {key} == ({type(val).__name__})")
    if isinstance(val, dict):
        print("keys:", sorted(val.keys())[:25])
        inner = val.get("dailySleepDTO")
        if isinstance(inner, dict):
            print("dailySleepDTO keys:", sorted(inner.keys())[:30])
            for probe in ("sleepTimeSeconds", "remSleepSeconds", "deepSleepSeconds"):
                print(f"  {probe} =", inner.get(probe))
        stats_probe = {k: val.get(k) for k in (
            "bodyBatteryChargedValue", "bodyBatteryDrainedValue",
            "averageStressLevel", "steps", "restingHeartRate")}
        if any(v is not None for v in stats_probe.values()):
            print("stats probes:", stats_probe)
    else:
        print(str(val)[:300])
