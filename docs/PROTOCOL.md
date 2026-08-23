# Frozen Protocol v1.0 — ratified 2026-08-24

Changes require logging intent in DECISION_LOG.md **before** recomputing anything.

## Instruments

| Stream | Instrument | Cadence | Label |
|---|---|---|---|
| Wellbeing anchor | WHO-5 (5 items, 0–5, 2-week recall) | Weekly, all-day Sunday window; grace to Mon 23:59 | `who5_anchored` |
| Somatic/arousal | Garmin nightly HRV, sleep duration/midpoint, RHR, BB charge/drain, stress avg | Daily pull | `garmin_raw` |
| Behavioral trace | ReccoBeats valence/energy/danceability/tempo of played tracks | Continuous ingest | `reccobeats_derived` |
| Latent state | HMM / dynamic factor on daily features | Deferred to spring, ≥8 anchored weeks | `latent_unvalidated` |

PHQ-2 may be added after ~4 weeks if WHO-5 feels too thin. No other additions in v1.0. **No daily self-report, ever, in this protocol.**

## Rulings (audit 2026-08-24)

- **R1 — WHO-5 overlap:** weekly sampling of a 2-week-recall instrument creates 8-day window overlaps → built-in autocorrelation. Keep official wording (cutoff validity); analyze AR-aware; optionally alternate weeks from week 6.
- **R2 — noise floor:** single-administration noise ≈ ±3–4 pct-points. A real change = Δ ≥ 10 points sustained ≥ 2 weeks. Below threshold: report "noise band."
- **R3 — floor effect:** repertoire sits near valence 0 where resolution degrades. If weekly mean < 0.15 through week 3, primary music metric switches to rank-based (share of plays in bottom feature quartile).
- **R4 — workload confound:** ASU term calendar, day-of-week, steps, intensity minutes are covariates in every analysis from day one.
- **R5 — reactivity:** passive dashboards stay descriptive; never evaluative scores. No optimization incentives against the panel itself.
- **R6 — HRV warmup:** z-scores suppressed until ≥14 worn nights post-resume (baseline rebuild); absolute values + coverage shown meanwhile.
- **R7 — status vocabulary:** every wellness day-row carries status ∈ {collected, not_worn, not_synced, synced_zero, api_error}. Missing ≠ zero. Aggregates report coverage n/N.

## Analysis rules

- Hypothesis generation only; effect sizes + plots; no p-value salad.
- Within-person standardization exclusively (z/rank vs own baseline).
- Vendor composites (Body Battery, stress score) stored but not modeled as raw-signal substitutes; they are collinear derivatives.
- Missed weeks = explicit NA rows; never imputed silently.

## Privacy

Raw data local-only (`data/*.sqlite` gitignored). Only public track IDs leave the machine (ReccoBeats). Secrets in `.env` only. Telegram bot is single-user (DM pairing).
