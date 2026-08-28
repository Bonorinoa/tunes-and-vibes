"""ReccoBeats enrichment: fill features for new tracks. Static per track -- fetch once.

Catalog misses are persisted on tracks.not_found so we never retry them.
"""

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


def pending_ids(con: sqlite3.Connection, limit: int = 300) -> list[str]:
    return [
        r[0]
        for r in con.execute(
            """SELECT t.track_id FROM tracks t
               LEFT JOIN features f ON f.track_id = t.track_id
               WHERE f.track_id IS NULL
                 AND COALESCE(t.not_found, 0) = 0
                 AND t.track_id IS NOT NULL
               LIMIT ?""",
            (limit,),
        ).fetchall()
    ]


def mark_not_found(con: sqlite3.Connection, ids: list[str]) -> None:
    con.executemany(
        "UPDATE tracks SET not_found=1 WHERE track_id=?",
        [(i,) for i in ids],
    )


def misses(chunk: list[str], pairs: list[tuple[str, str]]) -> list[str]:
    found = {sid for sid, _ in pairs}
    return [sid for sid in chunk if sid not in found]


def apply_lookup(
    con: sqlite3.Connection,
    chunk: list[str],
    pairs: list[tuple[str, str]] | None,
) -> tuple[int, list[tuple[str, str]]]:
    """Catalog misses persist. Transport failure (pairs is None) retries next poll."""
    if pairs is None:
        return len(chunk), []
    missing = misses(chunk, pairs)
    if missing:
        mark_not_found(con, missing)
    return len(missing), pairs


def _get(url: str, **kw) -> dict | None:
    for _ in range(3):
        try:
            resp = requests.get(url, timeout=25, **kw)
        except requests.RequestException as exc:
            print(f"  {type(exc).__name__} on {url}")
            return None
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


def lookup_ids(ids: list[str]) -> list[tuple[str, str]] | None:
    """Batch lookup. None = transport failure (retry later); list = catalog result."""
    if not ids:
        return []
    data = _get(f"{API}/track", params={"ids": ",".join(ids)})
    if data is None:
        if len(ids) > 1:
            mid = len(ids) // 2
            left = lookup_ids(ids[:mid])
            right = lookup_ids(ids[mid:])
            if left is None and right is None:
                return None
            return (left or []) + (right or [])
        return None
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
    pending = pending_ids(con)
    print(f"tracks needing features: {len(pending)}")

    done = failed = 0
    for i in range(0, len(pending), CHUNK):
        chunk = pending[i : i + CHUNK]
        pairs = lookup_ids(chunk)
        n_miss, pairs = apply_lookup(con, chunk, pairs)
        failed += n_miss
        for sid, uuid in pairs:
            feats = _get(f"{API}/track/{uuid}/audio-features")
            if not feats:
                failed += 1  # transport/HTTP — retry next poll, not a catalog miss
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
    n_miss = con.execute("SELECT COUNT(*) FROM tracks WHERE not_found=1").fetchone()[0]
    con.close()
    print(
        f"reccobeats: {done} enriched ({failed} failed) · "
        f"cache {n_feat} tracks ({n_val} w/ valence) · not_found {n_miss}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
