# src

Live ingest + snapshot + digest. Isolation ladder is done; this folder is the runtime.

| module | job |
|---|---|
| `schema.py` | SQLite DDL + self-migration |
| `ingest_spotify.py` | recently-played → plays/tracks |
| `ingest_garmin.py` | Connect pull; last-good wins on transient errors |
| `garmin_login.py` | One-time interactive MFA login |
| `spotify_auth.py` | One-time OAuth |
| `enrich_features.py` | ReccoBeats cache; `tracks.not_found` skips catalog misses |
| `snapshot.py` | daily + weekly ASCII panels |
| `digest.py` | Telegram body (WHO-5 + panels + 4-day strip) |
| `survey.py` | WHO-5 parse/store CLI `--store "4 4 3 4 5"` |

Tests: `../tests/` — `./.venv/bin/python -m unittest discover -s tests -v`.
