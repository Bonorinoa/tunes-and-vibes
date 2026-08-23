"""ReccoBeats enrichment: fill features for new tracks. Static per track -- fetch once."""

from __future__ import annotations

import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from schema import DB, init  # noqa: E402

API = "https://api.reccobeats.com/v1"
CHUNK = 50


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _get(url: str, **kw) -> dict | None:
    for _ in range(3):
        resp = requests.get(url, timeout=25, **kw)
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code == 429:
            wait = int(resp.headers.get("Retry-After", "5"))
            print(f"  429 · waiting {wait}s")
            time.sleep(wait)
            continue
        print(f"  HTTP {resp.status_code} on {url}")
        return None
    return None


def _lookup_ids(con: sqlite3.Connection, ids: list[str]) -> list[tuple[str, str]]:
    """Batch lookup with adaptive splitting: ReccoBeats 400s on large ID lists."""
    if not ids:
        return []
    data = _get(f"{API}/track", params={"ids": ",".join(ids)})
    if data is None and len(ids) > 1:
        mid = len(ids) // 2
        return _lookup_ids(con, ids[:mid]) + _lookup_ids(con, ids[mid:])
    if not data:
        return []
    pairs = []
    for item in data.get("content") or []:
        href = item.get("href") or ""
        sid = href.rsplit("/", 1)[-1]
        if sid and item.get("id"):
            pairs.append((sid, item["id"]))
    return pairs


def main() -> int:
    init()
    con = sqlite3.connect(DB)
    pending = [
        r[0]
        for r in con.execute(
            """SELECT t.track_id FROM tracks t
               LEFT JOIN features f ON f.track_id = t.track_id
               WHERE f.track_id IS NULL AND t.track_id IS NOT NULL LIMIT 300"""
        ).fetchall()
    ]
    print(f"tracks needing features: {len(pending)}")

    done = failed = 0
    for i in range(0, len(pending), CHUNK):
        chunk = pending[i : i + CHUNK]
        pairs = _lookup_ids(con, chunk)
        failed += len(chunk) - len(pairs)
        for sid, uuid in pairs:
            feats = _get(f"{API}/track/{uuid}/audio-features")
            if not feats:
                failed += 1
                continue
            con.execute(
                """INSERT INTO features (rb_uuid, track_id, valence, energy, danceability,
                     tempo, acousticness, instrumentalness, liveness, loudness, speechiness,
                     key, mode, fetched_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(rb_uuid) DO NOTHING""",
                (
                    uuid,
                    sid,
                    feats.get("valence"),
                    feats.get("energy"),
                    feats.get("danceability"),
                    feats.get("tempo"),
                    feats.get("acousticness"),
                    feats.get("instrumentalness"),
                    feats.get("liveness"),
                    feats.get("loudness"),
                    feats.get("speechiness"),
                    feats.get("key"),
                    feats.get("mode"),
                    now(),
                ),
            )
            done += 1

    con.execute(
        "INSERT INTO ingest_log VALUES (?,?,?,?)",
        (now(), "reccobeats", "ok", f"done={done} failed={failed}"),
    )
    con.commit()
    n_feat, n_val = con.execute("SELECT COUNT(*), COUNT(valence) FROM features").fetchone()
    con.close()
    print(f"reccobeats: {done} enriched ({failed} failed) · cache {n_feat} tracks ({n_val} w/ valence)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
