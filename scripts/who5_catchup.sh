#!/bin/bash
# WHO-5 Monday catch-up (added 2026-10-15). Runs Monday 12:00 inside the protocol's Monday grace window.
# If last week's survey row exists: print nothing -> Hermes no_agent cron sends nothing.
# If it is missing: print one reminder line + the frozen survey text (reused, never copied).
# Why: Telegram deliveries rejected with send_path_degraded are not redelivered (upstream
# NousResearch/hermes-agent #123898, #127187). 2026-10-11 was lost that way.
set -u
DB="${TV_DB:-$HOME/Hermes/Projects/tunes-and-vibes/data/panel.sqlite}"
SURVEY="${TV_SURVEY_SCRIPT:-$HOME/.hermes/scripts/tv_who5_survey.sh}"
TODAY="${TV_TODAY:-$(date +%F)}"   # override for tests

# ISO Monday of the week being reported = the Monday 7 days before this Monday.
DOW=$(date -j -f %F "$TODAY" +%u)                       # 1 = Monday
WEEK_START=$(date -j -v-"$(( DOW - 1 + 7 ))"d -f %F "$TODAY" +%F)

if ! COUNT=$(sqlite3 -readonly "$DB" "SELECT COUNT(*) FROM survey WHERE week_start='$WEEK_START';" 2>/dev/null); then
  echo "tunes-and-vibes: WHO-5 catch-up could not read $DB. Check the panel database."
  exit 0
fi

if [ "$COUNT" -gt 0 ]; then
  exit 0   # answered: stay silent
fi

echo "Reminder: no WHO-5 answer stored for the week of $WEEK_START. Monday grace ends tonight."
echo
bash "$SURVEY"
