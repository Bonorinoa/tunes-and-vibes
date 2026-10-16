# Decision / engineering log

Living file. Newest first.

## 2026-10-15 — WHO-5 Monday catch-up (`tv-who5-catchup`)

Intent: no lost week, no new metrics. On 2026-10-11 the Sunday survey never reached Telegram: the live adapter was degraded, the standalone fallback hit `httpx.ConnectError`, and the queued redelivery never fired (known upstream bugs NousResearch/hermes-agent #123898, #127187). Augusto noticed and answered by hand on Monday (`channel=manual`), so week 2026-10-05 is stored. Fix: `scripts/who5_catchup.sh`, a no_agent cron on Monday 12:00 (inside the Monday grace window). If last week's `survey` row exists it prints nothing, so nothing is sent. If the row is missing it sends one reminder line plus the frozen survey text, reused from `tv_who5_survey.sh` rather than copied. An unreadable DB prints a loud one-liner. Questions-before-data still holds: the reminder carries no panel data. Tests: `tests/test_who5_catchup.py` (3 pass). Coverage audit, same day: WHO-5 has 8/8 weeks (2026-08-17 → 2026-10-05). Wellness has 53/53 days since 2026-08-24. Spotify is daily except the known Aug 28–30 gap. The ingest errors are short network drops, and the next 2-hourly run recovers from each one.

## 2026-08-31 — on-command HTML board (coverage, not Streamlit)

Intent: inspect the fridge without a new stack. `src/board.py` reads SQLite → `logs/board.html`. Cream page, dark ink, no new metrics, no emotion labels. Streamlit parked until the series is actually interesting.

## 2026-08-31 — digest/WHO-5 moved to 10:00 / 10:15

Laptop is rarely awake at 8am. Delivery, not collection: `tv-who5` Sunday 10:00, `tv-digest` daily 10:15 (after 10:07 ingest). `tv-ingest` stays `7 */2 * * *`. Collection window unchanged (all-day Sunday + Monday grace). Hermes catch-up still fires once on wake if a slot was missed; it does not replay every skipped 2h poll.

## 2026-08-31 — official WHO-5 week 1 + Spotify ingest unstick

Intent before compute: store Augusto's Sunday instrument (arrived Monday grace, desktop chat), then unstick live Spotify ingest. No new metrics, no `weekly` table, no VPS.

1. **WHO-5 week `2026-08-24`** — reply `3 2 4 2 4` → 15 raw / 60 pct. Channel `desktop`. Test-fire week `2026-08-17` stays labeled.
2. **Named-column inserts** — `tracks.not_found` (27 Aug) made positional `INSERT INTO tracks VALUES (?,?,?,?,?)` crash every poll since 27 Aug 23:07 UTC. Cron copy of `tv_ingest_all.sh` lacked `pipefail`, so heartbeat printed the traceback with `spotify(0)` and job status `ok`. Fix: named inserts + tests that ALTER an extra column; point cron ingest at the repo script (digest already does this).
3. **Paginate `recently-played`** — 6h/day listening overflows the 50-item page inside the 24h window whenever a poll is missed (sleep, crash). Walk `before` cursor up to 200 items. Still cannot recover >24h; Aug 28–30 live gap is gone until ESH.

## 2026-08-27 — foundation audit punch list (landed)

Intent before compute: keep the fridge, no new metrics. Commit the uncommitted 0.1.2 scar tissue (last-good Garmin, digest-from-SQLite, ReccoBeats `not_found`, tests) plus three correctness patches before Sunday's first official WHO-5.

1. **Monday grace** — `survey.week_start` on Monday pinned to the previous ISO Monday so a 31 Aug reply stores as week `2026-08-24`.
2. **Renderer honesty** — missing sleep is `—` not `0h 00m`; Garmin `avg_stress < 0` and morning `steps=0` with sentinel stress display as NA; valence prints ReccoBeats join coverage `n/N`.
3. **ReccoBeats transport ≠ catalog miss** — timeouts/connection resets retry next poll; lookup misses still persist on `tracks.not_found`.
4. **`ingest_all.sh` `pipefail`** — heartbeat `spotify(r)/garmin(r)/feats(r)` is the module exit, not `tail`'s 0.

No new streams, no `weekly` table, no pandas, no latent model. Analysis gate remains ≥6–8 weeks.

## 2026-08-26 — diagnose + patch morning digest (intent before compute)

Telegram 08:00 digest showed `GARMIN: api_error` and almost no useful daily panel. Forensics (do not recompute panel metrics until patches land):

1. **Transient Garmin timeout clobbered a good row.** 06:29 MST `GarminConnectConnectionError` (15s read timeout) upserted `api_error` + NULLs over the 04:41 `collected` row (sleep 483, HRV 80, RHR 43). Tokens are fine: 34 collected vs 2 timeouts. 08:07 recovered the data — seven minutes *after* the digest.
2. **Digest schedule is 7 min before ingest.** `tv-digest` `0 8 * * *` cats `logs/latest_snapshot.txt` written by `tv-ingest` `7 */2 * * *`. The 08:00 message is always the 06:29 snapshot.
3. **Snapshot renderer crashes on vendor strings.** `hrv_status='NONE'` (baseline not ready) goes through `_fmt` `:g` → Tuesday's digest was a traceback.
4. **Steps parser looks for the wrong key.** Garmin `get_stats` returns `totalSteps` (Aug 24 raw = 13409), never `steps`. Every day stored 0. `raw_json[:20000]` also drops the stats object once sleep is present, so later days cannot be re-parsed from disk.
5. **Spotify "no plays this local day" at 08:00** was mostly clock, not loss: overnight plays are previous local day; 06:58 MST plays landed at 08:07.

Intent: (a) never overwrite a substantive wellness row with transient `api_error`; (b) `_fmt` accepts strings; parse `totalSteps` + intensity minutes; compact `raw_json`; (c) digest regenerates the snapshot and prints a 4-day status strip; move digest to 08:15. ReccoBeats 109-miss retry storm parked for a follow-up — not what the user saw.

**Landed same morning.** 9/9 unittest. Live pull: today steps 385 (morning), sleep 483 / HRV 80 kept. Backfill: Aug 24 13409 steps from raw; Aug 25 live 13422 steps / 547 sleep. Digest body verified locally. `tv-digest` now 08:15 → `scripts/daily_digest.sh`.

## 2026-08-24 — tv-who5 delivery debugged; Plan C shipped

Four manual-fire tests to get the Sunday instrument delivering:

| # | Config | Result |
|---|---|---|
| 1 | unpinned model | empty response, 0 API calls |
| 2 | stealth/ox-alpha @ nous | empty content ×3 retries (works in interactive sessions only) |
| 3 | deepseek-v4-flash-0731 @ nous | HTTP 404 — slug resolved against OpenRouter, doesn't exist there |
| 4 | google/gemma-4-26b-a4b-it:free @ openrouter | HTTP 404 — account privacy/guardrail settings filter all endpoints |

**Root cause layers:** (a) cron jobs resolve models in fresh sessions and silently fall through to OpenRouter unless pinned; (b) user's OpenRouter privacy settings currently block free-tier endpoints entirely.

**Resolution:** job converted to **no_agent** (`scripts: tv_who5_survey.sh`) — survey text delivered verbatim to Telegram, zero LLM in the delivery path. Trade-offs accepted: duplicate-week guard lost (mitigated: `survey.py` upserts by ISO week, last-valid-wins); reply parsing moves to the live home-channel session, where models provably work.

**Action item surfaced:** EconLLM writers (Wed 09:00/09:05) use the exact gemma:free combo that just 404'd. Last OK run Aug 19. Check openrouter.ai/settings/privacy before Wednesday or expect writer failures.

## 2026-08-24 — Protocol audit + L5 wired

- Soundness audit done; 7 rulings frozen in `docs/PROTOCOL.md` v1.0 (R1 WHO-5 overlap, R2 ±10pt noise band, R3 valence-floor switch rule, R4 term-calendar covariates, R5 descriptive-only dashboards, R6 HRV z-gate ≥14 nights, R7 status vocabulary).
- `src/survey.py`: defensive parser (separators, range checks, last-valid-wins upsert by ISO week), strain flag ≤28 pct informational only.
- Cron deployed via Hermes scheduler (gateway-hosted, survives laptop wake):
  - `tv-ingest` (2be97cf1ba6e): every 2h at :07, no-agent bash chain, one heartbeat line, exit 0 always.
  - `tv-digest` (c445e15e0ad1): daily 08:00 → Telegram (WHO-5 trend + latest snapshot).
  - `tv-who5` (90661dafb8e1): Sunday 08:00 → Telegram, attach_to_session so replies parse in-session; questions-before-data ordering enforced; duplicate-week guard.
- Watch-off month ends tonight; HRV baseline rebuild ~3 weeks before z-scores unlock (R6).

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
