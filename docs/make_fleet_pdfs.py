#!/usr/bin/env python3
"""ArcticChain print set — blueprint PDFs for the whole node fleet.

Generates one multi-page PDF per node on ANSI B landscape sheets
(17 x 11 in), plus a fleet overview cover. Every sheet carries the
attribution block:

    DRAWN  Surafel Negussie — Planner / Maker
    OWNER  Emebet Inc. — emebetos.ca — SOLE PROPRIETARY OWNER
    PROPRIETARY & CONFIDENTIAL — ALL RIGHTS RESERVED

Sheets are SVG -> HTML (@page 17in x 11in) -> headless Chrome -> PDF.
Output: docs/print/*.pdf

Run:  python docs/make_fleet_pdfs.py
"""

import html
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "print"
OUT.mkdir(exist_ok=True)

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
if not Path(CHROME).exists():
    CHROME = "chrome"

# ------------------------------------------------------------------ palette
BG, GRID, LINE, DIM, ACC, PANEL, GOOD = (
    "#0b3a66", "#1a5288", "#d8ecff", "#8fc1ea", "#ffd479", "#0f4a80", "#7fe3ff")
RED = "#ff9d7a"

PW, PH = 1632, 1056          # ANSI B landscape at 96 dpi (17in x 11in)
M = 28                       # page margin
TODAY = date.today().isoformat()


# ------------------------------------------------------------------ helpers
def esc(s):
    return html.escape(str(s), quote=False)


def wrap(s, n):
    """Greedy word-wrap to ~n chars per line."""
    words, lines, cur = str(s).split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > n and cur:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return lines or [""]


class Sheet:
    """One ANSI B landscape blueprint sheet."""

    def __init__(self, dwg, title, subtitle, node, rev="A", status="PROTOTYPE"):
        self.dwg, self.title, self.subtitle = dwg, title, subtitle
        self.node, self.rev, self.status = node, rev, status
        self.el = []
        self._header()

    # -- primitives ------------------------------------------------------
    def t(self, x, y, s, size=11, anchor="start", color=LINE, weight="normal"):
        self.el.append(
            f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" text-anchor="{anchor}" '
            f'fill="{color}" font-weight="{weight}">{esc(s)}</text>')

    def ln(self, x1, y1, x2, y2, color=DIM, w=1.0, dash=None):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.el.append(
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="{color}" stroke-width="{w}"{d}/>')

    def rect(self, x, y, w, h, fill="none", stroke=LINE, sw=1.0, r=0, dash=None, opacity=None):
        op = f' opacity="{opacity}"' if opacity else ""
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.el.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{r}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{d}{op}/>')

    def circ(self, cx, cy, r, fill="none", stroke=LINE, sw=1.0, dash=None):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.el.append(
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="{sw}"{d}/>')

    def path(self, d, color=LINE, w=1.0, fill="none"):
        self.el.append(f'<path d="{d}" fill="{fill}" stroke="{color}" stroke-width="{w}"/>')

    def arrow(self, x1, y1, x2, y2, color=DIM):
        self.ln(x1, y1, x2, y2, color, 1.2)
        import math
        ang = math.atan2(y2 - y1, x2 - x1)
        for da in (2.6, -2.6):
            self.ln(x2, y2, x2 + 9 * math.cos(ang + da), y2 + 9 * math.sin(ang + da), color, 1.2)

    # -- composites ------------------------------------------------------
    def h(self, x, y, s, size=13):
        self.t(x, y, s, size, weight="bold", color=ACC)

    def p(self, x, y, s, size=10.5, color=DIM, width=110, lh=14):
        for i, ln_ in enumerate(wrap(s, width)):
            self.t(x, y + i * lh, ln_, size, color=color)
        return y + len(wrap(s, width)) * lh

    def bullets(self, x, y, items, size=10.5, color=DIM, width=115, lh=15, mark="·"):
        yy = y
        for it in items:
            for i, ln_ in enumerate(wrap(it, width)):
                self.t(x + (8 if i == 0 else 16), yy, (mark + " " if i == 0 else "") + ln_,
                       size, color=color)
                yy += lh
            yy += 2
        return yy

    def table(self, x, y, widths, headers, rows, rh=19, fs=9.5, hfs=10):
        """Simple ruled table; cells word-wrap inside their column."""
        cx = x
        total = sum(widths)
        self.rect(x, y, total, rh * (len(rows) + 1), fill=PANEL, stroke=LINE, sw=1.2)
        cx = x
        for w, htxt in zip(widths, headers):
            self.t(cx + 6, y + rh - 6, htxt, hfs, weight="bold", color=ACC)
            cx += w
        self.ln(x, y + rh, x + total, y + rh, LINE, 1.2)
        yy = y + rh
        for row in rows:
            cx = x
            maxlines = 1
            cells = [wrap(c, max(8, int(w / 5.6))) for c, w in zip(row, widths)]
            maxlines = max(len(c) for c in cells)
            rowh = max(rh, maxlines * 12 + 6)
            for i, (cell, w) in enumerate(zip(cells, widths)):
                for j, cl in enumerate(cell):
                    self.t(cx + 6, yy + 13 + j * 12, cl, fs, color=LINE)
            self.ln(x, yy + rowh, x + total, yy + rowh, DIM, 0.5, "3 3")
            cx = x
            for w in widths:
                cx += w
                self.ln(cx, yy, cx, yy + rowh, DIM, 0.5, "3 3")
            yy += rowh
        self.ln(x, yy, x + total, yy, LINE, 1.2)
        return yy

    def dims_h(self, x0, x1, y, label, size=10):
        self.ln(x0, y, x1, y, DIM, 1)
        for x in (x0, x1):
            self.ln(x, y - 5, x, y + 5, DIM, 1)
        self.t((x0 + x1) / 2, y - 7, label, size, "middle", DIM)

    def dims_v(self, x, y0, y1, label, size=10):
        self.ln(x, y0, x, y1, DIM, 1)
        for y in (y0, y1):
            self.ln(x - 5, y, x + 5, y, DIM, 1)
        self.el.append(
            f'<text x="{x - 8}" y="{(y0 + y1) / 2}" font-size="{size}" fill="{DIM}" '
            f'text-anchor="middle" transform="rotate(-90 {x - 8} {(y0 + y1) / 2})">{esc(label)}</text>')

    def box(self, x, y, w, h, title, sub=None, fill=PANEL, stroke=LINE, tcolor=ACC):
        self.rect(x, y, w, h, fill=fill, stroke=stroke, sw=1.2, r=6)
        self.t(x + w / 2, y + (18 if sub else h / 2 + 4), title, 10.5,
               "middle", tcolor, "bold")
        if sub:
            self.t(x + w / 2, y + 33, sub, 8.5, "middle", DIM)

    # -- frame ------------------------------------------------------------
    def _header(self):
        self.el.append(
            f'<defs><marker id="arr" viewBox="0 0 10 10" refX="5" refY="5" '
            f'markerWidth="6" markerHeight="6" orient="auto-start-reverse">'
            f'<path d="M0,0 L10,5 L0,10 z" fill="{DIM}"/></marker>'
            f'<pattern id="g" width="20" height="20" patternUnits="userSpaceOnUse">'
            f'<path d="M20 0 L0 0 0 20" fill="none" stroke="{GRID}" stroke-width="0.6"/>'
            f'</pattern></defs>')
        self.el.append(f'<rect width="{PW}" height="{PH}" fill="{BG}"/>')
        self.el.append(f'<rect width="{PW}" height="{PH}" fill="url(#g)"/>')
        self.rect(M, M, PW - 2 * M, PH - 2 * M, stroke=LINE, sw=2)
        # header band
        self.rect(M, M, PW - 2 * M, 74, fill=PANEL, stroke=LINE, sw=1.2)
        self.t(M + 18, M + 30, self.node, 20, weight="bold", color=ACC)
        self.t(M + 18, M + 50, self.title, 13, weight="bold")
        self.t(M + 18, M + 68, self.subtitle, 9.5, color=DIM)
        self.t(PW - M - 18, M + 30, self.dwg, 13, "end", weight="bold")
        self.t(PW - M - 18, M + 50, f"REV {self.rev} · {TODAY}", 10, "end", DIM)
        self.t(PW - M - 18, M + 66, self.status, 10, "end", GOOD)

    def _titleblock(self, sheet_no, sheets_total):
        x, y, w, h = PW - M - 560, PH - M - 118, 560, 104
        self.rect(x, y, w, h, fill=PANEL, stroke=LINE, sw=1.4)
        for yy in (26, 56, 80):
            self.ln(x, y + yy, x + w, y + yy, LINE, 1)
        self.ln(x + 300, y + 26, x + 300, y + h, LINE, 1)
        self.ln(x + 430, y + 56, x + 430, y + h, LINE, 1)
        self.t(x + 10, y + 18, "ARCTICCHAIN · RURAL NODE FLEET", 11, weight="bold")
        self.t(x + 10, y + 42, "PROPRIETARY & CONFIDENTIAL — EMEBET INC.", 9, color=RED, weight="bold")
        self.t(x + 10, y + 66, "DRAWN: Surafel Negussie — Planner / Maker", 9.5)
        self.t(x + 310, y + 42, "SOLE PROPRIETARY OWNER", 8.5, color=DIM)
        self.t(x + 310, y + 60, "Emebet Inc. · emebetos.ca", 10, weight="bold", color=ACC)
        self.t(x + 310, y + 76, "registered Canadian company — Edmonton, AB", 8.5, color=DIM)
        self.t(x + 440, y + 42, f"DWG {self.dwg}", 9.5, weight="bold")
        self.t(x + 440, y + 60, f"REV {self.rev}", 9.5)
        self.t(x + 440, y + 78, f"SCALE NTS · SHEET {sheet_no}/{sheets_total}", 8.5, color=DIM)
        self.t(x + 10, y + 98, "DESIGNED FOR RURAL & REMOTE CANADA — -45..+70 °C · IP65 · SOLAR-FIRST · COMMUNITY-OWNED",
           8, color=DIM)

    def footer_notice(self):
        self.t(M + 8, PH - M - 14,
               "EMEBET INC. — PROPRIETARY & CONFIDENTIAL — UNAUTHORIZED DISTRIBUTION PROHIBITED",
               8.5, color=RED)

    def svg(self, sheet_no, sheets_total):
        self._titleblock(sheet_no, sheets_total)
        self.footer_notice()
        body = "\n".join(self.el)
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {PW} {PH}" '
                f'font-family="Consolas, Menlo, monospace">{body}</svg>')


# ============================================================ L1 BRICK ====
def l1_sheets():
    out = []

    # ---- 101 general arrangement ----
    s = Sheet("AF-L1-101", "GENERAL ARRANGEMENT & FEATURES", "FIELD NODE — HANDHELD MESH BRICK", "L1 · BRICK")
    s.h(M + 16, 118, "WHAT THIS NODE IS")
    s.bullets(M + 16, 136, [
        "One handheld brick that is simultaneously: mailbox, mesh repeater, public bulletin (E-Ink), and SOS beacon.",
        "Runs the ArcticChain agent (poc/arcticchain_agent.py) — HTTP API on :8080, SQLite store-and-forward.",
        "Every node holds an Ed25519 identity; envelopes signed + replay-protected (mesh-net crate, 46 tests green).",
        "Works with zero connectivity: LoRa mesh to neighbors, LTE backhaul only when a tower exists.",
    ], width=118)
    # envelope drawing
    ex, ey = 700, 140
    s.t(ex, ey - 14, "ENVELOPE — HANDHELD BRICK", 11, weight="bold", color=ACC)
    s.rect(ex, ey, 330, 150, fill=PANEL, stroke=LINE, sw=1.6, r=10)
    s.rect(ex + 30, ey + 40, 180, 60, fill="#0b3a66", stroke=DIM, sw=1, r=4)
    s.t(ex + 120, ey + 105, "7.5in E-Ink (800×480)", 9, "middle", DIM)
    s.circ(ex + 285, ey + 70, 16, fill="none", stroke=ACC, sw=1.5)
    s.t(ex + 285, ey + 74, "SOS", 8, "middle", ACC)
    s.circ(ex + 40, ey + 30, 5, fill=ACC)
    s.t(ex + 55, ey + 34, "status LED", 8.5, DIM)
    s.dims_h(ex, ex + 330, ey + 185, "160.0")
    s.dims_v(ex - 24, ey, ey + 150, "~30 stack")
    s.t(ex, ey + 215, "shell: 160×80 mm face · ~32 mm thick w/ stack · ~100 g PETG", 9, color=DIM)
    # system block
    bx, by = M + 16, 330
    s.h(bx, by, "INTERNAL SYSTEM")
    parts = [
        ("CM5 + IO BOARD", "compute · 4GB · headers"),
        ("LTE HAT (SIM7600)", "4G backhaul · GNSS · BT"),
        ("E-INKE HAT 7.5in", "public display · SPI0"),
        ("LoRa SX1262", "915 MHz mesh · SPI1"),
        ("4×18650 TRAY", "14.8 V → 5 V buck"),
    ]
    yy = by + 16
    for name, sub in parts:
        s.box(bx, yy, 190, 44, name, sub)
        if yy > by + 16:
            s.arrow(bx + 95, yy - 8, bx + 95, yy - 2, DIM)
        yy += 54
    s.t(bx + 206, 630, "STACK bottom→top: USB-C pwr → CM5 IO → LTE → E-Ink → LoRa", 9, color=DIM)
    # roles table
    s.h(560, by + 20, "WHAT IT DOES FOR THE COMMUNITY")
    s.table(560, by + 34, [250, 430], ["Function", "How"], [
        ["Mailbox", "email/SMS-tier messages queue in SQLite and deliver when any path opens"],
        ["Repeater", "forwards signed envelopes — every node extends coverage ~5–15 km"],
        ["Bulletin", "E-Ink shows alerts, notices, prices — readable in sunlight, zero power to display"],
        ["SOS beacon", "front button pages responders over mesh when all else fails"],
    ], rh=22)
    # acceptance
    s.h(M + 16, 640, "ACCEPTANCE TEST (THE WHOLE PITCH IN ONE TEST)")
    s.bullets(M + 16, 658, [
        "Unit A: POST /message {\"to\":\"broadcast\",\"text\":\"Mesh test\"} → Unit B: GET /inbox returns it.",
        "Repeat with LTE in airplane mode — delivery with NO towers = the product.",
        "curl http://localhost:8080/health → {\"lora\":true,\"lte\":true,\"uptime\":...}",
    ], width=130)
    s.h(M + 16, 780, "KNOWN GAPS (BY DESIGN — BUILD_GUIDE.md)")
    s.bullets(M + 16, 798, [
        "LoRa send_frame/poll are TODOs — plaintext beacon until SX1262 driver + envelope land (wk 3).",
        "E-Ink is stub file-write; real Waveshare driver is Level-2.",
        "No power-path controller — battery swap reboots CM5 (acceptable PoC).",
    ], width=130, color=RED)
    out.append(s.svg(1, 4))

    # ---- 102 mechanical ----
    s = Sheet("AF-L1-102", "MECHANICAL & ENVELOPE", "PRINTED CHASSIS — PETG FIELD ENCLOSURE", "L1 · BRICK")
    s.h(M + 16, 118, "ENCLOSURE SPEC (FROM cad/level1_chassis.py → dimensions.json)")
    s.table(M + 16, 132, [210, 150, 210, 240],
            ["Parameter", "Value", "Parameter", "Value"], [
        ["Overall length (X)", "160.0 mm", "Wall thickness", "2.4 mm"],
        ["Overall width (Y)", "80.0 mm", "Floor thickness", "2.0 mm"],
        ["Corner radius", "8.0 mm", "Stack height", "~9.2 mm in ~22 mm cavity"],
        ["Shell mass (PETG)", "~100 g", "Total incl. internals", "~450–550 g est."],
        ["Button diameter", "12.0 mm (front)", "Status LED hole", "5.0 mm"],
        ["Battery tray", "4×18650 slide-in (rear)", "Cell format", "flat-top, protected"],
    ], rh=24)
    s.h(M + 16, 340, "PRINT SETTINGS")
    s.bullets(M + 16, 358, [
        "Material: PETG (field-rated; NOT PLA — enclosure lives outside). REV-B target: PC or ASA for -45 °C.",
        "Infill 40%, walls 4, no supports required (verify in slicer preview).",
        "Files: cad/level1/chassis_shell.stl (540 tris) + battery_tray.stl (2012 tris).",
        "Post-print: deburr seams, dry-fit stack, conformal-coat rev for IP65 (silicone gasket at lid seam).",
    ], width=118)
    s.h(M + 16, 520, "STACK-UP SECTION (SIDE VIEW)")
    # draw stack
    sx, sy = 70, 560
    layers = [
        ("USB-C PD in + fuse", 24, "#123f6b"),
        ("Battery tray (4×18650)", 40, "#0f4a80"),
        ("CM5 IO Board", 18, "#5c7da0"),
        ("LTE HAT (SIM7600)", 15, "#5c7da0"),
        ("E-Ink HAT 7.5in", 15, "#5c7da0"),
        ("LoRa SX1262 (GPIO 16–21)", 12, "#0f4a80"),
        ("Top cover + antenna ports", 20, "#123f6b"),
    ]
    yy = sy
    for name, hgt, col in layers:
        rh = hgt * 1.6
        s.rect(sx, yy, 440, rh, fill=col, stroke=LINE, sw=1)
        s.t(sx + 455, yy + rh / 2 + 3, name, 9.5, color=LINE)
        yy += rh + 4
    s.dims_v(sx - 24, sy, yy, "~32 mm")
    # antenna keepout
    s.h(700, 520, "ANTENNA KEEP-OUT (CRITICAL FOR RANGE)")
    s.bullets(700, 538, [
        "LTE whip: top edge, SMA bulkhead; ≥10 mm from LoRa antenna.",
        "LoRa 915 MHz: spring/whip at OPPOSITE end, vertical.",
        "NO metal (cells, buck inductor) within 15 mm of either antenna.",
        "Route through top grommets; seal with silicone.",
    ], width=105)
    s.h(700, 680, "MOUNTING & FIELD NOTES")
    s.bullets(700, 698, [
        "Handheld + pocket clip; SOS button reachable one-handed, glove-friendly rev-B.",
        "E-Ink readable in direct sun; updates only on new content (zero idle power).",
        "Operating target: -20..+50 °C gen-1; -45 °C requires LiFePO4/cold-rated cells rev-B.",
        "Two-person install NOT required — this is the personal node.",
    ], width=105)
    # rev roadmap strip
    s.h(M + 16, 850, "REVISION ROADMAP")
    s.table(M + 16, 864, [160, 260, 260, 240], ["Rev", "Change", "Driver", "Status"], [
        ["A (current)", "PETG shell, NMC 18650, stub E-Ink", "PoC build", "CAD done"],
        ["B", "PC/ASA, LiFePO4, IP65 gasket, glove SOS", "-45 °C + weather", "planned"],
        ["C", "power-path controller (BQ24075-class)", "hot-swap battery", "Level-2"],
        ["D", "real E-Ink driver + SX1262 envelope", "mesh-net integration", "wk 3–4"],
    ], rh=26)
    out.append(s.svg(2, 4))

    # ---- 103 electrical ----
    s = Sheet("AF-L1-103", "ELECTRICAL — BOM, POWER & GPIO", "CIRCUIT & PARTS SPECIFICATION", "L1 · BRICK")
    s.h(M + 16, 118, "BILL OF MATERIALS (PER UNIT — ORDER LIST ×2 FOR ACCEPTANCE TEST)")
    # noqa
    s.table(M + 16, 132, [24, 300, 190, 110, 90],
            ["#", "Part", "Supplier class", "Approx CAD", "Qty"], [
        ["1", "Raspberry Pi CM5 4GB + CM5 IO Board", "PiShop / Canada Computers", "$90–130", "1"],
        ["2", "7.5in e-Paper HAT 800×480 SPI (Waveshare-class)", "DFRobot / Amazon.ca", "$80–110", "1"],
        ["3", "SIM7600 4G/LTE HAT (GNSS+BT ok)", "DFRobot / Waveshare", "$60–90", "1"],
        ["4", "SX1262 LoRa breakout 915 MHz SPI (EBYTE E22-900M30S class)", "DFRobot / AliExpress", "$15–25", "1"],
        ["5", "Magnetic pogo-pin connector pairs ×6", "AliExpress / Amazon.ca", "$30–60", "1"],
        ["6", "4×18650 flat-top protected + 14.8V→5V 3A buck (USB-C PD)", "Electronics supplier", "$40–70", "1"],
        ["7", "PETG filament 1 kg (both shells + trays ~200 g)", "Any filament supplier", "$25–35", "0.5"],
    ], rh=26)
    y0 = 388
    s.h(M + 16, y0, "POWER TREE")
    s.box(M + 16, y0 + 14, 200, 50, "4×18650 (14.8 V nom)", "16.8 V full · 4S pack", fill="#123f6b")
    s.arrow(M + 116, y0 + 64, M + 116, y0 + 80, DIM)
    s.box(M + 16, y0 + 80, 200, 50, "14.8→5 V 3 A buck", "USB-C PD trigger", fill="#123f6b")
    s.arrow(M + 116, y0 + 130, M + 116, y0 + 146, DIM)
    s.box(M + 16, y0 + 146, 200, 50, "5 V rail → CM5 + HATs", "fuse 5 A; 10 A batt in", fill="#123f6b")
    s.t(M + 240, y0 + 40, "Runtime est: 4×3000 mAh ≈ 44 Wh →", 10, color=DIM)
    s.t(M + 240, y0 + 58, "LTE idle ~1–2 W, LoRa TX bursts ~0.1 W →", 10, color=DIM)
    s.t(M + 240, y0 + 76, "days-weeks autonomy; solar charge port rev-B.", 10, color=DIM)
    # GPIO table
    gx = 800
    s.h(gx, y0, "GPIO ALLOCATION (NO CONFLICTS)")
    s.table(gx, y0 + 14, [150, 210, 260], ["Signal", "GPIO", "Notes"], [
        ["E-Ink SPI", "9 MOSI · 10 MISO · 11 SCLK · 8 CE0", "spi0 HAT default"],
        ["E-Ink busy / rst", "25 / 17", "poll before refresh"],
        ["LoRa SPI1", "16–21 per breakout silkscreen", "dtoverlay=spi1-3cs — NOT spi0"],
        ["LoRa reset / DIO1", "24 / 23", "interrupt-driven RX"],
        ["LTE modem", "USB CDC-ACM (or UART 14/15)", "prefer USB — no pin conflicts"],
        ["SOS button", "27 (input pull-up)", "front panel wire"],
        ["Status LED", "22 (PWM)", "power + mesh activity"],
    ], rh=26)
    # config
    s.h(M + 16, y0 + 280, "/boot/firmware/config.txt — REQUIRED OVERLAYS")
    s.rect(M + 16, y0 + 294, 660, 150, fill="#071f36", stroke=DIM, sw=1)
    cfg = [
        "dtparam=i2c_arm=on", "dtparam=spi=on", "dtparam=uart0=on",
        "dtoverlay=spi1-3cs", "dtoverlay=gpio-shutdown", "disable_overscan=1",
        "# E-Ink=spi0 (GPIO7-11) · LoRa=spi1 (GPIO16-21) — never share",
    ]
    for i, c in enumerate(cfg):
        s.t(M + 30, y0 + 314 + i * 19, c, 10, color=GOOD)
    # stack order
    s.h(740, y0 + 280, "STACK ORDER (BOTTOM → TOP)")
    s.bullets(740, y0 + 298, [
        "USB-C power + battery tray (bottom bay)",
        "CM5 IO Board — power, HDMI, USB, GPIO header",
        "4G/LTE HAT — UART + USB AT commands",
        "E-Ink HAT — SPI0 + GPIO25 busy",
        "LoRa SX1262 — SPI1 GPIO16–21 (top)",
    ], width=100)
    s.h(740, y0 + 400, "WIRING RULES")
    s.bullets(740, y0 + 418, [
        "Standoffs M2.5 nylon at PCB corners; 2.5 mm headers between HATs.",
        "Thermal pad on CM5 SoC; keep buck inductor away from antennas.",
        "Double-check LoRa breakout silkscreen — CE/RESET/DIO numbering varies.",
    ], width=105)
    out.append(s.svg(3, 4))

    # ---- 104 software & assembly ----
    s = Sheet("AF-L1-104", "SOFTWARE, ASSEMBLY & TEST", "FIRMWARE + BUILD PROCEDURE", "L1 · BRICK")
    s.h(M + 16, 118, "SOFTWARE STACK")
    s.table(M + 16, 132, [220, 480], ["Component", "Detail"], [
        ["OS", "Raspberry Pi OS Lite 64-bit on 32 GB microSD; user 'arctic', SSH enabled"],
        ["Agent", "poc/arcticchain_agent.py — stdlib Python, systemd service arcticchain-agent.service"],
        ["API :8080", "GET /health · GET /inbox · GET /signal · POST /message {to,text}"],
        ["Store", "SQLite inbox/outbox — store-and-forward, survives days offline"],
        ["Mesh crypto", "mesh-net crate: Ed25519 sign · X25519 · ChaCha20-Poly1305 (Rust, 46 tests)"],
        ["Roadmap", "LoRa driver + envelope compat (wk3) → E-Ink driver (L2) → power-path (L2)"],
    ], rh=30)
    s.h(M + 16, 372, "ASSEMBLY SEQUENCE (7 STEPS — ORDER_LIST.md)")
    steps = [
        "Print chassis_shell.stl + battery_tray.stl — PETG, 40% infill, 4 walls.",
        "Flash Pi OS Lite to both SD cards (Imager → SSH on, user 'arctic').",
        "Bench-test bare CM5: boot, SSH, i2cdetect -y 1 — BEFORE stacking HATs.",
        "Stack per WIRING.md; wire LoRa to GPIO 16–21 (spi1, never spi0).",
        "Wire power: 4×18650 → 14.8→5 V buck → USB-C; fuse 5 A rail, 10 A input.",
        "Deploy agent: copy arcticchain_agent.py + systemd unit (poc/SETUP.md §5).",
        "Acceptance test: POST /message on A → GET /inbox on B → airplane-mode LTE → repeat.",
    ]
    yy = 390
    for i, st in enumerate(steps):
        s.circ(M + 28, yy + 4, 10, fill=PANEL, stroke=ACC, sw=1.2)
        s.t(M + 28, yy + 8, str(i + 1), 9, "middle", ACC, "bold")
        s.p(M + 48, yy + 8, st, size=10.5, color=LINE, width=140, lh=14)
        yy += 34
    s.h(M + 16, 660, "FIELD ACCEPTANCE CRITERIA")
    s.bullets(M + 16, 678, [
        "Two units exchange a mesh message with LTE disabled — verified on bench AND in field.",
        "Message latency < 60 s at ≤ 5 km line-of-sight (LoRa BW/SF tuned for range).",
        "Node survives -20 °C night + sun-loaded enclosure (+60 °C internal) — rev-B extends to -45 °C.",
        "Battery swap → clean reboot → inbox intact (SQLite on SD survives power loss).",
    ], width=118)
    s.h(760, 118, "FILES IN REPO")
    s.bullets(760, 136, [
        "cad/level1_chassis.py — parametric generator (CadQuery)",
        "cad/level1/*.stl + *.step + dimensions.json — validated",
        "poc/arcticchain_agent.py — hardware-bridge agent (stdlib only)",
        "poc/arcticchain-agent.service — systemd unit",
        "poc/SETUP.md · poc/WIRING.md — full setup + wiring",
        "docs/ORDER_LIST.md — orderable BOM ×2 + tools",
        "docs/BUILD_GUIDE.md — 16-week build program",
        "firmware-hal · mesh-net · compositor · simulator/ — Rust workspace (46 tests)",
    ], width=110)
    s.h(760, 420, "SUPPORTING DOCS")
    s.bullets(760, 438, [
        "docs/HARDWARE.md — fleet overview & design DNA",
        "docs/feasibility.md — market & technical feasibility",
        "MEGAPLAN.md — the ignition path (mesh → swarm → sats → launch)",
    ], width=110)
    out.append(s.svg(4, 4))
    return out


# ============================================================ S MITE ======
def mite_sheets():
    out = []

    # ---- 101 GA ----
    s = Sheet("AF-S-101", "GENERAL ARRANGEMENT — SWARM UNIT", "PERCHABLE ENVIRONMENTAL SENSOR NODE", "S · MITE")
    s.h(M + 16, 118, "DESIGN INTENT")
    s.bullets(M + 16, 136, [
        "The swarm IS the sensor — a hundred perched Miters form a distributed aperture that follows the fire season.",
        "Each unit is deliberately minimal: solar top, LoRa radio, temp/RH/VOC sensing, perch clip. Roles are assigned by the swarm AI, not fixed in hardware.",
        "Default state = perched and reporting. Flight is a later role, not the power budget's problem.",
        "Same signed mesh identity as every ArcticChain node — a Mite is a node with a clip, not a separate system.",
    ], width=118)
    # puck drawing
    px, py = 720, 150
    s.t(px, py - 14, "ENVELOPE — PERCH PUCK", 11, weight="bold", color=ACC)
    s.rect(px, py, 300, 300, fill=PANEL, stroke=LINE, sw=1.6, r=16)
    s.circ(px + 150, py + 150, 110, fill="#0b3a66", stroke=DIM, sw=1.2)
    s.rect(px + 105, py + 105, 90, 90, fill="#123f6b", stroke=ACC, sw=1.2, r=4)
    s.t(px + 150, py + 153, "SOLAR", 10, "middle", ACC, "bold")
    s.t(px + 150, py + 256, "62×62 mm cell · ~1 W", 8.5, "middle", DIM)
    # clip
    s.path(f"M {px+60} {py+285} a 60 60 0 0 0 180 0", color=DIM, w=4)
    s.t(px + 150, py + 320, "perch clip — grips Ø10–40 mm branches/poles", 8.5, "middle", DIM)
    s.dims_h(px + 110, px + 410, py + 345, "90.0")
    s.dims_v(px + 85, py + 10, py + 310, "35 + clip")
    s.t(px + 150, py + 375, "shell 90×90×35 mm · ~120 g assembled", 9, "middle", DIM)
    # roles
    s.h(M + 16, 480, "SWARM ROLES (ASSIGNED BY MESH AI)")
    s.table(M + 16, 494, [120, 260, 260], ["Role", "Payload", "Job"], [
        ["Sensor-bee", "temp/RH + VOC (ENS160)", "sniff anomalies — the primary detector"],
        ["Eye-bee", "thermal/visual (rev-C)", "converge on fixes to confirm"],
        ["Relay-bee", "LoRa only, high mast", "extend range over ridges"],
        ["Charger-bee", "dock contacts", "perch at Anchor, top off, rebroadcast"],
    ], rh=26)
    s.h(M + 16, 680, "GEN-1 vs ROADMAP")
    s.table(M + 16, 694, [160, 320, 320], ["Stage", "What", "Gate"], [
        ["Gen-1 (now)", "~90 mm puck, solar+LoRa+gas, perch clip", "orderable parts, no custom ASIC"],
        ["Gen-2", "smaller, lower cost, printed antenna", "volume pricing + field data"],
        ["Gen-3 (R&D)", "sub-bee perched motes, degradable", "transient-electronics program — see D SEED"],
    ], rh=26)
    s.h(700, 480, "DETECTION CHAIN")
    s.bullets(700, 498, [
        "Mites sample temp/RH/VOC every 5–15 min (duty-cycled).",
        "Anomaly → signed LoRa report up the mesh → nearest Anchor/Brick.",
        "AI correlates spatial+temporal signatures → fire-watch alert.",
        "Eye-bees (later) converge on the fix for visual/thermal confirm.",
        "Weak distributed readings triangulate plumes better than one strong sensor.",
    ], width=110)
    out.append(s.svg(1, 4))

    # ---- 102 mechanical ----
    s = Sheet("AF-S-102", "MECHANICAL & MOUNTING", "PUCK SHELL, LID, BATTERY BAY, PERCH CLIP", "S · MITE")
    s.h(M + 16, 118, "PARTS (cad/swarm_node.py → cad/swarm/*.stl)")
    s.table(M + 16, 132, [170, 240, 160, 120], ["Part", "File", "Material", "Print"], [
        ["Bottom shell", "mite_shell.stl", "ASA or PC-ABS (UV+cold)", "40% infill, 4 walls"],
        ["Top lid + solar recess", "mite_lid.stl", "same", "40%, 4 walls"],
        ["Battery bay tray", "mite_battery_bay.stl", "same", "20%, 3 walls"],
        ["Perch clip", "mite_perch_clip.stl", "PETG flex or ASA", "80% infill (spring)"],
    ], rh=26)
    s.h(M + 16, 300, "ENVELOPE DIMENSIONS")
    s.table(M + 16, 314, [180, 160, 180, 160], ["Parameter", "Value", "Parameter", "Value"], [
        ["Body", "90 × 90 × 35 mm", "Corner radius", "12 mm"],
        ["Wall / floor / lid", "2.0 / 1.6 / 3.0 mm", "Solar recess", "62×62×2.2 mm"],
        ["Battery bay", "54×38×9 mm (503450 LiPo)", "Carrier PCB", "38×38 mm"],
        ["Clip grip range", "Ø10–40 mm", "Clip drop below body", "10 mm"],
        ["Assembled mass", "~120 g est.", "Gasket", "lid groove, silicone bead"],
    ], rh=24)
    s.h(M + 16, 520, "MOUNTING — PERCH & GO")
    s.bullets(M + 16, 538, [
        "Branch/pole: C-clip cradle grips Ø10–40 mm; node sits horizontal, solar up.",
        "Fence/wire: same clip works on barbed wire or T-posts.",
        "Metal surface: N52 magnet puck variant (rev-B) for barns, tanks, towers.",
        "Anchor dock: bottom pogo pads mate with Anchor charging contacts.",
        "No tools, no screws — deploy in seconds, relocate as fire risk moves.",
    ], width=110)
    s.h(M + 16, 700, "WEATHERPROOFING")
    s.bullets(M + 16, 718, [
        "Lid gasket groove + silicone bead → IP65 perched in rain/snow.",
        "Solar panel under optical window film (replaceable if abraded).",
        "Breather vent (ePTFE) optional rev-B for condensation in freeze-thaw.",
        "All fasteners captive — nothing to lose in the bush.",
    ], width=110)
    s.h(700, 118, "SECTION — SIDE VIEW (SCHEMATIC)")
    # schematic stack
    lx, ly = 740, 150
    s.rect(lx, ly, 380, 60, fill="#0f4a80", stroke=LINE, sw=1.4)
    s.t(lx + 190, ly + 26, "TOP LID 3 mm", 10, "middle")
    s.t(lx + 190, ly + 42, "solar recess 62×62×2.2 + gasket groove", 8.5, "middle", DIM)
    s.rect(lx, ly + 60, 380, 200, fill="#0b3a66", stroke=LINE, sw=1.4)
    s.t(lx + 190, ly + 80, "CAVITY ~24 mm", 10, "middle", ACC)
    s.rect(lx + 30, ly + 200, 320, 16, fill="#123f6b", stroke=DIM, sw=1)
    s.t(lx + 190, ly + 211, "floor 1.6 mm", 8.5, "middle", DIM)
    s.rect(lx + 60, ly + 216, 260, 26, fill="none", stroke=ACC, sw=1.2, dash="5 3")
    s.t(lx + 190, ly + 232, "perch clip drop 10 mm", 8.5, "middle", ACC)
    s.dims_h(lx, lx + 380, ly + 268, "90.0")
    s.dims_v(lx - 24, ly, ly + 242, "35 + 10")
    s.t(lx, ly + 295, "shell cavity fits: carrier PCB 38×38 + battery 54×38×9 + standoffs", 9, color=DIM)
    s.h(700, 480, "MATERIALS RATIONALE")
    s.bullets(700, 498, [
        "ASA/PC-ABS: UV-stable + tough to -45 °C (PETG gets brittle cold).",
        "Solar: 60×60 mm poly ~1 W — orders of magnitude over duty-cycled need.",
        "Clip: printed cradle + replaceable steel spring strip (field-swappable).",
        "No metal fasteners exposed — clip and lid are tool-free.",
    ], width=105)
    s.h(700, 650, "REV NOTES")
    s.bullets(700, 668, [
        "REV A: 90 mm puck, 503450 LiPo, manual assembly.",
        "REV B: magnet base variant, ePTFE breather, castellated battery.",
        "REV C: eye-bee payload bay (thermal cam / extra sensor).",
        "REV D: sub-bee mote — separate D SEED program, not a shrink of this.",
    ], width=105)
    out.append(s.svg(2, 4))

    # ---- 103 electrical ----
    s = Sheet("AF-S-103", "ELECTRICAL — BOM, POWER & PINOUT", "PARTS + POWER BUDGET", "S · MITE")
    s.h(M + 16, 118, "BILL OF MATERIALS (GEN-1 — ALL ORDERABLE IN CANADA)")
    s.table(M + 16, 132, [24, 280, 190, 120, 90],
            ["#", "Part", "Supplier class", "Approx CAD", "Qty"], [
        ["1", "ESP32-S3-DevKitC-1 or S3-WROOM module carrier", "PiShop / DigiKey / Amazon.ca", "$8–15", "1"],
        ["2", "EBYTE E22-900M30S SX1262 LoRa breakout 915 MHz", "DFRobot / AliExpress", "$15–25", "1"],
        ["3", "Sensirion ENS160 VOC/AIQ sensor (I2C)", "DigiKey / Mouser", "$6–10", "1"],
        ["4", "Sensirion SHT41 temp/RH (I2C, optional 2nd)", "DigiKey / Mouser", "$4–7", "1"],
        ["5", "60×60 mm ~1 W 5 V poly solar cell", "Amazon.ca / electronics supplier", "$5–10", "1"],
        ["6", "503450 LiPo 2000 mAh + JST-PH leads", "Amazon.ca / RC supplier", "$12–18", "1"],
        ["7", "CN3791 MPPT solar charge module (or TP4056-class)", "AliExpress / Amazon.ca", "$3–6", "1"],
        ["8", "Custom carrier PCB ~38×38 mm (JLCPCB 5 pc)", "JLCPCB / PCBWay ships CA", "$15–30", "1"],
        ["9", "Printed enclosure set + spring strip", "Print farm / makerspace", "$5–10", "1"],
    ], rh=26)
    y0 = 430
    s.h(M + 16, y0, "POWER BUDGET (ESTIMATES — VERIFY ON BENCH)")
    s.table(M + 16, y0 + 14, [200, 150, 200, 240], ["State", "Current", "Duty", "Energy/day"], [
        ["Deep sleep (ESP32)", "~10 µA", "~95%", "~0.003 Wh"],
        ["Sense + process", "~80 mA @3.3 V", "~4% (5 min/hr)", "~0.013 Wh"],
        ["LoRa TX burst (30 dBm)", "~120 mA @3.3 V", "~1%", "~0.010 Wh"],
        ["RX listen windows", "~15 mA", "~5%", "~0.006 Wh"],
        ["TOTAL", "", "", "≈0.03 Wh/day"],
    ], rh=26)
    s.t(M + 16, y0 + 210, "2000 mAh LiPo ≈ 7.4 Wh → ~200+ days theoretical; winter sun + self-discharge → plan 60–90 day autonomy.",
       9.5, color=DIM)
    # pin map
    gx = 860
    s.h(gx, y0, "CARRIER PCB PIN MAP (ESP32-S3 ↔ SX1262 ↔ SENSORS)")
    s.table(gx, y0 + 14, [130, 220, 250], ["Net", "ESP32-S3 GPIO", "Function"], [
        ["LORA_SCK", "GPIO12", "SX1262 SPI clock"],
        ["LORA_MISO", "GPIO13", "SX1262 MISO"],
        ["LORA_MOSI", "GPIO11", "SX1262 MOSI"],
        ["LORA_NSS", "GPIO10", "SX1262 chip select"],
        ["LORA_RST", "GPIO9", "reset"],
        ["LORA_BUSY", "GPIO8", "DIO1 — RX/TX done IRQ"],
        ["I2C_SDA/SCL", "GPIO1/GPIO2", "ENS160 + SHT41 (0x53/0x44)"],
        ["BATT_ADC", "GPIO4 (ADC)", "battery voltage sense"],
        ["POGO_CHG", "GPIO3", "dock charge detect"],
        ["SOLAR_OK", "GPIO5", "charge status LED input"],
    ], rh=24)
    # block diagram
    s.h(M + 16, y0 + 280, "SYSTEM BLOCK")
    s.box(M + 16, y0 + 296, 170, 46, "SOLAR 1 W", "60×60 cell", fill="#123f6b")
    s.arrow(M + 186, y0 + 319, M + 210, y0 + 319, DIM)
    s.box(M + 210, y0 + 296, 170, 46, "CN3791 CHG", "MPPT-ish", fill="#123f6b")
    s.arrow(M + 380, y0 + 319, M + 404, y0 + 319, DIM)
    s.box(M + 404, y0 + 296, 170, 46, "LiPo 2000", "503450", fill="#123f6b")
    s.arrow(M + 574, y0 + 319, M + 598, y0 + 319, DIM)
    s.box(M + 598, y0 + 296, 170, 46, "LDO 3V3", "always-on", fill="#123f6b")
    s.t(M + 16, y0 + 368, "ESP32-S3 + SX1262 + ENS160 on 38×38 carrier; all sensors on I2C; radio on private SPI bus.", 9.5, color=DIM)
    s.h(M + 16, y0 + 400, "ALTERNATES / FUTURE REVS")
    s.bullets(M + 16, y0 + 418, [
        "Battery alt: 2×16340 LiPo (more compact) or single 18650 cold-rated (rev-B).",
        "Radio alt: SX1268 for +22 dBm if link budget demands (same footprint family).",
        "Sensor alt: SGP30 (cheaper VOC) or add SCD41 CO₂ for fire-season respiration proxy.",
        "Comms alt: LoRa backscatter / wake-up receiver for µW motes — D SEED research.",
    ], width=118)
    out.append(s.svg(3, 4))

    # ---- 104 software & assembly ----
    s = Sheet("AF-S-104", "FIRMWARE, ASSEMBLY & TEST", "SOFTWARE ROLE + BUILD PROCEDURE", "S · MITE")
    s.h(M + 16, 118, "FIRMWARE ARCHITECTURE")
    s.table(M + 16, 132, [220, 480], ["Component", "Detail"], [
        ["Runtime", "ESP-IDF (C) or Rust-embedded — gen-1 C for speed; Rust port when mesh-net envelope lands"],
        ["Envelope", "same signed format as mesh-net (Ed25519 + ChaCha20-Poly1305) — MUST match fleet"],
        ["Duty cycle", "deep-sleep 95% · sample 5 min · TX on anomaly or schedule · RX windows synced to mesh beacon"],
        ["Role", "announces capabilities; swarm AI assigns sensor/eye/relay/charger roles via mesh messages"],
        ["OTA", "signed firmware updates over mesh (rev-C); SD/USB for bench flashing"],
        ["Data", "temp/RH/VOC + battery + RSSI + role → compressed observation frame (<200 B)"],
    ], rh=30)
    s.h(M + 16, 372, "ASSEMBLY SEQUENCE")
    steps = [
        "Print shell, lid, battery bay, clip — ASA/PC-ABS shell, PETG clip strip.",
        "Populate carrier PCB: ESP32-S3, SX1262, ENS160, SHT41, charge circuit — or solder dev modules to carrier.",
        "Seat battery in tray, connect JST; verify charge path with CN3791 (solar simulator or bench supply).",
        "Close lid — gasket bead, solar cell under window film, captive screws/snaps.",
        "Attach perch clip; bench-test: boot, join test mesh, confirm signed envelope round-trip.",
        "Field trial: perch on fence line ×3 units, log range/RSSI/battery over 7 days.",
    ]
    yy = 390
    for i, st in enumerate(steps):
        s.circ(M + 28, yy + 4, 10, fill=PANEL, stroke=ACC, sw=1.2)
        s.t(M + 28, yy + 8, str(i + 1), 9, "middle", ACC, "bold")
        s.p(M + 48, yy + 8, st, size=10.5, color=LINE, width=140, lh=14)
        yy += 34
    s.h(M + 16, 660, "ACCEPTANCE / TEST CRITERIA")
    s.bullets(M + 16, 678, [
        "Two Miters exchange signed observations through a Brick/Anchor at ≥3 km LOS.",
        "Battery autonomy ≥60 days at 1 sample/10 min + hourly beacon (winter light derate).",
        "Survives -30 °C storage + operation; solar resumes charge at -10 °C (LiPo limit noted).",
        "Perch clip holds Ø25 mm branch through 60 km/h wind gust equivalent (shake test).",
        "False-positive smoke rate <1/week/unit in dust/inversion conditions (AI filter).",
    ], width=118)
    s.h(760, 118, "ROLE ASSIGNMENT PROTOCOL (SKETCH)")
    s.bullets(760, 136, [
        "All Miters broadcast hello + battery + capability every N hours.",
        "Anchor/Brick AI computes coverage gaps → assigns roles via signed cmd.",
        "Sensor-bees concentrate near fuel breaks/ridgelines in fire season.",
        "Charger-bees migrate to Anchor docks when battery <20%.",
        "Roles are soft state — units self-organize if the coordinator is gone.",
    ], width=110)
    s.h(760, 400, "OPEN ITEMS")
    s.bullets(760, 418, [
        "Carrier PCB layout — needs KiCad pass (this sheet = spec).",
        "ENS160 vs SGP30 selection on real smoke/dust test data.",
        "LoRa region config: 915 MHz ISM CA — duty-cycle limits apply.",
        "mesh-net envelope port to ESP32 (Rust-embedded or C shim).",
    ], width=110, color=RED)
    out.append(s.svg(4, 4))
    return out


# ============================================================ E TOTEM =====
def totem_sheets():
    out = []

    # ---- 101 GA ----
    s = Sheet("AF-E-101", "GENERAL ARRANGEMENT — COMMUNITY BOARD", "POLE-MOUNTED PUBLIC E-INK NOTICEBOARD + MESH NODE", "E · TOTEM")
    s.h(M + 16, 118, "WHAT THIS NODE IS")
    s.bullets(M + 16, 136, [
        "The town square in a box: a public E-Ink board that is ALSO a mesh node — it doesn't just display, it routes.",
        "Emergency alerts, community notices, local information, agency bulletins — readable at arm's length in sunlight.",
        "Zero power to display: E-Ink holds an image indefinitely on stored charge — the board works in a blackout.",
        "The community noticeboard is familiar, trusted rural technology. Nobody fears a sign.",
    ], width=118)
    # drawing
    tx, ty = 790, 150
    s.t(tx, ty - 14, "ENVELOPE — POLE-MOUNTED BOARD", 11, weight="bold", color=ACC)
    s.ln(tx + 160, ty + 60, tx + 160, ty + 320, DIM, 4)
    s.rect(tx + 60, ty + 40, 200, 160, fill=PANEL, stroke=LINE, sw=1.6, r=10)
    s.rect(tx + 75, ty + 55, 170, 110, fill="#0b3a66", stroke=ACC, sw=1.2, r=4)
    s.t(tx + 160, ty + 112, "E-INKE", 12, "middle", ACC, "bold")
    s.t(tx + 160, ty + 130, "7–13in class", 8.5, "middle", DIM)
    s.t(tx + 160, ty + 330, "pole / post mount", 8.5, "middle", DIM)
    s.dims_h(tx + 60, tx + 260, ty + 355, "~320")
    s.dims_v(tx + 290, ty + 40, ty + 200, "~220")
    s.t(tx + 160, ty + 385, "enclosure ~320×220×100 mm · pole 3 m class · total ~8 kg", 9, "middle", DIM)
    # content pipeline
    s.h(M + 16, 330, "CONTENT PIPELINE")
    s.box(M + 16, 346, 180, 50, "AGENCY / COMMUNITY", "CMS publishes alerts", fill="#123f6b")
    s.arrow(M + 196, 371, M + 220, 371, DIM)
    s.box(M + 220, 346, 180, 50, "MESH NETWORK", "signed envelopes · store-forward", fill="#123f6b")
    s.arrow(M + 400, 371, M + 424, 371, DIM)
    s.box(M + 424, 346, 180, 50, "TOTEM NODE", "LoRa RX → render → E-Ink", fill="#123f6b")
    s.arrow(M + 604, 371, M + 628, 371, DIM)
    s.box(M + 628, 346, 180, 50, "PUBLIC DISPLAY", "sunlight-readable · zero idle power", fill="#123f6b")
    s.h(M + 16, 460, "USE CASES")
    s.table(M + 16, 474, [180, 480], ["Use", "Detail"], [
        ["Emergency alerts", "wildfire evacuation, Amber-style, weather — pushed mesh-wide in minutes"],
        ["Community notices", "council, school, clinic, events — the digital general-store board"],
        ["Agency bulletins", "province, RCMP, health unit — one board, many authors, signed content"],
        ["Local info", "road conditions, water advisories, harvest deadlines, powwow/community events"],
        ["Mesh status", "optional: node shows mesh health — coverage is visible infrastructure"],
    ], rh=26)
    s.h(M + 16, 680, "WHY IT'S UNIQUE")
    s.bullets(M + 16, 698, [
        "Only public noticeboard that IS a network node — it routes, repeats, and stores, not just displays.",
        "Signed content: every notice carries publisher identity — no anonymous flyers, no defacement.",
        "Offline by design: works when grid AND cell network are both down (the blackout case).",
        "EN/FR content pipeline; community controls what appears — sovereignty in public space.",
    ], width=118)
    out.append(s.svg(1, 3))

    # ---- 102 mechanical ----
    s = Sheet("AF-E-102", "MECHANICAL & INSTALLATION", "ENCLOSURE, POLE MOUNT, DISPLAY WINDOW", "E · TOTEM")
    s.h(M + 16, 118, "ENCLOSURE SPEC")
    s.table(M + 16, 132, [180, 150, 180, 140], ["Parameter", "Value", "Parameter", "Value"], [
        ["Electronics box", "~320×220×100 mm", "Rating target", "IP66 (rain, dust, hose-down)"],
        ["Material", "polycarbonate or fiberglass box", "UV", "UV-stable resin, no PVC"],
        ["Display", "7.5–13.3in e-Paper HAT class", "Window", "optically clear PET/AC, gasketed"],
        ["Sun hood", "integral visor over window", "Readability", "arm's length, direct sun"],
        ["Pole", "50–75 mm class, 3 m", "Mount", "two U-bolts + backing plate"],
        ["Lock", "quarter-turn captive fasteners", "Tamper", "tool-required internals"],
    ], rh=24)
    s.h(M + 16, 340, "INSTALLATION")
    s.bullets(M + 16, 358, [
        "Two-person install, ~30 min: mount pole (post-hole or U-bolt to existing pole), hang box, connect solar leads.",
        "Orientation: display faces road/foot-traffic; antenna port top; solar panel south-facing tilt.",
        "No concrete required — expandable pole anchor or existing utility pole U-bolt.",
        "Service: front latch access to SD card + battery; field-swappable in <10 min.",
    ], width=118)
    s.h(M + 16, 520, "WEATHER & ENVIRONMENT")
    s.bullets(M + 16, 538, [
        "-45..+70 °C: polycarbonate box + wide-temp components; E-Ink loves cold.",
        "Ice loading: sloped top surfaces shed ice/snow; display window has drip edge.",
        "Condensation: breather vent or desiccant pack; check annually.",
        "Vandalism: no sharp edges, tamper-evident seal; content is signed so defacement is detectable.",
    ], width=118)
    s.h(700, 118, "BOX CANDIDATES (ORDERABLE)")
    s.table(700, 132, [300, 330], ["Option", "Notes"], [
        ["Bud Industries NBF-style polycarbonate ~320×220×100", "off-the-shelf IP66, modify front for window"],
        ["Custom fiberglass (local fabricator)", "better cold/UV, longer lead — rev-B"],
        ["Pelican-class case + custom mount", "heaviest, most durable — rev-C"],
    ], rh=30)
    s.h(700, 340, "DISPLAY WINDOW DETAIL")
    s.bullets(700, 358, [
        "Window: 3 mm optically clear PET film or AC sheet, gasketed to box lip.",
        "E-Ink sits 2–3 mm behind window (anti-static gap).",
        "Sun hood: 40 mm visor reduces washout + sheds water/ice.",
        "Optional: anti-graffiti laminate film (sacrificial, field-replaceable).",
    ], width=105)
    s.h(700, 560, "POLE MOUNT DETAIL")
    s.bullets(700, 578, [
        "Two stainless U-bolts through box rear flange, backing plate spreads load.",
        "Box hangs on rear hinge — swings down for service access.",
        "Cable entry: bottom grommet, drip loop; solar cable armored or conduit sleeve.",
        "Wind: box ~8 kg on 3 m pole — check pole class for 150 km/h gust site.",
    ], width=105)
    out.append(s.svg(2, 3))

    # ---- 103 electrical/software ----
    s = Sheet("AF-E-103", "ELECTRICAL, CONTENT & SOFTWARE", "BOM + POWER + CMS PIPELINE", "E · TOTEM")
    s.h(M + 16, 118, "BILL OF MATERIALS (PER TOTEM)")
    s.table(M + 16, 132, [24, 290, 170, 110, 80],
            ["#", "Part", "Supplier class", "Approx CAD", "Qty"], [
        ["1", "CM5 4GB + IO Board (same as L1 — fleet common)", "PiShop / Canada Computers", "$90–130", "1"],
        ["2", "13.3in or 7.5in e-Paper HAT (SPI)", "Waveshare / DFRobot", "$100–200", "1"],
        ["3", "SX1262 LoRa breakout 915 MHz", "DFRobot / AliExpress", "$15–25", "1"],
        ["4", "SIM7600 LTE HAT (optional backhaul)", "DFRobot / Waveshare", "$60–90", "0–1"],
        ["5", "20–30 W poly solar panel + MPPT 20 A", "Amazon.ca / Renogy CA", "$120–200", "1"],
        ["6", "12.8 V 20 Ah LiFePO4 battery", "Amazon.ca / electronics supplier", "$180–260", "1"],
        ["7", "IP66 polycarbonate box ~320×220×100", "Bud Industries / Amazon.ca", "$80–140", "1"],
        ["8", "Pole + U-bolts + window film + gasket", "hardware supplier", "$60–100", "1"],
    ], rh=26)
    y0 = 480
    s.h(M + 16, y0, "POWER SYSTEM")
    s.box(M + 16, y0 + 14, 150, 46, "20–30 W PANEL", "south tilt", fill="#123f6b")
    s.arrow(M + 194, y0 + 37, M + 218, y0 + 37, DIM)
    s.box(M + 218, y0 + 14, 150, 46, "MPPT 20 A", "CV/CC LiFePO4", fill="#123f6b")
    s.arrow(M + 372, y0 + 37, M + 396, y0 + 37, DIM)
    s.box(M + 396, y0 + 14, 150, 46, "LiFePO4 20 Ah", "≈256 Wh", fill="#123f6b")
    s.arrow(M + 550, y0 + 37, M + 574, y0 + 37, DIM)
    s.box(M + 574, y0 + 14, 150, 46, "5 V BMS → CM5", "always-on rail", fill="#123f6b")
    s.t(M + 16, y0 + 90, "Autonomy: ~256 Wh ÷ ~2–4 W avg ≈ 3–5 days no-sun; winter derate → oversized panel is the plan.", 9.5, color=DIM)
    # content pipeline detail
    gx = 790
    s.h(gx, y0, "CONTENT PIPELINE — SIGNED PUBLICATIONS")
    s.bullets(gx, y0 + 18, [
        "Publishers sign content (Ed25519) — community/agency keys.",
        "Mesh floods signed notice envelopes; node verifies before render.",
        "Display rotation: alerts > notices > info; expiry timestamps auto-clear.",
        "Rate-limit + dedup: one publisher can't spam the board.",
        "Offline queue: notices arrive whenever a path opens — order preserved.",
        "Moderation: community admin key can pin/hide categories (not delete history).",
    ], width=95)
    s.h(M + 16, y0 + 200, "SOFTWARE")
    s.bullets(M + 16, y0 + 218, [
        "Same arcticchain_agent.py base; Totem adds: content renderer → framebuffer → e-Paper driver.",
        "CMS side: simple signed-publish tool (repo: poc/ or later arcticchain-os).",
        "Node roles: display + repeater + optional gateway (LTE/Wi-Fi backhaul when present).",
    ], width=118)
    s.h(790, y0 + 200, "FIELD ACCEPTANCE")
    s.bullets(790, y0 + 218, [
        "Notice pushed from 10 km away renders on Totem within 60 s (mesh path).",
        "Board legible in full sun at 3 m; zero power draw between updates.",
        "Survives overnight -30 °C; resumes display + comms at dawn.",
        "Tamper test: locked box, signed content undetectable-defacement alarm.",
    ], width=95)
    out.append(s.svg(3, 3))
    return out


# ============================================================ A ANCHOR =====
def anchor_sheets():
    out = []

    # ---- 101 GA ----
    s = Sheet("AF-A-101", "GENERAL ARRANGEMENT — CHARGING STATION", "RENEWABLE STATION: SWARM DOCK + RELAY + BACKHAUL", "A · ANCHOR")
    s.h(M + 16, 118, "WHAT THIS NODE IS")
    s.bullets(M + 16, 136, [
        "The fixed, renewable-powered infrastructure the swarm needs — a station where Miters top off and the mesh gets strong.",
        "Sited at the community hub: band office, fire lookout, well site, school — wherever people already gather.",
        "Three jobs in one box: swarm charging dock, long-range LoRa relay, optional backhaul gateway (LTE/Wi-Fi/sat).",
        "The only node whose job is charging OTHER nodes — it turns the swarm from visitors into a persistent network.",
    ], width=118)
    # drawing
    ax, ay = 720, 150
    s.t(ax, ay - 14, "ENVELOPE — STATION", 11, weight="bold", color=ACC)
    s.rect(ax, ay, 320, 240, fill=PANEL, stroke=LINE, sw=1.6, r=10)
    s.rect(ax + 30, ay + 40, 260, 140, fill="#0b3a66", stroke=DIM, sw=1.2, r=6)
    s.t(ax + 160, ay + 105, "MAIN BOX", 11, "middle", LINE, "bold")
    s.t(ax + 160, ay + 125, "compute + radios + charge ctrl", 8.5, "middle", DIM)
    # solar panel
    s.rect(ax + 60, ay + 200, 200, 14, fill="#123f6b", stroke=ACC, sw=1.2)
    s.t(ax + 160, ay + 228, "20–60 W array (ground/pole mount)", 8.5, "middle", DIM)
    # dock contacts
    for i in range(4):
        s.circ(ax + 60 + i * 66, ay + 30, 6, fill=ACC)
    s.t(ax + 160, ay + 18, "pogo dock contacts ×4 (top)", 8.5, "middle", ACC)
    s.dims_h(ax, ax + 320, ay + 270, "~350")
    s.dims_v(ax - 24, ay, ay + 240, "~250")
    s.t(ax + 160, ay + 300, "box ~350×250×400 mm incl. battery bay · + separate array", 9, "middle", DIM)
    # roles
    s.h(M + 16, 450, "WHAT THE ANCHOR DOES")
    s.table(M + 16, 464, [190, 490], ["Function", "Detail"], [
        ["Swarm dock", "4 pogo-pin charge positions on top — Miters land, charge, rebroadcast"],
        ["Long-range relay", "SX1262 at height + bigger antenna — extends mesh over ridges/valleys"],
        ["Gateway", "LTE/Wi-Fi/sat backhaul when available — the mesh's door to the world"],
        ["Anchor sensor", "own temp/RH/VOC + wind — the fixed reference point for swarm data"],
        ["Status beacon", "E-Ink or LED shows mesh health — infrastructure you can read"],
    ], rh=26)
    s.h(M + 16, 680, "WHY ANCHORS MATTER")
    s.bullets(M + 16, 698, [
        "Swarm energy: docked Miters top off → perpetual patrol without battery swaps.",
        "Range: elevated relay doubles effective mesh diameter vs. ground nodes.",
        "Trust: the station is the visible, maintainable heart of the local mesh.",
        "Revenue anchor: gateways are what ISPs/communities pay for — the swarm rides free.",
    ], width=118)
    out.append(s.svg(1, 3))

    # ---- 102 mechanical ----
    s = Sheet("AF-A-102", "MECHANICAL & POWER SYSTEM", "ENCLOSURE, ARRAY, BATTERY, DOCK", "A · ANCHOR")
    s.h(M + 16, 118, "ENCLOSURE & PLACEMENT")
    s.table(M + 16, 132, [180, 150, 180, 140], ["Parameter", "Value", "Parameter", "Value"], [
        ["Main box", "~350×250×400 mm", "Rating", "IP65+ (pole/ground mount)"],
        ["Material", "polycarbonate/fiberglass", "Lock", "quarter-turn, tool-required"],
        ["Battery bay", "separate vented compartment", "Service", "front/rear latch access"],
        ["Solar array", "20–60 W, ground frame or pole", "Tilt", "site latitude-adjusted"],
        ["Mount", "concrete pad, pole, or trailer", "Wind", "150 km/h rated frame"],
    ], rh=24)
    s.h(M + 16, 340, "POWER SYSTEM — SIZED FOR WINTER")
    s.box(M + 16, 356, 170, 46, "20–60 W ARRAY", "oversized for Dec sun", fill="#123f6b")
    s.arrow(M + 186, 379, M + 210, 379, DIM)
    s.box(M + 210, 356, 170, 46, "MPPT 20–30 A", "LiFePO4 profile", fill="#123f6b")
    s.arrow(M + 380, 379, M + 404, 379, DIM)
    s.box(M + 404, 356, 170, 46, "LiFePO4 50–100 Ah", "12.8 V ≈ 640–1280 Wh", fill="#123f6b")
    s.arrow(M + 574, 379, M + 598, 379, DIM)
    s.box(M + 598, 356, 170, 46, "BMS → 5 V/12 V rails", "station + dock power", fill="#123f6b")
    s.t(M + 16, 430, "Autonomy target: 30–90 days no-sun (smaller load than it looks — LoRa is µW-class, compute sleeps).", 9.5, color=DIM)
    s.h(M + 16, 480, "SWARM DOCK — ELECTRICAL")
    s.bullets(M + 16, 498, [
        "4 pogo-pin positions on top lid: VBUS 5 V + GND + charge-detect line.",
        "Each dock: ~5 V / 500 mA charge path through CN3791-class controller per position.",
        "Mite bottom has 2 pogo pads + alignment notch — lands blind, charges, rebroadcasts.",
        "Dock schedule: rotating charge slots so no unit starves; mesh reports dock occupancy.",
    ], width=118)
    s.h(M + 16, 680, "ENCLOSURE LAYOUT")
    s.bullets(M + 16, 698, [
        "Top: dock contacts + antenna bulkheads (LoRa whip, LTE whip, GPS patch).",
        "Mid: compute bay (CM5-class) + radio bay + charge controllers.",
        "Bottom: sealed battery compartment (LiFePO4, vented, BMS external-access).",
        "Side: cable entry glands, status LED bar, optional small E-Ink status window.",
    ], width=115)
    # site drawing
    gx = 700
    s.h(gx, 118, "SITE EXAMPLES")
    s.bullets(gx, 136, [
        "Fire lookout tower base — elevated relay + swarm dock for patrol units.",
        "Band office / community hall — gateway + public Totem co-located.",
        "Well site / pump house — telemetry + mesh node where workers already go.",
        "School — charging dock doubles as device-charging station for students.",
        "Trailhead / boat launch — seasonal swarm staging point.",
    ], width=105)
    s.h(gx, 430, "SAFETY & CODE NOTES")
    s.bullets(gx, 448, [
        "LiFePO4: safer chemistry than Li-ion; BMS mandatory; vent battery compartment.",
        "Electrical: licensed electrician for permanent install; GFCI on AC backup input.",
        "Lightning: DC-side surge protection on solar + antenna ports (field replaceable).",
        "Wildlife: no food/scent; box is electronics-only — still use community-standard mounting.",
    ], width=105)
    out.append(s.svg(2, 3))

    # ---- 103 electrical ----
    s = Sheet("AF-A-103", "ELECTRICAL — BOM, BACKHAUL & DOCK", "PARTS + CONNECTIVITY OPTIONS", "A · ANCHOR")
    s.h(M + 16, 118, "BILL OF MATERIALS (PER STATION)")
    s.table(M + 16, 132, [24, 290, 160, 100, 80],
            ["#", "Part", "Supplier class", "Approx CAD", "Qty"], [
        ["1", "CM5 4GB + IO Board (gateway compute)", "PiShop / Canada Computers", "$90–130", "1"],
        ["2", "SX1262 LoRa breakout ×2 (node band + backbone)", "DFRobot / AliExpress", "$30–50", "2"],
        ["3", "LTE HAT (SIM7600) OR Wi-Fi bridge OR sat terminal", "DFRobot / Starlink / Iridium", "$60–600", "0–1"],
        ["4", "20–60 W poly panel + MPPT 20–30 A", "Renogy / Amazon.ca", "$150–400", "1"],
        ["5", "LiFePO4 12.8 V 50–100 Ah + BMS", "Amazon.ca / supplier", "$400–900", "1"],
        ["6", "IP65 box ~350×250×400 + pole/frame", "Bud Industries / fabricator", "$200–400", "1"],
        ["7", "Pogo dock ×4 + charge controllers", "custom/CN3791", "$40–80", "4"],
        ["8", "Antennas: LoRa whip ×2, LTE whip, GPS patch", "electronics supplier", "$60–120", "1 set"],
    ], rh=26)
    y0 = 420
    s.h(M + 16, y0, "BACKHAUL OPTIONS (HIERARCHY)")
    s.table(M + 16, y0 + 14, [170, 280, 320], ["Option", "Cost", "When"], [
        ["Mesh only", "$0", "no coverage — still fully functional as relay/dock"],
        ["LTE (SIM7600)", "$60–90", "any cell signal — most rural sites"],
        ["Starlink Mini/Residential", "$300–600 + $/mo", "true dead zones — business case required"],
        ["Iridium Certus/L-band", "OEM module $500+", "polar/north — matches future own-sat path"],
        ["ArcticChain sats (H MERIDIAN)", "future", "the mesh IS the ground segment"],
    ], rh=28)
    gx = 860
    s.h(gx, y0, "DOCK PROTOCOL")
    s.bullets(gx, y0 + 18, [
        "Mite lands on pogo pads → charge-detect line pulled low.",
        "Dock controller ID broadcasts slot assignment over LoRa.",
        "Charge until >80% or dock timeout; then release + 'charged' beacon.",
        "Rotating priority: lowest-battery docked unit gets next slot.",
        "All dock events signed + logged — swarm energy is mesh data.",
    ], width=105)
    s.h(M + 16, y0 + 220, "SYSTEM BLOCK")
    s.box(M + 16, y0 + 236, 160, 44, "ARRAY+MPPT", "solar in", fill="#123f6b")
    s.arrow(M + 176, y0 + 258, M + 200, y0 + 258, DIM)
    s.box(M + 200, y0 + 236, 160, 44, "LiFePO4+BMS", "energy store", fill="#123f6b")
    s.box(M + 380, y0 + 236, 160, 44, "CM5 GATEWAY", "agent + router", fill="#123f6b")
    s.box(M + 560, y0 + 236, 160, 44, "SX1262 ×2", "mesh + backbone", fill="#123f6b")
    s.box(M + 740, y0 + 236, 160, 44, "BACKHAUL", "LTE/Wi-Fi/sat", fill="#123f6b")
    s.t(M + 16, y0 + 310, "Dock controllers hang off I2C/GPIO; antenna ports on box top; all rails fused.", 9.5, color=DIM)
    s.h(M + 16, y0 + 340, "FIELD ACCEPTANCE")
    s.bullets(M + 16, y0 + 358, [
        "4 Miters dock, charge, undock on schedule — 72 h unattended soak test.",
        "Mesh throughput: ≥10 signed msgs/min relayed through Anchor at 5 km spacing.",
        "Backhaul failover: LTE drops → mesh store-forward continues → auto-reconnect.",
        "Winter test: -30 °C ambient, panel snow-covered 3 days → station still docks+relays.",
    ], width=118)
    out.append(s.svg(3, 3))
    return out


# ============================================================ P PHONE =====
def phone_sheets():
    out = []

    s = Sheet("AF-P-101", "CONCEPT — RURAL COMMS DEVICE", "MESH-NATIVE PHONE FOR RURAL & REMOTE CANADA", "P · ARCTICPHONE",
              rev="0", status="CONCEPT — ARCHITECTURE NOT FROZEN")
    s.h(M + 16, 118, "WHAT CHANGED VS MONOLITH")
    s.bullets(M + 16, 136, [
        "Monolith was a flagship research device — titanium spine, optical docks. Wrong phone for a rancher in a -35 °C truck cab.",
        "ArcticPhone is designed rural-first: mesh-native, satellite SOS-ready, offline-first, repairable, community-owned.",
        "Every ArcticPhone IS a node — calls, texts, data ride the community mesh when there's no cell signal.",
        "The phone respects that rural life is often offline life — it works when everything else has failed.",
    ], width=118)
    # envelope
    fx, fy = 720, 150
    s.t(fx, fy - 14, "ENVELOPE TARGET", 11, weight="bold", color=ACC)
    s.rect(fx + 60, fy, 200, 380, fill=PANEL, stroke=LINE, sw=1.6, r=18)
    s.rect(fx + 75, fy + 30, 170, 300, fill="#0b3a66", stroke=ACC, sw=1.2, r=8)
    s.t(fx + 160, fy + 180, "DISPLAY", 10, "middle", ACC)
    s.t(fx + 160, fy + 198, " glove-friendly UI", 8, "middle", DIM)
    s.t(fx + 160, fy + 420, "~145×72×14 mm · ~220 g", 9, "middle", DIM)
    s.t(fx + 160, fy + 440, "ruggedized · replaceable battery", 8.5, "middle", DIM)
    # architecture options
    s.h(M + 16, 350, "ARCHITECTURE OPTIONS (DECISION REQUIRED)")
    s.table(M + 16, 364, [80, 300, 280, 240], ["Opt", "Approach", "Pros", "Cons"], [
        ["A", "Rugged Android handset + ArcticChain mesh HAT (SX1262+MCU)", "fast to market, app ecosystem, camera", "Android bloat, certification effort"],
        ["B", "Custom Linux + mesh SoC (integrated SX1262)", "clean, sovereign, repairable, smallest", "OS work, smaller ecosystem"],
        ["C", "Hybrid: Linux core + Android-compatible layer", "best of both, more complex", "longest dev time"],
    ], rh=44)
    s.h(M + 16, 590, "CAPABILITY SET")
    s.table(M + 16, 604, [200, 480], ["Capability", "Implementation"], [
        ["Mesh node", "SX1262 LoRa 915 + signed envelopes — every phone extends the network"],
        ["Satellite SOS", "L-band messenger module (inReach-class now; own sats later) — SOS where nothing works"],
        ["Offline apps", "maps, manuals, forms, messaging EN/FR — useful with zero connectivity"],
        ["Cellular", "LTE Cat-1/4 when towers exist — off-the-shelf modem path proven on L1"],
        ["Power", "replaceable battery + USB-C PD + solar trickle option"],
        ["Rugged", "IP68, -30 °C operating, glove UI, MIL-STD-810H drop test target"],
    ], rh=28)
    s.h(M + 16, 830, "OPEN QUESTIONS")
    s.bullets(M + 16, 848, [
        "Architecture A/B/C decision — recommend A for speed, B for sovereignty.",
        "Satellite SOS: buy module now (inReach-class) vs wait for own constellation.",
        "Display: transflective sunlight-readable vs standard LCD + high-nit.",
        "Regulatory: phone certification (ISED) is a real cost — budget it.",
    ], width=125, color=RED)
    out.append(s.svg(1, 2))

    s = Sheet("AF-P-102", "CONCEPT — SPECIFICATION SKETCH", "TARGET SPEC + BOM CATEGORIES + ROADMAP", "P · ARCTICPHONE",
              rev="0", status="CONCEPT — ARCHITECTURE NOT FROZEN")
    s.h(M + 16, 118, "TARGET SPECIFICATION")
    s.table(M + 16, 132, [180, 160, 180, 160], ["Parameter", "Target", "Parameter", "Target"], [
        ["Envelope", "~145×72×14 mm", "Mass", "~220 g"],
        ["Display", "5–6in transflective", "SoC", "quad-core, LTE, GNSS"],
        ["Mesh radio", "SX1262 915 MHz + MCU", "Sat SOS", "L-band module (rev-A)"],
        ["Battery", "replaceable ~4000 mAh", "Charging", "USB-C PD + solar"],
        ["OS", "Android Go OR custom Linux", "UI", "glove-friendly, EN/FR"],
        ["Rating", "IP68 · -30..+55 °C", "Drop", "MIL-STD-810H 1.5 m"],
        ["Repair", "standard screws, open back", "Ownership", "community-owned network"],
    ], rh=26)
    s.h(M + 16, 380, "BOM CATEGORIES (NOT FIXED — ARCHITECTURE PENDING)")
    s.table(M + 16, 394, [200, 480], ["Category", "Options / notes"], [
        ["Compute+display", "rugged Android module (option A) OR custom board (option B)"],
        ["Mesh module", "SX1262 + nRF52/ESP32 coprocessor — same envelope as fleet"],
        ["Sat messenger", "Garmin inReach module class, OR Iridium Certus OEM, OR future own-sat"],
        ["Cellular", "LTE Cat-4 modem + SIM slot — proven path from L1 HAT"],
        ["Power", "4000 mAh LiFePO4 pouch, USB-C PD trigger, solar pad option"],
        ["Enclosure", "PC+TPU bumpers, gasketed ports, captive screws"],
    ], rh=30)
    s.h(M + 16, 640, "ROADMAP TO FIRST UNIT")
    s.bullets(M + 16, 658, [
        "Phase 0 (now): architecture decision + industrial design concept — this sheet.",
        "Phase 1: prototype on dev-kit + mesh HAT — prove mesh+SOS on existing hardware.",
        "Phase 2: custom enclosure + integration — 3D print → machined → mold decision.",
        "Phase 3: certification (ISED/RF) + pilot batch — 50–100 units for founding communities.",
        "Phase 4: volume — repairable design pays off at scale (modules, not glue).",
    ], width=118)
    s.h(760, 118, "UNIQUE vs EVERY OTHER PHONE")
    s.bullets(760, 136, [
        "The only phone that is a FIRST-CLASS MESH CITIZEN — your phone extends the network just by existing.",
        "Satellite SOS as a core feature, not an accessory — designed for the places towers aren't.",
        "Offline-first: apps, maps, forms, messaging all useful with zero bars.",
        "Community-owned: the network your phone joins belongs to your community, not a corporation.",
        "Repairable by design — a local tech fixes it with hand tools.",
    ], width=110)
    s.h(760, 420, "RELATIONSHIP TO OTHER NODES")
    s.bullets(760, 438, [
        "Phone = personal node; L1 = field/shared node; Totem = public node; Mite = environmental; Anchor = infrastructure.",
        "All speak the same signed mesh — a call can route phone→phone→brick→satellite.",
        "Phone is the highest-volume node — its mesh radio is the network's user terminal.",
    ], width=110)
    out.append(s.svg(2, 2))
    return out


# ============================================================ D SEED ======
def seed_sheets():
    out = []
    s = Sheet("AF-D-101", "R&D BRIEF — DEGRADABLE MOTE", "SEED-DROP SEASONAL SENSOR — RESEARCH PROGRAM", "D · SEED",
              rev="0", status="RESEARCH — NOT A PRODUCT")
    s.h(M + 16, 118, "THE IDEA")
    s.bullets(M + 16, 136, [
        "A ~20 mm mote of printed electronics on biodegradable substrate — seed-dropped over a fuel break or burn scar.",
        "It sprouts into a temporary sensor skin for fire season, reports through cluster heads, and dissolves.",
        "Zero e-waste, no retrieval, no grid to build — sensing that ENDS by design.",
        "This is a materials/transient-electronics program — fundable R&D, not a product. Every earlier rung must succeed first.",
    ], width=118)
    # right column — why + honest status
    s.h(760, 118, "WHY THIS MATTERS")
    s.bullets(760, 136, [
        "Fire season is seasonal — permanent sensors waste 11 months of life.",
        "Degradable motes match the threat's rhythm: deploy for the season, vanish after.",
        "Billions-scale is materials R&D, not drone fleet — the mesh math supports it (duty cycle + clustering).",
        "Precedent: DARPA/NSF computational-dust programs prove the research is real.",
    ], width=110)
    s.h(760, 250, "HONEST STATUS")
    s.bullets(760, 268, [
        "TRL ~2 — concept + literature. No ArcticChain mote exists yet.",
        "This sheet is a research brief, not a buildable BOM — deliberately.",
        "The swarm architecture (roles, perch, mesh) is the same — only the node shrinks.",
        "Do NOT promise motes to funders until Gate 2 demo exists.",
    ], width=110, color=RED)
    # form-factor drawing (right column, below text)
    dx, dy = 830, 430
    s.t(dx, dy - 14, "FORM FACTOR TARGET", 11, weight="bold", color=ACC)
    for i in range(14):
        import math, random
        random.seed(i * 7 + 3)
        cx, cy = dx + 110 + random.uniform(-95, 95), dy + 110 + random.uniform(-85, 85)
        s.circ(cx, cy, random.uniform(2.5, 4.5), fill=ACC)
    s.t(dx + 110, dy + 250, "seed cloud — thousands dropped, dissolves <12 mo", 8.5, "middle", DIM)
    s.dims_h(dx - 10, dx + 230, dy + 275, "drop zone ~200 m")
    s.t(dx + 110, dy + 305, "~20×20×5 mm mote · <1 g · printed electronics", 8.5, "middle", DIM)
    # targets table
    s.h(M + 16, 280, "RESEARCH TARGETS")
    s.table(M + 16, 294, [200, 480], ["Target", "Goal"], [
        ["Mass", "<1 g per mote (cluster head <5 g)"],
        ["Cost", "<$1/unit at volume (printed, not assembled)"],
        ["Life", "one fire season (~6 months) then degrade"],
        ["Degradation", "complete in <12 months, non-toxic residue"],
        ["Comms", "duty-cycled LoRa or backscatter — rare TX, local clustering"],
        ["Power", "printed battery + PV/TEG harvest — µW average"],
        ["Sensing", "temp/RH/VOC minimum; optical smoke later"],
    ], rh=28)
    s.h(M + 16, 545, "MATERIALS PATHWAY")
    s.table(M + 16, 559, [200, 480], ["Component", "Candidate materials / approach"], [
        ["Substrate", "cellulose paper, silk fibroin, or transient polymer"],
        ["Electronics", "printed Zn/MnO₂ battery, printed sensors, organic TFT"],
        ["Energy", "printed PV cell, thermoelectric, or RF harvest"],
        ["Comms", "backscatter (no TX power) or ultra-low-power LoRa wake-up"],
        ["Adhesion/deploy", "seed pod form factor — germinates sensor on moisture"],
    ], rh=28)
    s.h(M + 16, 770, "ROADMAP GATES")
    s.bullets(M + 16, 788, [
        "Gate 1: university transient-electronics partner identified (SR&ED eligible).",
        "Gate 2: lab demo — printed mote senses temp + reports 10 m through cluster head.",
        "Gate 3: field trial — 100 motes over 1 ha, one season, recoverable data.",
        "Gate 4: degradable variant — residue analysis confirms <12 month breakdown.",
        "Gate 5: scale — seed-drop deployment tied to Anchor/Brick infrastructure.",
    ], width=118)
    out.append(s.svg(1, 1))
    return out


# ============================================================ H MERIDIAN ====
def meridian_sheets():
    out = []
    s = Sheet("AF-H-101", "MISSION CONCEPT — SATELLITE PAYLOAD", "STORE-AND-FORWARD CONSTELLATION — THE MESH IS THE GROUND SEGMENT", "H · MERIDIAN",
              rev="0", status="VISION — EARNED, NOT SKIPPED")
    s.h(M + 16, 118, "THE INSIGHT")
    s.bullets(M + 16, 136, [
        "When the mesh needs backhaul beyond terrestrial reach, our own store-and-forward payload flies.",
        "Nobody else launching smallsats has a deployed rural ground network waiting — the mesh IS the satellite's user-terminal layer.",
        "A text message or sensor packet doesn't need Starlink bandwidth — it needs COVERAGE. A handful of CubeSats→smallsats can blanket Canada.",
        "Higher orbit is correct for THIS layer: bigger footprint per satellite = fewer needed. (Bandwidth wants LEO — that's a different game.)",
    ], width=118)
    # orbit diagram
    ox, oy = 720, 170
    s.t(ox, oy - 20, "ORBIT CONCEPT", 11, weight="bold", color=ACC)
    s.circ(ox + 200, oy + 140, 120, fill="none", stroke=DIM, sw=1.5)
    s.circ(ox + 200, oy + 140, 60, fill="#123f6b", stroke=LINE, sw=1)
    s.t(ox + 200, oy + 144, "EARTH", 10, "middle", LINE)
    s.path(f"M {ox} {oy + 140} A 200 70 0 0 1 {ox + 400} {oy + 140}", color=ACC, w=1.5)
    s.t(ox + 200, oy + 60, "polar ~600–1000 km", 9, "middle", ACC)
    s.t(ox + 200, oy + 330, "inclination ~99° — Arctic coverage", 9, "middle", DIM)
    # payload block
    s.h(M + 16, 400, "PAYLOAD — DERIVED FROM THE MESH")
    s.table(M + 16, 414, [200, 480], ["Element", "Implementation"], [
        ["Radio", "UHF/S-band store-and-forward transceiver — LoRa-derived waveform or CC1101-class"],
        ["Envelope", "same signed mesh-net format — satellite is just another hop"],
        ["Store", "onboard flash — holds envelopes until ground station passes"],
        ["Bus", "1U/3U CubeSat (GOMspace/EnduroSat/CubeSat Shop) or smallsat"],
        ["Ground segment", "the deployed mesh + community gateways = user terminals (already built)"],
    ], rh=30)
    s.h(M + 16, 640, "MISSION PROFILE")
    s.bullets(M + 16, 658, [
        "Coverage: polar LEO constellation blankets Canada incl. North — messaging/sensor tier, not broadband.",
        "Latency: store-and-forward hours, not seconds — right-sized for alerts, notices, telemetry.",
        "Capacity: each sat serves hundreds of nodes per pass — plenty for text/sensor traffic.",
        "Pathfinder: 2–6 sats prove the constellation, then scale to regional coverage.",
    ], width=118)
    s.h(760, 118, "ASCENT PATH")
    s.table(760, 132, [160, 300, 300], ["Stage", "Vehicle", "Cost class"], [
        ["Hosted payload", "existing Canadian sat (GHGSat/MDA/univ)", "$50–500k"],
        ["University CubeSat", "CSA CubeSat Initiative partner", "$50–500k"],
        ["Dedicated smallsat", "rideshare (ISRO/JAXA/Arianespace/RL NZ)", "$1–5M"],
        ["Pathfinder", "6–12 sats, own ground ops", "$10–30M"],
        ["Constellation", "regional Canada coverage", "earned by demand"],
    ], rh=30)
    s.h(760, 420, "FUNDING PATH")
    s.bullets(760, 438, [
        "CSA CubeSat Initiative — literally funds Canadian university smallsats.",
        "Provincial/territorial + Indigenous services contracts — northern connectivity mandate.",
        "IDEaS/defence dual-use — CAF buys commercial satcom; Canadian alternative is attractive.",
        "Strategic: the constellation is demand-side anchor for domestic launch (the summit).",
    ], width=110)
    s.h(M + 16, 860, "HONEST STATUS")
    s.bullets(M + 16, 878, [
        "Vision stage — no satellite exists. The mesh must prove itself first (L1→swarm→revenue).",
        "This sheet is the mission concept, not a spacecraft design — payload inherits mesh crypto/routing.",
        "Every earlier rung funds and justifies this one — the trailhead is the ground network.",
    ], width=125, color=RED)
    out.append(s.svg(1, 1))
    return out


# ============================================================ COVER =======
def cover_sheet():
    s = Sheet("AF-000", "FLEET OVERVIEW & DRAWING INDEX", "ARCTICCHAIN RURAL NODE FAMILY — COMPLETE PRINT SET", "COVER")
    s.h(M + 16, 118, "THE FLEET — ONE NETWORK, MANY SHAPES")
    s.table(M + 16, 132, [90, 140, 260, 200, 200, 120],
            ["Node", "Codename", "Role", "Envelope", "Power", "Status"], [
        ["L1", "Brick", "field node — mailbox+repeater+bulletin+SOS", "160×80×24 mm", "4×18650/solar", "CAD ready"],
        ["E", "Totem", "community board — public E-Ink + mesh node", "~320×220×80 + pole", "solar+LiFePO4", "spec"],
        ["S", "Mite", "swarm unit — perchable env sensor", "~90×90×35 mm", "solar+LiPo", "CAD scripted"],
        ["A", "Anchor", "charging station — dock+relay+backhaul", "~350×250×400 mm", "20–60 W+LiFePO4", "spec"],
        ["P", "ArcticPhone", "rural comms — mesh-native, sat SOS", "~145×72×14 mm", "replaceable+solar", "concept"],
        ["D", "Seed", "degradable mote — seasonal sensing", "~20×20×5 mm", "printed+harvest", "R&D"],
        ["H", "Meridian", "satellite payload — mesh IS ground segment", "1U/3U CubeSat", "solar array", "vision"],
    ], rh=40)
    s.h(M + 16, 520, "SHARED DESIGN DNA (EVERY NODE)")
    s.bullets(M + 16, 538, [
        "Climate: -45..+70 °C · IP65+ · UV-stable · LiFePO4-preferred · December-sized solar",
        "Power: solar-first · 30–90 day autonomy · works with zero grid",
        "Field: bear-country mounts · two-person install · hand-tool repair",
        "Sovereignty: community-owned mesh · data stays home · OCAP · EN/FR · privacy by design",
        "Appropriate tech: right-sized cost · repairable > sealed · open docs",
        "Offline dignity: works when everything else has failed — that IS the product",
    ], width=118)
    s.h(760, 520, "DRAWING INDEX")
    idx = [
        ("AF-000", "this sheet — fleet overview & index"),
        ("AF-L1-101…104", "L1 Brick — GA, mechanical, electrical, software/assembly"),
        ("AF-S-101…104", "S Mite — GA, mechanical, electrical, firmware/assembly"),
        ("AF-E-101…103", "E Totem — GA, mechanical, electrical/content/software"),
        ("AF-A-101…103", "A Anchor — GA, mechanical/power, electrical/backhaul"),
        ("AF-P-101…102", "P ArcticPhone — concept + spec sketch"),
        ("AF-D-101", "D Seed — R&D brief (degradable motes)"),
        ("AF-H-101", "H Meridian — satellite mission concept"),
    ]
    yy = 538
    for dwg, desc in idx:
        s.t(760, yy, dwg, 10.5, weight="bold", color=ACC)
        s.t(880, yy, desc, 10, color=DIM)
        yy += 26
    s.h(M + 16, 830, "HOW TO USE THIS SET")
    s.bullets(M + 16, 848, [
        "L1 Brick sheets are build-ready — real BOM, wiring, assembly, acceptance test.",
        "S Mite sheets are prototype-ready — orderable parts, CAD scripted (cad/swarm_node.py).",
        "E Totem / A Anchor sheets are spec-level — real parts selected, needs CAD pass.",
        "P Phone / D Seed / H Meridian are concept/R&D — honest status marked on every sheet.",
        "Every sheet: SURAFEL NEGUSSIE drew it · EMEBET INC. owns it · PROPRIETARY & CONFIDENTIAL.",
    ], width=118)
    return [s.svg(1, 1)]


# ============================================================ RENDER =======
ALL_SETS = {
    "00_Fleet_Overview": cover_sheet(),
    "01_L1_Brick": l1_sheets(),
    "02_S_Mite": mite_sheets(),
    "03_E_Totem": totem_sheets(),
    "04_A_Anchor": anchor_sheets(),
    "05_P_ArcticPhone": phone_sheets(),
    "06_D_Seed": seed_sheets(),
    "07_H_Meridian": meridian_sheets(),
}


def write_pdf(name, sheets):
    """Write one HTML with N page divs, print to PDF via headless Chrome."""
    pages = "".join(
        f'<div class="page">{svg}</div>' for svg in sheets)
    html_doc = f"""<!doctype html><html><head><meta charset="utf-8"><style>
@page {{ size: 17in 11in; margin: 0; }}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ background:#fff; }}
.page {{ width:17in; height:11in; page-break-after:always; overflow:hidden; }}
.page:last-child {{ page-break-after:auto; }}
svg {{ width:100%; height:100%; display:block; }}
</style></head><body>{pages}</body></html>"""
    html_path = OUT / f"{name}.html"
    pdf_path = OUT / f"{name}.pdf"
    html_path.write_text(html_doc, encoding="utf-8")
    cmd = [
        CHROME, "--headless", "--disable-gpu", "--no-pdf-header-footer",
        "--print-to-pdf=" + str(pdf_path), html_path.as_uri(),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    ok = pdf_path.exists() and pdf_path.stat().st_size > 5000
    print(f"{'OK ' if ok else 'FAIL'} {name}: {len(sheets)} sheet(s) -> {pdf_path.name}"
          + ("" if ok else f"  {r.stderr[-300:]}"))
    return ok


def main():
    only = sys.argv[1:] or None
    fails = 0
    for name, sheets in ALL_SETS.items():
        if only and not any(o.lower() in name.lower() for o in only):
            continue
        if not write_pdf(name, sheets):
            fails += 1
    print(f"\n{len(ALL_SETS) - fails}/{len(ALL_SETS)} PDFs written to {OUT}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
