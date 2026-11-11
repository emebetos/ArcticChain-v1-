#!/usr/bin/env python3
"""Render docs/blueprint.svg from the CAD layout (cad/out/dimensions.json) so the drawing
always matches the generated geometry."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
L = json.loads((ROOT / "cad/out/dimensions.json").read_text())
P, D = L["params"], L["derived"]
W, H = 1600, 1000
S = 3.2  # px per mm
BG, LINE, DIM, ACC = "#0b3a66", "#d8ecff", "#8fc1ea", "#ffd479"
out = []
a = out.append


def rrect(x, y, w, h, r, **kw):
    attrs = " ".join(f'{k.replace("_", "-")}="{v}"' for k, v in kw.items())
    a(f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" rx="{r:.2f}" {attrs}/>')


def text(x, y, s, size=12, anchor="start", color=LINE, weight="normal"):
    a(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" text-anchor="{anchor}" fill="{color}" font-weight="{weight}">{s}</text>')


def hdim(x0, x1, y, label):
    a(f'<line x1="{x0}" y1="{y}" x2="{x1}" y2="{y}" stroke="{DIM}" marker-start="url(#arr)" marker-end="url(#arr)"/>')
    text((x0 + x1) / 2, y - 5, label, 11, "middle", DIM)


def vdim(x, y0, y1, label):
    a(f'<line x1="{x}" y1="{y0}" x2="{x}" y2="{y1}" stroke="{DIM}" marker-start="url(#arr)" marker-end="url(#arr)"/>')
    a(f'<text x="{x - 6}" y="{(y0 + y1) / 2}" font-size="11" fill="{DIM}" text-anchor="middle" transform="rotate(-90 {x - 6} {(y0 + y1) / 2})">{label}</text>')


a(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" font-family="Consolas, Menlo, monospace">')
a(f'<defs><marker id="arr" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{DIM}"/></marker>'
  f'<pattern id="g" width="20" height="20" patternUnits="userSpaceOnUse"><path d="M20 0 L0 0 0 20" fill="none" stroke="#1a5288" stroke-width="0.6"/></pattern></defs>')
a(f'<rect width="{W}" height="{H}" fill="{BG}"/><rect width="{W}" height="{H}" fill="url(#g)"/>')
rrect(10, 10, W - 20, H - 20, 0, fill="none", stroke=LINE, stroke_width=2)

# ---- rear view (module bays) ----
ox, oy = 90, 120
w, h = P["width"] * S, P["length"] * S
text(ox, oy - 40, "REAR VIEW — MODULE BAYS &amp; OPTICAL DOCKS", 15, weight="bold")
text(ox, oy - 22, "scale 3.2 px/mm · all bays identical, left bays rotated 180°", 11, color=DIM)
rrect(ox, oy, w, h, P["corner_radius"] * S, fill="none", stroke=LINE, stroke_width=2)
cx0, cy0 = ox + w / 2, oy + h / 2
names = L["default_config"]
for bay in L["bays"]:
    bx = cx0 + (bay["cx"] - D["bay_width"] / 2) * S
    by = cy0 - (bay["cy"] + D["bay_height"] / 2) * S
    rrect(bx, by, D["bay_width"] * S, D["bay_height"] * S, D["bay_radius"] * S, fill="#0f4a80", stroke=LINE)
    s = bay["side"]
    lay = L["dock_layout"]
    for (u, v) in lay["pogo"]:
        x, y = s * (P["beam_width"] / 2 + u), bay["cy"] + s * v
        a(f'<circle cx="{cx0 + x * S:.1f}" cy="{cy0 - y * S:.1f}" r="{0.78 * S:.1f}" fill="{ACC}"/>')
    for (u, v) in lay["magnets"]:
        x, y = s * (P["beam_width"] / 2 + u), bay["cy"] + s * v
        a(f'<circle cx="{cx0 + x * S:.1f}" cy="{cy0 - y * S:.1f}" r="{3.05 * S:.1f}" fill="none" stroke="{LINE}" stroke-dasharray="3 2"/>')
    for (u, v) in lay["align"]:
        x, y = s * (P["beam_width"] / 2 + u), bay["cy"] + s * v
        a(f'<circle cx="{cx0 + x * S:.1f}" cy="{cy0 - y * S:.1f}" r="{1.0 * S:.1f}" fill="none" stroke="{LINE}"/>')
    u, v = lay["optical"]
    x, y = s * (P["beam_width"] / 2 + u), bay["cy"] + s * v
    rrect(cx0 + x * S - 1.25 * S, cy0 - y * S - 2 * S, 2.5 * S, 4 * S, 1, fill="#7fe3ff")
    text(bx + D["bay_width"] * S / 2, by + D["bay_height"] * S - 10, f'DOCK {bay["slot"]} · {names[bay["slot"]].upper()}', 10, "middle")
a(f'<line x1="{cx0}" y1="{oy + 14}" x2="{cx0}" y2="{oy + h - 14}" stroke="#7fe3ff" stroke-width="2" stroke-dasharray="8 4"/>')
hdim(ox, ox + w, oy + h + 26, f'{P["width"]:.1f}')
vdim(ox - 22, oy, oy + h, f'{P["length"]:.1f}')
hdim(cx0 + P["beam_width"] / 2 * S, cx0 + (P["beam_width"] / 2 + D["bay_width"]) * S, oy + 40, f'bay {D["bay_width"]:.1f}')
text(ox, oy + h + 56, "● pogo VBUS/DETECT/SIDEBAND/GND   ▮ optical transceiver window   ◌ N52 magnet   ○ Ø2 H7 alignment", 10, color=DIM)
text(ox, oy + h + 72, "- - central optical backbone (light guide in mid-plate)", 10, color="#7fe3ff")

# ---- side section ----
sx, sy = 420, 140
text(sx, sy - 20, "SECTION A–A — STACK-UP (×2)", 15, weight="bold")
k = 2 * S
layers = [("display + cover glass", P["display_recess"], "#123f6b"),
          ("Ti mid-plate + optical bus", P["midplate"], "#5c7da0"),
          ("module bay (snap-in block)", D["bay_depth"], "#0f4a80")]
y = sy
for name, t, col in layers:
    rrect(sx, y, 300, t * k, 0, fill=col, stroke=LINE)
    text(sx + 310, y + t * k / 2 + 4, f'{t:.2f} mm  {name}', 11)
    y += t * k
vdim(sx - 14, sy, y, f'{P["thickness"]}')

# ---- dock detail ----
dx, dy = 420, 360
text(dx, dy - 20, "DOCK CONNECTOR DETAIL (×6)", 15, weight="bold")
kk = 9
rrect(dx, dy, 22 * kk, 14 * kk, 6, fill="#0f4a80", stroke=LINE)
for i, (u, v) in enumerate(L["dock_layout"]["pogo"]):
    cx, cy = dx + 3.5 * kk, dy + 7 * kk - v * kk
    a(f'<circle cx="{cx}" cy="{cy}" r="{0.775 * kk}" fill="{ACC}"/>')
    text(cx - 14, cy + 4, L["dock_layout"]["pogo_roles"][i], 10, "end", ACC)
rrect(dx + 8.5 * kk - 1.25 * kk, dy + 7 * kk - 2 * kk, 2.5 * kk, 4 * kk, 2, fill="#7fe3ff")
text(dx + 10.5 * kk, dy + 7 * kk + 4, "optical lane ×2, 10 Gb/s each", 10)
fy = dy + 14 * kk + 26
text(dx, fy, "FITS (from cad/out/dimensions.json)", 12, weight="bold")
for i, f in enumerate(L["fits"]):
    text(dx, fy + 18 * (i + 1), f'{f["feature"]}: {f["clearance_mm"]} mm{" " + f["fit"] if "fit" in f else ""}', 11, color=DIM)

# ---- subsystems ----
qx, qy = 1070, 80
text(qx, qy, "SUBSYSTEMS", 15, weight="bold")
rows = [
    ("1  Lego spine", "magnetic pogo + optical bus · Rust HAL · hot-swap &lt;50 ms"),
    ("2  Programmable surface", "EAP clicks ≤80 µm · microfluidic ≤400 µm · privacy light-field"),
    ("3  Zero-charge power", "TEG + piezo harvest (µW) · solid-state buffer · NPU scheduler"),
    ("4  Node mesh", "LoRa 915 MHz + 60 GHz beamforming · Ed25519 · ChaCha20-Poly1305"),
    ("5  Dual display", "colour E-Ink front · mono E-Ink rear · laser MEMS tabletop"),
]
for i, (t1, t2) in enumerate(rows):
    text(qx, qy + 30 + i * 40, t1, 13, color=ACC)
    text(qx, qy + 47 + i * 40, t2, 11, color=DIM)

text(qx, 340, "DEFAULT MODULE LOADOUT", 15, weight="bold")
budget = [("camera", "1200 mW · 12 Gb/s · Normal"), ("projector", "3500 mW · 6 Gb/s · Low"),
          ("npu (spiking)", "1500 mW · 16 Gb/s · High"), ("satcom", "2500 mW · Normal"),
          ("battery ×2", "+4000 mW supply, 4.5 Wh each · Critical")]
for i, (n, d) in enumerate(budget):
    text(qx, 356 + i * 20, f"{n:<14}", 12)
    text(qx + 130, 356 + i * 20, d, 11, color=DIM)

text(qx, 490, "VERIFICATION", 15, weight="bold")
ver = L.get("verification", {})
nchk = len(ver.get("checks", []))
npass = sum(c["pass"] for c in ver.get("checks", []))
text(qx, 514, f"{npass}/{nchk} CAD checks pass · spine {ver.get('spine_mass_g', 0):.0f} g Ti-6Al-4V", 12, color=ACC)
text(qx, 532, "zero interference: every module × every dock (OCC boolean)", 11, color=DIM)
text(qx, 550, "46 Rust tests: HAL hot-swap, mesh routing/crypto, compositor", 11, color=DIM)

# ---- title block ----
tx, ty, tw, th = 1010, 820, 570, 160
rrect(tx, ty, tw, th, 0, fill="none", stroke=LINE, stroke_width=1.5)
for yy in (40, 80, 120):
    a(f'<line x1="{tx}" y1="{ty + yy}" x2="{tx + tw}" y2="{ty + yy}" stroke="{LINE}"/>')
a(f'<line x1="{tx + 380}" y1="{ty + 40}" x2="{tx + 380}" y2="{ty + th}" stroke="{LINE}"/>')
text(tx + 12, ty + 27, "PROJECT MONOLITH — OPEN MODULAR SMARTPHONE PLATFORM", 15, weight="bold")
text(tx + 12, ty + 66, "DWG PM-ENG-001 · TITANIUM SPINE &amp; DOCK INTERFACE", 12)
text(tx + 392, ty + 66, "REV B", 12)
text(tx + 12, ty + 106, "MATERIAL Ti-6Al-4V (Grade 5) · modules PC/GF + Al", 12)
text(tx + 392, ty + 106, "UNITS mm", 12)
text(tx + 12, ty + 146, "GENERATED FROM cad/monolith_cad.py (CadQuery)", 12)
text(tx + 392, ty + 146, "SHEET 1/1", 12)
a("</svg>")
(ROOT / "docs/blueprint.svg").write_text("\n".join(out))
print("wrote docs/blueprint.svg")
