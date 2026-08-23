# Decision / engineering log

Living file. Newest first.

## 2026-08-24 — L4 built and passing

- Full chain live: `schema` → `ingest_spotify` → `ingest_garmin` → `enrich_features` → `snapshot`. Idempotency verified (re-run: 0 new / 50 dups).
- Status contract fixed: API success with all-empty metrics now writes **not_worn**, not collected. First real catch: watch off >1 month produced empty-but-200 responses.
- ReccoBeats batch cap discovered (~50 IDs → HTTP 400): `_lookup_ids` splits adaptively on failure. 41/50 enriched first pass; 9 tracks absent from their catalog stay pending forever-by-design.
- `recently-played` carries no ms_played → listening minutes estimated from track durations (`tracks.duration_ms`, backfilled opportunistically; 210s fallback).
- Lesson: agent-side heredoc scripts trip the approval gate; file-based scripts don't. Pyright caught a missing sqlite3 import pre-run — keep static analysis on.
- File-swap incident: two write_file calls crossed mid-batch, leaving schema.py holding enrichment code. Caught on read-back before next run. Always re-read after suspicious tool output.
- Next: cron scheduling (L5) awaits explicit go — user wants to eyeball snapshots first.

## 2026-08-24 — Telegram wired (deferred tier starts)

- Bot created via BotFather; token stored in both `.env` files (project + Hermes home). Gateway restart picked it up: `Telegram ✓ configured`.
- Gotcha worth remembering: Hermes-home `.env` ships with the whole TELEGRAM block **commented out** — uncommenting just the token line is enough; every other var stays off (DM pairing > allowlists for us; `/sethome` sets delivery target).
- `/sethome` done from phone. Cron deliveries route to the bot chat.
- Exports policy logged: Account data (1y) later for preference/instrument tuning; ESH optional (no subset picker — packages are fixed). Neither blocks emotions panel.

## 2026-08-24 — L2 + L3 passed

- Spotify OAuth done via `src/spotify_auth.py` (spotipy, browser consent, refresh token in `.env`, cache in `auth/`). Recently-played smoke test returned live items.
- Garmin login done via `src/garmin_login.py` (garminconnect 0.3.x). Tokens cached in `auth/garmin/`.
- Quirk: Garmin mobile login endpoints return **429 per IP** before falling back to the browser-style flow; login still succeeds. Harmless at our volume; expect it on re-auth days.
- Endpoints verified live: sleep (`dailySleepDTO`, `sleepLevels`, `remSleepData`), daily stats (bodyBattery charged/drained, avgStress, SpO2…), heart-rates (restingHeartRate, 7-day avg).
- Approval-gate lesson: venv/pip installs and localhost listeners repeatedly timed out agent-side → user runs one-time setup commands in Terminal.app directly. Agent-side runs are fine for read-only probes inside the project dir.
- Next: L4 — SQLite schema + first ingest of today's plays/wellness + render daily & weekly snapshots from real partial data.

## 2026-08-23 — scaffold

- Project home: `~/Hermes/Projects/tunes-and-vibes/` (matches Spotify app name; Brain Fart graduation path).
- Secrets live only in `.env`. Scaffolded empty; user fills manually. Client secret is not stored in docs or git.
- Spotify app: Web API only. Redirect `http://127.0.0.1:8888/callback` must be an added chip, not just typed.
- Channel: Telegram, dedicated Hermes surface (no prior Telegram habits). Setup deferred until isolation works.
- WHO-5 weekly, all-day Sunday window, grace through Monday 23:59. PHQ-2 later if needed. No daily survey.
- ReccoBeats proven live; two-step ID map required (Spotify ID → ReccoBeats UUID → features).
- L1: system Python lacks pandas/matplotlib/requests. Isolated `.venv` at L2, not a system install.
- Scheduling and VPS parked. Prove snapshots first.
- Missing data is a row status. Watch-off ≠ crash.
- Do not name passive metrics "emotion" until WHO-5 contact (`garmin_raw`, `reccobeats_derived`, `latent_unvalidated`).

## 2026-08-22 — kickoff (pre-repo)

- Motivating question: emotions × music. Homework-inspired, original n=1 panel through year-end.
- Passive Spotify or it dies. Garmin vivoactive 5 as somatic/arousal stream.
- Self-report is a calibration instrument, not the outcome.
