#!/usr/bin/env python3
import html
import json
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "github-activity.json"
SVG_PATH = ROOT / "assets" / "github-activity.svg"


def esc(value):
    return html.escape(str(value), quote=True)


def fmt_int(value):
    return f"{int(value):,}"


def parse_date(value):
    return datetime.strptime(value, "%Y-%m-%d").date()


def month_label(day):
    return day.strftime("%b")


def heat_color(count, max_count):
    if count <= 0:
        return "#162033"
    ratio = count / max(1, max_count)
    if ratio < 0.25:
        return "#164E63"
    if ratio < 0.5:
        return "#0E7490"
    if ratio < 0.75:
        return "#00A6A6"
    return "#00C2A8"


def compact_daily(daily, max_columns=68):
    rows = []
    dates = [parse_date(item["date"]) for item in daily]
    counts = [int(item["count"]) for item in daily]
    if not dates:
        return rows

    start = dates[0]
    week_start = start - timedelta(days=start.weekday())
    weeks = []
    current = week_start
    lookup = {item["date"]: int(item["count"]) for item in daily}
    while current <= dates[-1]:
        days = []
        for offset in range(7):
            day = current + timedelta(days=offset)
            if day < dates[0] or day > dates[-1]:
                days.append(None)
            else:
                days.append({"date": day.isoformat(), "count": lookup.get(day.isoformat(), 0)})
        weeks.append({"start": current, "days": days, "total": sum(day["count"] for day in days if day)})
        current += timedelta(days=7)

    if len(weeks) <= max_columns:
        return weeks

    group_size = (len(weeks) + max_columns - 1) // max_columns
    for index in range(0, len(weeks), group_size):
        chunk = weeks[index : index + group_size]
        days = []
        for day_index in range(7):
            entries = [week["days"][day_index] for week in chunk if week["days"][day_index]]
            days.append(
                {
                    "date": entries[-1]["date"] if entries else chunk[-1]["start"].isoformat(),
                    "count": sum(item["count"] for item in entries),
                }
            )
        rows.append({"start": chunk[0]["start"], "days": days, "total": sum(week["total"] for week in chunk)})
    return rows


def build_weekly_path(weeks, x0, y0, width, height):
    if not weeks:
        return ""
    max_total = max(1, max(week["total"] for week in weeks))
    step = width / max(1, len(weeks) - 1)
    points = []
    for index, week in enumerate(weeks):
        x = x0 + index * step
        y = y0 + height - (week["total"] / max_total) * height
        points.append(f"{x:.1f},{y:.1f}")
    return " ".join(points)


data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
daily = data.get("daily", [])
weeks = compact_daily(daily)
max_count = max([int(item["count"]) for item in daily] + [1])
max_week = max([week["total"] for week in weeks] + [1])
start = parse_date(data["start_date"])
end = parse_date(data["end_date"])
period_days = (end - start).days + 1
source_labels = {
    "github_graphql": "GitHub API",
    "github_public_search": "GitHub public commit search",
    "local_git_preview": "local preview",
}
source_label = source_labels.get(data.get("source"), data.get("source", "unknown"))

cell = 13
gap = 4
heat_x = 78
heat_y = 212
bar_x = 78
bar_y = 354
bar_h = 72
bar_w = 1028
week_step = bar_w / max(1, len(weeks))
polyline = build_weekly_path(weeks, bar_x, bar_y, bar_w, bar_h)

month_marks = []
last_month = None
for index, week in enumerate(weeks):
    month = month_label(week["start"])
    if month != last_month:
        x = heat_x + index * (cell + gap)
        month_marks.append((x, month))
        last_month = month

heat_cells = []
for week_index, week in enumerate(weeks):
    for day_index, day in enumerate(week["days"]):
        if not day:
            continue
        count = int(day["count"])
        x = heat_x + week_index * (cell + gap)
        y = heat_y + day_index * (cell + gap)
        heat_cells.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{cell}" height="{cell}" rx="3" '
            f'fill="{heat_color(count, max_count)}"><title>{esc(day["date"])}: {count}</title></rect>'
        )

bars = []
for index, week in enumerate(weeks):
    height = 4 + (week["total"] / max_week) * (bar_h - 4)
    x = bar_x + index * week_step + 1
    y = bar_y + bar_h - height
    width = max(3, week_step - 4)
    bars.append(
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{width:.1f}" height="{height:.1f}" rx="2" '
        f'fill="#38BDF8" opacity="0.34"><title>Week of {esc(week["start"].isoformat())}: {week["total"]}</title></rect>'
    )

repo_items = []
for index, repo in enumerate(data.get("repositories", [])[:4]):
    y = 492 + index * 24
    repo_items.append(
        f'<text x="80" y="{y}" fill="#CBD5E1" font-family="JetBrains Mono, Consolas, monospace" font-size="15">'
        f'{esc(repo["name"])}'
        f'</text>'
        f'<text x="1035" y="{y}" text-anchor="end" fill="#00C2A8" font-family="JetBrains Mono, Consolas, monospace" font-size="15">'
        f'{fmt_int(repo.get("commits", 0))} commits'
        f'</text>'
    )

month_text = "\n".join(
    f'<text x="{x:.1f}" y="198" fill="#64748B" font-family="JetBrains Mono, Consolas, monospace" font-size="12">{esc(month)}</text>'
    for x, month in month_marks
)

svg = f'''<svg width="1200" height="620" viewBox="0 0 1200 620" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1200" y2="620" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="#0B1020"/>
      <stop offset="0.56" stop-color="#111827"/>
      <stop offset="1" stop-color="#16122A"/>
    </linearGradient>
    <linearGradient id="accent" x1="72" y1="122" x2="1130" y2="438" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="#00C2A8"/>
      <stop offset="0.55" stop-color="#38BDF8"/>
      <stop offset="1" stop-color="#A78BFA"/>
    </linearGradient>
    <pattern id="grid" width="44" height="44" patternUnits="userSpaceOnUse">
      <path d="M44 0H0V44" stroke="#263244" stroke-width="1" opacity="0.42"/>
    </pattern>
  </defs>
  <rect width="1200" height="620" rx="22" fill="url(#bg)"/>
  <rect width="1200" height="620" rx="22" fill="url(#grid)" opacity="0.18"/>
  <path d="M74 460C204 390 326 415 468 376C624 334 734 232 874 214C984 200 1062 232 1130 270" stroke="url(#accent)" stroke-width="2" opacity="0.42"/>

  <text x="64" y="68" fill="#E5E7EB" font-family="Inter, Segoe UI, Arial, sans-serif" font-size="34" font-weight="800">GitHub Activity Timeline</text>
  <text x="64" y="101" fill="#94A3B8" font-family="JetBrains Mono, Consolas, monospace" font-size="16">
    {esc(data["start_date"])} - {esc(data["end_date"])} • {period_days} days • source: {esc(source_label)} • updated {esc(data["updated_at"])}
  </text>

  <g transform="translate(64 126)">
    <rect width="254" height="72" rx="14" fill="#111827" stroke="#2A3A4D"/>
    <text x="22" y="28" fill="#94A3B8" font-family="JetBrains Mono, Consolas, monospace" font-size="14">Total commits</text>
    <text x="22" y="58" fill="#6EA8FE" font-family="Inter, Segoe UI, Arial, sans-serif" font-size="30" font-weight="800">{fmt_int(data.get("total_commits", 0))}</text>
  </g>
  <g transform="translate(338 126)">
    <rect width="254" height="72" rx="14" fill="#111827" stroke="#2A3A4D"/>
    <text x="22" y="28" fill="#94A3B8" font-family="JetBrains Mono, Consolas, monospace" font-size="14">Activity days</text>
    <text x="22" y="58" fill="#00C2A8" font-family="Inter, Segoe UI, Arial, sans-serif" font-size="30" font-weight="800">{fmt_int(data.get("active_days", 0))}</text>
  </g>
  <g transform="translate(612 126)">
    <rect width="254" height="72" rx="14" fill="#111827" stroke="#2A3A4D"/>
    <text x="22" y="28" fill="#94A3B8" font-family="JetBrains Mono, Consolas, monospace" font-size="14">Best streak</text>
    <text x="22" y="58" fill="#A78BFA" font-family="Inter, Segoe UI, Arial, sans-serif" font-size="30" font-weight="800">{fmt_int(data.get("best_streak", 0))} days</text>
  </g>
  <g transform="translate(886 126)">
    <rect width="250" height="72" rx="14" fill="#111827" stroke="#2A3A4D"/>
    <text x="22" y="28" fill="#94A3B8" font-family="JetBrains Mono, Consolas, monospace" font-size="14">Contributions</text>
    <text x="22" y="58" fill="#38BDF8" font-family="Inter, Segoe UI, Arial, sans-serif" font-size="30" font-weight="800">{fmt_int(data.get("total_contributions", 0))}</text>
  </g>

  {month_text}
  <g opacity="0.96">
    {''.join(heat_cells)}
  </g>
  <text x="64" y="342" fill="#94A3B8" font-family="JetBrains Mono, Consolas, monospace" font-size="14">Commit frequency by week</text>
  <g>
    {''.join(bars)}
    <polyline points="{polyline}" fill="none" stroke="url(#accent)" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
  </g>
  <text x="64" y="462" fill="#94A3B8" font-family="JetBrains Mono, Consolas, monospace" font-size="14">Top repositories by commit contributions</text>
  {''.join(repo_items)}
  <text x="64" y="590" fill="#64748B" font-family="JetBrains Mono, Consolas, monospace" font-size="13">
    Activity days represent days with recorded GitHub contribution activity; private contributions appear only when GitHub exposes them to the token.
  </text>
</svg>
'''

SVG_PATH.write_text(svg, encoding="utf-8")
print(f"Wrote {SVG_PATH}")
