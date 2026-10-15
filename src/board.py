"""On-command HTML board. Coverage instrument, not an emotion dashboard.

Stdlib only. Reads SQLite, writes logs/board.html.
"""

from __future__ import annotations

import html
import sqlite3
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from schema import DB  # noqa: E402

LOCAL_TZ = ZoneInfo("America/Phoenix")
OUT = ROOT / "logs" / "board.html"

CREAM = "#F4EBD8"
INK = "#1C1410"
MUTED = "#5C4E42"
OXBLOOD = "#7A1F2B"
SAND = "#FAF4E8"
LINE = "#D4C4AE"
GAP = "#A33B24"


def _esc(v) -> str:
    return html.escape("" if v is None else str(v), quote=True)


def _local_date(ts: str) -> date:
    raw = ts.replace("Z", "+00:00")
    return datetime.fromisoformat(raw).astimezone(LOCAL_TZ).date()


def _sleep_clock(sleep) -> str:
    if sleep is None:
        return "—"
    hh, mm = divmod(int(sleep), 60)
    return f"{hh}h {mm:02d}m"


def _f2(v) -> str:
    return "—" if v is None else f"{v:.2f}"


def _gather(con: sqlite3.Connection, today: date) -> dict:
    surveys = con.execute(
        "SELECT week_start, pct, i1,i2,i3,i4,i5, channel, note FROM survey ORDER BY week_start"
    ).fetchall()
    wellness = con.execute(
        """SELECT date, status, sleep_min, hrv_rmssd, hrv_status, rhr, steps, avg_stress
           FROM wellness ORDER BY date"""
    ).fetchall()
    wmap = {r[0]: r for r in wellness}

    play_rows = con.execute(
        """SELECT p.played_at, p.track_id, COALESCE(t.duration_ms, 210000), f.valence
           FROM plays p
           LEFT JOIN tracks t ON t.track_id = p.track_id
           LEFT JOIN features f ON f.track_id = p.track_id"""
    ).fetchall()
    by_day: dict[str, dict] = {}
    n_val = 0
    for ts, tid, dur, val in play_rows:
        d = _local_date(ts).isoformat()
        bucket = by_day.setdefault(d, {"n": 0, "ms": 0, "feat": 0})
        bucket["n"] += 1
        bucket["ms"] += int(dur or 210000)
        if val is not None:
            bucket["feat"] += 1
            n_val += 1

    dates: list[date] = []
    if wmap:
        dates.append(date.fromisoformat(min(wmap)))
    if by_day:
        dates.append(date.fromisoformat(min(by_day)))
    start = min(dates) if dates else today - timedelta(days=6)
    days = []
    d = start
    while d <= today:
        days.append(d.isoformat())
        d += timedelta(days=1)

    last = {}
    for source in ("garmin", "spotify", "reccobeats"):
        row = con.execute(
            "SELECT ts, outcome, substr(detail,1,160) FROM ingest_log "
            "WHERE source=? ORDER BY ts DESC LIMIT 1",
            (source,),
        ).fetchone()
        last[source] = row

    n_hrv = sum(1 for r in wellness if r[2] is not None and r[3] is not None)
    n_sleep = sum(1 for r in wellness if r[2] is not None)
    return {
        "today": today,
        "surveys": surveys,
        "wmap": wmap,
        "by_day": by_day,
        "days": days,
        "last": last,
        "n_plays": len(play_rows),
        "n_feat": n_val,
        "n_hrv": n_hrv,
        "n_sleep": n_sleep,
        "n_well": len(wellness),
    }


def _kind(day: str, wmap: dict, by_day: dict, today: str) -> str:
    row = wmap.get(day)
    if row is None:
        if day == today and day not in by_day:
            return "empty"
        if day not in by_day:
            return "gap"
        return "music"
    st = row[1]
    if st in {"not_worn", "api_error", "not_synced", "synced_zero"}:
        return st
    if row[2] is None:  # collected, no sleep
        return "daytime"
    return "night"


def _svg_nights(days: list[str], wmap: dict) -> str:
    pts_s, pts_h, pts_r = [], [], []
    for i, d in enumerate(days):
        row = wmap.get(d)
        if not row:
            continue
        x = i
        if row[2] is not None:
            pts_s.append((x, row[2] / 60.0))
        if row[3] is not None:
            pts_h.append((x, row[3]))
        if row[5] is not None:
            pts_r.append((x, row[5]))
    w, h = 560, 168
    pad_l, pad_r, pad_t, pad_b = 36, 12, 12, 28
    inner_w = w - pad_l - pad_r
    inner_h = h - pad_t - pad_b
    n = max(len(days) - 1, 1)

    def x_of(i: float) -> float:
        return pad_l + (i / n) * inner_w

    def y_of(v: float, lo: float, hi: float) -> float:
        v = min(hi, max(lo, v))
        return pad_t + (1 - (v - lo) / (hi - lo)) * inner_h

    def path(pts, lo, hi) -> str:
        if len(pts) < 1:
            return ""
        bits = []
        for i, (xi, v) in enumerate(pts):
            cmd = "M" if i == 0 else "L"
            bits.append(f"{cmd}{x_of(xi):.1f},{y_of(v, lo, hi):.1f}")
        return " ".join(bits)

    def dots(pts, lo, hi, fill) -> str:
        return "".join(
            f'<circle cx="{x_of(xi):.1f}" cy="{y_of(v, lo, hi):.1f}" r="3" fill="{fill}"/>'
            for xi, v in pts
        )

    grid = "".join(
        f'<path d="M{pad_l} {y} H{w - pad_r}" fill="none" stroke="{LINE}" stroke-width="1"/>'
        for y in (pad_t, pad_t + inner_h / 2, pad_t + inner_h)
    )
    labels = []
    step = 1 if len(days) <= 10 else 2
    for i, d in enumerate(days):
        if i % step:
            continue
        labels.append(
            f'<text x="{x_of(i):.1f}" y="{h - 8}" text-anchor="middle" fill="{MUTED}" font-size="10">{d[8:]}</text>'
        )
    return f"""
    <svg class="chart" viewBox="0 0 {w} {h}" role="img" aria-label="Sleep HRV RHR">
      {grid}
      <text x="4" y="{pad_t + 8}" fill="{MUTED}" font-size="10">9h</text>
      <text x="4" y="{pad_t + inner_h / 2 + 4}" fill="{MUTED}" font-size="10">6.5</text>
      <text x="4" y="{pad_t + inner_h}" fill="{MUTED}" font-size="10">4h</text>
      <path d="{path(pts_s, 4, 9.5)}" fill="none" stroke="{OXBLOOD}" stroke-width="2.3" stroke-linecap="round"/>
      {dots(pts_s, 4, 9.5, OXBLOOD)}
      <path d="{path(pts_h, 50, 100)}" fill="none" stroke="{INK}" stroke-width="1.8" stroke-dasharray="4 3" opacity=".85"/>
      {dots(pts_h, 50, 100, INK)}
      <path d="{path(pts_r, 35, 60)}" fill="none" stroke="{MUTED}" stroke-width="1.5"/>
      {dots(pts_r, 35, 60, MUTED)}
      {''.join(labels)}
    </svg>"""


def _svg_hours(days: list[str], by_day: dict) -> str:
    w, h = 560, 168
    pad_l, pad_r, pad_t, pad_b = 36, 12, 12, 28
    inner_w = w - pad_l - pad_r
    inner_h = h - pad_t - pad_b
    vals = [(d, (by_day.get(d, {}).get("ms") or 0) / 3_600_000) for d in days]
    peak = max((v for _, v in vals), default=0) or 1
    n = len(days) or 1
    bw = inner_w / n * 0.62
    bars = []
    labels = []
    step = 1 if n <= 10 else 2
    for i, (d, hrs) in enumerate(vals):
        x = pad_l + (i + 0.19) * (inner_w / n)
        bh = (hrs / peak) * inner_h
        y = pad_t + inner_h - bh
        fill = OXBLOOD if hrs else LINE
        op = "0.92" if hrs else "0.45"
        bars.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{max(bh, 1.5):.1f}" fill="{fill}" opacity="{op}"/>'
        )
        if i % step == 0:
            labels.append(
                f'<text x="{x + bw / 2:.1f}" y="{h - 8}" text-anchor="middle" fill="{MUTED}" font-size="10">{d[8:]}</text>'
            )
    return f"""
    <svg class="chart" viewBox="0 0 {w} {h}" role="img" aria-label="Listening hours">
      <path d="M{pad_l} {pad_t} H{w - pad_r} M{pad_l} {pad_t + inner_h / 2} H{w - pad_r} M{pad_l} {pad_t + inner_h} H{w - pad_r}" fill="none" stroke="{LINE}"/>
      <text x="4" y="{pad_t + 8}" fill="{MUTED}" font-size="10">{peak:.1f}h</text>
      {''.join(bars)}
      {''.join(labels)}
    </svg>"""


def compose(con: sqlite3.Connection, today: str | None = None) -> str:
    today_d = date.fromisoformat(today) if today else datetime.now(LOCAL_TZ).date()
    g = _gather(con, today_d)
    today_s = today_d.isoformat()
    surveys = g["surveys"]
    latest = surveys[-1] if surveys else None
    who5_kpi = f"{latest[1]:g}" if latest else "—"
    who5_sub = (
        f"week {latest[0]}" if latest else "no entries yet"
    )
    feat = g["n_feat"]
    plays = g["n_plays"]
    feat_s = f"{feat}/{plays}" if plays else "—"

    cells = []
    for d in g["days"]:
        kind = _kind(d, g["wmap"], g["by_day"], today_s)
        row = g["wmap"].get(d)
        music = g["by_day"].get(d)
        sleep = _sleep_clock(row[2]) if row else "—"
        plays_n = music["n"] if music else 0
        st = row[1] if row else kind
        cells.append(
            f'<div class="day {kind}" data-day="{d}" data-kind="{kind}">'
            f'<div class="d">{d[5:]}</div>'
            f'<div class="st">{_esc(st if row else kind)}</div>'
            f'<div>sleep {sleep}</div>'
            f'<div>plays {plays_n}</div>'
            f"</div>"
        )

    who_rows = []
    if not surveys:
        who_rows.append('<tr><td colspan="4">no entries yet</td></tr>')
    else:
        for w, pct, i1, i2, i3, i4, i5, ch, note in surveys:
            label = "test-fire" if note and "test-fire" in note.lower() else (ch or "")
            who_rows.append(
                f"<tr><td class='mono'>{_esc(w)}</td><td class='num'>{pct:g}</td>"
                f"<td class='mono'>{i1} {i2} {i3} {i4} {i5}</td><td>{_esc(label)}</td></tr>"
            )

    def ingest_line(src: str) -> str:
        row = g["last"].get(src)
        if not row:
            return f"{src}: (none)"
        return f"{src}: {row[0]} · {row[1]} · {row[2] or ''}"

    stamp = datetime.now(LOCAL_TZ).strftime("%a %b %d %H:%M %Z")
    hrv_gate = f"{g['n_hrv']}/14"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Tunes &amp; Vibes — board</title>
  <style>
    html, body {{
      margin: 0;
      padding: 0;
      background: {CREAM};
      color: {INK};
      font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
      font-size: 15px;
      line-height: 1.45;
    }}
    body {{ padding: 1.05rem 1.15rem 1.4rem; }}
    h1 {{
      font-family: "Iowan Old Style", Palatino, "Times New Roman", Times, serif;
      font-size: 1.55rem;
      font-weight: 600;
      margin: 0 0 .15rem;
      letter-spacing: -.02em;
    }}
    h2 {{
      font-family: "Iowan Old Style", Palatino, "Times New Roman", Times, serif;
      font-size: .78rem;
      font-weight: 600;
      letter-spacing: .14em;
      text-transform: uppercase;
      color: {OXBLOOD};
      margin: 1.25rem 0 .5rem;
    }}
    .lede {{ color: {MUTED}; margin: 0 0 .9rem; max-width: 68ch; }}
    .kpis {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(112px, 1fr));
      gap: .5rem;
    }}
    .kpi {{
      background: {SAND};
      border: 1px solid {LINE};
      border-radius: 10px;
      padding: .7rem .75rem .6rem;
    }}
    .kpi .n {{ font-size: 1.4rem; font-weight: 650; letter-spacing: -.03em; color: {OXBLOOD}; }}
    .kpi .l {{ font-size: .72rem; color: {MUTED}; margin-top: .18rem; }}
    .grid2 {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: .65rem;
    }}
    @media (max-width: 820px) {{ .grid2 {{ grid-template-columns: 1fr; }} }}
    .card {{
      background: {SAND};
      border: 1px solid {LINE};
      border-radius: 10px;
      padding: .75rem .8rem .65rem;
    }}
    .card h3 {{ margin: 0 0 .45rem; font-size: .92rem; }}
    svg.chart {{ width: 100%; height: auto; display: block; }}
    .legend {{ display: flex; flex-wrap: wrap; gap: .45rem 1rem; font-size: .72rem; color: {MUTED}; margin-top: .4rem; }}
    .sw {{ display: inline-block; width: 9px; height: 9px; border-radius: 2px; margin-right: .3rem; vertical-align: .05rem; }}
    .cal {{ display: grid; grid-template-columns: repeat(7, 1fr); gap: .35rem; }}
    .day {{
      border: 1px solid {LINE};
      border-radius: 8px;
      padding: .4rem .4rem .35rem;
      min-height: 78px;
      font-size: .7rem;
      background: {SAND};
      color: {INK};
    }}
    .day .d {{ color: {MUTED}; letter-spacing: .04em; }}
    .day .st {{ font-weight: 650; margin: .12rem 0 .15rem; text-transform: capitalize; }}
    .day.night {{ background: #E7D3C4; }}
    .day.daytime {{ background: #EFE4D0; }}
    .day.gap {{ background: #F3D5C8; color: {GAP}; }}
    .day.music {{ background: #E8E0CF; }}
    .day.empty {{ opacity: .72; }}
    table {{ width: 100%; border-collapse: collapse; font-size: .84rem; }}
    th {{
      text-align: left; font-size: .68rem; letter-spacing: .08em; text-transform: uppercase;
      color: {MUTED}; font-weight: 650; padding: .35rem 0; border-bottom: 1px solid {LINE};
    }}
    td {{ padding: .4rem 0; border-bottom: 1px solid {LINE}; }}
    .num {{ font-variant-numeric: tabular-nums; font-weight: 650; color: {OXBLOOD}; }}
    .mono {{ font-variant-numeric: tabular-nums; }}
    .note {{ font-size: .75rem; color: {MUTED}; margin: .4rem 0 0; }}
    button {{
      appearance: none;
      border: 1px solid {INK};
      background: {OXBLOOD};
      color: {CREAM};
      font: inherit;
      font-size: .82rem;
      padding: .42rem .75rem;
      border-radius: 8px;
      cursor: pointer;
    }}
    .btns {{ display: flex; gap: .4rem; margin: .35rem 0 .8rem; }}
  </style>
</head>
<body>
  <h1>Tunes &amp; Vibes</h1>
  <p class="lede">Coverage board · generated { _esc(stamp) }. Sensors are not emotions.
    Labels: garmin_raw · reccobeats_derived · who5_anchored. Gaps stay visible.</p>
  <div class="btns">
    <button data-hermes-send="Regenerate the Tunes and Vibes HTML board from live SQLite with src/board.py and preview logs/board.html.">Refresh from SQLite</button>
  </div>
  <div class="kpis">
    <div class="kpi"><div class="n">{_esc(who5_kpi)}</div><div class="l">WHO-5 latest</div><div class="l">{_esc(who5_sub)}</div></div>
    <div class="kpi"><div class="n">{g['n_sleep']}/{len(g['days'])}</div><div class="l">nights with sleep</div><div class="l">window {g['days'][0] if g['days'] else '—'} → {today_s}</div></div>
    <div class="kpi"><div class="n">{hrv_gate}</div><div class="l">HRV nights / R6=14</div><div class="l">z-scores gated</div></div>
    <div class="kpi"><div class="n">{plays}</div><div class="l">plays in fridge</div><div class="l">features {feat_s}</div></div>
  </div>

  <h2>Coverage calendar</h2>
  <div class="cal">{''.join(cells)}</div>
  <p class="note">night = sleep+HRV · daytime = worn, no night · gap = no row (28–29 Aug are live-API holes) · music = plays, no Garmin</p>

  <h2>Night series · garmin_raw</h2>
  <div class="grid2">
    <div class="card">
      <h3>Sleep / HRV / RHR</h3>
      {_svg_nights(g['days'], g['wmap'])}
      <div class="legend">
        <span><i class="sw" style="background:{OXBLOOD}"></i>sleep (h)</span>
        <span><i class="sw" style="background:{INK}"></i>HRV ms (dashed)</span>
        <span><i class="sw" style="background:{MUTED}"></i>RHR</span>
      </div>
      <p class="note">Missing nights are omitted, not plotted as zero. HRV status NONE until Garmin’s own baseline.</p>
    </div>
    <div class="card">
      <h3>Listening hours · local day</h3>
      {_svg_hours(g['days'], g['by_day'])}
      <div class="legend">
        <span><i class="sw" style="background:{OXBLOOD}"></i>hours from track duration (not ms_played)</span>
      </div>
      <p class="note">Empty bars are days with no plays in SQLite — including the 28–29 Aug hole.</p>
    </div>
  </div>

  <h2>WHO-5 · who5_anchored</h2>
  <div class="card">
    <table>
      <thead><tr><th>week (Mon)</th><th>pct</th><th>items</th><th>label</th></tr></thead>
      <tbody>{''.join(who_rows)}</tbody>
    </table>
    <p class="note">Noise band ±3–4 pts; a real change is Δ≥10 sustained 2 weeks (R2). Two points is not a trend.</p>
  </div>

  <h2>Last ingest</h2>
  <p class="note mono">{_esc(ingest_line('spotify'))}<br/>{_esc(ingest_line('garmin'))}<br/>{_esc(ingest_line('reccobeats'))}</p>
</body>
</html>
"""


def main() -> int:
    if not DB.exists():
        print("no database yet")
        return 1
    con = sqlite3.connect(DB)
    text = compose(con)
    con.close()
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    print(str(OUT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
