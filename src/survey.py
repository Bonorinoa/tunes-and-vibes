"""WHO-5 survey storage + defensive reply parsing. CLI only."""

from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from schema import DB, init  # noqa: E402

ITEMS = [
    "I have felt cheerful and in good spirits",
    "I have felt calm and relaxed",
    "I have felt active and vigorous",
    "I woke up feeling fresh and rested",
    "My daily life has been filled with things that interest me",
]


def week_start(d: date | None = None) -> str:
    """ISO Monday of the week containing d (default: today, local)."""
    d = d or date.today()
    return (d - timedelta(days=d.isoweekday() - 1)).isoformat()


def parse_reply(text: str) -> tuple[list[int] | None, str]:
    """Returns (items, issue). items is None when the reply is unusable."""
    parts = [p for p in re.split(r"[\s,;/|]+", text.strip()) if p]
    if len(parts) != 5:
        return None, f"expected 5 integers, got {len(parts)}"
    items: list[int] = []
    for i, p in enumerate(parts, 1):
        try:
            v = int(float(p))
        except ValueError:
            return None, f"item {i} ({p!r}) is not a number"
        if not 0 <= v <= 5:
            return None, f"item {i}={v} out of range 0–5"
        items.append(v)
    return items, ""


def store(items: list[int], channel: str = "manual") -> dict:
    init()
    ws = week_start()
    total = sum(items)
    con = sqlite3.connect(DB)
    con.execute(
        """INSERT INTO survey (week_start, responded_at, i1, i2, i3, i4, i5,
                               raw_total, pct, channel)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(week_start) DO UPDATE SET
             responded_at=excluded.responded_at, i1=excluded.i1, i2=excluded.i2,
             i3=excluded.i3, i4=excluded.i4, i5=excluded.i5,
             raw_total=excluded.raw_total, pct=excluded.pct, channel=excluded.channel""",
        (
            ws,
            datetime.now(timezone.utc).isoformat(timespec="seconds"),
            *items,
            total,
            total * 4,
            channel,
        ),
    )
    con.commit()
    got = con.execute(
        "SELECT week_start, pct FROM survey WHERE week_start=?", (ws,)
    ).fetchone()
    con.close()
    return {"week_start": got[0], "pct": got[1], "raw_total": total}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", help="reply text, e.g. \"4 4 3 4 5\"")
    ap.add_argument("--items", action="store_true", help="print the five WHO-5 items")
    args = ap.parse_args()
    if args.items or not args.store:
        for i, item in enumerate(ITEMS, 1):
            print(f"{i}. {item}")
        print("0 = at no time · 5 = all of the time · window: last 2 weeks")
    if args.store:
        items, issue = parse_reply(args.store)
        if items is None:
            print(f"REJECTED: {issue}")
            return 1
        res = store(items)
        flag = ""
        if res["pct"] < 28:
            flag = " · STRAIN FLAG (≤28) — informational, not diagnostic"
        elif res["pct"] < 50:
            flag = " · low-band (<50)"
        print(f"stored {res}")
        print(f"WHO-5 {res['pct']}/100{flag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
