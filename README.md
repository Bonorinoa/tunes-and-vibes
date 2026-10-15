# Tunes and Vibes

n=1 panel: weekly WHO-5 + passive Spotify listening + Garmin vivoactive 5.

**Status:** live fridge. Ingest every 2h (`tv-ingest` on the default Hermes profile), digest 10:15 Telegram, WHO-5 Sunday 10:00. Official WHO-5 series started Sunday 2026-08-30 (week `2026-08-24` stored Monday grace). The 2026-08-17 row is a labeled test-fire (60/100).

## What this is

A semester-length personal dataset for the relationship between music and wellbeing. Sensors and streams are *not* treated as emotions. Garmin covers arousal/recovery. ReccoBeats valence/energy is a behavioral trace. WHO-5 is the weekly validation anchor.

## Layout

```
.env                 secrets (gitignored — you fill this)
.env.example         same keys, empty
src/                 ingest + snapshot + digest + WHO-5 store
data/                sqlite + derived tables
exports/incoming/    drop Spotify ESH + Garmin archive zips here
scratch/             temp files stay inside the project (approval-gate safe)
logs/                ingest logs
docs/                architecture, decisions, open questions
```

## Setup (now)

1. Copy values into `.env`:
   - `SPOTIFY_CLIENT_ID`
   - `SPOTIFY_CLIENT_SECRET`
2. Optional but start the clock: request **Extended Streaming History** at [spotify.com/account/privacy](https://www.spotify.com/account/privacy) and **Export Your Data** from Garmin Connect → Account Settings.
3. Tell Hermes L2 is ready. OAuth happens on this machine against `http://127.0.0.1:8888/callback`.

Do not install packages into system Python. Project venv comes with L2.

## Run & verify

Use the project venv, never system Python:

```bash
./.venv/bin/python -m unittest discover -s tests -v   # verification: full suite
scripts/ingest_all.sh                                  # pull Spotify + Garmin
./.venv/bin/python src/snapshot.py                     # daily/weekly snapshot
./.venv/bin/python src/board.py                        # coverage board → logs/board.html
```

Scheduling is live on the default Hermes profile (`tv-ingest` every 2h, `tv-digest` 10:15, `tv-who5` Sunday 10:00) — do not duplicate those jobs into this profile.

## Hard rules

- Missing data is a status, never a crash.
- Raw rows are immutable. Cleaning happens downstream.
- No metric is named an emotion until it survives contact with WHO-5.
- No daily self-report. PHQ-2 is deferred.
- Scheduling is live (default-profile cron). Do not duplicate jobs into this profile.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and [docs/DECISION_LOG.md](docs/DECISION_LOG.md).
