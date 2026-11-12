#!/usr/bin/env python3
"""ArcticChain print set v2 — architectural-style blueprint PDFs.

White paper, black ink, orthographic views (top / front / side) with
dimension strings — styled after a real architectural drawing set.

Output: docs/print/*.pdf  (ANSI B landscape, 17 x 11 in)
PNGs:   docs/print/png/*.png (200 dpi previews)

Run:  python docs/make_fleet_pdfs.py
"""

import html
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "print"
PNG = OUT / "png"
OUT.mkdir(exist_ok=True)
PNG.mkdir(exist_ok=True)

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
if not Path(CHROME).exists():
    CHROME = "chrome"

# ------------------------------------------------------------------ palette
PAPER = "#ffffff"
INK = "#1c1c1c"        # main linework
SOFT = "#8a8a8a"       # dims / secondary
FAINT = "#d8d8d8"      # borders / grid
ACC = "#1a4f8a"        # accent (blue)
RED = "#b3261e"        # proprietary / warnings
FILL = "#f2f5f9"       # light component fill
TODAY = date.today().isoformat()

PW, PH = 1632, 1056          # 17in x 11in at 96 dpi
ML = 40                      # left margin
MR = 40
MT = 40
MB = 40
CW = PW - ML - MR           # content width  1552
CH = PH - MT - MB           # content height  976


# ------------------------------------------------------------------ helpers
def esc(s):
    return html.escape(str(s), quote=False)


def wrap(s, n):
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
    """One architectural-style sheet: border, title strip, title block."""

    def __init__(self, dwg, title, subtitle, node, rev="A", status="FOR REVIEW"):
        self.dwg, self.title, self.subtitle = dwg, title, subtitle
        self.node, self.rev, self.status = node, rev, status
        self.el = []
        self._frame()

    # -- primitives ------------------------------------------------------
    def t(self, x, y, s, size=13, anchor="start", color=INK, weight="normal",
          spacing=None):
        sp = f' letter-spacing="{spacing}"' if spacing else ""
        self.el.append(
            f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" text-anchor="{anchor}" '
            f'fill="{color}" font-weight="{weight}"{sp}>{esc(s)}</text>')

    def ln(self, x1, y1, x2, y2, color=INK, w=1.0, dash=None):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.el.append(
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="{color}" stroke-width="{w}"{d}/>')

    def rect(self, x, y, w, h, fill="none", stroke=INK, sw=1.0, r=0, dash=None):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.el.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{r}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{d}/>')

    def circ(self, cx, cy, r, fill="none", stroke=INK, sw=1.0, dash=None):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.el.append(
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="{sw}"{d}/>')

    def center_h(self, x1, y1, x2, y2, color=SOFT, w=0.8):
        """Long-dash centerline."""
        self.ln(x1, y1, x2, y2, color, w, "14 4 3 4")

    def center_v(self, x, y1, y2, color=SOFT, w=0.8):
        self.ln(x, y1, x, y2, color, w, "14 4 3 4")

    def arrow(self, x1, y1, x2, y2, color=SOFT, w=1.0):
        import math
        self.ln(x1, y1, x2, y2, color, w)
        ang = math.atan2(y2 - y1, x2 - x1)
        for da in (2.7, -2.7):
            self.ln(x2, y2, x2 + 9 * math.cos(ang + da),
                    y2 + 9 * math.sin(ang + da), color, w)

    # -- dimensions -------------------------------------------------------
    def dimh(self, x0, x1, y, label, size=12, off=16):
        """Horizontal dimension: extension lines, dim line, arrows, text."""
        for x in (x0, x1):
            self.ln(x, y - off, x, y + 3, SOFT, 0.7)
        self.arrow(x0, y, x0 + 6, y, SOFT)
        self.arrow(x1, y, x1 - 6, y, SOFT)
        self.ln(x0, y, x1, y, SOFT, 0.9)
        self.t((x0 + x1) / 2, y - 6, label, size, "middle", SOFT)

    def dimv(self, x, y0, y1, label, size=12, off=16):
        """Vertical dimension (text rotated -90)."""
        for y in (y0, y1):
            self.ln(x - off, y, x + 3, y, SOFT, 0.7)
        self.arrow(x, y0, x, y0 + 6, SOFT)
        self.arrow(x, y1, x, y1 - 6, SOFT)
        self.ln(x, y0, x, y1, SOFT, 0.9)
        self.el.append(
            f'<text x="{x - 8}" y="{(y0 + y1) / 2}" font-size="{size}" fill="{SOFT}" '
            f'text-anchor="middle" transform="rotate(-90 {x - 8} {(y0 + y1) / 2})">{esc(label)}</text>')

    def leader(self, x1, y1, x2, y2, label, size=12, anchor="start", color=INK):
        self.ln(x1, y1, x2, y2, SOFT, 0.7)
        self.circ(x1, y1, 1.6, fill=SOFT)
        self.t(x2 + (4 if anchor == "start" else -4), y2 + 4, label, size,
               anchor, color)

    # -- composites -------------------------------------------------------
    def h(self, x, y, s, size=15):
        self.t(x, y, s.upper(), size, weight="bold", color=INK, spacing="1")

    def note(self, x, y, s, size=13, color=SOFT):
        for i, ln_ in enumerate(wrap(s, 120)):
            self.t(x, y + i * 18, ln_, size, color=color)
        return y + len(wrap(s, 120)) * 18

    def bullets(self, x, y, items, size=13, color=INK, width=105, lh=20,
                mark="—"):
        yy = y
        for it in items:
            for i, ln_ in enumerate(wrap(it, width)):
                self.t(x + (10 if i == 0 else 22), yy,
                       (mark + " " if i == 0 else "") + ln_, size, color=color)
                yy += lh
            yy += 3
        return yy

    def table(self, x, y, widths, headers, rows, rh=26, fs=12, hfs=12):
        total = sum(widths)
        self.rect(x, y, total, rh * (len(rows) + 1), fill="none", stroke=INK, sw=1.2)
        cx = x
        for w, htxt in zip(widths, headers):
            self.t(cx + 7, y + rh - 8, htxt.upper(), hfs, weight="bold",
                   color=INK, spacing="0.5")
            cx += w
        self.ln(x, y + rh, x + total, y + rh, INK, 1.2)
        yy = y + rh
        for row in rows:
            cx = x
            cells = [wrap(c, max(8, int(w / 6.4))) for c, w in zip(row, widths)]
            rowh = max(rh, max(len(c) for c in cells) * 15 + 8)
            for cell, w in zip(cells, widths):
                for j, cl in enumerate(cell):
                    self.t(cx + 7, yy + 16 + j * 15, cl, fs)
                cx += w
                if cx < x + total:
                    self.ln(cx, yy, cx, yy + rowh, SOFT, 0.5, "4 3")
            self.ln(x, yy + rowh, x + total, yy + rowh, SOFT, 0.5, "4 3")
            yy += rowh
        self.ln(x, yy, x + total, yy, INK, 1.2)
        return yy

    # -- orthographic helpers ----------------------------------------------
    def plan(self, x, y, wpx, dpx, label=None):
        """Top-view outline rect, top-left origin (x,y). Returns bounds."""
        self.rect(x, y, wpx, dpx, fill=FILL, stroke=INK, sw=1.4)
        self.center_h(x, y + dpx / 2, x + wpx, y + dpx / 2)
        self.center_v(x + wpx / 2, y, y + dpx)
        if label:
            self.t(x + wpx / 2, y - 10, label, 13, "middle", SOFT, "bold")
        return x, y, x + wpx, y + dpx

    def elev(self, x, y, wpx, hpx, label=None):
        """Front/side elevation outline. Returns bounds."""
        self.rect(x, y, wpx, hpx, fill=FILL, stroke=INK, sw=1.4)
        self.center_h(x, y + hpx / 2, x + wpx, y + hpx / 2)
        self.center_v(x + wpx / 2, y, y + hpx)
        if label:
            self.t(x + wpx / 2, y - 10, label, 13, "middle", SOFT, "bold")
        return x, y, x + wpx, y + hpx

    # -- frame -------------------------------------------------------------
    def _frame(self):
        self.el.append(
            f'<rect x="0" y="0" width="{PW}" height="{PH}" fill="{PAPER}"/>')
        self.rect(ML, MT, CW, CH, stroke=INK, sw=2)
        self.rect(ML + 8, MT + 8, CW - 16, CH - 16, stroke=SOFT, sw=0.7)
        # title strip
        self.rect(ML, MT, CW, 56, fill="none", stroke=INK, sw=1.2)
        self.ln(ML + 300, MT, ML + 300, MT + 56, SOFT, 0.8)
        self.t(ML + 18, MT + 26, self.node, 18, weight="bold", color=INK)
        self.t(ML + 18, MT + 45, self.title, 11, color=SOFT)
        self.t(ML + 318, MT + 23, self.dwg, 15, weight="bold")
        self.t(ML + 318, MT + 43, f"REV {self.rev} · {TODAY}", 11, color=SOFT)
        self.t(PW - MR - 18, MT + 34, self.status, 12, "end", RED, "bold")

    def titleblock(self, sheet_no, sheets_total):
        """Architectural title block, bottom-right — label-over-value grid."""
        bw, bh = 560, 120
        x, y = PW - MR - bw, PH - MB - bh
        self.rect(x, y, bw, bh, stroke=INK, sw=1.4)
        self.ln(x + 250, y, x + 250, y + bh, INK, 1)
        # left: owner / attribution
        self.t(x + 12, y + 20, "ARCTICCHAIN — RURAL NODE FLEET", 13, weight="bold")
        self.t(x + 12, y + 38, "EMEBET INC. · emebetos.ca", 12, weight="bold", color=ACC)
        self.t(x + 12, y + 57, "SOLE PROPRIETARY OWNER", 10, color=SOFT)
        self.t(x + 12, y + 71, "SURAFEL NEGUSSIE — PLANNER/MAKER", 10, color=SOFT)
        self.t(x + 12, y + 92, "PROPRIETARY & CONFIDENTIAL", 10, RED, "bold")
        self.t(x + 12, y + 106, "UNAUTHORIZED DISTRIBUTION PROHIBITED", 9, RED)
        # right: two columns of label-over-value fields
        def field(fx, fy, label, value):
            self.t(fx, fy, label, 9, color=SOFT)
            self.t(fx, fy + 17, value, 12, weight="bold")
        for i, (lab, val) in enumerate([
                ("DRAWN", "Surafel Negussie"),
                ("DATE", TODAY),
                ("SCALE", "NTS")]):
            field(x + 270, y + 21 + i * 33, lab, val)
        for i, (lab, val) in enumerate([
                ("SHEET", f"{sheet_no}/{sheets_total}"),
                ("DWG NO", self.dwg),
                ("UNITS", "mm")]):
            field(x + 415, y + 21 + i * 33, lab, val)

    def footer(self):
        self.t(ML + 8, PH - MB + 22, "EMEBET INC. — PROPRIETARY & CONFIDENTIAL", 10, color=RED)

    def svg(self, sheet_no, sheets_total):
        self.titleblock(sheet_no, sheets_total)
        self.footer()
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {PW} {PH}" '
                f'font-family="Segoe UI, Arial, sans-serif">{"".join(self.el)}</svg>')


# ============================================================ view helpers
def view3(s, x, y, wpx, hpx, comps=None, label=None, hide_dims=False):
    """Generic elevation/plan box. comps: list of (fx, fy, fw, fh, text).
    Coordinates are fractions of the box. Returns (x0,y0,x1,y1)."""
    x0, y0, x1, y1 = s.elev(x, y, wpx, hpx, label)
    if comps:
        for fx, fy, fw, fh, txt in comps:
            rx = x0 + fx * wpx
            ry = y0 + fy * hpx
            rw = fw * wpx
            rh = fh * hpx
            s.rect(rx, ry, rw, rh, fill="none", stroke=INK, sw=0.9)
            if txt:
                s.t(rx + rw / 2, ry + rh / 2 + 4, txt, 11, "middle", SOFT)
    return x0, y0, x1, y1


# ============================================================ L1 BRICK ====
def l1():
    out = []

    # ---------------- 101 GENERAL ARRANGEMENT ----------------
    s = Sheet("AF-L1-101", "GENERAL ARRANGEMENT — ORTHOGRAPHIC VIEWS",
              "FIELD NODE · HANDHELD MESH BRICK · 160×80×32 mm", "L1 · BRICK")

    # TOP VIEW  (plan: X horizontal 160, Y vertical 80)
    vx, vy = 90, 170
    s.h(vx, vy - 40, "TOP VIEW")
    sc = 3.4
    Wpx, Dpx = 160 * sc, 80 * sc          # 544 x 272
    x0, y0 = vx, vy
    s.plan(x0, y0, Wpx, Dpx)
    # components (fractions)
    comps = [
        (0.04, 0.06, 0.16, 0.30, "LTE ANT"),
        (0.80, 0.06, 0.16, 0.30, "LORA ANT"),
        (0.34, 0.10, 0.32, 0.62, "E-INKE + CM5/HAT STACK"),
        (0.10, 0.74, 0.80, 0.18, "BATTERY 4×18650"),
    ]
    for fx, fy, fw, fh, txt in comps:
        rx, ry = x0 + fx * Wpx, y0 + fy * Dpx
        s.rect(rx, ry, fw * Wpx, fh * Dpx, fill="none", stroke=INK, sw=0.9)
        s.t(rx + fw * Wpx / 2, ry + fh * Dpx / 2 + 4, txt, 11, "middle", SOFT)
    s.dimh(x0, x0 + Wpx, y0 + Dpx + 34, "160")
    s.dimv(x0 - 34, y0, y0 + Dpx, "80")
    s.t(x0 + Wpx / 2, y0 + Dpx + 62,
       "scale: shown NTS · dims in mm", 11, "middle", SOFT)

    # FRONT VIEW  (160 wide × ~32 tall)
    fx_, fy_ = 700, 170
    s.h(fx_, fy_ - 40, "FRONT VIEW")
    fsc = 3.4
    FWpx, FHpx = 160 * fsc, 32 * fsc    # 544 x 109
    x1, y1 = fx_, fy_
    s.elev(x1, y1, FWpx, FHpx)
    fcomps = [
        (0.06, 0.10, 0.20, 0.55, "E-INKE"),
        (0.34, 0.20, 0.32, 0.40, "HAT STACK"),
        (0.70, 0.10, 0.20, 0.55, ""),
    ]
    for fx2, fy2, fw2, fh2, txt in fcomps:
        rx, ry = x1 + fx2 * FWpx, y1 + fy2 * FHpx
        s.rect(rx, ry, fw2 * FWpx, fh2 * FHpx, fill="none", stroke=INK, sw=0.9)
        if txt:
            s.t(rx + fw2 * FWpx / 2, ry + fh2 * FHpx / 2 + 4, txt, 11, "middle", SOFT)
    # SOS button + LED on front face
    s.circ(x1 + 0.52 * FWpx, y1 + 0.16 * FHpx, 11, fill=INK)
    s.t(x1 + 0.52 * FWpx, y1 + 0.16 * FHpx + 4, "SOS", 9, "middle", PAPER)
    s.circ(x1 + 0.56 * FWpx, y1 + 0.16 * FHpx, 4, fill=ACC)
    # USB-C port bottom edge
    s.rect(x1 + 0.30 * FWpx, y1 + FHpx - 4, 0.10 * FWpx, 5, fill=INK)
    # antenna whips
    s.ln(x1 + 0.12 * FWpx, y1, x1 + 0.12 * FWpx, y1 - 30, INK, 2)
    s.ln(x1 + 0.88 * FWpx, y1, x1 + 0.88 * FWpx, y1 - 30, INK, 2)
    s.dimh(x1, x1 + FWpx, y1 + FHpx + 34, "160")
    s.dimv(x1 - 34, y1, y1 + FHpx, "32")

    # SIDE VIEW  (80 × 32)
    sx_, sy_ = 1280, 170
    s.h(sx_, sy_ - 40, "SIDE VIEW")
    ssc = 3.4
    SWpx, SHpx = 80 * ssc, 32 * ssc     # 272 x 109
    x2, y2 = sx_, sy_
    s.elev(x2, y2, SWpx, SHpx)
    # battery tray at bottom (hidden line)
    s.rect(x2 + 8, y2 + SHpx * 0.72, SWpx - 16, SHpx * 0.24,
           fill="none", stroke=SOFT, sw=0.9, dash="6 3")
    s.t(x2 + SWpx / 2, y2 + SHpx * 0.86, "4×18650 TRAY", 10, "middle", SOFT)
    # board stack lines
    for i, yy in enumerate((0.30, 0.48, 0.66)):
        s.ln(x2 + 6, y2 + SHpx * yy, x2 + SWpx - 6, y2 + SHpx * yy, SOFT, 0.7)
    s.dimh(x2, x2 + SWpx, y2 + SHpx + 34, "80")
    s.dimv(x2 - 34, y2, y2 + SHpx, "32")

    # FEATURES strip (left column, below views)
    fy = 560
    s.h(90, fy, "WHAT THIS NODE IS")
    s.bullets(90, fy + 26, [
        "Handheld brick = mailbox + mesh repeater + public bulletin (E-Ink) + SOS beacon.",
        "Runs ArcticChain agent on :8080 — SQLite store-and-forward, signed Ed25519 envelopes.",
        "LoRa 915 MHz mesh to neighbors; LTE backhaul only when a tower exists.",
        "Works with zero connectivity — that is the product.",
    ], width=62)

    s.h(560, fy, "KEY FEATURES")
    s.table(560, fy + 18, [250, 640], ["Feature", "Detail"], [
        ["Display", "7.5in e-Paper 800×480 — sunlight readable, zero idle power"],
        ["Mesh radio", "SX1262 LoRa 915 MHz on SPI1 (GPIO 16–21)"],
        ["Backhaul", "SIM7600 LTE HAT (optional) + GNSS + BT"],
        ["Power", "4×18650 → 14.8 V → 5 V USB-C PD · ~44 Wh"],
        ["Enclosure", "160×80×32 mm printed PETG · ~450 g assembled"],
    ], rh=30)

    s.h(560, 780, "ACCEPTANCE TEST")
    s.bullets(560, 800, [
        "Unit A POST /message → Unit B GET /inbox — with LTE in airplane mode.",
        "Mesh delivery with no towers = the whole pitch in one test.",
    ], width=95)
    out.append(s.svg(1, 3))

    # ---------------- 102 PARTS & POWER ----------------
    s = Sheet("AF-L1-102", "PARTS LIST & POWER",
              "BILL OF MATERIALS · POWER TREE · GPIO", "L1 · BRICK")
    s.h(ML + 10, 150, "PARTS LIST — PER UNIT (ORDER ×2 FOR ACCEPTANCE TEST)")
    s.table(ML + 10, 168, [36, 430, 260, 150, 70],
            ["#", "Part", "Supplier", "Approx CAD", "Qty"], [
        ["1", "Raspberry Pi CM5 4GB + CM5 IO Board", "PiShop / Canada Computers", "$90–130", "1"],
        ["2", "7.5in e-Paper HAT 800×480 SPI", "Waveshare / DFRobot", "$80–110", "1"],
        ["3", "SIM7600 4G/LTE HAT (GNSS+BT ok)", "DFRobot / Waveshare", "$60–90", "1"],
        ["4", "SX1262 LoRa breakout 915 MHz (E22-900M30S class)", "DFrobot / AliExpress", "$15–25", "1"],
        ["5", "Magnetic pogo-pin connector pairs ×6", "AliExpress / Amazon.ca", "$30–60", "1"],
        ["6", "4×18650 flat-top protected + 14.8→5 V 3 A buck", "Electronics supplier", "$40–70", "1"],
        ["7", "PETG filament (both shells + trays ~200 g)", "Any filament supplier", "$25–35", "0.5"],
    ], rh=30)

    # power tree
    py = 480
    s.h(ML + 10, py, "POWER TREE")
    s.rect(ML + 10, py + 18, 200, 54, fill=FILL, stroke=INK, sw=1.2)
    s.t(ML + 110, py + 40, "4×18650", 14, "middle", weight="bold")
    s.t(ML + 110, py + 60, "14.8 V · 44 Wh", 11, "middle", SOFT)
    s.arrow(ML + 210, py + 45, ML + 240, py + 45)
    s.rect(ML + 240, py + 18, 200, 54, fill=FILL, stroke=INK, sw=1.2)
    s.t(ML + 340, py + 40, "14.8→5 V BUCK", 14, "middle", weight="bold")
    s.t(ML + 340, py + 60, "3 A · USB-C PD", 11, "middle", SOFT)
    s.arrow(ML + 440, py + 45, ML + 470, py + 45)
    s.rect(ML + 470, py + 18, 200, 54, fill=FILL, stroke=INK, sw=1.2)
    s.t(ML + 570, py + 40, "5 V RAIL", 14, "middle", weight="bold")
    s.t(ML + 570, py + 60, "fuse 5 A · 10 A in", 11, "middle", SOFT)
    s.note(ML + 10, py + 100,
          "Runtime est: days–weeks depending on LTE duty. Rev-B adds solar charge port "
          "and LiFePO4 cells for -45 °C service.", size=12)

    # GPIO table
    gx = 820
    s.h(gx, py, "GPIO ALLOCATION")
    s.table(gx, py + 18, [170, 240, 330], ["Signal", "GPIO", "Notes"], [
        ["E-Ink SPI", "9/10/11/8", "spi0 · HAT default"],
        ["E-Ink busy/rst", "25 / 17", "poll before refresh"],
        ["LoRa SPI1", "16–21", "dtoverlay=spi1-3cs — NOT spi0"],
        ["LoRa rst/DIO1", "24 / 23", "interrupt RX"],
        ["LTE modem", "USB", "CDC-ACM preferred"],
        ["SOS button", "27", "pull-up input"],
        ["Status LED", "22", "PWM"],
    ], rh=30)

    # config
    cy = 750
    s.h(ML + 10, cy, "/boot/firmware/config.txt — REQUIRED")
    cfg = [
        "dtparam=i2c_arm=on", "dtparam=spi=on", "dtparam=uart0=on",
        "dtoverlay=spi1-3cs", "dtoverlay=gpio-shutdown", "disable_overscan=1",
    ]
    s.rect(ML + 10, cy + 14, 700, 150, fill="#fafafa", stroke=SOFT, sw=0.8)
    for i, c in enumerate(cfg):
        s.t(ML + 26, cy + 40 + i * 22, c, 13, color=INK)
    s.note(ML + 10, cy + 190,
          "E-Ink = spi0 (GPIO 7–11) · LoRa = spi1 (GPIO 16–21). Never share a bus.",
          size=12, color=RED)

    s.h(820, cy, "STACK ORDER (BOTTOM → TOP)")
    s.bullets(820, cy + 26, [
        "USB-C power + battery tray (bottom bay)",
        "CM5 IO Board — power, HDMI, USB, GPIO",
        "4G/LTE HAT — UART + USB AT commands",
        "E-Ink HAT — SPI0 + GPIO25 busy",
        "LoRa SX1262 — SPI1 GPIO16–21 (top)",
    ], width=110)
    out.append(s.svg(2, 3))

    # ---------------- 103 ASSEMBLY & NOTES ----------------
    s = Sheet("AF-L1-103", "ASSEMBLY, SOFTWARE & NOTES",
              "BUILD SEQUENCE · AGENT API · KNOWN GAPS", "L1 · BRICK")
    s.h(ML + 10, 150, "ASSEMBLY SEQUENCE")
    steps = [
        "Print chassis_shell.stl + battery_tray.stl — PETG, 40% infill, 4 walls.",
        "Flash Pi OS Lite 64-bit to SD (Imager → SSH on, user 'arctic').",
        "Bench-test bare CM5 first: boot, SSH, i2cdetect -y 1.",
        "Stack HATs per sheet AF-L1-102; wire LoRa to GPIO 16–21 (spi1).",
        "Wire power: 4×18650 → buck → USB-C; fuse 5 A rail, 10 A input.",
        "Deploy agent: arcticchain_agent.py + systemd unit (poc/SETUP.md §5).",
        "Acceptance test: POST /message on A → GET /inbox on B, LTE off.",
    ]
    yy = 176
    for i, st in enumerate(steps):
        s.circ(ML + 22, yy + 2, 11, fill=FILL, stroke=INK, sw=1)
        s.t(ML + 22, yy + 7, str(i + 1), 12, "middle", weight="bold")
        s.note(ML + 44, yy - 2, st, size=13, color=INK)
        yy += 52

    s.h(900, 150, "AGENT API — :8080")
    s.table(900, 168, [150, 480], ["Endpoint", "Detail"], [
        ["GET /health", "lora/lte status, uptime, queue depth"],
        ["GET /inbox", "pending messages (JSON)"],
        ["GET /signal", "mesh signal metrics"],
        ["POST /message", "{to, text} — queues or sends via LoRa"],
    ], rh=30)

    s.h(760, 380, "KNOWN GAPS (BY DESIGN)")
    s.bullets(760, 404, [
        "LoRa send/poll are TODOs — plaintext beacon until SX1262 driver lands (wk 3).",
        "E-Ink rendering is a stub; real Waveshare driver is Level-2.",
        "No power-path controller — battery swap reboots CM5 (acceptable PoC).",
        "Rev-B targets: -45 °C cells, IP65 gasket, glove SOS, solar input.",
    ], width=88)

    s.h(ML + 10, 560, "FIELD ACCEPTANCE CRITERIA")
    s.table(ML + 10, 578, [320, 700], ["Test", "Pass condition"], [
        ["Mesh exchange", "message delivered A→B with LTE disabled, ≤60 s"],
        ["Range", "≥3 km line-of-sight at default SF"],
        ["Cold soak", "operates -20 °C (rev-B: -45 °C)"],
        ["Power loss", "SQLite inbox survives hard power cut"],
    ], rh=32)

    s.h(ML + 10, 800, "FILES IN REPO")
    s.bullets(ML + 10, 824, [
        "cad/level1_chassis.py → cad/level1/*.stl + dimensions.json (validated)",
        "poc/arcticchain_agent.py · arcticchain-agent.service · SETUP.md · WIRING.md",
        "docs/ORDER_LIST.md · BUILD_GUIDE.md · HARDWARE.md",
        "firmware-hal · mesh-net · compositor · simulator (Rust, 46 tests)",
    ], width=120)
    out.append(s.svg(3, 3))
    return out


# ============================================================ S MITE ======
def mite():
    out = []

    # ---------------- 101 GA ----------------
    s = Sheet("AF-S-101", "GENERAL ARRANGEMENT — SWARM UNIT",
              "PERCHABLE ENVIRONMENTAL SENSOR · 90×90×35 mm", "S · MITE")

    # TOP VIEW puck
    vx, vy = 110, 160
    s.h(vx, vy - 40, "TOP VIEW")
    sc = 3.6
    Wpx, Dpx = 90 * sc, 90 * sc          # 324
    s.plan(vx, vy, Wpx, Dpx)
    # solar cell center (dashed window)
    s.rect(vx + Wpx * 0.17, vy + Dpx * 0.17, Wpx * 0.66, Dpx * 0.66,
           fill="none", stroke=SOFT, sw=1, dash="8 4")
    s.t(vx + Wpx / 2, vy + Dpx / 2 + 4, "SOLAR 62×62", 12, "middle", SOFT, "bold")
    # pcb + battery offset
    s.rect(vx + Wpx * 0.62, vy + Dpx * 0.10, Wpx * 0.24, Wpx * 0.24,
           fill="none", stroke=INK, sw=0.9)
    s.t(vx + Wpx * 0.74, vy + Dpx * 0.22 + 4, "PCB", 10, "middle", SOFT)
    s.rect(vx + Wpx * 0.08, vy + Dpx * 0.66, Wpx * 0.40, Dpx * 0.20,
           fill="none", stroke=INK, sw=0.9, dash="6 3")
    s.t(vx + Wpx * 0.28, vy + Dpx * 0.78 + 4, "LiPo", 10, "middle", SOFT)
    # sensors
    s.circ(vx + Wpx * 0.80, vy + Dpx * 0.72, 10, fill=FILL, stroke=INK, sw=0.9)
    s.t(vx + Wpx * 0.80, vy + Dpx * 0.72 + 4, "SNS", 9, "middle", SOFT)
    s.dimh(vx, vx + Wpx, vy + Dpx + 34, "90")
    s.dimv(vx - 34, vy, vy + Dpx, "90")

    # FRONT VIEW (90 × 35)
    fx_, fy_ = 640, 160
    s.h(fx_, fy_ - 40, "FRONT VIEW")
    fsc = 3.6
    FWpx, FHpx = 90 * fsc, 35 * fsc     # 324 x 126
    x1, y1 = fx_, fy_
    s.elev(x1, y1, FWpx, FHpx)
    # solar top line
    s.ln(x1 + 4, y1 + 3, x1 + FWpx - 4, y1 + 3, INK, 2.5)
    s.t(x1 + FWpx / 2, y1 - 14, "SOLAR CELL (under window)", 11, "middle", SOFT)
    # clip below
    s.ln(x1 + FWpx * 0.25, y1 + FHpx, x1 + FWpx * 0.25, y1 + FHpx + 40, INK, 2)
    s.ln(x1 + FWpx * 0.75, y1 + FHpx, x1 + FWpx * 0.75, y1 + FHpx + 40, INK, 2)
    s.ln(x1 + FWpx * 0.25, y1 + FHpx + 40, x1 + FWpx * 0.75, y1 + FHpx + 40, INK, 2)
    s.circ(x1 + FWpx / 2, y1 + FHpx + 62, 22, fill="none", stroke=SOFT, sw=1, dash="5 3")
    s.t(x1 + FWpx / 2, y1 + FHpx + 108, "PERCH CLIP — grips Ø10–40", 11, "middle", SOFT)
    s.dimh(x1, x1 + FWpx, y1 + FHpx + 130, "90")
    s.dimv(x1 - 34, y1, y1 + FHpx, "35")

    # SIDE VIEW
    sx_, sy_ = 1100, 160
    s.h(sx_, sy_ - 40, "SIDE VIEW")
    ssc = 3.6
    SWpx, SHpx = 90 * ssc, 35 * ssc
    x2, y2 = sx_, sy_
    s.elev(x2, y2, SWpx, SHpx)
    s.rect(x2 + SWpx * 0.30, y2 + SHpx * 0.25, SWpx * 0.40, SHpx * 0.30,
           fill="none", stroke=SOFT, sw=0.9, dash="6 3")
    s.t(x2 + SWpx * 0.50, y2 + SHpx * 0.42 + 4, "PCB+RADIO", 10, "middle", SOFT)
    s.rect(x2 + SWpx * 0.08, y2 + SHpx * 0.62, SWpx * 0.50, SHpx * 0.16,
           fill="none", stroke=SOFT, sw=0.9, dash="6 3")
    s.t(x2 + SWpx * 0.33, y2 + SHpx * 0.72 + 4, "BATTERY", 10, "middle", SOFT)
    s.ln(x2 + SWpx * 0.25, y2 + SHpx, x2 + SWpx * 0.25, y2 + SHpx + 40, INK, 2)
    s.ln(x2 + SWpx * 0.75, y2 + SHpx, x2 + SWpx * 0.75, y2 + SHpx + 40, INK, 2)
    s.ln(x2 + SWpx * 0.25, y2 + SHpx + 40, x2 + SWpx * 0.75, y2 + SHpx + 40, INK, 2)
    s.dimh(x2, x2 + SWpx, y2 + SHpx + 34, "90")
    s.dimv(x2 - 34, y2, y2 + SHpx, "35")

    # features
    fy = 560
    s.h(110, fy, "WHAT THIS NODE IS")
    s.bullets(110, fy + 26, [
        "One member of the fire-watch swarm — the swarm IS the sensor, not the individual bee.",
        "Minimal on purpose: solar top, LoRa radio, temp/RH/VOC sensing, perch clip.",
        "Default state = perched and reporting. Flight is a later role, not the power budget.",
        "Same signed mesh identity as every ArcticChain node.",
    ], width=110)

    s.h(640, fy, "SWARM ROLES (ASSIGNED BY MESH AI)")
    s.table(640, fy + 18, [150, 300, 380], ["Role", "Payload", "Job"], [
        ["Sensor-bee", "temp/RH + VOC", "sniff anomalies — primary detector"],
        ["Eye-bee", "thermal/visual (rev-C)", "converge on fixes to confirm"],
        ["Relay-bee", "LoRa only, high perch", "extend range over ridges"],
        ["Charger-bee", "dock contacts", "perch at Anchor, top off, rebroadcast"],
    ], rh=34)

    s.h(110, 800, "GEN-1 vs ROADMAP")
    s.table(110, 818, [140, 340, 340], ["Stage", "What", "Gate"], [
        ["Gen-1 (now)", "~90 mm puck, solar+LoRa+gas, perch clip", "orderable parts only"],
        ["Gen-2", "smaller, printed antenna, lower cost", "volume + field data"],
        ["Gen-3 (R&D)", "sub-bee perched motes, degradable", "transient-electronics — see D SEED"],
    ], rh=34)
    out.append(s.svg(1, 3))

    # ---------------- 102 PARTS & POWER ----------------
    s = Sheet("AF-S-102", "PARTS LIST & POWER",
              "BILL OF MATERIALS · POWER BUDGET · PIN MAP", "S · MITE")
    s.h(ML + 10, 150, "PARTS LIST — GEN-1 (ALL ORDERABLE IN CANADA)")
    s.table(ML + 10, 168, [36, 400, 230, 160, 70],
            ["#", "Part", "Supplier", "Approx CAD", "Qty"], [
        ["1", "ESP32-S3-DevKitC-1 / S3-WROOM carrier", "PiShop / DigiKey", "$8–15", "1"],
        ["2", "EBYTE E22-900M30S SX1262 LoRa 915 MHz", "DFRobot / AliExpress", "$15–25", "1"],
        ["3", "Sensirion ENS160 VOC/AIQ (I2C)", "DigiKey / Mouser", "$6–10", "1"],
        ["4", "Sensirion SHT41 temp/RH (I2C)", "DigiKey / Mouser", "$4–7", "1"],
        ["5", "60×60 mm ~1 W 5 V poly solar cell", "Amazon.ca / supplier", "$5–10", "1"],
        ["6", "503450 LiPo 2000 mAh + JST-PH", "Amazon.ca / RC supplier", "$12–18", "1"],
        ["7", "CN3791 MPPT solar charge module", "AliExpress / Amazon.ca", "$3–6", "1"],
        ["8", "Custom carrier PCB ~38×38 mm (JLCPCB)", "JLCPCB / PCBWay", "$15–30", "1"],
        ["9", "Printed enclosure set + spring strip", "Print farm", "$5–10", "1"],
    ], rh=30)

    # power budget
    py = 560
    s.h(ML + 10, py, "POWER BUDGET (ESTIMATES — VERIFY ON BENCH)")
    s.table(ML + 10, py + 18, [250, 140, 130, 200], ["State", "Current", "Duty", "Energy/day"], [
        ["Deep sleep (ESP32)", "~10 µA", "~95%", "~0.003 Wh"],
        ["Sense + process", "~80 mA @3.3 V", "~4%", "~0.013 Wh"],
        ["LoRa TX burst", "~120 mA @3.3 V", "~1%", "~0.010 Wh"],
        ["RX listen windows", "~15 mA", "~5%", "~0.006 Wh"],
        ["TOTAL", "", "", "≈0.03 Wh/day"],
    ], rh=32)
    s.note(ML + 10, py + 222,
          "2000 mAh LiPo ≈ 7.4 Wh → ~200 days theoretical; winter + self-discharge → plan 60–90 day autonomy.",
          size=12)

    # pin map
    gx = 780
    s.h(gx, py, "CARRIER PCB PIN MAP")
    s.table(gx, py + 18, [150, 220, 330], ["Net", "ESP32-S3 GPIO", "Function"], [
        ["LORA_SCK/MISO/MOSI", "12 / 13 / 11", "SX1262 SPI"],
        ["LORA_NSS/RST/BUSY", "10 / 9 / 8", "chip select · reset · DIO1 IRQ"],
        ["I2C_SDA/SCL", "1 / 2", "ENS160 (0x53) + SHT41 (0x44)"],
        ["BATT_ADC", "4", "battery voltage sense"],
        ["POGO_CHG", "3", "dock charge detect"],
        ["SOLAR_OK", "5", "charge status"],
    ], rh=32)

    # block diagram
    by = 830
    s.h(ML + 10, by, "SYSTEM BLOCK")
    s.rect(ML + 10, by + 16, 170, 50, fill=FILL, stroke=INK, sw=1.2)
    s.t(ML + 95, by + 38, "SOLAR 1 W", 13, "middle", weight="bold")
    s.t(ML + 95, by + 56, "60×60 cell", 11, "middle", SOFT)
    s.arrow(ML + 180, by + 41, ML + 210, by + 41)
    s.rect(ML + 210, by + 16, 170, 50, fill=FILL, stroke=INK, sw=1.2)
    s.t(ML + 295, by + 38, "CN3791 CHG", 13, "middle", weight="bold")
    s.t(ML + 295, by + 56, "MPPT-ish", 11, "middle", SOFT)
    s.arrow(ML + 380, by + 41, ML + 410, by + 41)
    s.rect(ML + 410, by + 16, 170, 50, fill=FILL, stroke=INK, sw=1.2)
    s.t(ML + 495, by + 38, "LiPo 2000", 13, "middle", weight="bold")
    s.t(ML + 495, by + 56, "503450", 11, "middle", SOFT)
    s.arrow(ML + 580, by + 41, ML + 610, by + 41)
    s.rect(ML + 610, by + 16, 170, 50, fill=FILL, stroke=INK, sw=1.2)
    s.t(ML + 695, by + 38, "LDO 3V3", 13, "middle", weight="bold")
    s.t(ML + 695, by + 56, "always-on", 11, "middle", SOFT)
    s.note(ML + 10, by + 90,
          "ESP32-S3 + SX1262 + ENS160 on 38×38 carrier; sensors on I2C; radio on private SPI.",
          size=12)
    out.append(s.svg(2, 3))

    # ---------------- 103 ASSEMBLY & ROLES ----------------
    s = Sheet("AF-S-103", "ASSEMBLY, FIRMWARE & ROLES",
              "BUILD SEQUENCE · DUTY CYCLE · ACCEPTANCE", "S · MITE")
    s.h(ML + 10, 150, "ASSEMBLY SEQUENCE")
    steps = [
        "Print shell, lid, battery bay, clip — ASA/PC-ABS shell, PETG clip.",
        "Populate carrier PCB: ESP32-S3, SX1262, ENS160, SHT41, charge circuit.",
        "Seat battery, connect JST; verify charge path (bench supply or solar sim).",
        "Close lid — gasket bead, solar under window film.",
        "Attach perch clip; bench-test join to test mesh.",
        "Field trial: perch ×3 units on fence line, log 7 days.",
    ]
    yy = 176
    for i, st in enumerate(steps):
        s.circ(ML + 22, yy + 2, 11, fill=FILL, stroke=INK, sw=1)
        s.t(ML + 22, yy + 7, str(i + 1), 12, "middle", weight="bold")
        s.note(ML + 44, yy - 2, st, size=13, color=INK)
        yy += 52

    s.h(760, 150, "FIRMWARE")
    s.table(760, 168, [160, 480], ["Item", "Detail"], [
        ["Runtime", "ESP-IDF (C) gen-1; Rust port when mesh-net envelope lands"],
        ["Envelope", "same signed format as fleet — MUST match mesh-net"],
        ["Duty cycle", "deep-sleep 95% · sample 5 min · TX on anomaly/schedule"],
        ["Data", "temp/RH/VOC + battery + RSSI + role → <200 B frame"],
        ["OTA", "signed updates over mesh (rev-C); USB/SD bench flash"],
    ], rh=34)

    s.h(760, 420, "ROLE ASSIGNMENT (SKETCH)")
    s.bullets(760, 446, [
        "All Miters broadcast hello + battery + capability every N hours.",
        "Anchor/Brick AI computes coverage gaps → assigns roles via signed cmd.",
        "Sensor-bees concentrate near fuel breaks/ridgelines in fire season.",
        "Charger-bees migrate to Anchor docks when battery <20%.",
        "Roles are soft state — units self-organize if coordinator is gone.",
    ], width=100)

    s.h(ML + 10, 560, "ACCEPTANCE / TEST CRITERIA")
    s.table(ML + 10, 578, [340, 660], ["Test", "Pass condition"], [
        ["Mesh range", "signed observations A→B via Brick/Anchor ≥3 km LOS"],
        ["Autonomy", "≥60 days at 1 sample/10 min + hourly beacon"],
        ["Cold", "operates -30 °C; solar resumes charge at -10 °C"],
        ["Perch", "clip holds Ø25 mm branch through wind-shake test"],
        ["False positive", "<1 smoke alarm/week/unit in dust/inversion"],
    ], rh=34)
    out.append(s.svg(3, 3))
    return out


# ============================================================ E TOTEM =====
def totem():
    out = []

    # ---------------- 101 GA ----------------
    s = Sheet("AF-E-101", "GENERAL ARRANGEMENT — COMMUNITY BOARD",
              "POLE-MOUNTED PUBLIC E-INKE NOTICEBOARD + MESH NODE", "E · TOTEM")

    # FRONT ELEVATION: pole + box
    vx, vy = 140, 170
    s.h(vx, vy - 40, "FRONT ELEVATION")
    # pole
    s.rect(vx + 300, vy - 60, 16, 560, fill="none", stroke=INK, sw=2)
    # box 320x220 -> scale ~1.5 px/mm => 480x330
    sc = 1.5
    bw_, bh_ = 320 * sc, 220 * sc     # 480 x 330
    bx, by = vx + 80, vy
    s.rect(bx, by, bw_, bh_, fill=FILL, stroke=INK, sw=1.6)
    # display window
    s.rect(bx + bw_ * 0.10, by + bh_ * 0.14, bw_ * 0.80, bh_ * 0.56,
           fill="none", stroke=INK, sw=1.2)
    s.t(bx + bw_ / 2, by + bh_ * 0.46, "E-INKE DISPLAY", 14, "middle", weight="bold")
    s.t(bx + bw_ / 2, by + bh_ * 0.46 + 20, "7–13 in class", 11, "middle", SOFT)
    # lower vent/status
    s.rect(bx + bw_ * 0.10, by + bh_ * 0.78, bw_ * 0.30, bh_ * 0.10,
           fill="none", stroke=SOFT, sw=0.9)
    s.t(bx + bw_ * 0.25, by + bh_ * 0.85 + 4, "VENT", 10, "middle", SOFT)
    s.circ(bx + bw_ * 0.80, by + bh_ * 0.83, 6, fill=ACC)
    # mount arms
    s.ln(bx + bw_ * 0.5, by + bh_ * 0.85, vx + 308, by + bh_ * 0.85, INK, 2)
    s.ln(bx + bw_ * 0.5, by + bh_ * 0.15, vx + 308, by + bh_ * 0.15, INK, 2)
    # dims
    s.dimh(bx, bx + bw_, by + bh_ + 40, "320")
    s.dimv(bx - 40, by, by + bh_, "220")
    s.t(bx + bw_ / 2, by + bh_ + 70,
       "box ~320×220×100 mm · pole 3 m class · NTS vertically", 11, "middle", SOFT)

    # SIDE ELEVATION
    sx_, sy_ = 800, 170
    s.h(sx_, sy_ - 40, "SIDE ELEVATION")
    ssc = 1.5
    sd_ = 100 * ssc                    # depth 100mm -> 150px
    s.rect(sx_ + 140, sy_, sd_, bh_, fill=FILL, stroke=INK, sw=1.6)
    s.rect(sx_ + 140 + sd_ * 0.2, sy_ + bh_ * 0.14, sd_ * 0.6, bh_ * 0.56,
           fill="none", stroke=SOFT, sw=0.9, dash="6 3")
    s.t(sx_ + 140 + sd_ / 2, sy_ + bh_ * 0.46, "DEPTH", 11, "middle", SOFT)
    s.rect(sx_ + 146, sy_ - 60, 10, 560, fill="none", stroke=INK, sw=2)
    s.dimh(sx_ + 140, sx_ + 140 + sd_, sy_ + bh_ + 40, "100")
    s.t(sx_ + 140 + sd_ / 2, sy_ + bh_ + 70, "pole-mounted", 11, "middle", SOFT)

    # CONTENT PIPELINE diagram
    px, py = 1100, 200
    s.h(px, py - 30, "CONTENT PIPELINE")
    steps_ = [
        ("PUBLISHER", "community / agency signs content"),
        ("MESH", "signed envelopes flood the network"),
        ("TOTEM", "verify → render → E-Ink"),
        ("PUBLIC", "sunlight-readable · zero idle power"),
    ]
    yy = py
    for i, (nm, sub) in enumerate(steps_):
        s.rect(px, yy, 400, 56, fill=FILL, stroke=INK, sw=1.2)
        s.t(px + 14, yy + 24, nm, 14, weight="bold")
        s.t(px + 14, yy + 44, sub, 11, color=SOFT)
        if i < 3:
            s.arrow(px + 200, yy + 56, px + 200, yy + 76)
        yy += 80

    # use cases
    fy = 620
    s.h(110, fy, "USE CASES")
    s.table(110, fy + 18, [220, 800], ["Use", "Detail"], [
        ["Emergency alerts", "wildfire evacuation, weather — mesh-wide in minutes"],
        ["Community notices", "council, school, clinic, events — the digital general-store board"],
        ["Agency bulletins", "province, RCMP, health unit — signed content only"],
        ["Local info", "road conditions, water advisories, powwow/community events"],
        ["Mesh status", "optional node-health display — coverage made visible"],
    ], rh=36)

    s.h(px, 580, "WHY IT'S UNIQUE")
    s.bullets(px, 606, [
        "Only public noticeboard that IS a network node — it routes, repeats, stores.",
        "Signed content: every notice carries publisher identity — no anonymous flyers.",
        "Works when grid AND cell network are both down — the blackout case.",
        "EN/FR pipeline; community controls what appears — sovereignty in public space.",
    ], width=56)
    out.append(s.svg(1, 2))

    # ---------------- 102 PARTS & INSTALL ----------------
    s = Sheet("AF-E-102", "PARTS LIST & INSTALLATION",
              "BILL OF MATERIALS · POWER SYSTEM · FIELD INSTALL", "E · TOTEM")
    s.h(ML + 10, 150, "PARTS LIST — PER TOTEM")
    s.table(ML + 10, 168, [36, 400, 230, 160, 70],
            ["#", "Part", "Supplier", "Approx CAD", "Qty"], [
        ["1", "CM5 4GB + IO Board (same as L1 — fleet common)", "PiShop / Canada Computers", "$90–130", "1"],
        ["2", "13.3in or 7.5in e-Paper HAT (SPI)", "Waveshare / DFRobot", "$100–200", "1"],
        ["3", "SX1262 LoRa breakout 915 MHz", "DFRobot / AliExpress", "$15–25", "1"],
        ["4", "SIM7600 LTE HAT (optional backhaul)", "DFrobot / Waveshare", "$60–90", "0–1"],
        ["5", "20–30 W poly solar panel + MPPT 20 A", "Amazon.ca / Renogy", "$120–200", "1"],
        ["6", "12.8 V 20 Ah LiFePO4 battery", "Amazon.ca / supplier", "$180–260", "1"],
        ["7", "IP66 polycarbonate box ~320×220×100", "Bud Industries / Amazon.ca", "$80–140", "1"],
        ["8", "Pole + U-bolts + window film + gasket", "hardware supplier", "$60–100", "1"],
    ], rh=32)

    # power system
    py = 560
    s.h(ML + 10, py, "POWER SYSTEM")
    s.rect(ML + 10, py + 16, 180, 50, fill=FILL, stroke=INK, sw=1.2)
    s.t(ML + 100, py + 38, "20–30 W PANEL", 13, "middle", weight="bold")
    s.t(ML + 100, py + 56, "south tilt", 11, "middle", SOFT)
    s.arrow(ML + 190, py + 41, ML + 220, py + 41)
    s.rect(ML + 220, py + 16, 180, 50, fill=FILL, stroke=INK, sw=1.2)
    s.t(ML + 310, py + 38, "MPPT 20 A", 13, "middle", weight="bold")
    s.t(ML + 310, py + 56, "LiFePO4 profile", 11, "middle", SOFT)
    s.arrow(ML + 400, py + 41, ML + 430, py + 41)
    s.rect(ML + 430, py + 16, 180, 50, fill=FILL, stroke=INK, sw=1.2)
    s.t(ML + 520, py + 38, "LiFePO4 20 Ah", 13, "middle", weight="bold")
    s.t(ML + 520, py + 56, "≈256 Wh", 11, "middle", SOFT)
    s.arrow(ML + 610, py + 41, ML + 640, py + 41)
    s.rect(ML + 640, py + 16, 180, 50, fill=FILL, stroke=INK, sw=1.2)
    s.t(ML + 730, py + 38, "5 V BMS → CM5", 13, "middle", weight="bold")
    s.t(ML + 730, py + 56, "always-on", 11, "middle", SOFT)
    s.note(ML + 10, py + 92,
          "Autonomy ≈3–5 days no-sun at 2–4 W avg; oversized panel is the winter plan.",
          size=12)

    # install steps
    gx = 900
    s.h(gx, py, "INSTALLATION — TWO PERSON, ~30 MIN")
    steps_ = [
        "Set pole (post-hole or existing utility pole U-bolt).",
        "Hang box on rear hinge; face display to road/foot traffic.",
        "Connect solar leads; route antenna ports top, drip-loop cable.",
        "Power on; verify mesh join + first content render.",
        "Service: front latch → SD card + battery swap <10 min.",
    ]
    yy = py + 26
    for i, st in enumerate(steps_):
        s.circ(gx + 12, yy + 2, 10, fill=FILL, stroke=INK, sw=1)
        s.t(gx + 12, yy + 7, str(i + 1), 11, "middle", weight="bold")
        s.note(gx + 32, yy - 2, st, size=12, color=INK)
        yy += 48

    # content pipeline notes
    s.h(ML + 10, 800, "CONTENT PIPELINE — SIGNED PUBLICATIONS")
    s.bullets(ML + 10, 826, [
        "Publishers sign content (Ed25519) — community/agency keys.",
        "Mesh floods signed notice envelopes; node verifies before render.",
        "Rotation: alerts > notices > info; expiry timestamps auto-clear.",
        "Rate-limit + dedup; offline queue preserves order; admin can pin/hide.",
    ], width=118)
    out.append(s.svg(2, 2))
    return out


# ============================================================ A ANCHOR =====
def anchor():
    out = []

    # ---------------- 101 GA ----------------
    s = Sheet("AF-A-101", "GENERAL ARRANGEMENT — CHARGING STATION",
              "RENEWABLE STATION · SWARM DOCK + RELAY + BACKHAUL", "A · ANCHOR")

    # FRONT ELEVATION
    vx, vy = 140, 170
    s.h(vx, vy - 40, "FRONT ELEVATION")
    sc = 0.9
    bw_, bh_ = 350 * sc, 250 * sc     # 315 x 225
    bx, by = vx + 60, vy
    s.rect(bx, by, bw_, bh_, fill=FILL, stroke=INK, sw=1.6)
    # battery compartment (lower, hatch)
    s.rect(bx + bw_ * 0.08, by + bh_ * 0.62, bw_ * 0.84, bh_ * 0.30,
           fill="none", stroke=SOFT, sw=0.9, dash="7 4")
    s.t(bx + bw_ / 2, by + bh_ * 0.80, "LiFePO4 50–100 Ah + BMS", 12, "middle", SOFT)
    # upper: compute + radios
    s.rect(bx + bw_ * 0.08, by + bh_ * 0.10, bw_ * 0.40, bh_ * 0.40,
           fill="none", stroke=INK, sw=0.9)
    s.t(bx + bw_ * 0.28, by + bh_ * 0.32 + 4, "CM5", 12, "middle", SOFT)
    s.rect(bx + bw_ * 0.55, by + bh_ * 0.10, bw_ * 0.37, bh_ * 0.40,
           fill="none", stroke=INK, sw=0.9)
    s.t(bx + bw_ * 0.73, by + bh_ * 0.32 + 4, "RADIOS ×2", 12, "middle", SOFT)
    # dock contacts on top edge
    for i in range(4):
        s.circ(bx + bw_ * (0.15 + i * 0.22), by - 4, 6, fill=ACC)
    s.t(bx + bw_ / 2, by - 22, "POGO DOCK ×4 (top)", 11, "middle", SOFT)
    # antenna ports
    s.ln(bx + bw_ * 0.2, by, bx + bw_ * 0.2, by - 26, INK, 2)
    s.ln(bx + bw_ * 0.8, by, bx + bw_ * 0.8, by - 26, INK, 2)
    s.dimh(bx, bx + bw_, by + bh_ + 40, "350")
    s.dimv(bx - 40, by, by + bh_, "250")
    s.t(bx + bw_ / 2, by + bh_ + 56,
       "box ~350×250×400 mm · antenna ports top: LoRa ×2 · LTE · GPS · NTS", 11, "middle", SOFT)

    # solar array beside
    sx_, sy_ = 760, 170
    s.h(sx_, sy_ - 40, "SOLAR ARRAY (SEPARATE)")
    s.rect(sx_ + 60, sy_ + 60, 380, 26, fill=FILL, stroke=INK, sw=1.4)
    for i in range(1, 6):
        s.ln(sx_ + 60 + i * 63, sy_ + 60, sx_ + 60 + i * 63, sy_ + 86, SOFT, 0.7)
    s.t(sx_ + 250, sy_ + 110, "20–60 W poly panel", 12, "middle", SOFT)
    s.ln(sx_ + 60, sy_ + 86, sx_ + 30, sy_ + 200, SOFT, 1.5)
    s.ln(sx_ + 440, sy_ + 86, sx_ + 470, sy_ + 200, SOFT, 1.5)
    s.ln(sx_ + 30, sy_ + 200, sx_ + 470, sy_ + 200, SOFT, 1.5)
    s.t(sx_ + 250, sy_ + 228, "ground frame / pole mount", 11, "middle", SOFT)
    s.t(sx_ + 250, sy_ + 258, "oversized for December sun", 11, "middle", SOFT)

    # dock detail
    dx_, dy_ = 760, 420
    s.h(dx_, dy_ - 30, "SWARM DOCK DETAIL")
    for i in range(4):
        s.circ(dx_ + 40 + i * 90, dy_ + 20, 12, fill=FILL, stroke=INK, sw=1.2)
        s.t(dx_ + 40 + i * 90, dy_ + 56, f"P{i+1}", 11, "middle", SOFT)
    s.note(dx_, dy_ + 90,
          "Mite bottom has 2 pogo pads + alignment notch — lands blind, charges, rebroadcasts. "
          "Each dock ~5 V / 500 mA via CN3791-class controller.", size=12)

    # roles
    fy = 640
    s.h(140, fy, "WHAT THE ANCHOR DOES")
    s.table(140, fy + 18, [200, 900], ["Function", "Detail"], [
        ["Swarm dock", "4 pogo-pin charge positions — Miters land, charge, rebroadcast"],
        ["Long-range relay", "SX1262 at height + bigger antenna — extends mesh over ridges"],
        ["Gateway", "LTE/Wi-Fi/sat backhaul when available — the mesh's door out"],
        ["Anchor sensor", "own temp/RH/VOC + wind — fixed reference for swarm data"],
        ["Status beacon", "E-Ink or LED shows mesh health — readable infrastructure"],
    ], rh=38)

    s.h(dx_, 600, "WHY ANCHORS MATTER")
    s.bullets(dx_, 626, [
        "Docked Miters top off → perpetual patrol without battery swaps.",
        "Elevated relay roughly doubles effective mesh diameter vs. ground nodes.",
        "The visible, maintainable heart of the local mesh — trust infrastructure.",
        "Gateways are what communities pay for — the swarm rides on top.",
    ], width=62)
    out.append(s.svg(1, 2))

    # ---------------- 102 PARTS & SYSTEM ----------------
    s = Sheet("AF-A-102", "PARTS LIST & POWER SYSTEM",
              "BILL OF MATERIALS · WINTER POWER · BACKHAUL", "A · ANCHOR")
    s.h(ML + 10, 150, "PARTS LIST — PER STATION")
    s.table(ML + 10, 168, [36, 380, 220, 150, 70],
            ["#", "Part", "Supplier", "Approx CAD", "Qty"], [
        ["1", "CM5 4GB + IO Board (gateway compute)", "PiShop / Canada Computers", "$90–130", "1"],
        ["2", "SX1262 LoRa breakout ×2 (node + backbone)", "DFRobot / AliExpress", "$30–50", "2"],
        ["3", "LTE HAT OR Wi-Fi bridge OR sat terminal", "DFRobot / Starlink / Iridium", "$60–600", "0–1"],
        ["4", "20–60 W poly panel + MPPT 20–30 A", "Renogy / Amazon.ca", "$150–400", "1"],
        ["5", "LiFePO4 12.8 V 50–100 Ah + BMS", "Amazon.ca / supplier", "$400–900", "1"],
        ["6", "IP65 box ~350×250×400 + pole/frame", "Bud Industries / fabricator", "$200–400", "1"],
        ["7", "Pogo dock ×4 + charge controllers", "custom / CN3791", "$40–80", "4"],
        ["8", "Antennas: LoRa whip ×2, LTE whip, GPS patch", "electronics supplier", "$60–120", "1 set"],
    ], rh=32)

    # power system
    py = 560
    s.h(ML + 10, py, "POWER SYSTEM — SIZED FOR WINTER")
    s.rect(ML + 10, py + 16, 180, 50, fill=FILL, stroke=INK, sw=1.2)
    s.t(ML + 100, py + 38, "20–60 W ARRAY", 13, "middle", weight="bold")
    s.t(ML + 100, py + 56, "oversized Dec", 11, "middle", SOFT)
    s.arrow(ML + 190, py + 41, ML + 220, py + 41)
    s.rect(ML + 220, py + 16, 180, 50, fill=FILL, stroke=INK, sw=1.2)
    s.t(ML + 310, py + 38, "MPPT 20–30 A", 13, "middle", weight="bold")
    s.t(ML + 310, py + 56, "LiFePO4", 11, "middle", SOFT)
    s.arrow(ML + 400, py + 41, ML + 430, py + 41)
    s.rect(ML + 430, py + 16, 180, 50, fill=FILL, stroke=INK, sw=1.2)
    s.t(ML + 520, py + 38, "LiFePO4 50–100 Ah", 13, "middle", weight="bold")
    s.t(ML + 520, py + 56, "640–1280 Wh", 11, "middle", SOFT)
    s.arrow(ML + 610, py + 41, ML + 640, py + 41)
    s.rect(ML + 640, py + 16, 180, 50, fill=FILL, stroke=INK, sw=1.2)
    s.t(ML + 730, py + 38, "BMS → 5/12 V", 13, "middle", weight="bold")
    s.t(ML + 730, py + 56, "station + dock", 11, "middle", SOFT)
    s.note(ML + 10, py + 92,
          "Autonomy target 30–90 days no-sun — LoRa is µW-class, compute sleeps.", size=12)

    # backhaul options
    gx = 900
    s.h(gx, py, "BACKHAUL OPTIONS (HIERARCHY)")
    s.table(gx, py + 18, [165, 180, 290], ["Option", "Cost", "When"], [
        ["Mesh only", "$0", "no coverage — still relays + docks"],
        ["LTE (SIM7600)", "$60–90", "any cell signal — most rural sites"],
        ["Starlink Mini/Res", "$300–600 + $/mo", "true dead zones — business case"],
        ["Iridium Certus/L-band", "OEM $500+", "polar/north — own-sat path"],
        ["ArcticChain sats", "future", "the mesh IS the ground segment"],
    ], rh=34)

    # dock protocol
    s.h(ML + 10, 800, "DOCK PROTOCOL")
    s.bullets(ML + 10, 826, [
        "Mite lands on pogo pads → charge-detect line pulled low.",
        "Dock controller broadcasts slot assignment over LoRa.",
        "Charge until >80% or timeout; release + 'charged' beacon.",
        "Rotating priority: lowest-battery docked unit gets next slot.",
        "All dock events signed + logged — swarm energy is mesh data.",
    ], width=118)

    s.h(900, 800, "FIELD ACCEPTANCE")
    s.bullets(900, 826, [
        "4 Miters dock, charge, undock on schedule — 72 h soak.",
        "≥10 signed msgs/min relayed through Anchor at 5 km spacing.",
        "LTE failover: drop → store-forward continues → auto-reconnect.",
        "Winter: -30 °C, panel snow-covered 3 days → still docks + relays.",
    ], width=100)
    out.append(s.svg(2, 2))
    return out


# ============================================================ P PHONE =====
def phone():
    out = []

    # ---------------- 101 CONCEPT ----------------
    s = Sheet("AF-P-101", "CONCEPT — RURAL COMMS DEVICE",
              "MESH-NATIVE PHONE FOR RURAL & REMOTE CANADA", "P · ARCTICPHONE",
              rev="0", status="CONCEPT — NOT FROZEN")

    # phone outline
    fx, fy = 150, 170
    s.h(fx, fy - 40, "FRONT VIEW — TARGET FORM")
    pw_, ph_ = 200, 400
    s.rect(fx, fy, pw_, ph_, fill=FILL, stroke=INK, sw=1.8, r=22)
    s.rect(fx + 14, fy + 26, pw_ - 28, ph_ - 90, fill="none", stroke=SOFT, sw=0.9, r=6)
    s.t(fx + pw_ / 2, fy + ph_ * 0.45, "DISPLAY", 14, "middle", weight="bold")
    s.t(fx + pw_ / 2, fy + ph_ * 0.45 + 20, "glove-friendly UI", 11, "middle", SOFT)
    # camera dot + mesh marks
    s.circ(fx + pw_ / 2, fy + 14, 5, fill=INK)
    for i, yy in enumerate((0.55, 0.65, 0.75)):
        s.ln(fx + pw_ * 0.12, fy + ph_ * yy, fx + pw_ * 0.30, fy + ph_ * yy, ACC, 1.5)
        s.ln(fx + pw_ * 0.70, fy + ph_ * yy, fx + pw_ * 0.88, fy + ph_ * yy, ACC, 1.5)
    s.t(fx + pw_ / 2, fy + ph_ + 34, "~145×72×14 mm · ~220 g · NTS", 12, "middle", SOFT)
    s.t(fx + pw_ / 2, fy + ph_ + 56, "mesh radio marks shown in blue", 11, "middle", SOFT)

    # what changed vs monolith
    gx = 640
    s.h(gx, 170, "WHAT CHANGED VS MONOLITH")
    s.bullets(gx, 200, [
        "Monolith = flagship research device (titanium spine, optical docks).",
        "Wrong phone for a rancher in a -35 °C truck cab or a fly-in community.",
        "ArcticPhone is rural-first: mesh-native, satellite SOS-ready, offline-first, repairable, community-owned.",
        "Every ArcticPhone IS a node — calls, texts, data ride the community mesh.",
    ], width=105)

    # architecture options
    s.h(gx, 430, "ARCHITECTURE OPTIONS (DECISION REQUIRED)")
    s.table(gx, 456, [50, 280, 280, 240], ["Opt", "Approach", "Pros", "Cons"], [
        ["A", "Rugged Android + ArcticChain mesh HAT", "fast to market, app ecosystem", "Android bloat, cert effort"],
        ["B", "Custom Linux + mesh SoC (integrated SX1262)", "clean, sovereign, repairable", "OS work, smaller ecosystem"],
        ["C", "Hybrid: Linux core + Android layer", "best of both", "longest dev time"],
    ], rh=56)

    # capability set
    s.h(ML + 10, 664, "CAPABILITY SET")
    s.table(ML + 10, 692, [220, 760], ["Capability", "Implementation"], [
        ["Mesh node", "SX1262 LoRa 915 + signed envelopes — every phone extends the network"],
        ["Satellite SOS", "L-band messenger module now; own constellation later"],
        ["Offline apps", "maps, manuals, forms, messaging EN/FR — useful with zero bars"],
        ["Cellular", "LTE Cat-1/4 when towers exist — proven path from L1"],
        ["Power", "replaceable battery + USB-C PD + solar trickle option"],
        ["Rugged", "IP68 · -30..+55 °C · glove UI · 1.5 m drop target"],
    ], rh=36)
    out.append(s.svg(1, 2))

    # ---------------- 102 SPEC ----------------
    s = Sheet("AF-P-102", "SPECIFICATION SKETCH",
              "TARGET SPEC · BOM CATEGORIES · ROADMAP", "P · ARCTICPHONE",
              rev="0", status="CONCEPT — NOT FROZEN")
    s.h(ML + 10, 150, "TARGET SPECIFICATION")
    s.table(ML + 10, 168, [240, 220, 240, 260], ["Parameter", "Target", "Parameter", "Target"], [
        ["Envelope", "~145×72×14 mm", "Mass", "~220 g"],
        ["Display", "5–6in transflective", "SoC", "quad-core, LTE, GNSS"],
        ["Mesh radio", "SX1262 915 + MCU", "Sat SOS", "L-band module (rev-A)"],
        ["Battery", "replaceable ~4000 mAh", "Charging", "USB-C PD + solar"],
        ["OS", "Android Go OR Linux", "UI", "glove-friendly, EN/FR"],
        ["Rating", "IP68 · -30..+55 °C", "Repair", "standard screws, open back"],
    ], rh=34)

    s.h(ML + 10, 480, "BOM CATEGORIES (NOT FIXED — ARCHITECTURE PENDING)")
    s.table(ML + 10, 506, [220, 760], ["Category", "Options / notes"], [
        ["Compute+display", "rugged Android module (A) OR custom board (B)"],
        ["Mesh module", "SX1262 + nRF52/ESP32 — same envelope as fleet"],
        ["Sat messenger", "inReach-class module, Iridium Certus OEM, or future own-sat"],
        ["Cellular", "LTE Cat-4 modem + SIM — proven path from L1 HAT"],
        ["Power", "4000 mAh LiFePO4 pouch, USB-C PD, solar pad option"],
        ["Enclosure", "PC+TPU bumpers, gasketed ports, captive screws"],
    ], rh=36)

    s.h(ML + 10, 780, "ROADMAP TO FIRST UNIT")
    s.bullets(ML + 10, 808, [
        "Phase 0 (now): architecture decision + industrial design — this sheet.",
        "Phase 1: prototype on dev-kit + mesh HAT — prove mesh+SOS on existing hardware.",
        "Phase 2: custom enclosure + integration — print → machine → mold decision.",
        "Phase 3: certification (ISED/RF) + pilot batch — 50–100 units for founding communities.",
        "Phase 4: volume — repairable design pays off at scale (modules, not glue).",
    ], width=118)

    s.h(900, 480, "UNIQUE VS EVERY OTHER PHONE")
    s.bullets(900, 508, [
        "The only phone that is a FIRST-CLASS MESH CITIZEN — your phone extends the network.",
        "Satellite SOS as a core feature, not an accessory — for places towers aren't.",
        "Offline-first: apps, maps, forms, messaging all useful with zero bars.",
        "Community-owned: the network your phone joins belongs to your community.",
        "Repairable by design — a local tech fixes it with hand tools.",
    ], width=100)

    s.h(900, 700, "RELATIONSHIP TO OTHER NODES")
    s.bullets(900, 728, [
        "Phone = personal node; L1 = field/shared; Totem = public; Mite = environmental; Anchor = infrastructure.",
        "All speak the same signed mesh — a call routes phone→phone→brick→satellite.",
        "Phone is the highest-volume node — its radio is the network's user terminal.",
    ], width=100)
    out.append(s.svg(2, 2))
    return out


# ============================================================ D SEED ======
def seed():
    out = []
    s = Sheet("AF-D-101", "R&D BRIEF — DEGRADABLE MOTE",
              "SEED-DROP SEASONAL SENSOR — RESEARCH PROGRAM", "D · SEED",
              rev="0", status="RESEARCH — NOT A PRODUCT")

    s.h(ML + 10, 150, "THE IDEA")
    s.bullets(ML + 10, 180, [
        "A ~20 mm mote of printed electronics on biodegradable substrate — seed-dropped over a fuel break or burn scar.",
        "It sprouts into a temporary sensor skin for fire season, reports through cluster heads, and dissolves.",
        "Zero e-waste, no retrieval, no grid to build — sensing that ENDS by design.",
        "Materials/transient-electronics program — fundable R&D, not a product. Every earlier rung must succeed first.",
    ], width=118)

    s.h(ML + 10, 420, "RESEARCH TARGETS")
    s.table(ML + 10, 448, [220, 700], ["Target", "Goal"], [
        ["Mass", "<1 g per mote (cluster head <5 g)"],
        ["Cost", "<$1/unit at volume (printed, not assembled)"],
        ["Life", "one fire season (~6 months) then degrade"],
        ["Degradation", "complete in <12 months, non-toxic residue"],
        ["Comms", "duty-cycled LoRa or backscatter — rare TX, local clustering"],
        ["Power", "printed battery + PV/TEG harvest — µW average"],
        ["Sensing", "temp/RH/VOC minimum; optical smoke later"],
    ], rh=40)

    s.h(ML + 10, 800, "ROADMAP GATES")
    s.bullets(ML + 10, 828, [
        "Gate 1: university transient-electronics partner (SR&ED eligible).",
        "Gate 2: lab demo — printed mote senses temp + reports 10 m via cluster head.",
        "Gate 3: field trial — 100 motes over 1 ha, one season, recoverable data.",
        "Gate 4: degradable variant — residue confirms <12 month breakdown.",
        "Gate 5: scale — seed-drop tied to Anchor/Brick infrastructure.",
    ], width=118)

    s.h(900, 150, "MATERIALS PATHWAY")
    s.table(900, 178, [200, 560], ["Component", "Candidate materials / approach"], [
        ["Substrate", "cellulose paper, silk fibroin, transient polymer"],
        ["Electronics", "printed Zn/MnO₂ battery, printed sensors, organic TFT"],
        ["Energy", "printed PV cell, thermoelectric, RF harvest"],
        ["Comms", "backscatter (no TX) or ultra-low-power LoRa wake-up"],
        ["Deploy", "seed pod form factor — germinates sensor on moisture"],
    ], rh=44)

    s.h(900, 560, "WHY THIS MATTERS")
    s.bullets(900, 590, [
        "Fire season is seasonal — permanent sensors waste 11 months.",
        "Degradable motes match the threat's rhythm: deploy, vanish.",
        "Billions-scale is materials R&D, not drone fleet — mesh math supports it.",
        "Precedent: DARPA/NSF computational-dust programs prove it's real.",
    ], width=105)

    s.h(900, 736, "HONEST STATUS")
    s.bullets(900, 764, [
        "TRL ~2 — concept + literature. No ArcticChain mote exists yet.",
        "This sheet is a research brief, not a buildable BOM — deliberately.",
        "Swarm architecture is the same — only the node shrinks.",
        "Do NOT promise motes to funders until Gate 2 demo exists.",
    ], width=92, color=RED)
    out.append(s.svg(1, 1))
    return out


# ============================================================ H MERIDIAN ====
def meridian():
    out = []
    s = Sheet("AF-H-101", "MISSION CONCEPT — SATELLITE PAYLOAD",
              "STORE-AND-FORWARD CONSTELLATION — THE MESH IS THE GROUND SEGMENT",
              "H · MERIDIAN", rev="0", status="VISION — EARNED")

    s.h(ML + 10, 150, "THE INSIGHT")
    s.bullets(ML + 10, 180, [
        "When the mesh needs backhaul beyond terrestrial reach, our own store-and-forward payload flies.",
        "Nobody else launching smallsats has a deployed rural ground network waiting — the mesh IS the user-terminal layer.",
        "A text message or sensor packet needs COVERAGE, not Starlink bandwidth — a handful of CubeSats can blanket Canada.",
        "Higher orbit is correct for THIS layer: bigger footprint per satellite = fewer needed.",
    ], width=85)

    # orbit sketch — right column
    ox = 1130
    s.t(ox, 148, "ORBIT CONCEPT", 15, "middle", SOFT, "bold")
    s.circ(ox, 310, 95, fill="none", stroke=INK, sw=1.5)
    s.circ(ox, 310, 42, fill=FILL, stroke=INK, sw=1)
    s.t(ox, 315, "EARTH", 12, "middle", weight="bold")
    s.el.append(
        f'<path d="M {ox - 185} 310 A 185 62 0 0 1 {ox + 185} 310" '
        f'fill="none" stroke="{ACC}" stroke-width="1.5" stroke-dasharray="8 4"/>')
    s.t(ox, 238, "polar ~600–1000 km", 12, "middle", ACC, "bold")
    s.t(ox, 402, "inclination ~99° — Arctic coverage", 12, "middle", SOFT)

    # payload table — right column
    s.h(720, 450, "PAYLOAD — DERIVED FROM THE MESH")
    s.table(720, 476, [190, 600], ["Element", "Implementation"], [
        ["Radio", "UHF/S-band store-and-forward transceiver — LoRa-derived or CC1101-class"],
        ["Envelope", "same signed mesh-net format — satellite is just another hop"],
        ["Store", "onboard flash — holds envelopes until ground station passes"],
        ["Bus", "1U/3U CubeSat (GOMspace/EnduroSat/CubeSat Shop) or smallsat"],
        ["Ground segment", "the deployed mesh + community gateways = user terminals"],
    ], rh=32)

    # mission profile — left column
    s.h(ML + 10, 430, "MISSION PROFILE")
    s.bullets(ML + 10, 458, [
        "Polar LEO constellation blankets Canada incl. North — messaging/sensor tier.",
        "Latency: store-and-forward hours — right-sized for alerts, notices, telemetry.",
        "Each sat serves hundreds of nodes per pass — plenty for text/sensor traffic.",
        "Pathfinder: 2–6 sats prove the constellation, then scale regional.",
    ], width=85)

    # ascent + funding — right column bottom
    s.h(720, 700, "ASCENT & FUNDING PATH")
    s.bullets(720, 728, [
        "Ascent: hosted payload → university CubeSat (CSA) → dedicated smallsat (non-US rideshare) → pathfinder 6–12 sats → regional constellation.",
        "Funding: CSA CubeSat Initiative · provincial/Indigenous services · IDEaS/defence dual-use · anchor demand for domestic launch.",
    ], width=92)

    # honest status — left column bottom
    s.h(ML + 10, 640, "HONEST STATUS")
    s.bullets(ML + 10, 670, [
        "Vision stage — no satellite exists. The mesh must prove itself first (L1→swarm→revenue).",
        "This sheet is mission concept, not spacecraft design — payload inherits mesh crypto/routing.",
        "Every earlier rung funds and justifies this one — the trailhead is the ground network.",
    ], width=85, color=RED)
    out.append(s.svg(1, 1))
    return out


# ============================================================ COVER =======
def cover():
    s = Sheet("AF-000", "FLEET OVERVIEW & DRAWING INDEX",
              "ARCTICCHAIN RURAL NODE FAMILY — COMPLETE PRINT SET", "COVER",
              status="MASTER INDEX")

    s.h(ML + 10, 150, "THE FLEET — ONE NETWORK, MANY SHAPES")
    s.table(ML + 10, 178, [60, 110, 300, 210, 200, 140],
            ["Node", "Name", "Role", "Envelope", "Power", "Status"], [
        ["L1", "Brick", "field node — mailbox+repeater+bulletin+SOS", "160×80×24 mm", "4×18650/solar", "CAD ready"],
        ["E", "Totem", "community board — public E-Ink + mesh node", "~320×220×80+pole", "solar+LiFePO4", "spec"],
        ["S", "Mite", "swarm unit — perchable env sensor", "~90×90×35 mm", "solar+LiPo", "CAD scripted"],
        ["A", "Anchor", "charging station — dock+relay+backhaul", "~350×250×400+array", "20–60 W+LiFePO4", "spec"],
        ["P", "ArcticPhone", "rural comms — mesh-native, sat SOS", "~145×72×14 mm", "replaceable+solar", "concept"],
        ["D", "Seed", "degradable mote — seasonal sensing", "~20×20×5 mm", "printed+harvest", "R&D"],
        ["H", "Meridian", "satellite payload — mesh IS ground segment", "1U/3U CubeSat", "solar array", "vision"],
    ], rh=44)

    s.h(ML + 10, 560, "SHARED DESIGN DNA (EVERY NODE)")
    s.bullets(ML + 10, 590, [
        "Climate: -45..+70 °C · IP65+ · UV-stable · LiFePO4-preferred · December-sized solar.",
        "Power: solar-first · 30–90 day autonomy · works with zero grid.",
        "Field: bear-country mounts · two-person install · hand-tool repair.",
        "Sovereignty: community-owned mesh · data stays home · OCAP · EN/FR · privacy by design.",
        "Appropriate tech: right-sized cost · repairable > sealed · open docs.",
        "Offline dignity: works when everything else has failed — that IS the product.",
    ], width=118)

    s.h(860, 560, "DRAWING INDEX")
    idx = [
        ("AF-000", "this sheet — fleet overview & index"),
        ("AF-L1-101…103", "L1 Brick — arrangement, parts/power, assembly"),
        ("AF-S-101…103", "S Mite — arrangement, parts/power, assembly/roles"),
        ("AF-E-101…102", "E Totem — arrangement, parts/install"),
        ("AF-A-101…102", "A Anchor — arrangement, parts/power"),
        ("AF-P-101…102", "P ArcticPhone — concept + spec sketch"),
        ("AF-D-101", "D Seed — R&D brief (degradable motes)"),
        ("AF-H-101", "H Meridian — satellite mission concept"),
    ]
    yy = 590
    for dwg, desc in idx:
        s.t(860, yy, dwg, 13, weight="bold", color=ACC)
        s.t(1000, yy, desc, 13, color=SOFT)
        yy += 32

    s.h(ML + 10, 868, "HOW TO READ THIS SET")
    s.bullets(ML + 10, 894, [
        "L1 Brick sheets are build-ready — real BOM, wiring, assembly, acceptance test.",
        "S Mite sheets are prototype-ready — orderable parts, CAD scripted (cad/swarm_node.py).",
        "E Totem / A Anchor sheets are spec-level — real parts selected, needs CAD pass.",
        "P Phone / D Seed / H Meridian are concept/R&D — honest status on every sheet.",
        "Every sheet: SURAFEL NEGUSSIE drew it · EMEBET INC. owns it · PROPRIETARY & CONFIDENTIAL.",
    ], width=118)
    return [s.svg(1, 1)]


# ============================================================ RENDER =======
ALL_SETS = {
    "00_Fleet_Overview": cover(),
    "01_L1_Brick": l1(),
    "02_S_Mite": mite(),
    "03_E_Totem": totem(),
    "04_A_Anchor": anchor(),
    "05_P_ArcticPhone": phone(),
    "06_D_Seed": seed(),
    "07_H_Meridian": meridian(),
}


def write_pdf(name, sheets):
    pages = "".join(f'<div class="page">{svg}</div>' for svg in sheets)
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
    cmd = [CHROME, "--headless", "--disable-gpu", "--no-pdf-header-footer",
           "--print-to-pdf=" + str(pdf_path), html_path.as_uri()]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    ok = pdf_path.exists() and pdf_path.stat().st_size > 5000
    print(f"{'OK ' if ok else 'FAIL'} {name}: {len(sheets)} sheet(s)")
    return ok, pdf_path


def render_pngs(pdf_path):
    import pymupdf
    doc = pymupdf.open(str(pdf_path))
    for i, page in enumerate(doc):
        pix = page.get_pixmap(dpi=200)
        pix.save(str(PNG / f"{pdf_path.stem}_p{i+1}.png"))


def main():
    only = sys.argv[1:] or None
    fails = 0
    for name, sheets in ALL_SETS.items():
        if only and not any(o.lower() in name.lower() for o in only):
            continue
        ok, pdf_path = write_pdf(name, sheets)
        if ok:
            try:
                render_pngs(pdf_path)
            except Exception as e:
                print(f"  png render failed: {e}")
        else:
            fails += 1
    print(f"\ndone — PDFs in {OUT} · PNG previews in {PNG}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
