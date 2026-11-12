#!/usr/bin/env python3
"""Render docs/fleet_blueprint.svg — the ArcticChain rural node fleet sheet.

Pure Python (no CAD kernel needed). One sheet showing every node type with
envelope dims, role, key features, and design status. See docs/HARDWARE.md.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
W, H = 1600, 1560
BG, LINE, DIM, ACC, PANEL = "#0b3a66", "#d8ecff", "#8fc1ea", "#ffd479", "#0f4a80"
out = []
a = out.append


def rrect(x, y, w, h, r, **kw):
    attrs = " ".join(f'{k.replace("_", "-")}="{v}"' for k, v in kw.items())
    a(f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" rx="{r:.2f}" {attrs}/>')


def text(x, y, s, size=12, anchor="start", color=LINE, weight="normal"):
    a(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" text-anchor="{anchor}" fill="{color}" font-weight="{weight}">{s}</text>')


def chip(x, y, label, color):
    w = len(label) * 7.2 + 18
    rrect(x, y, w, 20, 10, fill="none", stroke=color, stroke_width=1)
    text(x + w / 2, y + 14, label, 10, "middle", color)


a(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" font-family="Consolas, Menlo, monospace">')
a(f'<defs><pattern id="g" width="20" height="20" patternUnits="userSpaceOnUse">'
  f'<path d="M20 0 L0 0 0 20" fill="none" stroke="#1a5288" stroke-width="0.6"/></pattern></defs>')
a(f'<rect width="{W}" height="{H}" fill="{BG}"/><rect width="{W}" height="{H}" fill="url(#g)"/>')
rrect(10, 10, W - 20, H - 20, 0, fill="none", stroke=LINE, stroke_width=2)

# ---------------- header ----------------
text(60, 70, "ARCTICCHAIN NODE FLEET — RURAL &amp; REMOTE CANADA", 22, weight="bold")
text(60, 96, "every node: signed mesh identity · store-and-forward · solar-first · IP65 · -45..+70 °C · community-owned", 12, color=DIM)

# ---------------- design DNA strip ----------------
dna = [
    ("CLIMATE", "-45..+70 °C · IP65+ · UV-stable · LiFePO4 · December-sized solar"),
    ("POWER", "solar-first · 30–90 day autonomy · no grid required"),
    ("FIELD", "bear-country mounts · two-person install · hand-tool repair"),
    ("SOVEREIGNTY", "community-owned mesh · data stays home · OCAP · EN/FR"),
    ("APPROPRIATE", "right-sized cost · repairable > sealed · open docs"),
    ("OFFLINE", "works when everything else has failed — that IS the product"),
]
yy = 130
for i, (t, d) in enumerate(dna):
    col = i % 3
    row = i // 3
    x = 60 + col * 500
    y = yy + row * 56
    text(x, y, t, 12, color=ACC, weight="bold")
    text(x + 110, y, d, 11, color=DIM)
a('<line x1="60" y1="252" x2="1540" y2="252" stroke="#1a5288" stroke-width="1.5"/>')

# ---------------- node cards ----------------
# (name, codename, dims, role, features, status, glyph kind, glyph color)
NODES = [
    ("L1 BRICK", "FIELD NODE", "160×80×24 mm", "handheld mailbox + repeater + bulletin + SOS",
     ["LoRa 915 + LTE backhaul", "E-Ink public display", "4×18650 → USB-C PD", "glove-friendly SOS button"],
     "CAD READY", "#7fe3ff",
     ["brickshell"]),
    ("E TOTEM", "COMMUNITY BOARD", "~320×220×80 mm + pole", "public E-Ink noticeboard that IS a mesh node",
     ["7–13″ E-Ink, zero-power display", "town alerts & notices, EN/FR", "LoRa (+LTE optional)", "pole/post mount, tamper-resistant"],
     "SPEC", "#8fc1ea",
     ["totem"]),
    ("S MITE", "SWARM UNIT", "~90×90×35 mm", "perchable env sensor — the swarm IS the sensor",
     ["solar top + tiny cell", "LoRa + temp/RH/VOC", "branch/pole/fence perch clip", "perch-and-report; flight later"],
     "CAD SCRIPTED", "#ffd479",
     ["mite"]),
    ("A ANCHOR", "CHARGING STATION", "~350×250×400 mm + array", "renewable station: swarm dock + relay + backhaul",
     ["20–60 W solar + LiFePO4", "charges docked swarm units", "LoRa + LTE/sat backhaul", "community-hub siting"],
     "SPEC", "#8fc1ea",
     ["anchor"]),
    ("P PHONE", "RURAL COMMS", "~145×72×14 mm", "mesh-native phone — satellite SOS-ready, offline-first",
     ["every phone IS a node", "sat-SOS where nothing works", "offline maps/forms EN/FR", "replaceable battery, -30 °C"],
     "RE-DESIGN", "#ff9d7a",
     ["phone"]),
    ("D SEED", "DEGRADABLE MOTE", "~20×20×5 mm", "seed-dropped seasonal sensor — sensing that ends",
     ["printed electronics", "biodegradable substrate", "reports via cluster heads", "zero e-waste, no retrieval"],
     "R&D", "#c58fff",
     ["seed"]),
]

CW, CH = 470, 330
GX, GY = 62, 285


def draw_glyph(kind, cx, cy, w, h, col):
    """Tiny isometric-ish glyph per node type."""
    if kind == "brickshell":
        rrect(cx - 80, cy - 22, 160, 44, 8, fill="none", stroke=col, stroke_width=2)
        rrect(cx - 62, cy - 12, 60, 24, 4, fill="#0f4a80", stroke=col, stroke_width=1)
        a(f'<circle cx="{cx + 62}" cy="{cy}" r="8" fill="none" stroke="{col}" stroke-width="1.5"/>')
        text(cx, cy + 42, "brick", 9, "middle", DIM)
    elif kind == "totem":
        a(f'<line x1="{cx}" y1="{cy + 40}" x2="{cx}" y2="{cy - 30}" stroke="{DIM}" stroke-width="3"/>')
        rrect(cx - 65, cy - 48, 130, 62, 6, fill="#0f4a80", stroke=col, stroke_width="1.5")
        for k in range(3):
            a(f'<line x1="{cx - 50}" y1="{cy - 30 + k * 16}" x2="{cx + 50}" y2="{cy - 30 + k * 16}" stroke="{DIM}" stroke-width="1" stroke-dasharray="4 3"/>')
        text(cx, cy + 58, "pole-mounted board", 9, "middle", DIM)
    elif kind == "mite":
        a(f'<circle cx="{cx}" cy="{cy}" r="34" fill="#0f4a80" stroke="{col}" stroke-width="2"/>')
        a(f'<rect x="{cx - 26}" y="{cy - 8}" width="52" height="16" rx="3" fill="#0b3a66" stroke="{col}" stroke-width="1"/>')
        for ang in (30, 150, 270):
            import math
            x2 = cx + 44 * math.cos(math.radians(ang))
            y2 = cy + 44 * math.sin(math.radians(ang))
            a(f'<line x1="{cx}" y1="{cy}" x2="{x2:.0f}" y2="{y2:.0f}" stroke="{col}" stroke-width="1" stroke-dasharray="2 2"/>')
        text(cx, cy + 52, "perch puck", 9, "middle", DIM)
    elif kind == "anchor":
        rrect(cx - 55, cy - 30, 110, 66, 8, fill="#0f4a80", stroke=col, stroke_width=1.5)
        a(f'<line x1="{cx - 40}" y1="{cy - 44}" x2="{cx + 40}" y2="{cy - 44}" stroke="{col}" stroke-width="2"/>')
        for k in (-1, 0, 1):
            a(f'<line x1="{cx + k * 30}" y1="{cy - 44}" x2="{cx + k * 30}" y2="{cy - 58}" stroke="{col}" stroke-width="1.5"/>')
        a(f'<rect x="{cx - 38}" y="{cy - 14}" width="76" height="40" rx="4" fill="#0b3a66" stroke="{DIM}" stroke-width="1"/>')
        text(cx, cy + 52, "station + array", 9, "middle", DIM)
    elif kind == "phone":
        rrect(cx - 26, cy - 46, 52, 92, 10, fill="#0f4a80", stroke=col, stroke_width="2")
        rrect(cx - 18, cy - 34, 36, 62, 4, fill="#0b3a66", stroke=DIM, stroke_width="1")
        a(f'<circle cx="{cx}" cy="{cy + 38}" r="3" fill="{col}"/>')
        text(cx, cy + 58, "rural comms", 9, "middle", DIM)
    elif kind == "seed":
        for k in range(9):
            import math, random
            random.seed(k)
            dx, dy = random.uniform(-55, 55), random.uniform(-30, 30)
            a(f'<circle cx="{cx + dx:.0f}" cy="{cy + dy:.0f}" r="3.5" fill="{col}" opacity="0.85"/>')
        text(cx, cy + 52, "seed cloud", 9, "middle", DIM)


for i, (name, codename, dims, role, feats, status, scol, glyph) in enumerate(NODES):
    col, row = i % 3, i // 3
    x, y = GX + col * (CW + 18), GY + row * (CH + 30)
    rrect(x, y, CW, CH, 10, fill=PANEL, stroke=LINE, stroke_width=1.5)
    # status chip top-right
    chip(x + CW - len(status) * 7.2 - 36, y + 12, status, scol)
    text(x + 18, y + 30, name, 17, weight="bold")
    text(x + 18, y + 48, codename, 10, color=DIM)
    text(x + 18, y + 70, dims, 11, color=ACC)
    # glyph area
    gx, gy, gw, gh = x + CW / 2, y + 175, 190, 110
    rrect(gx - gw / 2, gy - gh / 2, gw, gh, 6, fill="#0b3a66", stroke=DIM, stroke_width=1, stroke_dasharray="4 3")
    draw_glyph(glyph[0], gx, gy, gw, gh, scol)
    # role + features
    text(x + 18, y + 268, role, 10.5, color=LINE)
    for j, f in enumerate(feats):
        text(x + 18, y + 292 + j * 13, "· " + f, 9.5, color=DIM)

# ---------------- shared DNA callouts ----------------
qy = GY + 2 * CH + 62
text(60, qy, "SHARED NODE DNA — what makes them one network", 14, weight="bold")
dna2 = [
    ("signed identity", "every node holds an Ed25519 key — envelopes are signed, replay-protected"),
    ("store-and-forward", "SQLite queue on every node — messages survive days without backhaul"),
    ("one radio plan", "LoRa 915 MHz ISM (Canada) everywhere; LTE/sat only as backhaul"),
    ("same agent", "poc/arcticchain_agent.py HTTP API (:8080) runs on every node type"),
]
for i, (t, d) in enumerate(dna2):
    col, row = i % 2, i // 2
    x = 60 + col * 740
    y = qy + 26 + row * 34
    text(x, y, t, 11.5, color=ACC, weight="bold")
    text(x + 170, y, d, 11, color=DIM)

# ---------------- horizon ----------------
text(60, qy + 118, "HORIZON", 14, weight="bold")
text(60, qy + 140, "D Seed (degradable motes) and H Meridian (CubeSat payload — the mesh IS the ground segment) are", 11, color=DIM)
text(60, qy + 158, "earned stages, not skipped rungs. See docs/HARDWARE.md §5 for the design sequence.", 11, color=DIM)

# ---------------- title block ----------------
tx, ty, tw, th = 1010, H - 185, 570, 145
rrect(tx, ty, tw, th, 0, fill="none", stroke=LINE, stroke_width=1.5)
for yy2 in (38, 76, 114):
    a(f'<line x1="{tx}" y1="{ty + yy2}" x2="{tx + tw}" y2="{ty + yy2}" stroke="{LINE}"/>')
a(f'<line x1="{tx + 380}" y1="{ty + 38}" x2="{tx + 380}" y2="{ty + th}" stroke="{LINE}"/>')
text(tx + 12, ty + 25, "ARCTICCHAIN — RURAL NODE FLEET", 14, weight="bold")
text(tx + 12, ty + 62, "DWG AF-FLEET-001 · NODE FAMILY OVERVIEW", 11)
text(tx + 392, ty + 62, "REV A", 11)
text(tx + 12, ty + 98, "DESIGN BASIS: rural & remote Canada — climate, culture, sovereignty", 11)
text(tx + 392, ty + 98, "UNITS mm", 11)
text(tx + 12, ty + 134, "GENERATED FROM docs/make_fleet_blueprint.py", 11)
text(tx + 392, ty + 134, "SHEET 1/1", 11)

a("</svg>")
(ROOT / "docs/fleet_blueprint.svg").write_text("\n".join(out), encoding="utf-8")
print("wrote docs/fleet_blueprint.svg")
