#!/bin/bash
# Tunes-and-Vibes ingest chain. Designed for no-agent cron: one heartbeat line,
# never crashes the scheduler. Module failures are visible in the line + log.
set -uo pipefail
cd "$HOME/Hermes/Projects/tunes-and-vibes" || exit 1
mkdir -p logs
PY=./.venv/bin/python

"$PY" src/schema.py >/dev/null 2>&1

s1=$("$PY" src/ingest_spotify.py 2>&1 | tail -1); r1=$?
s2=$("$PY" src/ingest_garmin.py 2>&1 | tail -1); r2=$?
s3=$("$PY" src/enrich_features.py 2>&1 | tail -1); r3=$?

"$PY" src/snapshot.py > logs/latest_snapshot.txt 2>&1 || true

echo "[tv-ingest $(date '+%F %H:%M')] spotify($r1): $s1 | garmin($r2): $s2 | feats($r3): $s3"
exit 0
