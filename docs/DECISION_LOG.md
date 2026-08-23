# Decision / engineering log

Living file. Newest first.

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
