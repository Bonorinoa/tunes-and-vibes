"""Daily + weekly snapshot rendering from SQLite. Read-only. Stdlib only.

Missing data is a state, not an error: every section reports coverage,
empty states render as empty panels.
"""

from __future__ import annotations

import sqlite3
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "panel.sqlite"
LOCAL_TZ = ZoneInfo("America/Phoenix")

W = 62  # panel width (kept for back-compat; not used in telegram output)


def _box(title: str, lines: list[str]) -> str:
    """Plain section header + body. Telegram-friendly: no box-drawing chars,
    no line clipping. Each non-empty `line` becomes a bullet; leading-space
    convention from the caller is preserved (1 space = nested under a
    category label)."""
    out = [f"**{title}**"]
    for ln in lines:
        s = ln.lstrip()
        if not s:
            continue
        # If caller already prefixed a bullet, keep their alignment; else add ours.
        if s.startswith("•"):
            indent = len(ln) - len(s)
            out.append(" " * indent + s)
        else:
            indent = len(ln) - len(s)
            out.append((" " * indent) + f"• {s}")
    return "\n".join(out)


def _fmt(v, suffix=""):
    if v is None:
        return "—"
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return f"{v}{suffix}"
    if suffix == "" and isinstance(v, float):
        return f"{v:.2f}".rstrip("0").rstrip(".")
    return f"{v:g}{suffix}"


def f2(v) -> str:
    """Fixed two decimals or em-dash."""
    return "—" if v is None else f"{v:.2f}"


def _sleep_clock(sleep) -> str:
    if sleep is None:
        return "—"
    hh, mm = divmod(int(sleep), 60)
    return f"{hh}h {mm:02d}m"


def _stress_label(stress) -> str:
    if stress is None or (isinstance(stress, (int, float)) and not isinstance(stress, bool) and stress < 0):
        return "—"
    return _fmt(stress)


def _steps_label(steps, stress) -> str:
    """0 steps + missing/sentinel stress = day stats not in yet, not a true zero."""
    if steps == 0 and (
        stress is None
        or (isinstance(stress, (int, float)) and not isinstance(stress, bool) and stress < 0)
    ):
        return "—"
    return _fmt(steps)


def daily(con: sqlite3.Connection, day: str | None = None) -> str:
    day = day or datetime.now(LOCAL_TZ).strftime("%Y-%m-%d")
    lines: list[str] = []
    wrow = con.execute(
        "SELECT status,sleep_min,rem_min,rhr,rhr_7d,hrv_rmssd,hrv_status,"
        "bb_charged,bb_drained,avg_stress,steps FROM wellness WHERE date=?",
        (day,),
    ).fetchone()
    if wrow:
        (_st, sleep, rem, rhr, rhr7, hrv, hrvs, bbc, bbd, stress, steps) = wrow
        st = wrow[0]
        if st == "collected":
            lines.append(f"GARMIN ({st})")
            hrv_label = "—" if not hrvs or str(hrvs).upper() == "NONE" else str(hrvs)
            lines.append(f" Sleep     {_sleep_clock(sleep)} · REM {_fmt(rem, 'm')}")
            lines.append(f" HRV       {_fmt(hrv)}ms [{hrv_label}] · RHR {_fmt(rhr)} (7d {_fmt(rhr7)})")
            lines.append(f" Battery   +{_fmt(bbc)} / -{_fmt(bbd)} · stress avg {_stress_label(stress)}")
            lines.append(f" Steps     {_steps_label(steps, stress)}")
        else:
            lines.append(f"GARMIN: {st}" + (f" — see ingest_log" if st == "api_error" else ""))
    else:
        lines.append("GARMIN: no row yet")

    # Plays grouped by LOCAL calendar day from UTC stamps.
    start_utc = datetime.fromisoformat(f"{day}T00:00:00").replace(tzinfo=LOCAL_TZ).astimezone(timezone.utc)
    end_utc = start_utc + timedelta(days=1)
    prow = con.execute(
        """SELECT COUNT(*), COALESCE(SUM(COALESCE(t.duration_ms, 210000)), 0),
                  SUM(CASE WHEN p.track_id IS NULL THEN 1 ELSE 0 END),
                  COUNT(DISTINCT p.artist_names),
                  AVG(f.valence), AVG(f.energy), COUNT(f.valence)
           FROM plays p
           LEFT JOIN tracks t ON t.track_id = p.track_id
           LEFT JOIN features f ON f.track_id = p.track_id
           WHERE p.played_at >= ? AND p.played_at < ?""",
        (start_utc.isoformat().replace("+00:00", "Z"), end_utc.isoformat().replace("+00:00", "Z")),
    ).fetchone()
    n_plays, total_ms, n_pod, n_artists, val, ene, n_feat = prow
    if n_plays:
        mins = int((total_ms or 0) / 60000)
        pod_share = (n_pod / n_plays * 100) if n_plays else 0
        lines.append("")
        lines.append("SPOTIFY")
        feat_note = (
            f" · valence {f2(val)} ({n_feat}/{n_plays}) · energy {f2(ene)}"
            if val is not None
            else ""
        )
        lines.append(
            f"  • ~{mins} min · {n_plays} plays{feat_note} · podcasts {pod_share:.0f}%"
        )
        top = con.execute(
            """SELECT artist_names, COUNT(*) c FROM plays
               WHERE played_at >= ? AND played_at < ? AND artist_names IS NOT NULL
               GROUP BY artist_names ORDER BY c DESC LIMIT 3""",
            (start_utc.isoformat().replace("+00:00", "Z"), end_utc.isoformat().replace("+00:00", "Z")),
        ).fetchall()
        if top:
            lines.append("  • Top: " + " · ".join(f"{a.split(',')[0]} ×{c}" for a, c in top))
    else:
        lines.append("")
        lines.append("SPOTIFY: no plays recorded this local day")
        ystart = start_utc - timedelta(days=1)
        yn = con.execute(
            "SELECT COUNT(*) FROM plays WHERE played_at >= ? AND played_at < ?",
            (
                ystart.isoformat().replace("+00:00", "Z"),
                start_utc.isoformat().replace("+00:00", "Z"),
            ),
        ).fetchone()[0]
        if yn:
            lines.append(f" (yesterday: {yn} plays)")
    return _box(f"DAILY PANEL · {day}", lines)


def weekly(con: sqlite3.Connection) -> str:
    today = datetime.now(LOCAL_TZ).date()
    days = [ (today - timedelta(days=i)).isoformat() for i in range(6, -1, -1) ]
    lines: list[str] = []

    surv = con.execute(
        "SELECT pct FROM survey WHERE week_start >= ?", (days[0],)
    ).fetchone()
    lines.append("WHO-5   " + (_fmt(surv[0], "/100") if surv else "not answered this week"))

    vals = con.execute(
        f"""SELECT hrv_rmssd, sleep_min, rhr, status FROM wellness
            WHERE date BETWEEN '{days[0]}' AND '{days[-1]}'"""
    ).fetchall()
    got = [v for v in vals if v[3] == "collected"]
    if got:
        hrvs = [v[0] for v in got if v[0] is not None]
        sleeps = [v[1] for v in got if v[1] is not None]
        rhrs = [v[2] for v in got if v[2] is not None]
        lines.append(
            f"HRV     mean {_fmt(sum(hrvs)/len(hrvs))}ms · n={len(hrvs)}/{len(days)}"
            if hrvs else f"HRV     no data · coverage {len(got)}/{len(days)}"
        )
        if sleeps:
            hh, mm = divmod(int(sum(sleeps) / len(sleeps)), 60)
            lines.append(f"SLEEP   mean {hh}h {mm:02d}m · n={len(sleeps)}/{len(days)}")
        if rhrs:
            lines.append(f"RHR     mean {int(round(sum(rhrs)/len(rhrs)))}bpm · n={len(rhrs)}/{len(days)}")
    else:
        lines.append(f"Garmin  coverage 0/{len(days)}")

    start_utc = datetime.fromisoformat(f"{days[0]}T00:00:00").replace(tzinfo=LOCAL_TZ).astimezone(timezone.utc)
    prow = con.execute(
        """SELECT COUNT(*),
                  COALESCE(SUM(COALESCE(t.duration_ms, 210000)), 0),
                  AVG(f.valence), AVG(f.energy), COUNT(f.valence),
                  SUM(CASE WHEN p.track_id IS NULL THEN 1 ELSE 0 END)
           FROM plays p
           LEFT JOIN tracks t ON t.track_id = p.track_id
           LEFT JOIN features f ON f.track_id = p.track_id
           WHERE p.played_at >= ?""",
        (start_utc.isoformat().replace("+00:00", "Z"),),
    ).fetchone()
    n, total_ms, val, ene, n_feat, pods = prow
    if n:
        hrs = (total_ms or 0) / 3_600_000
        pod_pct = (pods / n * 100) if pods else 0
        lines.append(
            f"MUSIC   {hrs:.1f}h · valence {f2(val)} · energy {f2(ene)}  [reccobeats_derived]"
        )
        lines.append(f"        {n} plays · features {n_feat}/{n} · podcasts {pod_pct:.0f}%")
        arts = con.execute(
            "SELECT COUNT(DISTINCT artist_names) FROM plays WHERE played_at >= ?",
            (start_utc.isoformat().replace("+00:00", "Z"),),
        ).fetchone()[0]
        lines.append(f"        {arts} distinct artists")
    else:
        lines.append("MUSIC   no plays in window")
    lines.append("")
    lines.append("window: trailing 7 days · labels: reccobeats_derived")
    return _box(f"WEEKLY DIGEST · wk of {days[0]}", lines)


def main() -> int:
    if not DB.exists():
        print("no database yet — run schema.init() and an ingest first")
        return 1
    con = sqlite3.connect(DB)
    day = sys.argv[1] if len(sys.argv) > 1 else None
    print(daily(con, day))
    print()
    print(weekly(con))
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
