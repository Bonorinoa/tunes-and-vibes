# 001: VPS ingest from HEL1 (read-only spike)

**Date:** 2026-09-07  
**Host:** `ubuntu-4gb-hel1-2` (Hetzner CX23, Helsinki) as `parrot@89.167.62.23`  
**Question:** Can one Tunes-and-Vibes ingest run on the Personal Parrot VPS without touching Loro (no Hermes cron, no Telegram, no `~/venv`, no systemd timer)?

Throwaway tree: `/home/parrot/fridge-spike/` (chmod 700). Own `.venv` (CPython 3.12.3). Copied `.env` + `auth/` + a snapshot of `data/panel.sqlite`. Mac production DB was not written back.

## Given / When / Then

Given Loro is idle-enough (no live inbound call; leftover selftest rooms had already hung up), when we run `src/ingest_spotify.py` + `src/ingest_garmin.py` + `src/enrich_features.py` with `TZ=America/Phoenix` and `HOME=/home/parrot/fridge-spike`, then Spotify and Garmin accept the existing tokens from Helsinki, ReccoBeats is a no-op on a warm cache, peak RSS stays tens of MB, and `parrot-agent` / `hermes-gateway` RSS do not move.

## What we ran

```
timeout 30  python src/ingest_spotify.py
timeout 45  python src/ingest_garmin.py
timeout 90  python src/enrich_features.py
```

No `tv-*` cron, no new Telegram bot, no Loro config edit, no unit files.

## Results (live)

| Step | rc | wall | max RSS | outcome |
|---|---|---|---|---|
| Spotify | 0 | 1.08 s | 44 MB | `ok` · `new=0 dup=50 new_tracks=0 pages_items=50` |
| Garmin | 0 | 1.75 s | 39 MB | `not_worn` · `api ok · all metrics empty (watch off?)` — **same status as Mac 14:07 MST** |
| ReccoBeats | 0 | 0.50 s | 30 MB | `done=0 failed=0` · cache 531 / not_found 299 |

Host around the run:

- Before: 1402 Mi used / **2417 Mi available**, load 0.35, swap 0
- Right after: 1455 / 2364, load 0.35, swap 0
- `hermes-gateway` RSS **244184 kB → 244184 kB**
- `parrot-agent` main **141096 → 141100 kB** (noise)
- `~/.garth` / `~/.garminconnect` under `/home/parrot`: **none** (HOME isolated)
- Token files not rewritten (Spotify mtime still 21:07Z from the Mac poll; Garmin still 12:06Z)
- VPS Hermes cron still empty; no fridge systemd units
- Loro services still `active` (`parrot-agent`, `livekit-server`, user `hermes-gateway`)

Tree size: **109 MB** (mostly `.venv`; `curl_cffi` + `garminconnect` 0.3.11).

## Verdict: VALIDATED (with constraints)

Helsinki is a viable ingest host for this poll. Garmin did **not** 401/403 on the session cookies. Spotify refresh was not even needed. Resource cost is a rounding error next to Loro's 1.1 G cgroup cap.

### What worked

- Isolated dir + venv, not `~/venv` and not `~/.hermes`
- Existing Garmin `auth/garmin/garmin_tokens.json` worked from HEL1 on `garminconnect==0.3.11` (Mac venv is still `0.3.2`)
- `not_worn` is a real API success, matching the laptop — not a geo-empty payload
- HOME isolation kept garth off Loro's homedir
- `TZ=America/Phoenix` made `date.today()` match the Mac calendar day (UTC happened to be the same date at 14:40 MST; it will not be after 17:00 MST)

### What we did **not** prove

- ReccoBeats cold path (pending=0 on this snapshot). That is the slow tail on the Mac (timeouts, not CPU).
- A run overlapping a real inbound call. Guard is still required; this spike waited out `selftest-*` rooms.
- Multi-day Garmin token refresh / MFA from a new ASN
- Digest / WHO-5 delivery (intentionally out of scope)
- Single source-of-truth sqlite (VPS copy now has extra `ingest_log` rows; Mac DB untouched)

### Surprises

- `python3-venv` apt package is **not** installed; `python3 -m venv` still created a working venv with pip.
- Unpinned `pip install -r requirements.txt` pulled `garminconnect 0.3.11` vs Mac `0.3.2`. Tokens still loaded. Pin before any real move.
- Box is UTC. Without `TZ=America/Phoenix`, wellness `date` will flip at 17:00 Phoenix.
- Pip's Garmin stack drags in logfire/OpenTelemetry. Harmless here; ugly for a 3-second cron.

### Recommendation for the real build (not done)

Keep the split from the consult:

1. **Ingest-only** sidecar: systemd timer, own venv, `MemoryMax≈256M`, `Nice=10`, `TZ=America/Phoenix`, skip-if-call-active (file/health, not a chatty API).
2. **Do not** put `tv-*` on Loro's Hermes gateway or `@Pparrots_bot`.
3. Pin `garminconnect`/`garth`/`spotipy` to the Mac freeze.
4. One sqlite as source of truth (VPS) before a second writer exists. Two copies will fork the series.
5. Leave WHO-5 + digest on the Mac default Telegram until ingest has a few quiet days.
6. Delete or lock down `/home/parrot/fridge-spike/` when the spike is done — it holds `.env` + Garmin session cookies.

Leave the tree in place until Augusto says otherwise. No timer was installed.
