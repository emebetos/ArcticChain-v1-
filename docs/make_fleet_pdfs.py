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


def shade(hexcolor, factor):
    """Lighten (>1) or darken (<1) a #rrggbb color, clamped."""
    h = hexcolor.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    c = lambda v: max(0, min(255, int(v * factor)))
    return f"#{c(r):02x}{c(g):02x}{c(b):02x}"


class Sheet:
    """One architectural-style sheet: border, title strip, title block."""

    def __init__(self, dwg, title, subtitle, node, rev="A", status="FOR REVIEW"):
        self.dwg, self.title, self.subtitle = dwg, title, subtitle
        self.node, self.rev, self.status = node, rev, status
        self.el = []
        self._ngrad = 0
        self._nscr = 0
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

    def poly(self, pts, fill="none", stroke=INK, sw=1.0):
        p = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        self.el.append(
            f'<polygon points="{p}" fill="{fill}" stroke="{stroke}" '
            f'stroke-width="{sw}"/>')

    def iso(self, cx, cy, w, h, d, front, top=None, side=None):
        """Oblique 'product shot' box: front face + top + side, auto-shaded.
        front/top/side are hex colors; top/side default to shaded variants."""
        dx, dy = d * 0.45, -d * 0.42
        fx, fy = cx - w / 2, cy - h / 2
        if top is None:
            top = shade(front, 1.28)
        if side is None:
            side = shade(front, 0.72)
        # side face
        self.poly([(fx + w, fy), (fx + w + dx, fy + dy),
                   (fx + w + dx, fy + h + dy), (fx + w, fy + h)],
                  fill=side, stroke=INK, sw=1.4)
        # top face
        self.poly([(fx, fy), (fx + dx, fy + dy),
                   (fx + w + dx, fy + dy), (fx + w, fy)],
                  fill=top, stroke=INK, sw=1.4)
        # front face
        self.rect(fx, fy, w, h, fill=front, stroke=INK, sw=1.4)
        return fx, fy, dx, dy

    # -- product-shot device ----------------------------------------------
    def device(self, cx, cy, w, h, d, color, top=None, side=None, rad=14):
        """Realistic product shot: gradient-shaded faces, rounded front,
        drop shadow. Returns geometry dict G for face-mapped details."""
        dx, dy = d * 0.45, -d * 0.42
        fx, fy = cx - w / 2, cy - h / 2
        if top is None:
            top = shade(color, 1.30)
        if side is None:
            side = shade(color, 0.70)
        gid = f"dg{self._ngrad}"
        self._ngrad += 1
        self.el.append(
            f'<defs><linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0" stop-color="{shade(color, 1.24)}"/>'
            f'<stop offset="0.5" stop-color="{color}"/>'
            f'<stop offset="1" stop-color="{shade(color, 0.80)}"/>'
            f'</linearGradient></defs>')
        # drop shadow (drawn first, under device)
        self.el.append(
            f'<ellipse cx="{cx + dx * 0.55:.1f}" cy="{cy + h / 2 + abs(dy) * 0.55:.1f}" '
            f'rx="{w * 0.56:.1f}" ry="{max(10, d * 0.28):.1f}" fill="#000" fill-opacity="0.13"/>')
        self.poly([(fx + w, fy), (fx + w + dx, fy + dy),
                   (fx + w + dx, fy + h + dy), (fx + w, fy + h)],
                  fill=side, stroke=INK, sw=1.4)
        self.poly([(fx, fy), (fx + dx, fy + dy),
                   (fx + w + dx, fy + dy), (fx + w, fy)],
                  fill=top, stroke=INK, sw=1.4)
        self.rect(fx, fy, w, h, fill=f"url(#{gid})", stroke=INK, sw=1.4, r=rad)
        # edge highlight on top face
        self.el.append(
            f'<line x1="{fx + rad:.1f}" y1="{fy + 1.5:.1f}" '
            f'x2="{fx + w - rad:.1f}" y2="{fy + 1.5:.1f}" stroke="#ffffff" '
            f'stroke-width="1.2" stroke-opacity="0.35"/>')
        return {"fx": fx, "fy": fy, "w": w, "h": h, "dx": dx, "dy": dy,
                "cx": cx, "cy": cy, "color": color, "rad": rad}

    @staticmethod
    def fpt(G, fxr, fyr):
        """Front-face fraction → absolute point."""
        return G["fx"] + fxr * G["w"], G["fy"] + fyr * G["h"]

    @staticmethod
    def tpt(G, a, b):
        """Top-face point: a = left→right, b = front→back."""
        return (G["fx"] + a * G["w"] + b * G["dx"], G["fy"] + b * G["dy"])

    @staticmethod
    def spt(G, a, b):
        """Side-face point: a = front→back (depth), b = top→bottom."""
        return (G["fx"] + G["w"] + a * G["dx"], G["fy"] + b * G["h"] + a * G["dy"])

    def screen(self, G, fxr, fyr, fw, fh, mode="lcd"):
        """Bezeled display on front face. mode: 'lcd' glass UI or 'eink' paper."""
        fx, fy, w, h = G["fx"], G["fy"], G["w"], G["h"]
        x, y, ww, hh = fx + fxr * w, fy + fyr * h, fw * w, fh * h
        self.rect(x - 5, y - 5, ww + 10, hh + 10, fill="#10151c",
                  stroke=INK, sw=1.2, r=10)
        if mode == "eink":
            self.rect(x, y, ww, hh, fill="#d9e0cf", stroke=SOFT, sw=0.8, r=4)
            self.rect(x + 4, y + 4, ww - 8, hh * 0.13, fill="#bccbb0",
                      stroke="none", r=2)
            self.t(x + 10, y + hh * 0.125 - 2, "COMMUNITY BOARD", 9, color="#5a6b52")
            for i in range(4):
                ly = y + hh * (0.26 + i * 0.155)
                self.rect(x + 8, ly, ww * (0.86 - 0.09 * (i % 2)), 5,
                          fill="#a7b499", stroke="none", r=2)
            self.rect(x + 8, y + hh - 13, ww * 0.42, 5, fill="#bccbb0",
                      stroke="none", r=2)
            self.rect(x + ww - 26, y + hh - 13, 18, 5, fill="#8fa184",
                      stroke="none", r=2)
        else:
            gid = f"sc{self._nscr}"
            self._nscr += 1
            self.el.append(
                f'<defs><linearGradient id="{gid}" x1="0" y1="0" x2="1" y2="1">'
                f'<stop offset="0" stop-color="#0e1a2b"/>'
                f'<stop offset="1" stop-color="#1e3a5c"/></linearGradient></defs>')
            self.rect(x, y, ww, hh, fill=f"url(#{gid})", stroke=SOFT, sw=0.8, r=4)
            # status bar
            self.ln(x + 6, y + hh * 0.10, x + ww - 6, y + hh * 0.10, "#33506e", 0.7)
            self.rect(x + 9, y + hh * 0.035, 16, 3.5, fill="#5eead4", stroke="none", r=1)
            self.rect(x + ww - 30, y + hh * 0.032, 18, 4, fill="none",
                      stroke="#5eead4", sw=0.8, r=1)
            # content lines
            for i, (lw, lc) in enumerate(
                    [(0.88, "#9fc3e8"), (0.72, "#7ea6cf"),
                     (0.84, "#9fc3e8"), (0.5, "#5f87ad")]):
                ly = y + hh * (0.24 + i * 0.16)
                self.rect(x + 8, ly, ww * lw, max(4, hh * 0.05),
                          fill=lc, stroke="none", r=2)
            # glare
            self.el.append(
                f'<polygon points="{x:.1f},{y:.1f} {x + ww * 0.55:.1f},{y:.1f} '
                f'{x + ww * 0.22:.1f},{y + hh:.1f} {x:.1f},{y + hh * 0.75:.1f}" '
                f'fill="#ffffff" fill-opacity="0.09"/>')

    # -- face-mapped product details --------------------------------------
    def sidebtn(self, G, a0, a1, b0, b1, color=None):
        """Button quad on the side (depth) face. a=depth frac, b=height frac."""
        pts = [self.spt(G, a0, b0), self.spt(G, a1, b0),
               self.spt(G, a1, b1), self.spt(G, a0, b1)]
        self.poly(pts, fill=color or shade(G["color"], 0.5), stroke=INK, sw=1)

    def port(self, G, a, b, size=1.0):
        """Connector cutout on side face (USB-C / pogo / gland)."""
        wf, hf = 0.045 * size, 0.028 * size
        pts = [self.spt(G, a - wf, b - hf), self.spt(G, a + wf, b - hf),
               self.spt(G, a + wf, b + hf), self.spt(G, a - wf, b + hf)]
        self.poly(pts, fill="#0b0e12", stroke=INK, sw=0.8)
        mx, my = self.spt(G, a, b)
        self.circ(mx, my, 1.6 * size, fill="#2c3644", stroke="none")

    def solar(self, G, a0, a1, b0, b1):
        """Photovoltaic panel mapped onto the top face."""
        c = [self.tpt(G, a0, b0), self.tpt(G, a1, b0),
             self.tpt(G, a1, b1), self.tpt(G, a0, b1)]
        self.poly(c, fill="#122740", stroke=INK, sw=1)
        lerp = lambda p, q, t: (p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t)
        for i in range(1, 4):
            t = i / 4
            self.ln(*lerp(c[0], c[3], t), *lerp(c[1], c[2], t), "#33517c", 0.6)
        for i in range(1, 3):
            t = i / 3
            self.ln(*lerp(c[0], c[1], t), *lerp(c[3], c[2], t), "#33517c", 0.6)

    def whip(self, G, a, b, height=52):
        """Antenna whip rising from a top-face point."""
        x, y = self.tpt(G, a, b)
        self.ln(x, y, x, y - height, INK, 2.4)
        self.circ(x, y - height, 2.4, fill=INK)

    def cam(self, G, fxr, fyr, fr):
        """Camera module on front face."""
        x, y = self.fpt(G, fxr, fyr)
        r = fr * G["w"]
        self.circ(x, y, r, fill="#0d1117", stroke=INK, sw=1)
        self.circ(x, y, r * 0.55, fill="#1a2f4a", stroke="#3a5a86", sw=0.8)
        self.circ(x - r * 0.18, y - r * 0.18, r * 0.16, fill="#8fc0ea", stroke="none")

    def vents(self, G, fxr, fyr, fw, fh, n=5):
        """Slot vents on front face."""
        x, y = self.fpt(G, fxr, fyr)
        w, h = fw * G["w"], fh * G["h"]
        for i in range(n):
            yy = y + (i + 0.5) * h / n
            self.ln(x + 4, yy, x + w - 4, yy, INK, 2)

    def dock(self, G, fxr, fyr, fw, fh):
        """Recessed charging dock on front face with pogo pins."""
        x, y = self.fpt(G, fxr, fyr)
        w, h = fw * G["w"], fh * G["h"]
        self.rect(x, y, w, h, fill="#0b0f15", stroke=INK, sw=1.4, r=8)
        self.rect(x + 6, y + 6, w - 12, h - 12, fill="none", stroke=SOFT, sw=0.8, r=5)
        for i in range(4):
            self.circ(x + w * (0.32 + i * 0.12), y + h * 0.5, 3.4,
                      fill="#c9a227", stroke=INK, sw=0.6)

    def front_text(self, G, txt, fxr, fyr, size=10, color=None, spacing="2"):
        """Brand/logo text on front face."""
        x, y = self.fpt(G, fxr, fyr)
        self.t(x, y, txt, size, "middle", color or shade(G["color"], 0.4),
               "bold", spacing)

    def seam(self, G, fxr, fyr, fw, fh):
        """Door/panel seam rectangle on front face."""
        x, y = self.fpt(G, fxr, fyr)
        self.rect(x, y, fw * G["w"], fh * G["h"], fill="none",
                  stroke=shade(G["color"], 0.55), sw=1, dash="7 4")

    def swatch(self, x, y, w, h, color, label, sub=None):
        self.rect(x, y, w, h, fill=color, stroke=INK, sw=1)
        self.t(x + w / 2, y + h + 18, label, 12, "middle", weight="bold")
        if sub:
            self.t(x + w / 2, y + h + 34, sub, 10, "middle", SOFT)

    def callout(self, x1, y1, x2, y2, label, size=12):
        """Leader line from feature point to label."""
        self.ln(x1, y1, x2, y2, SOFT, 0.8)
        self.circ(x1, y1, 2.2, fill=INK)
        self.t(x2, y2 + 4, label, size, color=INK)

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
        wrapped = [[wrap(c, max(8, int(w / 6.4))) for c, w in zip(row, widths)]
                   for row in rows]
        heights = [max(rh, max(len(c) for c in cells) * 17 + 10)
                   for cells in wrapped]
        self.rect(x, y, total, rh + sum(heights), fill="none", stroke=INK, sw=1.2)
        cx = x
        for w, htxt in zip(widths, headers):
            self.t(cx + 7, y + rh - 8, htxt.upper(), hfs, weight="bold",
                   color=INK, spacing="0.5")
            cx += w
        self.ln(x, y + rh, x + total, y + rh, INK, 1.2)
        yy = y + rh
        for cells, rowh in zip(wrapped, heights):
            cx = x
            for cell, w in zip(cells, widths):
                for j, cl in enumerate(cell):
                    self.t(cx + 7, yy + 17 + j * 17, cl, fs)
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
    s.dimv(x0 - 26, y0, y0 + Dpx, "80")
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
    out.append(s.svg(1, 5))

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
    out.append(s.svg(2, 5))

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
    out.append(s.svg(3, 5))
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
    out.append(s.svg(1, 7))

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
    out.append(s.svg(2, 7))

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
    out.append(s.svg(3, 7))
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
    out.append(s.svg(1, 3))

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
    out.append(s.svg(2, 3))
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
    out.append(s.svg(1, 3))

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
    out.append(s.svg(2, 3))
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

    # capability set — left column, clears the title block (top edge y=896)
    s.h(ML + 10, 650, "CAPABILITY SET")
    s.table(ML + 10, 676, [280, 620], ["Capability", "Implementation"], [
        ["Mesh node", "SX1262 LoRa 915 + signed envelopes — every phone extends the network"],
        ["Satellite SOS", "L-band messenger module now; own constellation later"],
        ["Offline apps", "maps, manuals, forms, messaging EN/FR — useful with zero bars"],
        ["Cellular", "LTE Cat-1/4 when towers exist — proven path from L1"],
        ["Power", "replaceable battery + USB-C PD + solar trickle option"],
        ["Rugged", "IP68 · -30..+55 °C · glove UI · 1.5 m drop target"],
    ], rh=30)
    out.append(s.svg(1, 7))

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
    out.append(s.svg(2, 7))
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
    out.append(s.svg(1, 3))
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


# ============================================================ L1 ELECTRONICS ==
def l1_electronics():
    s = Sheet("AF-L1-104", "ELECTRONICS DETAIL",
              "SPI MAP · RF CONFIG · POWER SEQUENCING · LEVELS", "L1 · BRICK")

    s.h(ML + 10, 150, "SPI / BUS MAP")
    s.table(ML + 10, 172, [110, 170, 160, 90, 180],
            ["Bus", "Device", "Pins", "Speed", "Notes"], [
        ["SPI0", "E-Ink 7.5in", "GPIO 9/10/11 · CE0=8", "8 MHz", "Waveshare HAT default"],
        ["SPI0 ctrl", "busy / reset", "GPIO 25 / 17", "—", "poll BUSY before refresh"],
        ["SPI1", "SX1262 LoRa", "GPIO 16–19 · CE1=17?", "8 MHz", "dtoverlay=spi1-3cs"],
        ["SPI1 ctrl", "NSS/RST/BUSY/DIO1", "GPIO 20/21/22/23", "—", "DIO1 = RX interrupt"],
        ["I2C", "PMIC / sensors", "GPIO 2/3 (i2c_arm)", "400 kHz", "i2cdetect -y 1"],
        ["UART", "LTE modem", "USB CDC-ACM", "115200", "preferred — no GPIO cost"],
        ["GPIO", "SOS / LED", "GPIO 27 / 22", "—", "pull-up input / PWM out"],
    ], rh=32)

    s.h(ML + 10, 480, "SX1262 RADIO CONFIG (915 MHz ISM)")
    s.table(ML + 10, 502, [140, 190, 190, 190], ["Param", "Value", "Param", "Value"], [
        ["Frequency", "915–928 MHz", "Spreading factor", "SF7–SF12 (adaptive)"],
        ["Bandwidth", "125 kHz", "Coding rate", "4/5 – 4/8"],
        ["TX power", "+22 dBm max", "Preamble", "8 symbols"],
        ["CAD", "enabled", "CAD duration", "2 symbols"],
        ["Duty cycle", "<1% target", "CAD → RX window", "~200 ms"],
    ], rh=34)
    s.note(ML + 10, 716,
          "Mesh envelope = signed mesh-net frame (~200 B max). Broadcast beacon every "
          "30–60 s; unicast relay on demand. CRC + whitening on.", size=12)

    # power sequencing — right column
    px = 800
    s.h(px, 150, "POWER SEQUENCING")
    steps = [
        ("1 · BAT", "4×18650 → 14.8 V → 5 V buck 3 A"),
        ("2 · 5V RAIL", "fuse 5 A → CM5 USB-C PD"),
        ("3 · HATS", "LTE HAT 5 V · E-Ink 3V3 rail · LoRa 3V3"),
        ("4 · PERIPH", "LoRa EN · display reset · button pull-ups"),
    ]
    yy = 178
    for tag, desc in steps:
        s.rect(px, yy, 720, 46, fill=FILL, stroke=INK, sw=1.1)
        s.t(px + 14, yy + 20, tag, 13, weight="bold")
        s.t(px + 14, yy + 38, desc, 11, color=SOFT)
        if yy < 300:
            s.arrow(px + 360, yy + 46, px + 360, yy + 56)
        yy += 60
    s.note(px, 430,
          "All logic = 3V3. E-Ink needs 3V3+5V flash rails per Waveshare spec — "
          "HAT handles it. Never feed 5 V to SX1262.", size=12)

    s.h(px, 500, "LEVEL / SAFETY NOTES")
    s.bullets(px, 526, [
        "SX1262 = 1V8–3V6 supply, 3V3 logic — do NOT 5 V tolerate.",
        "LoRa NSS on GPIO20 conflicts nothing on spi1-3cs — verify DT overlay at boot.",
        "E-Ink BUSY must be polled — refresh takes 3–20 s depending on waveform.",
        "USB-C PD negotiates 5 V/3 A; barrel alternative = 14.8→5 V buck only.",
        "Static-safe layout: keep 915 MHz trace <30 mm, 50 Ω controlled.",
    ], width=88)

    s.h(ML + 10, 780, "BRING-UP ORDER")
    s.bullets(ML + 10, 806, [
        "1. Boot bare CM5 — SSH, i2cdetect, vcgencmd get_throttled.",
        "2. spi0 E-Ink — Waveshare python lib, show test pattern.",
        "3. spi1 SX1262 — send/recv test with second unit (or SDR).",
        "4. LTE HAT — AT init, signal query, data session.",
        "5. Agent — systemd up, /health green, acceptance test.",
    ], width=95)
    return s.svg(4, 4)


# ============================================================ L1 FINISH ======
def finish_sheet(dwg, title, subtitle, node, sheet_no, sheets_total,
                 renders, materials, finishes, notes):
    """Shared FINISH & MATERIALS sheet builder.
    renders: list of (iso-callable spec dict)
    materials: table rows [component, material, finish, note]
    finishes: list of (color_hex, name, sub) swatches
    notes: bullet list"""
    s = Sheet(dwg, "FINISH & MATERIALS — FINAL LOOK",
              subtitle, node, status="APPEARANCE REV A")

    # render zone: up to 2 product shots, centered in left ~950px
    rs = renders[:2]
    total_w = sum(r["w"] + r["d"] * 0.45 for r in rs) + (len(rs) - 1) * 90
    fx_cursor = 60 + max(0, (950 - total_w) / 2)
    for r in rs:
        cx = fx_cursor + r["w"] / 2
        cy = 300
        G = s.device(cx, cy, r["w"], r["h"], r["d"], r["color"],
                     r.get("top"), r.get("side"), r.get("rad", 14))
        for det in r.get("details", []):
            kind = det[0]
            if kind == "screen":
                s.screen(G, *det[1:6])
            elif kind == "rect":
                _, fxr, fyr, fw, fh = det[:5]
                fill = det[5] if len(det) > 5 else "none"
                txt = det[6] if len(det) > 6 else None
                rr = det[7] if len(det) > 7 else 4
                x, y = s.fpt(G, fxr, fyr)
                s.rect(x, y, fw * G["w"], fh * G["h"], fill=fill,
                       stroke=INK, sw=1, r=rr)
                if txt:
                    dark = fill in (None, "none")
                    s.t(x + fw * G["w"] / 2, y + fh * G["h"] / 2 + 4, txt, 10,
                         "middle", INK if dark else "#ffffff")
            elif kind == "circle":
                _, fxr, fyr, fd = det[:4]
                fill = det[4] if len(det) > 4 else "#c0392b"
                txt = det[5] if len(det) > 5 else None
                x, y = s.fpt(G, fxr, fyr)
                rad = fd * G["w"] / 2
                s.circ(x, y, rad, fill=fill, stroke=INK, sw=1)
                if txt:
                    s.t(x, y + rad * 0.35, txt, max(7, rad * 0.55), "middle",
                         "#ffffff", "bold")
            elif kind == "sidebtn":
                s.sidebtn(G, *det[1:5], color=det[5] if len(det) > 5 else None)
            elif kind == "port":
                s.port(G, *det[1:4])
            elif kind == "solar":
                s.solar(G, *det[1:5])
            elif kind == "whip":
                s.whip(G, *det[1:4])
            elif kind == "cam":
                s.cam(G, *det[1:4])
            elif kind == "vents":
                s.vents(G, *det[1:6])
            elif kind == "dock":
                s.dock(G, *det[1:5])
            elif kind == "logo":
                s.front_text(G, *det[1:5])
            elif kind == "seam":
                s.seam(G, *det[1:5])
        s.t(cx, cy + r["h"] / 2 + r["d"] * 0.42 + 34, r.get("caption", ""),
           12, "middle", SOFT)
        s.t(cx, cy + r["h"] / 2 + r["d"] * 0.42 + 54, r.get("sub", ""),
           10, "middle", SOFT)
        fx_cursor += r["w"] + r["d"] * 0.45 + 90

    s.h(ML + 10, 560, "COLOR / FINISH OPTIONS")
    for i, (col, name, sub) in enumerate(finishes):
        s.swatch(ML + 10 + i * 200, 590, 120, 60, col, name, sub)

    s.h(ML + 10, 720, "MATERIALS SPEC")
    s.table(ML + 10, 744, [190, 260, 190, 300],
            ["Component", "Material", "Finish", "Note"], materials, rh=30)

    # notes right column (clear of materials table which ends ~x990)
    s.h(1000, 570, "DESIGN NOTES")
    s.bullets(1000, 596, notes, width=75)
    return s.svg(sheet_no, sheets_total)


def l1_finish():
    return finish_sheet(
        "AF-L1-105", "L1 BRICK", "FINAL LOOK — COLOR, FINISH, MATERIALS",
        "L1 · BRICK", 5, 5,
        renders=[{
            "w": 600, "h": 200, "d": 120, "color": "#3a4148", "rad": 10,
            "caption": "L1 BRICK — REV A",
            "sub": "160 × 80 × 32 mm · ~450 g · matte textured",
            "details": [
                ("screen", 0.05, 0.14, 0.52, 0.60, "eink"),
                ("circle", 0.66, 0.28, 0.055, "#c0392b", "SOS"),
                ("circle", 0.66, 0.55, 0.018, "#5eead4", None),
                ("sidebtn", 0.55, 0.95, 0.34, 0.46),
                ("sidebtn", 0.55, 0.95, 0.52, 0.62),
                ("port", 0.50, 0.92, 1.2),
                ("whip", 0.16, 0.10, 58),
                ("whip", 0.84, 0.10, 58),
                ("logo", "ARCTICCHAIN", 0.5, 0.90, 9),
            ],
        }],
        materials=[
            ["Shell + tray", "PETG (or ASA -20°C)", "matte, 0.2 mm layers", "hand-printable, repairable"],
            ["Gasket/bezel", "TPU 95A", "soft-touch", "display window seal"],
            ["Fasteners", "M3 stainless + threadlock", "black oxide", "hand-tool service"],
            ["Labels", "laser-etched PET or engraved", "—", "no stickers — wipes clean"],
            ["Antenna", "SMA whip + u.fl", "rubber boot", "field-replaceable"],
        ],
        finishes=[
            ("#3a4148", "GRAPHITE", "default — hides dirt"),
            ("#c96a1e", "HI-VIS ORANGE", "search & rescue"),
            ("#e8e4da", "SAND", "desert/arid sites"),
        ],
        notes=[
            "Matte texture = glare-free in sun, hides scratches, better grip with gloves.",
            "Hi-vis orange variant mandatory for fire-season deployments.",
            "No painted logos — laser-etched 'ARCTICCHAIN · EMEBET INC.' on rear.",
            "Color does NOT change internals — same BOM, different filament only.",
            "Rev-B: soft-touch TPU overmold option for consumer feel.",
        ])


# ============================================================ MITE ELECTRONICS =
def mite_electronics():
    s = Sheet("AF-S-104", "CARRIER ELECTRONICS DETAIL",
              "BLOCK DIAGRAM · SLEEP DOMAINS · RF CHAIN", "S · MITE")

    # block diagram
    bx, by = ML + 10, 215
    s.h(bx, 130, "CARRIER BLOCK DIAGRAM (38×38 mm)")
    blocks = [
        (bx + 10, by, 170, 56, "ESP32-S3", "dual-core · LP-core sleep", "#dfe9f5"),
        (bx + 230, by - 75, 180, 52, "SX1262", "LoRa 915 · SPI", "#dfe9f5"),
        (bx + 230, by + 65, 180, 52, "ENS160+SHT41", "I2C · gas+env", "#dfe9f5"),
        (bx + 450, by - 35, 170, 56, "CN3791", "solar charge · MPPT", "#dfe9f5"),
        (bx + 660, by - 95, 160, 50, "LiPo 2000", "503450 · JST", "#f5e6d0"),
        (bx + 660, by + 55, 160, 56, "POGO DOCK", "2-pad + notch", "#dfe9f5"),
        (bx + 450, by + 95, 170, 50, "ANTENNA", "PCB meander / whip", "#dfe9f5"),
    ]
    for x, y, w, h, t1, t2, col in blocks:
        s.rect(x, y, w, h, fill=col, stroke=INK, sw=1.2)
        s.t(x + w / 2, y + h / 2 - 4, t1, 13, "middle", weight="bold")
        s.t(x + w / 2, y + h / 2 + 14, t2, 10, "middle", SOFT)
    # links
    s.arrow(bx + 180, by + 20, bx + 230, by - 40)
    s.arrow(bx + 180, by + 40, bx + 230, by + 90)
    s.ln(bx + 410, by - 10, bx + 450, by - 8, SOFT, 1)
    s.ln(bx + 620, by - 15, bx + 660, by - 60, SOFT, 1)
    s.ln(bx + 620, by + 83, bx + 660, by + 80, SOFT, 1)
    s.ln(bx + 535, by + 95, bx + 535, by + 150, SOFT, 1)
    s.ln(bx + 535, by + 150, bx + 740, by + 150, SOFT, 1)
    s.ln(bx + 740, by + 150, bx + 740, by + 111, SOFT, 1)
    s.note(bx, by + 185, "ESP32-S3 = brain · SX1262 = voice · sensors on shared I2C · "
         "charge path independent of compute", size=12)

    # sleep domains — left bottom
    s.h(bx, 470, "SLEEP DOMAINS (WHO STAYS ON)")
    s.table(bx, 494, [200, 320, 300], ["Domain", "State in deep sleep", "Wake source"], [
        ["ESP32-S3", "ULP RISC-V only", "RTC timer / GPIO"],
        ["SX1262", "sleep (~µA) + CAD armed", "DIO1 / host poll"],
        ["ENS160+SHT41", "power-gated OFF", "ESP32 rail control"],
        ["CN3791", "always (harvesting)", "— hardware"],
        ["RTC", "always", "32 kHz crystal"],
    ], rh=32)

    # RF + timing — right column
    rx = 900
    s.h(rx, 170, "RADIO & TIMING")
    s.table(rx, 194, [200, 340], ["Param", "Value"], [
        ["LoRa SF / BW", "SF7 / 125 kHz — short range bursts"],
        ["TX power", "+20 dBm (E22-900M30S)"],
        ["Antenna", "PCB meander 915 MHz or ¼-wave whip"],
        ["Sample", "every 5–10 min (temp/RH/VOC)"],
        ["Beacon", "every 60 min signed hello"],
        ["Anomaly TX", "immediate, then 5-min confirm"],
        ["CAD listen", "2 × 200 ms windows/hour"],
    ], rh=34)

    s.h(rx, 480, "WAKE-UP CHAIN")
    s.bullets(rx, 506, [
        "Solar voltage sense → wake when dawn charging starts.",
        "RTC alarm → periodic sense window.",
        "SX1262 CAD detect → swarm traffic wakes host.",
        "Dock pogo detect → charge mode + beacon boost.",
        "All wake sources logged — swarm energy is mesh data.",
    ], width=88)
    return s.svg(4, 7)


# ============================================================ MITE VARIANTS ====
def mite_variants():
    s = Sheet("AF-S-105", "SWARM VARIANTS — ROLE PAYLOADS",
              "ONE PLATFORM · FOUR ROLES · DIFFERENT BOM DELTAS", "S · MITE")

    s.h(ML + 10, 150, "VARIANT MATRIX")
    s.table(ML + 10, 178, [105, 240, 300, 175],
            ["Variant", "Payload delta", "Extra parts", "Cost / detection role"], [
        ["SENSOR-BEE", "ENS160 + SHT41 (base)", "— none —", "+$0 · primary gas/temp anomaly"],
        ["EYE-BEE", "thermal IR array (rev-C)", "AMG8833 or MLX90640 + lens", "+$25–45 · confirm fixes visually"],
        ["RELAY-BEE", "tall antenna, no sensors", "915 MHz whip 8 dBi", "+$8–15 · extend range over ridges"],
        ["CHARGER-BEE", "dock pads + charge LED", "2 pogo + indicator", "+$3–5 · perch at Anchor, rebroadcast"],
    ], rh=52)

    s.h(ML + 10, 480, "ROLE SELECTION LOGIC")
    s.bullets(ML + 10, 508, [
        "All variants share: ESP32-S3 + SX1262 + solar + LiPo + perch clip + mesh identity.",
        "Coordinator (Anchor/Brick) assigns role via signed command — soft state, self-heals.",
        "Fire season: 70% sensor-bees at fuel breaks, 20% relay on ridgelines, 10% chargers.",
        "Non-fire season: roles rotate to flood/snowpack/beetle surveillance automatically.",
        "Eye-bees are rev-C — thermal array needs carrier respin; sensor-bees fly first.",
    ], width=110)

    s.h(ML + 10, 720, "COST AT VOLUME (EST.)")
    s.table(ML + 10, 748, [200, 200, 200, 200], ["Volume", "Sensor", "Relay", "All variants blended"], [
        ["1–10 units", "$90–130 ea", "$95–140 ea", "≈$110 avg"],
        ["100 units", "$55–75 ea", "$60–80 ea", "≈$65 avg"],
        ["1,000 units", "$35–50 ea", "$38–55 ea", "≈$42 avg"],
        ["10,000+", "$20–30 ea", "$22–32 ea", "≈$25 avg — seed-drop economics"],
    ], rh=38)

    s.h(880, 150, "PHYSICAL DIFFERENCES")
    s.table(880, 178, [160, 460], ["Variant", "What changes physically"], [
        ["SENSOR-BEE", "base puck — solar window + gas vent membrane"],
        ["EYE-BEE", "domed IR window replaces solar center (rev-C)"],
        ["RELAY-BEE", "extended top mast, whip antenna, minimal face"],
        ["CHARGER-BEE", "bottom pogo pads exposed, dock-align notch"],
    ], rh=44)

    s.h(880, 480, "FIELD HIRING (HOW ROLES GET FILLED)")
    s.bullets(880, 510, [
        "Swarm joins mesh → coordinator reads capability flags.",
        "Gap analysis: coverage map × season threat model → role demand.",
        "Nearest capable unit gets signed role assignment.",
        "Unit confirms, adopts payload profile, reports ready.",
        "Reassignment on battery/sensor failure — automatic.",
    ], width=85)
    return s.svg(5, 7)


# ============================================================ MITE MECHANICAL =
def mite_mechanical():
    s = Sheet("AF-S-106", "MECHANICAL DETAIL",
              "PERCH CLIP SECTION · ENCLOSURE STACK · SEAL", "S · MITE")

    # perch clip section drawing
    vx, vy = 110, 160
    s.h(vx, vy - 40, "PERCH CLIP — SECTION")
    # clip profile: two jaws gripping a branch (circle)
    s.circ(vx + 180, vy + 130, 60, fill="none", stroke=SOFT, sw=1.2, dash="6 4")
    s.t(vx + 180, vy + 205, "BRANCH Ø10–40", 11, "middle", SOFT)
    # upper jaw
    s.poly([(vx + 60, vy + 40), (vx + 300, vy + 40), (vx + 300, vy + 90),
            (vx + 240, vy + 160), (vx + 120, vy + 160), (vx + 60, vy + 90)],
           fill=FILL, stroke=INK, sw=1.4)
    # lower jaw
    s.poly([(vx + 60, vy + 220), (vx + 300, vy + 220), (vx + 300, vy + 270),
            (vx + 240, vy + 200), (vx + 120, vy + 200), (vx + 60, vy + 270)],
           fill=FILL, stroke=INK, sw=1.4)
    # spring
    s.ln(vx + 180, vy + 90, vx + 180, vy + 200, INK, 3)
    s.t(vx + 180, vy + 30, "PUCK BODY 90×90×35", 12, "middle", weight="bold")
    s.t(vx + 180, vy + 290, "spring steel clip — tool-less snap", 11, "middle", SOFT)
    s.dimh(vx + 60, vx + 300, vy + 345, "90")

    # enclosure stack
    sx, sy = 620, 160
    s.h(sx, sy - 40, "ENCLOSURE STACK-UP")
    layers = [
        ("TOP LID — PC-ABS", "2.0 mm", "snap fit + gasket groove"),
        ("SOLAR WINDOW — PC film", "1.0 mm", "90% transmission, UV stable"),
        ("MAIN SHELL — ASA", "2.5 mm", "gas-permeable vent zone"),
        ("CARRIER PCB — FR4", "1.6 mm", "38×38, ENIG finish"),
        ("BATTERY BAY — PETG", "3.0 mm", "slide-in, JST access"),
    ]
    yy = sy
    for name, th, note in layers:
        s.rect(sx, yy, 380, 44, fill=FILL, stroke=INK, sw=1.1)
        s.t(sx + 12, yy + 19, name, 12, weight="bold")
        s.t(sx + 12, yy + 36, f"{th} — {note}", 10, color=SOFT)
        yy += 54
    s.note(sx, yy + 10, "Total Z ≈ 35 mm body + 10 mm clip = 45 mm field height.",
           size=12)

    # sealing + service
    gx = 1100
    s.h(gx, 160, "SEALING & SERVICE")
    s.table(gx, 184, [150, 420], ["Feature", "Detail"], [
        ["Gasket", "TPU bead around lid — IP65 splash"],
        ["Vent", "ePTFE membrane — gas exchange, no water"],
        ["Solar", "under-window film — replaceable"],
        ["Battery", "slide tray — swap in field, no tools"],
        ["PCB", "2× M2 screws — hand driver only"],
        ["Clip", "spring steel — replaceable spare"],
    ], rh=38)

    s.h(gx, 460, "DIMENSIONS")
    s.table(gx, 484, [150, 420], ["Dim", "Value"], [
        ["Body", "90 × 90 × 35 mm (L×W×H)"],
        ["Clip span", "Ø10–40 mm branch"],
        ["Weight", "~180 g with battery"],
        ["Solar cell", "62 × 62 mm active area"],
        ["Carrier PCB", "38 × 38 mm, 4-layer"],
        ["Operating", "-30..+60 °C (rev-A)"],
    ], rh=38)

    s.h(110, 560, "PERCH BEHAVIOR")
    s.bullets(110, 586, [
        "Clip grips branch/fence/rock — unit hangs vertically, solar faces up-ish.",
        "Wind-shake test: survives 60 km/h gusts on Ø25 mm branch.",
        "Perch sites chosen by mesh: fuel breaks, ridgelines, creek crossings.",
        "Docked variant (CHARGER-BEE) swaps clip for pogo alignment feet.",
    ], width=105)

    s.h(110, 800, "MANUFACTURING")
    s.bullets(110, 826, [
        "Shell/lid/bay: FDM print ASA or PC-ABS — or injection mold at volume.",
        "Clip: laser-cut 0.8 mm spring steel, powder-coated.",
        "Gasket: die-cut TPU sheet or printed-in-place.",
        "Carrier PCB: JLCPCB 4-layer ENIG — $15–30/pc at 10+.",
        "Assembly: hand-solderable — no BGA, no reflow oven needed.",
    ], width=105)
    return s.svg(6, 7)


# ============================================================ MITE FINISH =====
# ============================================================ MITE MISSIONS ====
def mite_missions():
    s = Sheet("AF-S-107", "MISSION PAYLOADS — MULTI-ROLE SWARM",
              "ONE CARRIER · SWAPPABLE MISSION PODS · SENSE · ACT · REACH",
              "S · MITE", rev="0", status="REV-C RESEARCH — SENSING FIRST")

    s.h(ML + 10, 150, "MISSION TAXONOMY")
    s.table(ML + 10, 178, [130, 270, 240, 160],
            ["Mission class", "Example payloads", "TRL / status", "Buyer"], [
        ["DETECT & MONITOR", "ENS160+SHT41, thermal IR, GPS, mic", "TRL 6–7 — prototype flies",
         "fire/ag/municipal"],
        ["ENVIRONMENTAL CLEANUP", "microplastic skimmer, sheen recovery, "
         "invasive pull/sever tool, debris grab", "TRL 2–3 — actuation R&D",
         "watershed/industry"],
        ["RESEARCH — REACH", "gas sampler, water sampler, stereo imager, "
         "contact sensor", "TRL 3–4 — payloads exist, miniaturize",
         "universities/parks"],
        ["TRANSPORT", "payload ferry between Anchors", "TRL 2 — concept",
         "remote ops/industry"],
    ], rh=58)

    s.note(ML + 10, 480,
          "Carrier is FIXED: ESP32-S3 + SX1262 + solar + perch + mesh identity. "
          "Mission pods hot-swap on the top bay — same open-bay philosophy as "
          "the ArcticPhone. A bee re-tasks by swapping a pod, not buying a new bee.",
          size=12)

    s.h(ML + 10, 560, "MISSION PODS (TOP-BAY MODULES)")
    s.table(ML + 10, 586, [170, 300, 300], ["Pod", "Hardware delta", "Notes"], [
        ["SENSE-POD", "ENS160 + SHT41 + mic + GPS", "base — every swarm needs this"],
        ["EYE-POD", "AMG8833/MLX90640 thermal + lens", "confirm fixes visually/thermally"],
        ["CLEAN-POD", "skimmer mesh / grabber / sever tool", "actuation — rev-C, gated"],
        ["LAB-POD", "gas+water sampler, pH/conductivity", "research missions — rev-C"],
        ["RELAY-POD", "8 dBi whip, sensors removed", "range extension over ridges"],
        ["CHARGE-POD", "dock pads + beacon", "Anchor perch — rebroadcast node"],
    ], rh=38)

    # right column — pod mechanics
    rx = 880
    s.h(rx, 150, "POD MECHANICS (TOP VIEW)")
    px, py = rx + 10, 190
    s.rect(px, py, 300, 270, fill=FILL, stroke=INK, sw=1.4, r=18)
    s.rect(px + 40, py + 40, 220, 140, fill="none", stroke=INK, sw=1.2, r=10, dash="8 4")
    s.t(px + 150, py + 108, "MISSION POD", 14, "middle", weight="bold")
    s.t(px + 150, py + 130, "pogo + guide pins", 10, "middle", SOFT)
    # carrier beneath
    s.rect(px + 60, py + 290, 180, 38, fill="#dfe9f5", stroke=INK, sw=1.2, r=8)
    s.t(px + 150, py + 313, "CARRIER (fixed)", 11, "middle", weight="bold")
    s.t(px + 150, py + 352, "pod face ~38×38 mm", 10, "middle", SOFT)

    s.h(rx, 560, "MISSION SEQUENCING")
    s.bullets(rx, 586, [
        "Coordinator reads swarm capability flags + threat model.",
        "Season map: fire → fuel breaks; melt → river corridors; "
        "spills → water patrol; research → unreachable sites.",
        "Pods pre-staged at Anchor — swap takes <60 s, hand tools only.",
        "Failed pod = bee reverts to SENSE-POD and keeps watching.",
        "Every mission logged on mesh — provenance for regulators.",
    ], width=80)

    s.h(rx, 790, "HONEST GATES")
    s.bullets(rx, 816, [
        "Sensing swarm flies FIRST — cleanup/research are payload programs.",
        "Actuation payloads need their own safety review + pilot funding.",
        "No promise of cleanup before the sensing mechanism is proven.",
        "Transport is the furthest horizon — listed for platform completeness.",
    ], width=80, color=RED)
    return s.svg(7, 8)


def mite_finish():
    return finish_sheet(
        "AF-S-108", "S MITE", "FINAL LOOK — SWARM UNIT APPEARANCE",
        "S · MITE", 8, 8,
        renders=[{
            "w": 340, "h": 340, "d": 95, "color": "#4a6741", "rad": 16,
            "caption": "S MITE — SENSOR-BEE",
            "sub": "90 × 90 × 35 mm · ~180 g · forest camouflage",
            "details": [
                ("solar", 0.10, 0.90, 0.14, 0.82),
                ("circle", 0.50, 0.55, 0.045, "#22301f", None),
                ("circle", 0.50, 0.55, 0.018, "#5eead4", None),
                ("vents", 0.40, 0.68, 0.20, 0.10, 4),
                ("whip", 0.88, 0.16, 34),
                ("sidebtn", 0.50, 0.95, 0.30, 0.42),
            ],
        }],
        materials=[
            ["Shell", "ASA or PC-ABS", "matte — forest tones", "UV stable, -30 °C"],
            ["Solar", "poly cell + PC window", "anti-reflective", "replaceable film"],
            ["Gasket", "TPU bead", "—", "IP65 splash"],
            ["Clip", "spring steel 0.8 mm", "olive drab powder-coat", "field spare"],
            ["Labels", "laser-etched ID", "—", "swarm serial + role"],
        ],
        finishes=[
            ("#4a6741", "FOREST", "default — blends in"),
            ("#8a8f6a", "SAGE", "arid grassland"),
            ("#c96a1e", "HI-VIS", "training/retrieval"),
        ],
        notes=[
            "Forest green is deliberate — swarm should disappear into canopy.",
            "Hi-vis variant ONLY for bench testing and recovery ops.",
            "Solar window slightly recessed — survives branch strikes.",
            "Role variants share shell — only top insert + antenna differ.",
            "No logos on top face — solar area is sacred.",
        ])


# ============================================================ TOTEM FINISH =====
def totem_finish():
    return finish_sheet(
        "AF-E-103", "E TOTEM", "FINAL LOOK — COMMUNITY BOARD APPEARANCE",
        "E · TOTEM", 3, 3,
        renders=[{
            "w": 520, "h": 340, "d": 110, "color": "#2e3a45", "rad": 8,
            "caption": "E TOTEM — FRONT",
            "sub": "~320 × 220 × 100 mm box on 3 m pole · IP66",
            "details": [
                ("screen", 0.08, 0.10, 0.84, 0.64, "eink"),
                ("vents", 0.10, 0.80, 0.26, 0.13, 4),
                ("circle", 0.84, 0.86, 0.022, "#5eead4", None),
                ("whip", 0.78, 0.80, 64),
                ("port", 0.50, 0.94, 1.4),
                ("logo", "COMMUNITY BOARD", 0.5, 0.955, 9, "#8fa3b5"),
            ],
        }],
        materials=[
            ["Enclosure", "polycarbonate IP66 box", "texture, UV stable", "Bud Industries class"],
            ["Display", "E-Ink 13.3in + window film", "matte anti-glare", "sunlight readable"],
            ["Pole", "galvanized steel / treated wood", "powder-coat charcoal", "community install"],
            ["Gasket", "silicone continuous bead", "—", 'IP66 "driving rain"'],
            ["Labels", "vinyl-cut bilingual", "reflective", "EN/FR community ID"],
        ],
        finishes=[
            ("#2e3a45", "CHARCOAL", "default civic color"),
            ("#1e4634", "FOREST", "park/natural areas"),
            ("#7a2d2d", "COMMUNITY RED", "custom per community"),
        ],
        notes=[
            "Charcoal powder-coat hides fingerprints and 10-year weathering.",
            "Community name + nation badge on lower bezel — vinyl, field-replaceable.",
            "Display window recessed 8 mm — survives thrown objects, hockey pucks.",
            "Totem IS the landmark — finish should read 'public infrastructure', not gadget.",
            "Solar panel separate, same charcoal frame — visual unity.",
        ])


# ============================================================ ANCHOR FINISH =====
def anchor_finish():
    return finish_sheet(
        "AF-A-103", "A ANCHOR", "FINAL LOOK — CHARGING STATION APPEARANCE",
        "A · ANCHOR", 3, 3,
        renders=[{
            "w": 460, "h": 320, "d": 120, "color": "#37424e", "rad": 8,
            "caption": "A ANCHOR — STATION",
            "sub": "~350 × 250 × 400 mm · solar array separate · IP65",
            "details": [
                ("seam", 0.06, 0.06, 0.88, 0.82),
                ("rect", 0.10, 0.10, 0.34, 0.36, "#22303c", "COMPUTE", 4),
                ("rect", 0.50, 0.10, 0.36, 0.36, "#22303c", "RADIOS", 4),
                ("dock", 0.30, 0.60, 0.40, 0.26),
                ("circle", 0.76, 0.66, 0.014, "#5eead4", None),
                ("circle", 0.76, 0.74, 0.014, "#e8b13c", None),
                ("circle", 0.76, 0.82, 0.014, "#c0392b", None),
                ("vents", 0.72, 0.14, 0.22, 0.34, 6),
                ("whip", 0.50, 0.45, 72),
                ("port", 0.30, 0.94, 1.6),
                ("port", 0.70, 0.94, 1.2),
            ],
        }],
        materials=[
            ["Cabinet", "powder-coated steel IP65", "texture charcoal", "field-replaceable panels"],
            ["Solar", "anodized Al frame + poly", "anti-reflective", "ground/pole mount"],
            ["Dock", "gold-plated pogo + PBT", "—", "self-cleaning tips"],
            ["Battery", "LiFePO4 rack", "—", "swappable brick"],
            ["Labels", "engraved SS plate", "—", "weatherproof ID"],
        ],
        finishes=[
            ("#37424e", "CHARCOAL", "default — utility look"),
            ("#4a6741", "FOREST", "wildland sites"),
            ("#8a6d3b", "SAFETY YELLOW", "airfield/industrial"),
        ],
        notes=[
            "Anchor is infrastructure — finish reads 'utility cabinet', survives decades.",
            "Dock contacts gold-plated — 10k mate cycles, self-wiping on landing.",
            "Battery bay front-access — swap in <15 min with hand tools.",
            "Status LED visible 100 m — green mesh-up, amber degraded, red fault.",
            "No sharp edges anywhere — glove + branch contact safe.",
        ])


# ============================================================ PHONE: SPECIAL =====
def phone_definition():
    s = Sheet("AF-P-103", "PRODUCT DEFINITION — WHY IT STANDS OUT",
              "THE ONLY PHONE THAT IS A CITIZEN OF YOUR COMMUNITY'S NETWORK",
              "P · ARCTICPHONE", rev="0", status="CONCEPT — NOT FROZEN")

    s.h(ML + 10, 150, "THE ONE-LINE PITCH")
    s.t(ML + 10, 190, "“A phone that joins YOUR network — not just the carrier's.”", 22, weight="bold")
    s.t(ML + 10, 224, "Every ArcticPhone is a mesh node, a repeater, a satellite SOS beacon, "
       "and an offline-first computer — in one rugged, repairable, community-owned device.",
       14, color=SOFT)

    s.h(ML + 10, 300, "SIX THINGS NO OTHER PHONE DOES")
    s.table(ML + 10, 328, [40, 280, 640], ["#", "Feature", "Why it matters"], [
        ["1", "TRI-RADIO", "LoRa mesh + LTE + satellite — three independent paths; at least one always works"],
        ["2", "EVERY PHONE A REPEATER", "each unit extends coverage for the next — density IS the network"],
        ["3", "SATELLITE SOS STANDARD", "one hardware key press reaches help anywhere on Earth — not an accessory, a core feature"],
        ["4", "OFFLINE DIGNITY SUITE", "maps, manuals, forms, messaging, notices — fully useful with zero bars"],
        ["5", "COMMUNITY SYNC", "Totem public boards push to your phone; your posts can reach the Totem"],
        ["6", "REPAIRABLE BY DESIGN", "screws not glue, standard connectors, a local tech fixes it with hand tools"],
    ], rh=46)

    s.h(ML + 10, 672, "VS THE ALTERNATIVES")
    s.table(ML + 10, 700, [140, 120, 120, 120, 120, 120],
            ["Need", "Smartphone", "Rugged phone", "Sat messenger", "Mesh radio", "ARCTICPHONE"], [
        ["Cellular calls", "✓", "✓", "—", "—", "✓"],
        ["Works with no towers", "—", "—", "✓", "✓", "✓"],
        ["Satellite SOS", "app only", "—", "✓", "—", "✓ built-in"],
        ["Extends a network", "—", "—", "—", "✓", "✓"],
        ["Offline apps", "partial", "partial", "—", "—", "✓ full"],
        ["Repairable", "glue", "screws", "sealed", "—", "screws"],
        ["Community-owned", "carrier", "carrier", "corporate", "DIY", "community"],
    ], rh=34)

    s.h(880, 300, "THE MOAT — WHY IT COMPOUNDS")
    s.bullets(880, 330, [
        "Network effect: every phone sold adds a repeater — the 100th user has "
        "better coverage than the 1st. Competitors can't copy deployed density.",
        "Community ownership: the mesh belongs to the town, not a carrier — "
        "that's a procurement argument AND a loyalty argument.",
        "Data stays home: messages route community mesh first — sovereignty "
        "is a feature regulators and communities both want.",
        "Module ecosystem: open bay spec → third parties build sat, thermal, "
        "battery modules → platform, not product.",
        "The phone is the user terminal for the whole ArcticChain stack — "
        "mesh, swarm, Totem, satellites. One device, the entire ecosystem.",
    ], width=80)

    s.h(880, 640, "WHAT IT IS NOT")
    s.bullets(880, 668, [
        "NOT a smartphone killer — it's for places smartphones fail.",
        "NOT a Starlink terminal — L-band messenger class for SOS/short messages.",
        "NOT a toy mesh radio — it's certified cellular + satellite + mesh, carrier-grade.",
        "NOT locked to one community — joins any ArcticChain mesh, carries identity.",
    ], width=80)
    return s.svg(3, 7)


def phone_triradio():
    s = Sheet("AF-P-104", "TRI-RADIO ARCHITECTURE",
              "LoRa MESH + LTE + SATELLITE — ANTENNAS · COEXISTENCE · FAILOVER",
              "P · ARCTICPHONE", rev="0", status="CONCEPT — NOT FROZEN")

    # radio blocks
    s.h(ML + 10, 150, "RADIO BLOCKS")
    radios = [
        (ML + 10, "MESH — SX1262", "LoRa 915 MHz", "0.3–50 kbps", "5–15 km LOS", "~50 mW", "#dfe9f5"),
        (ML + 310, "CELLULAR — LTE Cat-4", "B1/2/5/13/66", "50–150 Mbps", "tower range", "~1–2 W", "#dfe9f5"),
        (ML + 610, "SATELLITE — L-band", "Iridium Certus class", "~22 kbps", "global", "~3–5 W", "#f5e6d0"),
    ]
    for x, t1, t2, t3, t4, t5, col in radios:
        s.rect(x, 178, 280, 120, fill=col, stroke=INK, sw=1.3)
        s.t(x + 14, 208, t1, 14, weight="bold")
        s.t(x + 14, 230, t2, 12)
        s.t(x + 14, 252, t3, 11, color=SOFT)
        s.t(x + 14, 274, t4, 11, color=SOFT)
        s.t(x + 14, 292, t5, 10, color=SOFT)
    s.note(ML + 10, 320, "All three share the SoC via SDIO/UART — coexistence filtering "
         "required: cellular fundamental can desense LoRa.", size=12)

    # antenna layout — phone outline
    s.h(1000, 140, "ANTENNA LAYOUT (TARGET)")
    px_, py_ = 1050, 210
    s.rect(px_, py_, 180, 350, fill=FILL, stroke=INK, sw=1.5, r=18)
    s.rect(px_ + 12, py_ + 24, 156, 290, fill="none", stroke=SOFT, sw=0.8, r=6)
    s.t(px_ + 90, py_ + 175, "DISPLAY", 12, "middle", SOFT)
    # antennas
    s.ln(px_ + 40, py_, px_ + 40, py_ - 40, INK, 3)      # top whip
    s.ln(px_ + 140, py_, px_ + 140, py_ - 40, INK, 3)    # top whip 2
    s.t(px_ + 48, py_ - 14, "LoRa", 10, "start", SOFT)
    s.t(px_ + 148, py_ - 14, "LTE", 10, "start", SOFT)
    s.rect(px_ + 30, py_ + 318, 120, 8, fill=ACC)        # bottom L-band strip
    s.t(px_ + 90, py_ + 344, "L-band PIFA (bottom edge)", 10, "middle", SOFT)
    s.t(px_ + 90, py_ + 368, "GPS/BT: ceramic patch rear", 10, "middle", SOFT)

    # coexistence + failover
    s.h(ML + 10, 400, "COEXISTENCE & FAILOVER")
    s.table(ML + 10, 428, [180, 300, 340], ["Scenario", "Radio used", "Behavior"], [
        ["In community mesh range", "LoRa primary", "calls/texts route peer-to-peer signed"],
        ["No mesh, cell exists", "LTE", "normal cellular + mesh backhaul opportunistic"],
        ["No cell, no mesh", "L-band sat", "SOS + short messages only (22 kbps)"],
        ["All three present", "mesh→LTE→sat priority", "mesh for local, LTE for internet, sat reserved SOS"],
        ["Simultaneous TX", "TDM scheduler", "cellular TX pauses LoRa RX windows"],
    ], rh=44)

    s.h(ML + 10, 700, "LINK BUDGET (LoRa, typical)")
    s.table(ML + 10, 728, [200, 170, 170, 200], ["Path", "Range", "Data", "Use"], [
        ["Phone ↔ phone", "1–3 km", "text/voice-meta", "direct mesh call"],
        ["Phone ↔ Brick/Totem", "3–10 km", "notices/data", "community services"],
        ["Phone ↔ Anchor", "5–15 km", "backhaul relay", "reach the gateway"],
        ["Phone ↔ satellite", "global", "22 kbps", "SOS + telemetry only"],
    ], rh=38)

    s.h(880, 640, "WHY TRI-RADIO WINS")
    s.bullets(880, 668, [
        "Single-radio phones fail exactly where they're needed — no towers, "
        "no mesh, no service. Three radios = three independent lifelines.",
        "LoRa mesh is FREE — unlicensed 915 MHz, zero carrier cost, community-owned.",
        "LTE is familiar — works today, every Canadian knows it.",
        "L-band sat is the insurance policy — works at the cabin, the fire line, "
        "the North. SOS doesn't care about coverage maps.",
        "Failover is automatic and signed — the network decides, user just talks.",
    ], width=82)
    return s.svg(4, 7)


def phone_modules():
    s = Sheet("AF-P-105", "EXPANSION MODULES — THE OPEN BAY",
              "SWAPPABLE MISSION MODULES · POGO + GUIDE PINS · SIGNED AUTH",
              "P · ARCTICPHONE", rev="0", status="CONCEPT — NOT FROZEN")

    s.h(ML + 10, 150, "MODULE BAY SPEC (TARGET)")
    s.table(ML + 10, 178, [150, 300, 200, 200, 160],
            ["Module", "Function", "Interface", "Power", "Est. cost"], [
        ["SAT-TERM", "full Iridium/Globalstar terminal", "USB3 + pogo", "5 V 2 A", "$80–150"],
        ["THERMAL", "FLIR Lepton-class camera", "MIPI + pogo", "5 V 1 A", "$120–250"],
        ["EXT-BATT", "second 4000 mAh cell", "pogo charge", "pass-through", "$25–40"],
        ["LORA-BOOST", "external antenna + PA", "U.FL + pogo", "5 V 0.5 A", "$15–30"],
        ["E-INK DOCK", "public display accessory", "SPI + pogo", "5 V 1 A", "$40–80"],
        ["STORAGE", "1 TB encrypted card", "microSD slot", "—", "$50–90"],
        ["CUSTOM", "third-party open spec", "pogo + USB-C", "5 V ≤2 A", "open"],
    ], rh=40)

    # bay mechanical — phone rear view
    s.h(880, 150, "BAY MECHANICS (REAR VIEW)")
    bx, by = 950, 190
    s.rect(bx, by, 200, 380, fill=FILL, stroke=INK, sw=1.5, r=18)
    s.rect(bx + 30, by + 40, 140, 300, fill="none", stroke=INK, sw=1.2, r=8, dash="8 4")
    s.t(bx + 100, by + 190, "MODULE BAY", 13, "middle", weight="bold")
    # pogo pins
    for i in range(6):
        s.circ(bx + 55 + i * 18, by + 350, 4, fill=ACC)
    s.t(bx + 100, by + 372, "6× pogo (pwr/gnd/SPI/I2C/ID)", 9, "middle", SOFT)
    # guide pins
    s.circ(bx + 45, by + 60, 5, fill="none", stroke=INK, sw=1.2)
    s.circ(bx + 155, by + 60, 5, fill="none", stroke=INK, sw=1.2)
    s.t(bx + 100, by + 30, "guide pins + captive screws", 10, "middle", SOFT)
    s.t(bx + 100, by + 420, "hot-swap? NO — power down to change", 10, "middle", SOFT)
    s.t(bx + 100, by + 440, "signed module auth on insert", 10, "middle", SOFT)

    s.h(ML + 10, 560, "MODULE AUTH & SAFETY")
    s.bullets(ML + 10, 590, [
        "Each module carries signed ID — phone verifies before enabling power.",
        "Power budget enforced: module draws only within its rated envelope.",
        "Thermal/current foldback — a bad module can't cook the phone.",
        "Open spec published — third parties can build modules (revenue share).",
        "Modules are field-swappable with one screwdriver — 60-second change.",
    ], width=105)

    s.h(ML + 10, 780, "ECOSYSTEM PLAY")
    s.bullets(ML + 10, 808, [
        "Phase 1: first-party modules (sat, thermal, battery).",
        "Phase 2: certified partners — ag sensors, medical, survey gear.",
        "Phase 3: open marketplace — community-built modules.",
        "Every module is a node accessory — extends the mesh's reach.",
        "This is how a phone becomes a PLATFORM — the moat compounds.",
    ], width=105)
    return s.svg(5, 7)


def phone_ux():
    s = Sheet("AF-P-106", "FIELD UX — DESIGNED FOR GLOVES & ZERO BARS",
              "SOS CHAIN · MESH DASHBOARD · OFFLINE SUITE · NOTICES",
              "P · ARCTICPHONE", rev="0", status="CONCEPT — NOT FROZEN")

    s.h(ML + 10, 150, "SOS CHAIN — ONE KEY, EVERY PATH")
    s.bullets(ML + 10, 180, [
        "Physical SOS key (dedicated, glove-proof, hardware interrupt — not software).",
        "Press → phone broadcasts signed SOS on mesh → nearest node relays.",
        "If no mesh ack in 30 s → escalate to LTE data.",
        "If no LTE → satellite messenger sends GPS + vitals packet.",
        "Responder sees: identity, GPS, battery, mesh path taken — full provenance.",
        "Works upside-down, wet, -30 °C, screen cracked — hardware path only.",
    ], width=105)

    s.h(ML + 10, 400, "MESH DASHBOARD (LIVE)")
    s.table(ML + 10, 428, [200, 400], ["Metric", "What user sees"], [
        ["Coverage bubble", "your mesh range on a local map — live, offline"],
        ["Node count", "how many phones/bridges repeat your signal right now"],
        ["Message latency", "mesh vs LTE vs sat — which path carried your last msg"],
        ["Mesh score", "your contribution — messages relayed, hours online"],
        ["Community notices", "Totem board content synced to phone"],
    ], rh=38)

    s.h(ML + 10, 690, "OFFLINE DIGNITY SUITE")
    s.table(ML + 10, 716, [200, 400], ["App", "Offline capability"], [
        ["Maps", "full regional maps pre-loaded — routing without bars"],
        ["Manuals", "equipment/service docs — searchable, no data"],
        ["Forms", "government/clinic/ag forms — fill, sign, queue to send"],
        ["Messaging", "mesh SMS between phones — store-and-forward"],
        ["Notices", "community bulletin — Totem content cached"],
        ["Camera", "photos tagged GPS — queue upload when backhaul returns"],
    ], rh=36)

    s.h(880, 150, "GLove-FIRST HARDWARE")
    s.table(880, 178, [160, 460], ["Element", "Design choice"], [
        ["SOS key", "dedicated hardware button, 3 mm travel, textured"],
        ["Display", "transflective — readable in sun, low power"],
        ["UI", "high contrast, large targets, haptic confirm"],
        ["Buttons", "3 physical (vol/PAN) + SOS — no touchscreen-only"],
        ["Audio", "loud speaker + mic — works with mask/glove"],
        ["Charging", "USB-C + pogo — one-hand dock charge"],
    ], rh=42)

    s.h(880, 480, "COMMUNITY INTEGRATION")
    s.bullets(880, 510, [
        "Phone joins community mesh automatically on first boot — "
        "no carrier account needed for mesh service.",
        "Community admin sees node health (opt-in) — coverage gaps visible.",
        "Totem public boards sync notices to phones within range.",
        "Your posts can go to the Totem — community bulletin from your pocket.",
        "Data sovereignty: mesh traffic stays on community infrastructure "
        "unless explicitly routed out.",
        "EN/FR UI throughout — language is a first-class setting.",
    ], width=82)

    s.h(880, 760, "BATTERY & POWER UX")
    s.bullets(880, 788, [
        "Replaceable battery — swap in field with one tool, no adhesive.",
        "USB-C PD fast charge — 0→80% in ~45 min.",
        "Solar trickle mode — leaves on dash, gains ~10%/day.",
        "Ultra-low-power standby — 30 days standby on mesh listen.",
        "Battery health shown — honest capacity, not fake percentages.",
    ], width=82)
    return s.svg(6, 7)


def phone_finish():
    return finish_sheet(
        "AF-P-107", "P ARCTICPHONE", "FINAL LOOK — RURAL PHONE APPEARANCE",
        "P · ARCTICPHONE", 7, 7,
        renders=[{
            "w": 175, "h": 330, "d": 20, "color": "#2b3440", "rad": 16,
            "caption": "P ARCTICPHONE — FRONT",
            "sub": "~145 × 72 × 14 mm · ~220 g · IP68",
            "details": [
                ("rect", 0.36, 0.018, 0.13, 0.014, "#0d1117", None, 3),
                ("cam", 0.62, 0.030, 0.028),
                ("screen", 0.05, 0.055, 0.90, 0.90, "lcd"),
                ("sidebtn", 0.55, 0.97, 0.22, 0.34),
                ("sidebtn", 0.55, 0.97, 0.38, 0.50),
                ("sidebtn", 0.55, 0.97, 0.55, 0.74, "#c0392b"),
                ("port", 0.5, 0.985, 0.9),
            ],
        }, {
            "w": 175, "h": 330, "d": 20, "color": "#2b3440", "rad": 16,
            "caption": "REAR — MODULE BAY",
            "sub": "bay covers 40% of rear — hot-swap modules",
            "details": [
                ("cam", 0.13, 0.075, 0.045),
                ("seam", 0.14, 0.16, 0.72, 0.62),
                ("rect", 0.17, 0.20, 0.66, 0.50, "#222b36", None, 8),
                ("circle", 0.5, 0.62, 0.028, "#c9a227", None),
                ("circle", 0.30, 0.685, 0.012, "#8fa3b5", None),
                ("circle", 0.42, 0.685, 0.012, "#8fa3b5", None),
                ("circle", 0.58, 0.685, 0.012, "#8fa3b5", None),
                ("circle", 0.70, 0.685, 0.012, "#8fa3b5", None),
                ("logo", "ARCTICPHONE", 0.5, 0.93, 8, "#8fa3b5"),
            ],
        }],
        materials=[
            ["Chassis", "polycarbonate + TPU bumpers", "textured matte", "IP68 sealed"],
            ["Display", "transflective LCD 5–6in", "anti-glare", "sunlight + gloves"],
            ["Buttons", "silicone overlay + metal", "tactile 3mm", "glove-proof"],
            ["Antenna", "LDS laser-direct structuring", "—", "no external whips needed"],
            ["Bay cover", "PC + TPU gasket", "thumb-screw", "tool-light swap"],
        ],
        finishes=[
            ("#2b3440", "GRAPHITE", "default — professional"),
            ("#3d5a45", "FOREST", "field/rural identity"),
            ("#c96a1e", "HI-VIS", "SAR / search roles"),
        ],
        notes=[
            "Rugged but NOT ugly — matte graphite reads 'serious tool', not 'military'.",
            "Bumper corners absorb 1.5 m drops onto gravel — replaceable.",
            "Module bay cover is the visual signature — slightly raised, thumb screw.",
            "Transflective display: readable in sun WITHOUT backlight — days of battery.",
            "No glass back — polycarbonate shrugs off drops and cold.",
            "Color options are filament/finish only — same internal BOM.",
        ])


# ============================================================ SEED MATERIALS ===
def seed_materials():
    s = Sheet("AF-D-102", "MATERIALS STACK & DEGRADATION",
              "WHAT THE MOTE IS MADE OF — AND HOW IT DISAPPEARS", "D · SEED",
              rev="0", status="RESEARCH — NOT A PRODUCT")

    s.h(ML + 10, 150, "MATERIALS STACK (TARGET)")
    s.table(ML + 10, 178, [130, 240, 240, 190], ["Layer", "Candidate material", "Function", "Degradation"], [
        ["Substrate", "cellulose paper / silk fibroin", "structure + insulation", "weeks–months in moisture"],
        ["Electronics", "printed Zn/MnO₂ + organic TFT", "compute + sensing", "dissolves with substrate"],
        ["Energy", "printed PV / TEG / RF harvest", "µW power", "encapsulated, degrades slowly"],
        ["Comms", "backscatter or LoRa wake", "rare TX bursts", "antenna dissolves last"],
        ["Encapsulant", "shellac / protein coating", "weather protection", "months — timed release"],
        ["Seed pod", "compressed fiber + nutrient", "germination trigger", "sprouts sensor on moisture"],
    ], rh=46)

    s.h(ML + 10, 510, "DEGRADATION TIMELINE")
    tl = [("0–2 mo", "ACTIVE", "sensing + reporting season", "#dfe9f5"),
          ("2–6 mo", "DORMANT", "low-power sentinel, minimal TX", "#f5e6d0"),
          ("6–12 mo", "DEGRADING", "encapsulant fails, electronics dissolve", "#f0d0d0"),
          ("12+ mo", "GONE", "biodegraded residue — no e-waste", "#d0e8d0")]
    xx = ML + 10
    for i, (t, phase, desc, col) in enumerate(tl):
        bx = xx + i * 205
        s.rect(bx, 552, 185, 68, fill=col, stroke=INK, sw=1.2)
        s.t(bx + 92, 580, t, 14, "middle", weight="bold")
        s.t(bx + 92, 600, phase, 11, "middle", weight="bold")
        s.t(bx + 92, 619, desc, 9, "middle", SOFT)
        if i < 3:
            s.arrow(bx + 185, 586, bx + 205, 586, SOFT)

    s.h(ML + 10, 660, "WHY DEGRADABLE MATTERS")
    s.bullets(ML + 10, 690, [
        "Fire season is seasonal — permanent sensors waste 11 months of their life.",
        "Degradable motes match the threat's rhythm: deploy, serve, vanish.",
        "No retrieval mission, no e-waste in wilderness, no environmental liability.",
        "Seed-drop economics: $0.10–1.00/mote at volume vs $100+ for durable nodes.",
        "Residue is cellulose/protein — composts in the forest it monitored.",
    ], width=110)

    s.h(880, 150, "MANUFACTURING PATHWAY")
    s.table(880, 178, [160, 440], ["Stage", "Process"], [
        ["Printed electronics", "inkjet/aerosol jet — Zn, carbon, dielectric inks"],
        ["Substrate", "cellulose sheet or silk fibroin cast"],
        ["Energy", "printed battery (Zn/MnO₂) or RF harvest coil"],
        ["Assembly", "roll-to-roll print + singulate — no pick-and-place"],
        ["Seed pod", "compressed fiber pellet — moisture germinates"],
    ], rh=44)

    s.h(880, 460, "PRECEDENT / FUNDING")
    s.bullets(880, 490, [
        "DARPA/NSF 'computational dust' programs — real funded research.",
        "Transient electronics groups (UIUC, Northwestern, ETH) publish weekly.",
        "SR&ED eligible — Canadian research tax credit covers 35%+.",
        "University partners: materials science + EE joint projects.",
    ], width=82)

    s.h(880, 680, "HONEST GAPS")
    s.bullets(880, 710, [
        "No working ArcticChain mote exists — this is a research brief.",
        "Printed batteries at µW scale are lab-grade, not field-grade.",
        "LoRa radios don't degrade — antenna/comms is the hard part.",
        "Cluster heads must be durable — motes feed THEM, not the backbone.",
        "Gate: lab demo (temp + 10 m report) before ANY field promise.",
    ], width=82, color=RED)
    return s.svg(2, 3)


def seed_protocol():
    s = Sheet("AF-D-103", "CLUSTER NETWORK PROTOCOL",
              "HOW BILLIONS OF MOTES TALK — HIERARCHY · DUTY CYCLE · WIRELESS POWER",
              "D · SEED", rev="0", status="RESEARCH — NOT A PRODUCT")

    s.h(ML + 10, 150, "NETWORK HIERARCHY")
    s.table(ML + 10, 178, [160, 300, 340], ["Tier", "Role", "Count / density"], [
        ["Motes", "sense temp/RH/VOC — never talk to backbone", "thousands–millions per km²"],
        ["Cluster heads", "aggregate mote data, relay to backbone", "1 per ~100 motes"],
        ["Backbone", "Anchor/Brick/LTE/sat — the real mesh", "existing fleet"],
    ], rh=44)
    s.note(ML + 10, 360,
          "Motes don't each shout — they whisper to their cluster head. Density is free; "
          "backhaul is precious. Same pattern as satellite constellations.", size=12)

    s.h(ML + 10, 430, "DUTY CYCLE — ENERGY BUDGET")
    s.table(ML + 10, 458, [200, 160, 160, 240], ["State", "Current", "Duty", "Notes"], [
        ["Deep sleep", "~1 µA", "~98%", "printed RTC + wake source"],
        ["Sense window", "~50 µA", "~1.5%", "10 s every 10 min"],
        ["Local TX (to head)", "~5 mA burst", "~0.5%", "LoRa or backscatter"],
        ["Harvest", "solar/TEG/RF", "continuous", "µW average suffices"],
    ], rh=38)

    s.h(ML + 10, 700, "WAKE-UP METHODS (NO RTC CRYSTAL NEEDED)")
    s.bullets(ML + 10, 730, [
        "Solar voltage threshold — dawn wakes the field.",
        "Wake-on-radio — cluster head pings, motes respond.",
        "Vibration/seismic — fire/vehicle triggers sense window.",
        "Chemical timer — printed RC slow-release wake.",
        "Anomaly escalation — mote detects → wakes neighbors to confirm.",
    ], width=105)

    # protocol diagram right
    rx = 880
    s.h(rx, 150, "DATA FLOW")
    flow = [
        ("MOTES ×1000", "temp/RH/VOC every 10 min", "aggregate locally"),
        ("CLUSTER HEAD", "median + anomaly flag", "LoRa to Anchor"),
        ("ANCHOR/BRICK", "verify + store-forward", "mesh → backhaul"),
        ("CLOUD/COMMUNITY", "dashboard + alerts", "EN/FR, OCAP"),
    ]
    yy = 190
    for i, (t, sub, note) in enumerate(flow):
        s.rect(rx, yy, 560, 64, fill=FILL, stroke=INK, sw=1.2)
        s.t(rx + 14, yy + 26, t, 13, weight="bold")
        s.t(rx + 14, yy + 46, f"{sub} → {note}", 11, color=SOFT)
        if i < 3:
            s.arrow(rx + 280, yy + 64, rx + 280, yy + 82)
        yy += 92
    s.note(rx, yy + 10, "Only ANOMALIES leave the cluster — raw data stays local. "
         "Bandwidth is the constraint; intelligence is the answer.", size=12)

    s.h(rx, 700, "OPEN RESEARCH QUESTIONS")
    s.bullets(rx, 730, [
        "Printed LoRa-class radio — does backscatter suffice at 915 MHz?",
        "Cluster head durability — can IT be semi-degradable?",
        "Mote density vs detection probability — modeling needed.",
        "Biodegradation rate vs fire season length — materials tuning.",
        "Wake-up reliability — missed windows = missed detections.",
    ], width=85)
    return s.svg(3, 3)


# ============================================================ X MATRICES ======
def radio_matrix():
    s = Sheet("AF-X-101", "RADIO & MODEM SELECTION MATRIX",
              "EVERY WIRELESS DECISION IN THE FLEET — OPTIONS · TRADE-OFFS · VERDICT",
              "X · DECISIONS", status="LIVING DOCUMENT")

    s.h(ML + 10, 150, "SUB-GHz / LONG-RANGE RADIOS")
    s.table(ML + 10, 178, [150, 90, 110, 90, 110, 90, 170],
            ["Module", "Band", "Range", "Rate", "Power", "Cost", "Verdict"], [
        ["SX1262 (E22-900M30S)", "915 MHz", "5–15 km", "0.3–50 kbps", "22 dBm", "$15–25", "MESH STANDARD — fleet default"],
        ["SX1276", "868/915 MHz", "similar", "0.3–50 kbps", "20 dBm", "$10–18", "alt — older, more libs"],
        ["CC1101", "315/433/868/915", "1–3 km", "1.2–500 kbps", "10 dBm", "$5–10", "sensor motes — short range"],
        ["nRF905", "433/868/915", "2–5 km", "20–100 kbps", "13 dBm", "$8–15", "legacy — superseded by SX1262"],
        ["LoRa32 / RFM95", "915 MHz", "same radio", "same", "14–20 dBm", "$20–35", "dev boards only"],
    ], rh=42)

    s.h(ML + 10, 520, "CELLULAR / BACKHAUL")
    s.table(ML + 10, 548, [120, 90, 120, 100, 100, 100, 170],
            ["Module", "Gen", "Rate", "GNSS", "Cost", "Power", "Verdict"], [
        ["SIM7600", "LTE Cat-4", "150 Mbps", "yes", "$60–90", "~1 W avg", "L1/TOTEM/ANCHOR backhaul"],
        ["SIM7070", "LTE Cat-1", "10 Mbps", "yes", "$40–60", "~0.5 W", "MITE/PHONE low-power"],
        ["BG96", "LTE Cat-M1/NB-IoT", "1 Mbps", "no", "$25–40", "~0.1 W", "sensor backhaul — tiny data"],
        ["Starlink Mini", "LEO sat", "100+ Mbps", "—", "$300–600", "~30 W", "ANCHOR true dead zones"],
        ["Iridium Certus", "L-band", "22–128 kbps", "—", "OEM $500+", "~5 W", "PHONE SOS + north"],
    ], rh=42)

    s.h(ML + 10, 830, "DECISION RULES")
    s.bullets(ML + 10, 856, [
        "Mesh = SX1262 everywhere — one radio, one firmware path, fleet commonality.",
        "Backhaul = LTE where towers exist (SIM7600), NB-IoT where they barely do "
        "(BG96). SOS = Iridium-class L-band — the only global guarantee.",
        "Starlink = Anchor-level only — power-hungry, business case required.",
        "No module gets chosen without: Canadian availability, -30 °C rating, "
        "supply chain ≥2 sources.",
    ], width=110)

    s.h(880, 150, "ANTENNA OPTIONS")
    s.table(880, 178, [160, 200, 200], ["Type", "Gain", "Use"], [
        ["¼-wave whip SMA", "2–5 dBi", "L1/Anchor field replaceable"],
        ["PCB meander", "1–2 dBi", "Mite — space-constrained"],
        ["Helical", "3–8 dBi", "Relay-bee high perch"],
        ["Yagi directional", "8–12 dBi", "Anchor backbone backhaul"],
        ["LDS (laser-direct)", "—", "Phone — no external whips"],
    ], rh=42)

    s.h(880, 480, "REJECTED OPTIONS (AND WHY)")
    s.bullets(880, 510, [
        "Wi-Fi HaLow — promising but ecosystem immature; revisit rev-C.",
        "Meshtastic commodity modules — closed firmware, no signed envelopes.",
        "Cellular-only 'solution' — fails exactly where ArcticChain lives.",
        "Satellite broadband for nodes — watts and dollars for kbps of need.",
        "Proprietary mesh radios — vendor lock-in kills community ownership.",
    ], width=82)
    return s.svg(1, 2)


def platform_matrix():
    s = Sheet("AF-X-102", "PLATFORM SELECTION MATRIX",
              "COMPUTE · POWER · DISPLAY · ENCLOSURE — EVERY HARDWARE DECISION",
              "X · DECISIONS", status="LIVING DOCUMENT")

    s.h(ML + 10, 150, "COMPUTE / MCU")
    s.table(ML + 10, 178, [120, 120, 140, 140, 140, 160],
            ["Chip", "Class", "Price", "Power", "Use", "Verdict"], [
        ["ESP32-S3", "MCU+WiFi", "$3–8", "~0.5 W", "Mite/swarm", "DEFAULT for nodes"],
        ["nRF52840", "MCU+BLE", "$4–8", "~0.1 W", "ultra-low-power", "seed motes candidate"],
        ["STM32WB", "MCU+BLE", "$5–10", "~0.2 W", "industrial", "alt for certified builds"],
        ["CM5", "SBC Linux", "$60–90", "~5 W", "L1/Totem/Anchor", "gateway compute"],
        ["RK3326", "SBC Android", "$40–70", "~4 W", "phone-class", "Phone option B"],
    ], rh=40)

    s.h(ML + 10, 480, "POWER STORAGE")
    s.table(ML + 10, 508, [130, 140, 160, 160, 160],
            ["Chemistry", "Energy", "Cycle life", "Cold rating", "Verdict"], [
        ["18650 Li-ion", "3 Ah/cell", "300–500", "-20 °C derate", "L1 portable"],
        ["LiFePO4", "3.2 V/cell", "2000+", "-30 °C ok", "STATIONARY default"],
        ["LiPo pouch", "varies", "300–500", "-20 °C", "Mite/Phone compact"],
        ["Printed battery", "µWh", "season", "—", "Seed motes (R&D)"],
    ], rh=40)

    s.h(ML + 10, 740, "DISPLAY")
    s.table(ML + 10, 768, [140, 160, 160, 200],
            ["Type", "Power", "Sunlight", "Use"], [
        ["E-Ink 7.5–13.3in", "zero idle", "perfect", "Totem/L1 public"],
        ["Transflective LCD", "low", "good", "Phone outdoor"],
        ["OLED", "med", "poor", "consumer look — wrong for field"],
        ["LED matrix", "low", "ok", "status only — not content"],
    ], rh=38)

    s.h(880, 150, "ENCLOSURE / MECHANICAL")
    s.table(880, 178, [130, 160, 170, 160],
            ["Option", "Cost", "Tooling", "Verdict"], [
        ["FDM print PETG/ASA", "low", "none", "prototypes + field spares"],
        ["Injection mold PC/ABS", "high NRE", "mold $5–20k", "volume products"],
        ["Polycarbonate box", "med", "none", "IP66 infrastructure"],
        ["Sheet metal + gasket", "med", "fab", "Anchor industrial"],
        ["3D-print + TPU overmold", "low-med", "print", "Phone rev-B option"],
    ], rh=36)

    s.h(880, 430, "CONNECTORS / INTERFACES")
    s.table(880, 456, [150, 220, 200], ["Standard", "Use", "Why"], [
        ["USB-C PD", "power + data", "universal, glove-friendly"],
        ["Pogo pins", "dock/module", "blind-mate, no doors"],
        ["SMA/U.FL", "antennas", "field-replaceable"],
        ["JST-PH", "battery", "polarized, tool-light"],
        ["M2/M3 screws", "enclosure", "hand-tool service"],
        ["Magnetic catch", "lids", "tool-less battery access"],
    ], rh=34)

    s.h(880, 740, "THE PLATFORM RULE")
    s.bullets(880, 764, [
        "Common compute (ESP32-S3/CM5), SX1262 mesh, USB-C, signed envelope — everywhere.",
        "Diversity only where environment demands: battery, display, enclosure.",
        "Every choice must pass: Canadian supplier? -30 °C? hand-tool repair? "
        "community-open?",
    ], width=105)
    return s.svg(2, 2)


# ============================================================ COVER =======
def cover():
    s = Sheet("AF-000", "FLEET OVERVIEW & DRAWING INDEX",
              "ARCTICCHAIN RURAL NODE FAMILY — COMPLETE PRINT SET", "COVER",
              status="MASTER INDEX")

    s.h(ML + 10, 150, "THE FLEET — ONE NETWORK, MANY SHAPES")
    s.table(ML + 10, 178, [50, 90, 250, 170, 160, 120, 190],
            ["Node", "Name", "Role", "Envelope", "Power", "Finish", "Status"], [
        ["L1", "Brick", "field node — mailbox+repeater+bulletin+SOS", "160×80×24 mm", "4×18650/solar", "graphite PETG matte", "CAD ready"],
        ["E", "Totem", "community board — public E-Ink + mesh node", "~320×220×80+pole", "solar+LiFePO4", "charcoal PC IP66", "spec"],
        ["S", "Mite", "swarm unit — perchable multi-mission node", "~90×90×35 mm", "solar+LiPo", "forest ASA matte", "CAD scripted"],
        ["A", "Anchor", "charging station — dock+relay+backhaul", "~350×250×400+array", "20–60 W+LiFePO4", "charcoal powder-coat", "spec"],
        ["P", "ArcticPhone", "rural comms — mesh-native, sat SOS", "~145×72×14 mm", "replaceable+solar", "graphite PC+TPU", "concept"],
        ["D", "Seed", "degradable mote — seasonal sensing", "~20×20×5 mm", "printed+harvest", "cellulose — vanishes", "R&D"],
        ["H", "Meridian", "satellite payload — mesh IS ground segment", "1U/3U CubeSat", "solar array", "aluminum 1U", "vision"],
    ], rh=40)

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
        ("AF-L1-101…105", "L1 Brick — arrangement, parts/power, assembly, electronics, finish"),
        ("AF-S-101…108", "S Mite — arrangement, parts, assembly, electronics, variants, mechanical, missions, finish"),
        ("AF-E-101…103", "E Totem — arrangement, parts/install, finish"),
        ("AF-A-101…103", "A Anchor — arrangement, parts/power, finish"),
        ("AF-P-101…107", "P ArcticPhone — concept, spec, definition, tri-radio, modules, UX, finish"),
        ("AF-D-101…103", "D Seed — R&D brief, materials/degradation, cluster protocol"),
        ("AF-H-101", "H Meridian — satellite mission concept"),
        ("AF-X-101…102", "Component matrices — radios, compute, power, displays, enclosures"),
    ]
    yy = 590
    for dwg, desc in idx:
        s.t(860, yy, dwg, 13, weight="bold", color=ACC)
        s.t(1000, yy, desc, 13, color=SOFT)
        yy += 32

    s.h(ML + 10, 868, "HOW TO READ THIS SET")
    s.bullets(ML + 10, 894, [
        "L1 Brick = build-ready (BOM, wiring, electronics, assembly, acceptance test).",
        "S Mite = prototype-ready (orderable parts, 4 swarm variants, CAD scripted).",
        "Totem/Anchor = spec-level · Phone = concept · Seed/Meridian = R&D/vision.",
        "Every product has a FINISH & MATERIALS sheet — final look + materials spec.",
        "AF-X matrices = every electronic decision — radios, compute, power, displays.",
        "Every sheet: SURAFEL NEGUSSIE drew it · EMEBET INC. owns it · PROPRIETARY.",
    ], width=110)
    return [s.svg(1, 1)]


# ============================================================ RENDER =======
ALL_SETS = {
    "00_Fleet_Overview": cover(),
    "01_L1_Brick": l1() + [l1_electronics(), l1_finish()],
    "02_S_Mite": mite() + [mite_electronics(), mite_variants(),
                           mite_mechanical(), mite_missions(), mite_finish()],
    "03_E_Totem": totem() + [totem_finish()],
    "04_A_Anchor": anchor() + [anchor_finish()],
    "05_P_ArcticPhone": phone() + [phone_definition(), phone_triradio(),
                                   phone_modules(), phone_ux(), phone_finish()],
    "06_D_Seed": seed() + [seed_materials(), seed_protocol()],
    "07_H_Meridian": meridian(),
    "08_Component_Matrices": [radio_matrix(), platform_matrix()],
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
