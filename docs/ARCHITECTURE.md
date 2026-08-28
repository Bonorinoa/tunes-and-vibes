# Architecture

Three planes. Plane 1 is live. Planes 2–3 wait for archive zips and ≥6–8 weeks of WHO-5.

## Planes

1. **Live feed** — Spotify `GET /me/player/recently-played` (≤50 items) + Garmin Connect via `garth`/`garminconnect`. Local SQLite. Idempotent append, dedupe on natural keys.
2. **Archive** — one-time Spotify Extended Streaming History + Garmin account export. Fuzzy join on artist+title; label match confidence; never silently drop.
3. **Anchor** — WHO-5, all-day Sunday, one-line reply `4 4 3 4 5`. Questions before any digest numbers. Telegram is the delivery surface (no_agent cron). Monday 23:59 is grace for Sunday's week.

## Feature join

Spotify no longer gives audio features to new apps. ReccoBeats is keyless:

1. `GET /v1/track?ids=<spotify_ids>` → internal UUID
2. `GET /v1/track/<uuid>/audio-features` → valence, energy, danceability, tempo, …

Verified 2026-08-23 on *Blinding Lights*: values match the old Spotify Echo Nest numbers to three decimals.

## Status vocabulary (every day-row)

`collected | not_worn | not_synced | synced_zero | api_error | missing`

Aggregates report coverage (`hrv 5/7`) and accept NA. Tests punch holes in synthetic panels.

## Isolation ladder

| Rung | What | Gate |
|------|------|------|
| L0 | ReccoBeats | done |
| L1 | Python env | done · `.venv` |
| L2 | Spotify OAuth → recently-played → SQLite | done |
| L3 | Garmin login → one night of sleep/HRV | done |
| L4 | Daily + weekly snapshot from real partial data | done |
| L5 | Telegram + cron | done (exports ingest still parked) |

## Runtime constraints (this Mac)

- Hermes terminal approvals time out if nobody clicks. Unattended cron cannot depend on prompts.
- Pipeline must not delete outside this project directory (even `/tmp` cleanup can trip the gate).
- System Python 3.9.6 is not the runtime. Use `.venv` here.

## Not yet

Dedicated Hermes profile exists (`tunes-and-vibes`). Cron stays on the **default** profile. VPS / always-on box only after a pre-committed tripwire (missed Sunday because Mac slept, Spotify window loss, or travel >48h). Latent models deferred to spring / ≥8 anchored weeks.
