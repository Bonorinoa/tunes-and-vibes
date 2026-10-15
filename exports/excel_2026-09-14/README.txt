Tunes & Vibes Excel export  2026-09-14
Source: data/panel.sqlite  TZ: America/Phoenix for local_date / wellness.date

START HERE
  panel_daily.csv    one row per local day (Garmin + music + WHO-5 of that ISO week)
  panel_weekly.csv   ISO Monday weeks aligned to survey.week_start

RAW
  plays.csv / plays_with_features.csv / tracks.csv / features.csv
  wellness.csv  (raw_json omitted — forensic blob, not Excel-friendly)
  survey.csv / ingest_log.csv

LABELS
  garmin_raw / reccobeats_derived / who5_anchored
  ReccoBeats NULLs are omitted from means; use features_coverage n/N
  WHO-5 asks about the last TWO weeks — consecutive Sundays overlap
  Night metrics sit on the wake date (ingest convention)
  Empty cells = missing, not zero
Encoding: UTF-8 with BOM (Excel).
