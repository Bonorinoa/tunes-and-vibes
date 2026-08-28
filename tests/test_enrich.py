"""ReccoBeats miss cache: persist catalog-absent tracks, skip on next poll."""

from __future__ import annotations

import sqlite3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from schema import DDL  # noqa: E402
import enrich_features as ef  # noqa: E402


def _db() -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    con.executescript(DDL)
    return con


class MissCacheTests(unittest.TestCase):
    def test_pending_skips_not_found(self) -> None:
        con = _db()
        con.execute("INSERT INTO tracks VALUES ('a','A','x','t',100,0)")
        con.execute("INSERT INTO tracks VALUES ('b','B','x','t',100,1)")
        con.execute("INSERT INTO tracks VALUES ('c','C','x','t',100,0)")
        con.execute(
            "INSERT INTO features (rb_uuid, track_id, valence, fetched_at) VALUES ('u','c',0.1,'t')"
        )
        self.assertEqual(ef.pending_ids(con), ["a"])

    def test_misses_are_ids_not_in_pairs(self) -> None:
        chunk = ["a", "b", "c"]
        pairs = [("a", "uuid-a")]
        self.assertEqual(ef.misses(chunk, pairs), ["b", "c"])

    def test_mark_not_found_drops_from_pending(self) -> None:
        con = _db()
        con.execute("INSERT INTO tracks VALUES ('a','A','x','t',100,0)")
        ef.mark_not_found(con, ["a"])
        self.assertEqual(ef.pending_ids(con), [])
        self.assertEqual(
            con.execute("SELECT not_found FROM tracks WHERE track_id='a'").fetchone()[0],
            1,
        )

    def test_transport_failure_does_not_mark_not_found(self) -> None:
        con = _db()
        con.execute("INSERT INTO tracks VALUES ('a','A','x','t',100,0)")
        n_fail, to_fetch = ef.apply_lookup(con, ["a"], None)
        self.assertEqual(n_fail, 1)
        self.assertEqual(to_fetch, [])
        self.assertEqual(ef.pending_ids(con), ["a"])

    def test_catalog_miss_still_persists(self) -> None:
        con = _db()
        con.execute("INSERT INTO tracks VALUES ('a','A','x','t',100,0)")
        n_fail, to_fetch = ef.apply_lookup(con, ["a"], [])
        self.assertEqual(n_fail, 1)
        self.assertEqual(to_fetch, [])
        self.assertEqual(ef.pending_ids(con), [])


if __name__ == "__main__":
    unittest.main()
