"""Spotify ingest: recently-played -> plays/tracks tables. Idempotent (PK on played_at)."""

from __future__ import annotations

import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from schema import DB, init  # noqa: E402

SCOPES = (
    "user-read-private user-read-email user-read-recently-played "
    "user-read-currently-playing user-top-read user-library-read "
    "playlist-read-private playlist-read-collaborative"
)

# Live endpoint keeps ~24h. 200 items ≈ 4 pages — enough for ~6h/day listening
# after a missed poll, not enough to reconstruct a multi-day hole.
MAX_RECENT = 200


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def collect_recent_pages(client, *, max_items: int = MAX_RECENT, limit: int = 50) -> list:
    """Walk recently-played `before` cursors until empty, no next, or max_items."""
    items: list = []
    before = None
    while len(items) < max_items:
        kwargs = {"limit": limit}
        if before is not None:
            kwargs["before"] = before
        feed = client.current_user_recently_played(**kwargs) or {}
        batch = feed.get("items") or []
        if not batch:
            break
        room = max_items - len(items)
        items.extend(batch[:room])
        if len(items) >= max_items:
            break
        if not feed.get("next"):
            break
        before = (feed.get("cursors") or {}).get("before")
        if not before:
            break
    return items


def persist_items(con: sqlite3.Connection, items: list, ingested_at: str) -> tuple[int, int, int]:
    """Insert plays/tracks with named columns so ALTERs cannot break ingest."""
    new_plays = dup_plays = new_tracks = 0
    for item in items:
        played_at = item["played_at"]
        track = item.get("track") or {}
        ctx = item.get("context") or {}

        # Track catalog upsert FIRST -- must run even when the play is a dupe,
        # so duration backfill keeps working across polls.
        artists = track.get("artists") or []
        tid = track.get("id")
        duration_ms = track.get("duration_ms")
        artist_names = ", ".join(a.get("name") or "" for a in artists)
        if tid and not con.execute("SELECT 1 FROM tracks WHERE track_id=?", (tid,)).fetchone():
            con.execute(
                """INSERT INTO tracks (track_id, track_name, artist_names, first_seen, duration_ms)
                   VALUES (?, ?, ?, ?, ?)""",
                (tid, track.get("name"), artist_names, ingested_at, duration_ms),
            )
            new_tracks += 1
        elif tid and duration_ms:
            con.execute(
                "UPDATE tracks SET duration_ms=? WHERE track_id=? AND duration_ms IS NULL",
                (duration_ms, tid),
            )

        if con.execute("SELECT 1 FROM plays WHERE played_at=?", (played_at,)).fetchone():
            dup_plays += 1
            continue

        context_uri = ctx.get("uri")
        con.execute(
            """INSERT INTO plays (
                 played_at, track_id, track_name, artist_ids, artist_names,
                 album_name, context_type, context_uri, ms_played, ingested_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                played_at,
                track.get("id"),
                track.get("name"),
                ",".join(a.get("id") or "" for a in artists),
                artist_names,
                (track.get("album") or {}).get("name"),
                context_uri.split(":")[1] if context_uri else None,
                context_uri,
                item.get("ms_played"),
                ingested_at,
            ),
        )
        new_plays += 1
    return new_plays, dup_plays, new_tracks


def _log(con: sqlite3.Connection, outcome: str, detail: str) -> None:
    con.execute(
        "INSERT INTO ingest_log (ts, source, outcome, detail) VALUES (?, ?, ?, ?)",
        (now(), "spotify", outcome, detail[:500]),
    )


def main() -> int:
    load_dotenv(ROOT / ".env")
    init()
    try:
        oauth = SpotifyOAuth(
            client_id=os.environ["SPOTIFY_CLIENT_ID"],
            client_secret=os.environ["SPOTIFY_CLIENT_SECRET"],
            redirect_uri=os.environ.get("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback"),
            scope=SCOPES,
            cache_path=str(ROOT / "auth" / "spotify_token.json"),
            open_browser=False,
        )
        client = Spotify(auth_manager=oauth)
        items = collect_recent_pages(client)
        con = sqlite3.connect(DB)
        new_plays, dup_plays, new_tracks = persist_items(con, items, now())
        _log(con, "ok", f"new={new_plays} dup={dup_plays} new_tracks={new_tracks} pages_items={len(items)}")
        con.commit()
        con.close()
        print(
            f"spotify ingest: {new_plays} new plays, {dup_plays} dups skipped, "
            f"{new_tracks} new tracks, window={len(items)}"
        )
        return 0
    except Exception as exc:  # noqa: BLE001 - recorded, never crashes cron
        try:
            con = sqlite3.connect(DB)
            _log(con, "api_error", f"{type(exc).__name__}: {exc}")
            con.commit()
            con.close()
        except Exception:
            pass
        print(f"spotify ingest failed: {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
