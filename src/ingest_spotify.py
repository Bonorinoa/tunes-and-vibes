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


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def main() -> int:
    load_dotenv(ROOT / ".env")
    init()
    oauth = SpotifyOAuth(
        client_id=os.environ["SPOTIFY_CLIENT_ID"],
        client_secret=os.environ["SPOTIFY_CLIENT_SECRET"],
        redirect_uri=os.environ.get("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback"),
        scope=SCOPES,
        cache_path=str(ROOT / "auth" / "spotify_token.json"),
        open_browser=False,
    )
    sp = Spotify(auth_manager=oauth)
    feed = sp.current_user_recently_played(limit=50) or {}
    items = feed.get("items", [])

    con = sqlite3.connect(DB)
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
        if tid and not con.execute("SELECT 1 FROM tracks WHERE track_id=?", (tid,)).fetchone():
            con.execute(
                "INSERT INTO tracks VALUES (?,?,?,?,?)",
                (
                    tid,
                    track.get("name"),
                    ", ".join(a.get("name") or "" for a in artists),
                    now(),
                    duration_ms,
                ),
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
            "INSERT INTO plays VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                played_at,
                track.get("id"),
                track.get("name"),
                ",".join(a.get("id") or "" for a in artists),
                ", ".join(a.get("name") or "" for a in artists),
                (track.get("album") or {}).get("name"),
                context_uri.split(":")[1] if context_uri else None,
                context_uri,
                item.get("ms_played"),
                now(),
            ),
        )
        new_plays += 1

    con.execute(
        "INSERT INTO ingest_log VALUES (?,?,?,?)",
        (now(), "spotify", "ok", f"new={new_plays} dup={dup_plays} new_tracks={new_tracks}"),
    )
    con.commit()
    con.close()
    print(f"spotify ingest: {new_plays} new plays, {dup_plays} dups skipped, {new_tracks} new tracks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
