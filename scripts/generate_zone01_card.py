#!/usr/bin/env python3
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
data = json.loads((ROOT / "data" / "zone01.json").read_text(encoding="utf-8"))

level = int(data["level"])
level_width = max(8, min(100, level / 30 * 100))
checkpoint = int(data["checkpoint_level"])
checkpoint_width = max(8, min(100, checkpoint))

def e(value):
    return html.escape(str(value), quote=True)

svg = f'''<svg width="1200" height="360" viewBox="0 0 1200 360" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1200" y2="360" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="#0B1020"/>
      <stop offset="0.58" stop-color="#111827"/>
      <stop offset="1" stop-color="#16122A"/>
    </linearGradient>
    <linearGradient id="line" x1="120" y1="90" x2="1080" y2="280" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="#00C2A8"/>
      <stop offset="0.55" stop-color="#38BDF8"/>
      <stop offset="1" stop-color="#A78BFA"/>
    </linearGradient>
    <pattern id="grid" width="42" height="42" patternUnits="userSpaceOnUse">
      <path d="M42 0H0V42" stroke="#263244" stroke-width="1" opacity="0.45"/>
    </pattern>
  </defs>
  <rect width="1200" height="360" rx="22" fill="url(#bg)"/>
  <rect width="1200" height="360" rx="22" fill="url(#grid)" opacity="0.2"/>
  <path d="M72 268C185 185 284 206 384 230C520 263 626 226 724 162C842 84 964 83 1128 130" stroke="url(#line)" stroke-width="2" opacity="0.5"/>
  <text x="64" y="70" fill="#E5E7EB" font-family="Inter, Segoe UI, Arial, sans-serif" font-size="34" font-weight="800">Zone01 Progress</text>
  <text x="64" y="103" fill="#94A3B8" font-family="JetBrains Mono, Consolas, monospace" font-size="17">{e(data["campus"])} • {e(data["program"])} • {e(data["cohort"])}</text>
  <g transform="translate(64 138)">
    <rect width="304" height="150" rx="18" fill="#111827" stroke="#2A3A4D"/>
    <text x="28" y="42" fill="#94A3B8" font-family="JetBrains Mono, Consolas, monospace" font-size="16">Current level</text>
    <text x="28" y="92" fill="#00C2A8" font-family="Inter, Segoe UI, Arial, sans-serif" font-size="54" font-weight="800">{level}</text>
    <rect x="28" y="112" width="248" height="12" rx="6" fill="#1F2937"/>
    <rect x="28" y="112" width="{248 * level_width / 100:.1f}" height="12" rx="6" fill="url(#line)"/>
  </g>
  <g transform="translate(396 138)">
    <rect width="344" height="150" rx="18" fill="#111827" stroke="#2A3A4D"/>
    <text x="28" y="42" fill="#94A3B8" font-family="JetBrains Mono, Consolas, monospace" font-size="16">Checkpoint level</text>
    <text x="28" y="88" fill="#E5E7EB" font-family="Inter, Segoe UI, Arial, sans-serif" font-size="42" font-weight="800">{checkpoint}</text>
    <text x="28" y="122" fill="#00C2A8" font-family="JetBrains Mono, Consolas, monospace" font-size="16">{e(data["note"])}</text>
    <rect x="188" y="74" width="116" height="10" rx="5" fill="#1F2937"/>
    <rect x="188" y="74" width="{116 * checkpoint_width / 100:.1f}" height="10" rx="5" fill="#A78BFA"/>
  </g>
  <g transform="translate(768 138)">
    <rect width="368" height="150" rx="18" fill="#111827" stroke="#2A3A4D"/>
    <text x="28" y="42" fill="#94A3B8" font-family="JetBrains Mono, Consolas, monospace" font-size="16">Current module</text>
    <text x="28" y="84" fill="#E5E7EB" font-family="Inter, Segoe UI, Arial, sans-serif" font-size="32" font-weight="800">{e(data["module"])} • {e(data["status"])}</text>
    <text x="28" y="120" fill="#A78BFA" font-family="JetBrains Mono, Consolas, monospace" font-size="16">Last skill: {e(data["last_skill"])} • XP: {e(data["xp"])}</text>
  </g>
  <g transform="translate(64 315)" font-family="JetBrains Mono, Consolas, monospace" font-size="15">
    <text fill="#94A3B8">Rank: </text>
    <text x="56" fill="#E5E7EB">{e(data["rank"])}</text>
    <text x="270" fill="#94A3B8">Next rank: </text>
    <text x="374" fill="#E5E7EB">{e(data["next_rank"])}</text>
    <text x="585" fill="#94A3B8">Joined: </text>
    <text x="660" fill="#E5E7EB">{e(data["joined_at"])}</text>
    <text x="875" fill="#94A3B8">Updated: </text>
    <text x="960" fill="#E5E7EB">{e(data["updated_at"])}</text>
  </g>
</svg>
'''

(ROOT / "assets" / "zone01-progress.svg").write_text(svg, encoding="utf-8")
