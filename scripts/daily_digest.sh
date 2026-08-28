#!/bin/bash
# Tunes-and-Vibes daily digest. Regenerates from SQLite; never cats a stale crash.
set -u
cd "$HOME/Hermes/Projects/tunes-and-vibes" || exit 1
mkdir -p logs
./.venv/bin/python src/digest.py
exit 0
