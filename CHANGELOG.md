# CHANGELOG

## 0.1.3 — 2026-08-27

- WHO-5 Monday grace stores on Sunday's ISO week (`week_start` 31 Aug → 24 Aug).
- Snapshot: missing sleep is `—` not `0h 00m`; Garmin stress `< 0` and morning `steps=0`+sentinel stress display as NA; ReccoBeats valence prints join coverage `n/N`.
- ReccoBeats: transport/timeout is not `tracks.not_found` (retry next poll). Catalog misses still persist.
- `ingest_all.sh`: `pipefail` so heartbeat exit codes are the module's, not `tail`'s.

## 0.1.2 — 2026-08-27

- ReccoBeats misses persist on `tracks.not_found` (no 2h retry storm).
- WHO-5 CLI restored (`--store`); tests use a temp DB, never the live panel.
- Digest + enrich unit tests. 23 tests, stdlib unittest.
- Removed one-off scratch/src probes and unused pandas/matplotlib runtime deps.

## 0.1.1 — 2026-08-26

- Garmin: parse `totalSteps` + intensity minutes; compact `raw_json`; transient `api_error` no longer wipes a good day.
- Snapshot: `_fmt` accepts vendor strings (`hrv_status=NONE`); yesterday-plays hint when today is empty.
- Digest: `src/digest.py` regenerates from SQLite + 4-day Garmin strip. Cron moved to 08:15.
- Tests: `tests/test_snapshot.py`, `tests/test_garmin.py` (stdlib unittest).

## 0.0.1 — 2026-08-23

- Scaffold: secrets template, docs, empty data planes.
- No ingest code yet.
