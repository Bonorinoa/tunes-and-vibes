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
    """ISO Monday of the WHO-5 administration week.

    Sunday's instrument belongs to that ISO week. Monday is grace for
    Sunday's administration, so it pins to the previous ISO Monday.
    Tuesday–Saturday use the ISO week containing d.
    """
    d = d or date.today()
    if d.isoweekday() == 1:  # Monday grace → Sunday's week
        d = d - timedelta(days=1)
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


def store(
    items: list[int],
    channel: str = "manual",
    *,
    db_path: Path | None = None,
    on: date | None = None,
    note: str | None = None,
) -> dict:
    path = db_path or DB
    init(path)
    ws = week_start(on)
    total = sum(items)
    con = sqlite3.connect(path)
    con.execute(
        """INSERT INTO survey (week_start, responded_at, i1, i2, i3, i4, i5,
                               raw_total, pct, channel, note)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(week_start) DO UPDATE SET
             responded_at=excluded.responded_at, i1=excluded.i1, i2=excluded.i2,
             i3=excluded.i3, i4=excluded.i4, i5=excluded.i5,
             raw_total=excluded.raw_total, pct=excluded.pct,
             channel=excluded.channel, note=excluded.note""",
        (
            ws,
            datetime.now(timezone.utc).isoformat(timespec="seconds"),
            *items,
            total,
            total * 4,
            channel,
            note,
        ),
    )
    con.commit()
    got = con.execute(
        "SELECT week_start, pct FROM survey WHERE week_start=?", (ws,)
    ).fetchone()
    con.close()
    return {"week_start": got[0], "pct": got[1], "raw_total": total}


def store_reply(text: str, channel: str = "telegram", *, db_path: Path | None = None,
                on: date | None = None) -> dict | None:
    """Parse a free-text reply and upsert. None if unusable."""
    items, issue = parse_reply(text)
    if items is None:
        return None
    return store(items, channel, db_path=db_path, on=on, note=f"parsed from {channel}: {text.strip()}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", help='reply text, e.g. "4 4 3 4 5"')
    ap.add_argument("--channel", default="manual")
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
        res = store(items, channel=args.channel)
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
