"""SQLite schema. One file, stdlib only. Run once (idempotent)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parents[1] / "data" / "panel.sqlite"

DDL = """
CREATE TABLE IF NOT EXISTS plays (
  played_at     TEXT PRIMARY KEY,   -- Spotify UTC timestamp; natural dedupe key
  track_id      TEXT,
  track_name    TEXT,
  artist_ids    TEXT,
  artist_names  TEXT,
  album_name    TEXT,
  context_type  TEXT,
  context_uri   TEXT,
  ms_played     INTEGER,
  ingested_at   TEXT
);

CREATE TABLE IF NOT EXISTS tracks (
  track_id     TEXT PRIMARY KEY,
  track_name   TEXT,
  artist_names TEXT,
  first_seen   TEXT,
  duration_ms  INTEGER,
  not_found    INTEGER DEFAULT 0   -- ReccoBeats catalog miss; never retry
);

-- ReccoBeats features are static per track: fetch once, never again.
CREATE TABLE IF NOT EXISTS features (
  rb_uuid           TEXT PRIMARY KEY,
  track_id          TEXT UNIQUE,
  valence REAL, energy REAL, danceability REAL, tempo REAL,
  acousticness REAL, instrumentalness REAL, liveness REAL,
  loudness REAL, speechiness REAL, key INTEGER, mode INTEGER,
  not_found         INTEGER DEFAULT 0,   -- 1 if ReccoBeats catalog miss
  fetched_at        TEXT
);

-- One row per LOCAL calendar day. Night metrics belong to the wake date.
CREATE TABLE IF NOT EXISTS wellness (
  date         TEXT PRIMARY KEY,    -- YYYY-MM-DD local
  status       TEXT NOT NULL,       -- collected|not_worn|not_synced|synced_zero|api_error
  hrv_rmssd    REAL,
  hrv_status   TEXT,
  sleep_min    REAL,
  rem_min      REAL,
  deep_min     REAL,
  sleep_score  REAL,
  rhr          REAL,
  rhr_7d       REAL,
  bb_charged   INTEGER,
  bb_drained   INTEGER,
  avg_stress   REAL,
  spo2_avg     REAL,
  steps        INTEGER,
  active_kcal  REAL,
  mod_min      REAL,
  vig_min      REAL,
  note         TEXT,
  raw_json     TEXT,
  ingested_at  TEXT
);

CREATE TABLE IF NOT EXISTS survey (
  week_start   TEXT PRIMARY KEY,    -- ISO Monday of the reported week
  responded_at TEXT,
  i1 INTEGER, i2 INTEGER, i3 INTEGER, i4 INTEGER, i5 INTEGER,
  raw_total    INTEGER,
  pct          REAL,
  channel      TEXT,
  note         TEXT
);

CREATE TABLE IF NOT EXISTS ingest_log (
  ts      TEXT,
  source  TEXT,
  outcome TEXT,
  detail  TEXT
);
"""


def init(db_path: Path = DB) -> Path:
    db_path.parent.mkdir(exist_ok=True)
    con = sqlite3.connect(db_path)
    con.executescript(DDL)
    # Self-migration for DBs created before duration_ms / intensity columns / not_found existed.
    for stmt in (
        "ALTER TABLE tracks ADD COLUMN duration_ms INTEGER",
        "ALTER TABLE tracks ADD COLUMN not_found INTEGER DEFAULT 0",
        "ALTER TABLE wellness ADD COLUMN mod_min REAL",
        "ALTER TABLE wellness ADD COLUMN vig_min REAL",
        "ALTER TABLE features ADD COLUMN not_found INTEGER DEFAULT 0",
    ):
        try:
            con.execute(stmt)
        except sqlite3.OperationalError:
            pass  # column already exists
    con.execute("PRAGMA journal_mode=WAL")
    con.commit()
    con.close()
    return db_path


if __name__ == "__main__":
    print("schema ok:", init())
