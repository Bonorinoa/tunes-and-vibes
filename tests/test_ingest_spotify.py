"""Spotify persist must survive tracks schema growth; pages walk the 24h window."""

from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import ingest_spotify as sp  # noqa: E402
from schema import init  # noqa: E402


def _item(played_at: str, tid: str, name: str = "Song") -> dict:
    return {
        "played_at": played_at,
        "ms_played": None,
        "track": {
            "id": tid,
            "name": name,
            "duration_ms": 180000,
            "artists": [{"id": "ar1", "name": "Art"}],
            "album": {"name": "Al"},
        },
        "context": {"uri": "spotify:playlist:xyz"},
    }


class PersistTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp()) / "t.sqlite"
        init(self.tmp)
        self.con = sqlite3.connect(self.tmp)

    def tearDown(self) -> None:
        self.con.close()

    def test_new_track_insert_survives_extra_tracks_column(self) -> None:
        self.con.execute("ALTER TABLE tracks ADD COLUMN extra TEXT")
        n_new, n_dup, n_tracks = sp.persist_items(
            self.con,
            [_item("2026-08-31T12:00:00.000Z", "tid1")],
            ingested_at="t",
        )
        self.con.commit()
        self.assertEqual((n_new, n_dup, n_tracks), (1, 0, 1))
        row = self.con.execute(
            "SELECT track_id, track_name, duration_ms, not_found FROM tracks"
        ).fetchone()
        self.assertEqual(row, ("tid1", "Song", 180000, 0))

    def test_same_played_at_is_idempotent(self) -> None:
        item = _item("2026-08-31T12:00:00.000Z", "tid1")
        sp.persist_items(self.con, [item], ingested_at="t")
        n_new, n_dup, n_tracks = sp.persist_items(self.con, [item], ingested_at="t")
        self.con.commit()
        self.assertEqual((n_new, n_dup, n_tracks), (0, 1, 0))
        n_plays = self.con.execute("SELECT COUNT(*) FROM plays").fetchone()[0]
        self.assertEqual(n_plays, 1)


class PageTests(unittest.TestCase):
    def test_collect_recent_pages_walks_before_cursor(self) -> None:
        pages = [
            {
                "items": [_item("2026-08-31T12:00:00.000Z", "a")],
                "cursors": {"before": "111", "after": "222"},
                "next": "https://api.spotify.com/v1/me/player/recently-played?before=111",
            },
            {
                "items": [_item("2026-08-31T10:00:00.000Z", "b")],
                "cursors": {"before": "000", "after": "111"},
                "next": None,
            },
        ]

        class Fake:
            def __init__(self) -> None:
                self.calls: list[dict] = []
                self._pages = list(pages)

            def current_user_recently_played(self, limit=50, after=None, before=None):
                self.calls.append({"limit": limit, "after": after, "before": before})
                if not self._pages:
                    return {"items": []}
                return self._pages.pop(0)

        client = Fake()
        items = sp.collect_recent_pages(client, max_items=200)
        self.assertEqual([i["track"]["id"] for i in items], ["a", "b"])
        self.assertEqual(client.calls[0]["before"], None)
        self.assertEqual(client.calls[1]["before"], "111")
        self.assertEqual(len(client.calls), 2)

    def test_collect_recent_pages_stops_at_max_items(self) -> None:
        class Fake:
            def current_user_recently_played(self, limit=50, after=None, before=None):
                return {
                    "items": [_item(f"2026-08-31T12:00:0{i}.000Z", f"t{i}") for i in range(3)],
                    "cursors": {"before": "x"},
                    "next": "https://example/next",
                }

        items = sp.collect_recent_pages(Fake(), max_items=3)
        self.assertEqual(len(items), 3)


if __name__ == "__main__":
    unittest.main()
