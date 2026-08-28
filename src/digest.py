"""Telegram digest body. Regenerates the snapshot; never cats a crashed file."""

from __future__ import annotations

import sqlite3
import sys
import traceback
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from schema import DB  # noqa: E402
import snapshot  # noqa: E402

LOCAL_TZ = ZoneInfo("America/Phoenix")


def _who5(con: sqlite3.Connection) -> str:
    rows = con.execute(
        "SELECT week_start, pct FROM survey ORDER BY week_start DESC LIMIT 4"
    ).fetchall()
    if not rows:
        return "WHO-5: no entries yet — first prompt lands Sunday 08:00."
    lines = ["WHO-5 (pct/100, newest first):"]
    lines.extend(f"  {w}  {p:g}" for w, p in rows)
    return "\n".join(lines)


def _garmin_strip(con: sqlite3.Connection) -> str:
    rows = con.execute(
        """SELECT date, status, sleep_min, hrv_rmssd, rhr, steps, substr(note,1,60)
           FROM wellness ORDER BY date DESC LIMIT 4"""
    ).fetchall()
    if not rows:
        return "Garmin last 4 days: (no rows)"
    lines = ["Garmin last 4 days (newest first):"]
    for d, st, sleep, hrv, rhr, steps, note in rows:
        extra = f" · {note}" if note else ""
        lines.append(
            f"  {d}  {st}  sleep={snapshot._fmt(sleep,'m')}  "
            f"hrv={snapshot._fmt(hrv)}  rhr={snapshot._fmt(rhr)}  "
            f"steps={snapshot._fmt(steps)}{extra}"
        )
    return "\n".join(lines)


def _last_ingest(con: sqlite3.Connection, source: str) -> str:
    row = con.execute(
        "SELECT ts, outcome, substr(detail,1,120) FROM ingest_log "
        "WHERE source=? ORDER BY ts DESC LIMIT 1",
        (source,),
    ).fetchone()
    if not row:
        return f"Last {source} ingest: (none)"
    return f"Last {source} ingest: {row[0]}  {row[1]}  {row[2]}"


def compose(con: sqlite3.Connection) -> str:
    today = datetime.now(LOCAL_TZ).strftime("%a %b %d")
    parts = [f"TUNES & VIBES · {today}", "", _who5(con), ""]
    try:
        parts.append(snapshot.daily(con))
        parts.append("")
        parts.append(snapshot.weekly(con))
    except Exception:  # noqa: BLE001 - digest must still ship the strip
        parts.append("snapshot renderer failed:")
        parts.append(traceback.format_exc().strip().splitlines()[-1])
    parts.extend(["", _garmin_strip(con), _last_ingest(con, "garmin"), _last_ingest(con, "spotify")])
    return "\n".join(parts)


def main() -> int:
    if not DB.exists():
        print("no database yet")
        return 1
    con = sqlite3.connect(DB)
    text = compose(con)
    con.close()
    out = ROOT / "logs" / "latest_snapshot.txt"
    out.parent.mkdir(exist_ok=True)
    out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
