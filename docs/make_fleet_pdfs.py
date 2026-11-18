#!/usr/bin/env python3
"""ArctikChain print set v2 — architectural-style blueprint PDFs.

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

    def __init__(self, dwg, title, subtitle, node, rev="A", status="FOR REVIEW",
                 public=False):
        self.dwg, self.title, self.subtitle = dwg, title, subtitle
        self.node, self.rev, self.status = node, rev, status
        self.public = public
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

    def poly(self, pts, fill="none", stroke=INK, sw=1.0, dash=None):
        p = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.el.append(
            f'<polygon points="{p}" fill="{fill}" stroke="{stroke}" '
            f'stroke-width="{sw}"{d}/>')

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
        self.t(x + 12, y + 20, "ARCTIKCHAIN — RURAL NODE FLEET", 13, weight="bold")
        self.t(x + 12, y + 38, "EMEBET INC. · emebetos.ca", 12, weight="bold", color=ACC)
        self.t(x + 12, y + 57, "SOLE PROPRIETARY OWNER", 10, color=SOFT)
        self.t(x + 12, y + 71, "SURAFEL NEGUSSIE — PLANNER/MAKER", 10, color=SOFT)
        if self.public:
            self.t(x + 12, y + 92, "© EMEBET INC. — PUBLIC PRESENTATION", 10, ACC, "bold")
            self.t(x + 12, y + 106, "FABRICATION SHEETS SHARED UNDER NDA", 9, SOFT)
        else:
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
        if self.public:
            self.t(ML + 8, PH - MB + 22, "EMEBET INC. — PUBLIC PRESENTATION SHEET",
                   10, color=ACC)
        else:
            self.t(ML + 8, PH - MB + 22, "EMEBET INC. — PROPRIETARY & CONFIDENTIAL",
                   10, color=RED)

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


# ============================================================ detail library
# Reusable hardware details — screws, solar cells, antennas, vents, clips,
# connectors, PCBs, cells, fasteners. Every figure uses the same vocabulary
# so the whole set reads like one engineering language.

import math


def d_screw(s, x, y, r=5):
    """Countersunk pan screw: head circle + drive slot."""
    s.circ(x, y, r, fill="#e9e9e9", stroke=INK, sw=1)
    s.ln(x - r * 0.55, y, x + r * 0.55, y, INK, 1.1)


def d_solar(s, x, y, w, h, nx=3, ny=3, label=None):
    """Solar cell window: blue-tinted area + cell bus grid."""
    s.rect(x, y, w, h, fill="#dbe7f4", stroke=INK, sw=1.3)
    for i in range(1, nx):
        s.ln(x + i * w / nx, y + 3, x + i * w / nx, y + h - 3, SOFT, 0.9)
    for j in range(1, ny):
        s.ln(x + 3, y + j * h / ny, x + w - 3, y + j * h / ny, SOFT, 0.9)
    if label:
        s.t(x + w / 2, y + h + 16, label, 10, "middle", SOFT)


def d_whip(s, x, y, h=60, lean=0):
    """Antenna whip: tapered body + connector base. (x,y) = base top."""
    s.rect(x - 5, y - 4, 10, 10, fill="#3a3a3a", stroke=INK, sw=1, r=2)
    s.poly([(x - 3, y - 4), (x + 3, y - 4),
            (x + 1.4 + lean, y - h), (x - 1.4 + lean, y - h)],
           fill="#2a2a2a", stroke=INK, sw=0.8)


def d_vent(s, x, y, w, n=6):
    """Row of vent slots (ePTFE membrane zone)."""
    for i in range(n):
        s.rect(x + i * w / n, y, w / n * 0.45, 9,
               fill="none", stroke=SOFT, sw=0.9, r=2)


def d_usbc(s, x, y, scale=1.0):
    """USB-C port face."""
    w, h = 34 * scale, 13 * scale
    s.rect(x - w / 2, y - h / 2, w, h, fill="none", stroke=INK, sw=1.2, r=h / 2)
    s.rect(x - w * 0.32, y - h * 0.22, w * 0.64, h * 0.44,
           fill=INK, r=h * 0.2)


def d_btn(s, x, y, w, h, color="#3a3a3a"):
    """Tactile key (side button)."""
    s.rect(x, y, w, h, fill=color, stroke=INK, sw=1, r=min(5, h / 3))


def d_led(s, x, y, r=4, color=ACC):
    """Status LED + light-pipe bezel."""
    s.circ(x, y, r + 2.5, fill="none", stroke=SOFT, sw=0.7)
    s.circ(x, y, r, fill=color, stroke=INK, sw=0.8)


def d_gland(s, x, y):
    """Cable gland, bottom edge."""
    s.rect(x - 9, y - 11, 18, 15, fill="none", stroke=INK, sw=1.2, r=3)
    for i in range(3):
        s.ln(x - 9, y - 7 + i * 4.5, x + 9, y - 7 + i * 4.5, SOFT, 0.7)


def d_pogo(s, x, y, r=7):
    """Pogo-pin dock contact pad."""
    s.circ(x, y, r, fill="#e9e9e9", stroke=INK, sw=1.2)
    s.circ(x, y, r * 0.45, fill="none", stroke=SOFT, sw=0.9)


def d_pcb(s, x, y, w, h, label="PCB"):
    """Circuit board with chips + trace hint."""
    s.rect(x, y, w, h, fill="#e4ede0", stroke=INK, sw=1.1)
    s.rect(x + w * 0.10, y + h * 0.18, w * 0.30, h * 0.30,
           fill="#cdd6ca", stroke=INK, sw=0.8)
    s.rect(x + w * 0.52, y + h * 0.14, w * 0.34, h * 0.24,
           fill="#cdd6ca", stroke=INK, sw=0.8)
    s.rect(x + w * 0.55, y + h * 0.55, w * 0.30, h * 0.18,
           fill="#d8c88a", stroke=INK, sw=0.7)
    for i in range(3):
        s.ln(x + w * 0.10, y + h * (0.58 + i * 0.10),
             x + w * 0.42, y + h * (0.58 + i * 0.10), SOFT, 0.6)
    s.t(x + w / 2, y + h - 6, label, 9, "middle", SOFT)


def d_cells(s, x, y, n=4, r=16, gap=8):
    """Row of 18650 cells (end-on circles)."""
    for i in range(n):
        cx = x + i * (2 * r + gap) + r
        s.circ(cx, y + r, r, fill="#e9e9e9", stroke=INK, sw=1)
        s.circ(cx, y + r, 4.5, fill="none", stroke=INK, sw=0.8)


def d_cam(s, x, y, r=10):
    """Camera: outer ring + lens + glint."""
    s.circ(x, y, r, fill="#151515", stroke=INK, sw=1.2)
    s.circ(x, y, r * 0.55, fill="#2c3e50", stroke="#4a6a8a", sw=1)
    s.circ(x - r * 0.2, y - r * 0.2, r * 0.15, fill="#aaccee", stroke="none")


def d_grille(s, x, y, w=44, rows=2):
    """Speaker/mic pinhole grille."""
    for j in range(rows):
        for i in range(int(w / 9)):
            s.circ(x + i * 9, y + j * 9, 1.6, fill=INK)


def d_latch(s, x, y):
    """Enclosure draw-latch clasp."""
    s.rect(x - 9, y - 13, 18, 26, fill="none", stroke=INK, sw=1.2, r=4)
    s.rect(x - 5, y - 6, 10, 9, fill="#e9e9e9", stroke=INK, sw=0.8)


def d_hinge(s, x, y, w=26):
    """Door hinge knuckle: barrel + pin caps."""
    s.rect(x, y - 8, w, 16, fill="none", stroke=INK, sw=1.2, r=6)
    s.circ(x + 4, y, 3, fill="#e9e9e9", stroke=INK, sw=0.8)
    s.circ(x + w - 4, y, 3, fill="#e9e9e9", stroke=INK, sw=0.8)


def d_thumbs(s, x, y, r=9):
    """Knurled thumb screw (module bay)."""
    s.circ(x, y, r, fill="#e9e9e9", stroke=INK, sw=1.2)
    for i in range(8):
        a = i * math.pi / 4
        s.ln(x + (r - 2.5) * math.cos(a), y + (r - 2.5) * math.sin(a),
             x + r * math.cos(a), y + r * math.sin(a), INK, 0.7)
    s.circ(x, y, 2.5, fill=INK)


def d_rotor(s, x, y, rx=56, ry=21, spin=1):
    """Ducted rotor in top-plane oblique view: guard ring + disc + prop + hub."""
    s.el.append(f'<ellipse cx="{x:.1f}" cy="{y:.1f}" rx="{rx}" ry="{ry}" '
                f'fill="none" stroke="{INK}" stroke-width="2.4"/>')
    s.el.append(f'<ellipse cx="{x:.1f}" cy="{y:.1f}" rx="{rx * 0.80}" '
                f'ry="{ry * 0.80}" fill="#e8eef5" stroke="{SOFT}" '
                f'stroke-width="0.8"/>')
    # prop blades — two swept blades across the hub
    a = 0.5 * spin
    bx1 = x - rx * 0.60 * math.cos(a)
    by1 = y - rx * 0.60 * math.sin(a) * 0.35
    bx2 = x + rx * 0.60 * math.cos(a)
    by2 = y + rx * 0.60 * math.sin(a) * 0.35
    s.ln(bx1, by1, bx2, by2, "#2a2a2a", 6)
    s.circ(x, y, ry * 0.42, fill="#2c3e50", stroke=INK, sw=1.1)
    s.circ(x, y, ry * 0.42 * 0.4, fill="#151515")


def d_rotor_top(s, x, y, r=55):
    """Ducted rotor, plan view: guard ring + disc + prop line + motor hub."""
    s.circ(x, y, r, fill="none", stroke=INK, sw=2.4)
    s.circ(x, y, r * 0.82, fill="#e8eef5", stroke=SOFT, sw=0.8)
    s.ln(x - r * 0.62, y, x + r * 0.62, y, "#2a2a2a", 6)
    s.circ(x, y, r * 0.11, fill="#2c3e50", stroke=INK, sw=1.1)


def d_leg(s, x, y, span=74, drop=58, flip=1):
    """Perch leg: hip → knee → foot + claw hook. flip mirrors left/right."""
    kx, ky = x + flip * span * 0.55, y + drop * 0.58
    fx, fy = x + flip * span, y + drop
    s.ln(x, y, kx, ky, INK, 3.6)
    s.ln(kx, ky, fx, fy, INK, 3.2)
    s.circ(x, y, 4.5, fill="#e9e9e9", stroke=INK, sw=1.1)
    s.circ(kx, ky, 4.5, fill="#e9e9e9", stroke=INK, sw=1.1)
    # claw — two short hooks curving back under the foot
    s.ln(fx, fy, fx - flip * 14, fy + 9, INK, 2.8)
    s.ln(fx - flip * 14, fy + 9, fx - flip * 20, fy + 2, INK, 2.8)


def d_camisle(s, x, y, w, h, thermal=True):
    """2026 camera island: squircle bump — main + ultrawide + thermal, flash, mic."""
    s.rect(x, y, w, h, fill="#232c38", stroke=INK, sw=1.5, r=w * 0.22)
    d_cam(s, x + w * 0.30, y + h * 0.30, r=w * 0.19)
    d_cam(s, x + w * 0.72, y + h * 0.30, r=w * 0.145)
    d_cam(s, x + w * 0.30, y + h * 0.74, r=w * 0.145)
    s.circ(x + w * 0.72, y + h * 0.74, w * 0.05, fill="#f0e0a0",
           stroke=INK, sw=0.7)
    s.circ(x + w * 0.88, y + h * 0.16, w * 0.032, fill=INK)


def d_punch(s, x, y, r=5):
    """Hole-punch selfie camera in a display."""
    s.circ(x, y, r, fill="#0d1117", stroke="#3a4a5a", sw=0.9)
    s.circ(x, y, r * 0.45, fill="#1a2f4a", stroke="none")


def d_branch(s, x, cy, w, r=26):
    """Horizontal perch branch: woody band + end grain ring."""
    s.rect(x, cy - r, w, 2 * r, fill="#cdbba0", stroke=INK, sw=1.2)
    for i in range(3):
        s.ln(x + w * (0.15 + i * 0.3), cy - r + 4,
             x + w * (0.15 + i * 0.3), cy + r - 4, "#a89070", 1)


def d_slab(s, x, y, w, d=20, h=15, color=FILL, sw=1.1):
    """Exploded-view plate: front face + top face + side sliver."""
    dx, dy = d * 0.45, -d * 0.42
    if color != "none":
        s.poly([(x, y), (x + dx, y + dy), (x + w + dx, y + dy), (x + w, y)],
               fill=shade(color, 1.18), stroke=INK, sw=sw)
        s.poly([(x + w, y), (x + w + dx, y + dy),
                (x + w + dx, y + h + dy), (x + w, y + h)],
               fill=shade(color, 0.72), stroke=INK, sw=sw)
    s.rect(x, y, w, h, fill=color, stroke=INK, sw=sw)


def figcap(s, cx, y, num, caption):
    """'Fig. N — CAPTION' centered under a figure."""
    s.t(cx, y, f"Fig. {num}", 13, "middle", weight="bold")
    s.t(cx, y + 19, caption.upper(), 10.5, "middle", SOFT, spacing="0.8")


def explode(s, x, y, w, layers, d=22, h=15, gap=30, callx=None):
    """Vertical exploded stack. layers: [(name, color, detail)].
    Returns bottom y. Callouts drawn at callx (default right side)."""
    yy = y
    if callx is None:
        callx = x + w + d + 70
    for i, (name, color, detail) in enumerate(layers):
        d_slab(s, x, yy, w, d=d, h=h, color=color)
        s.t(callx, yy + h / 2 + 4, name, 12, weight="bold")
        s.t(callx, yy + h / 2 + 17, detail, 9.5, color=SOFT)
        s.ln(x + w + d, yy + h / 2, callx - 8, yy + h / 2 + 4, SOFT, 0.7)
        if i < len(layers) - 1:
            s.ln(x + w / 2, yy + h, x + w / 2, yy + h + gap, SOFT, 0.8, "4 4")
        yy += h + gap
    return yy


# ============================================================ L1 BRICK ====
def l1():
    out = []

    # ---------------- 101 GA — prototype figure sheet ----------------
    s = Sheet("AF-L1-101", "GENERAL ARRANGEMENT — FIELD NODE",
              "HANDHELD MESH BRICK · 160×80×32 mm", "L1 · BRICK")

    # ===== Fig. 1 — hero: brick face-up, e-ink live =====
    cx, cy = 520, 340
    G = s.device(cx, cy, 470, 235, 44, "#39424c", rad=18)
    # e-ink window on front face — the public surface
    ex0, ey0 = s.fpt(G, 0.06, 0.10)
    ex1, ey1 = s.fpt(G, 0.60, 0.90)
    s.rect(ex0, ey0, ex1 - ex0, ey1 - ey0, fill="#e8ecdf",
           stroke=INK, sw=1.3, r=4)
    for i, txt in enumerate(("ARCTIKCHAIN MESH", "3 NODES · 14 MSG",
                             "FIRE BAN ACTIVE")):
        lx, ly = s.fpt(G, 0.10, 0.26 + i * 0.22)
        s.t(lx, ly, txt, 11 if i else 13, color="#3a4a3a",
            weight="bold" if i == 0 else "normal")
    # SOS key + status LED on top face right side
    sox, soy = s.tpt(G, 0.79, 0.5)
    s.circ(sox, soy, 22, fill="#a83c2e", stroke=INK, sw=1.3)
    s.t(sox, soy + 4, "SOS", 10, "middle", "#f4d7d2", "bold")
    d_led(s, *s.tpt(G, 0.92, 0.16), r=4)
    # shell screws
    for a, b in ((0.05, 0.08), (0.95, 0.08), (0.05, 0.92), (0.95, 0.92)):
        d_screw(s, *s.tpt(G, a, b), r=5)
    # whips exiting top edge (LTE + LoRa)
    w1x, w1y = s.fpt(G, 0.10, 0.0)
    w2x, w2y = s.fpt(G, 0.90, 0.0)
    d_whip(s, w1x, w1y, 74, lean=-12)
    d_whip(s, w2x, w2y, 74, lean=12)
    # front edge: USB-C + lanyard anchor + pogo contacts
    ucx, ucy = s.fpt(G, 0.30, 1.0)
    d_usbc(s, ucx, ucy + 2, 0.8)
    for i in range(2):
        d_pogo(s, *s.fpt(G, 0.55 + i * 0.14, 1.0), r=5)
    lx_, ly_ = s.fpt(G, 0.88, 1.0)
    s.rect(lx_ - 10, ly_ - 2, 20, 10, fill="none", stroke=INK, sw=1.4, r=5)
    # callouts
    s.callout(ex1 - 30, ey1 + 8, 100, 130,
              "7.5 E-INK — public bulletin, zero idle power")
    s.callout(sox, soy, 950, 300, "SOS KEY — dedicated hardware")
    s.callout(w2x, w2y - 70, 950, 170, "LORA WHIP — 915 MHz mesh")
    s.callout(w1x, w1y - 70, 100, 165, "LTE WHIP — backhaul when towers exist")
    s.callout(ucx, ucy, 950, 500, "USB-C PD — charge + flash")
    s.callout(*s.fpt(G, 0.62, 1.0), 950, 420, "POGO — sled/dock contacts")
    s.callout(*s.fpt(G, 0.97, 0.62), 950, 600, "PETG SHELL — printed, hand-fixable")
    figcap(s, cx, 640, 1, "L1 BRICK — field face, e-ink bulletin live")

    # ===== Fig. 2 — top view (lid off: internals) =====
    t2x, t2y, t2w, t2h = 1120, 150, 430, 215
    s.rect(t2x, t2y, t2w, t2h, fill=FILL, stroke=INK, sw=1.6, r=16)
    d_cells(s, t2x + 24, t2y + t2h * 0.62, n=4, r=15, gap=10)
    s.t(t2x + 24 + 4 * 38 // 2, t2y + t2h * 0.62 + 44,
        "4×18650 — 44 Wh", 10, "middle", SOFT)
    d_pcb(s, t2x + 24, t2y + 20, t2w * 0.46, t2h * 0.34, "CM5 + HATS")
    d_pcb(s, t2x + t2w * 0.55, t2y + 20, t2w * 0.30, t2h * 0.34, "SX1262")
    s.rect(t2x + t2w * 0.88, t2y + 20, 24, 70, fill="#dbe7f4",
           stroke=INK, sw=0.9)
    s.t(t2x + t2w * 0.88 + 12, t2y + 96, "SIM7600", 8, "middle", SOFT)
    for a in (0.06, 0.94):
        s.rect(t2x + a * t2w - 8, t2y - 6, 16, 12, fill="#3a3a3a",
               stroke=INK, sw=1, r=3)
    s.callout(t2x + t2w * 0.06, t2y - 4, 950, 108, "ANTENNA BASES ×2")
    s.dimh(t2x, t2x + t2w, t2y + t2h + 34, "160")
    s.dimv(t2x - 30, t2y, t2y + t2h, "80")
    figcap(s, t2x + t2w / 2, t2y + t2h + 70, 2, "Top — lid off, internals")

    # ===== Fig. 3 — side section =====
    s3x, s3y, s3w, s3h = 1120, 470, 300, 100
    s.rect(s3x, s3y, s3w, s3h, fill=FILL, stroke=INK, sw=1.5, r=10)
    s.rect(s3x + 12, s3y + 12, s3w - 24, s3h * 0.30, fill="#e4ede0",
           stroke=SOFT, sw=0.8, dash="5 3")
    s.t(s3x + s3w / 2, s3y + 34, "HAT STACK — e-ink / LoRa / LTE", 9, "middle", SOFT)
    s.rect(s3x + 12, s3y + s3h * 0.52, s3w - 24, s3h * 0.34,
           fill="none", stroke=SOFT, sw=0.9, dash="5 3")
    s.t(s3x + s3w / 2, s3y + s3h * 0.72, "CELL TRAY", 9, "middle", SOFT)
    s.dimh(s3x, s3x + s3w, s3y + s3h + 30, "80")
    s.dimv(s3x - 30, s3y, s3y + s3h, "32")
    figcap(s, s3x + s3w / 2, s3y + s3h + 64, 3, "Section B-B — stack")

    # ===== Fig. 4 — exploded =====
    e4x, e4y = 90, 730
    explode(s, e4x, e4y, 210, [
        ("TOP SHELL + E-INK", "#39424c", "window + SOS key + seal"),
        ("HAT STACK", "#e4ede0", "CM5 + LoRa + LTE HATs"),
        ("CELL TRAY", "#f0e8d8", "4×18650 → 14.8→5 V buck"),
        ("LOWER SHELL", "#e9e9e9", "PETG + pogo + lanyard boss"),
    ], d=18, h=14, gap=19, callx=e4x + 280)
    figcap(s, e4x + 105, e4y + 170, 4, "Exploded — four assemblies")

    # ===== right column — features + acceptance =====
    s.h(1050, 680, "KEY FEATURES")
    s.table(1050, 704, [130, 300], ["Feature", "Detail"], [
        ["Display", "7.5in e-Paper — sun readable"],
        ["Mesh + backhaul", "SX1262 915 · SIM7600 LTE"],
        ["Power", "44 Wh · USB-C PD"],
        ["Agent", ":8080 — signed envelopes"],
    ], rh=30)
    s.note(1050, 872, "Mailbox + repeater + bulletin + SOS. Works with zero "
           "connectivity — that is the product.", size=10)
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

    # ---------------- 101 GA — mobile micro-robot figure sheet ----------------
    s = Sheet("AF-S-101", "GENERAL ARRANGEMENT — MICRO-ROBOT",
              "FLY · CRAWL · PERCH · DOCK — ENVIRONMENTAL SWARM UNIT", "S · MITE")

    # ===== Fig. 1 — hero: quad-rotor mite in perch approach, isometric =====
    cx, cy = 500, 350
    # perch branch below — the target, drawn first (mite hovers above it)
    s.el.append(
        f'<g transform="rotate(-14 {cx} {cy + 260})">'
        f'<rect x="{cx - 300}" y="{cy + 236}" width="620" height="42" rx="21" '
        f'fill="#cdbba0" stroke="{INK}" stroke-width="1.5"/>'
        f'<ellipse cx="{cx - 300}" cy="{cy + 257}" rx="9" ry="21" '
        f'fill="#b5a284" stroke="{INK}" stroke-width="1.2"/>'
        f'</g>')
    # rotor ring positions on the pod's top plane (front pair closer to viewer)
    rings = [(-0.62, -0.62, -1), (1.62, -0.62, 1),
             (-0.60, 1.45, -1), (1.60, 1.45, 1)]
    G = s.device(cx, cy, 200, 64, 96, "#3d4a42", rad=18)
    fx, fy = G["fx"], G["fy"]
    # arms — pod top-face edges out to each ring, drawn under the pod
    arm_ends = {(-0.62, -0.62): (fx + 26, fy + 34), (1.62, -0.62): (fx + 174, fy + 34),
                (-0.60, 1.45): (fx + 34, fy - 24), (1.60, 1.45): (fx + 168, fy - 24)}
    for (a, b, _f) in rings:
        rx_, ry_ = s.tpt(G, a, b)
        ax_, ay_ = arm_ends[(a, b)]
        s.ln(ax_, ay_, rx_, ry_, "#3a4340", 7)
        s.circ(ax_, ay_, 5, fill="#3a4340")
    for i, (a, b, spin) in enumerate(rings):
        rx_, ry_ = s.tpt(G, a, b)
        d_rotor(s, rx_, ry_, rx=54, ry=20, spin=spin)
    # solar deck on pod top face + mission-pod bay dashed outline
    tx0, ty0 = s.tpt(G, 0.12, 0.14)
    tx1, ty1 = s.tpt(G, 0.88, 0.14)
    tx2, ty2 = s.tpt(G, 0.88, 0.55)
    tx3, ty3 = s.tpt(G, 0.12, 0.55)
    s.poly([(tx0, ty0), (tx1, ty1), (tx2, ty2), (tx3, ty3)],
           fill="#dbe7f4", stroke=INK, sw=1.2)
    for a in (0.37, 0.63):
        s.ln(*s.tpt(G, a, 0.14), *s.tpt(G, a, 0.55), SOFT, 0.8)
    bx0, by0 = s.tpt(G, 0.22, 0.62)
    bx1, by1 = s.tpt(G, 0.78, 0.62)
    bx2, by2 = s.tpt(G, 0.78, 0.94)
    bx3, by3 = s.tpt(G, 0.22, 0.94)
    s.poly([(bx0, by0), (bx1, by1), (bx2, by2), (bx3, by3)],
           fill="none", stroke=SOFT, sw=0.9, dash="6 4")
    s.t(*s.tpt(G, 0.5, 0.82), "POD BAY", 8, "middle", SOFT, spacing="0.5")
    for a, b in ((0.07, 0.10), (0.93, 0.10)):
        d_screw(s, *s.tpt(G, a, b), r=4)
    # front face: gasket seam + vent + LED + antenna stub on side
    sx0, sy0 = s.fpt(G, 0.05, 0.32)
    sx1, sy1 = s.fpt(G, 0.95, 0.32)
    s.ln(sx0, sy0, sx1, sy1, SOFT, 1, "7 4")
    d_vent(s, *s.fpt(G, 0.08, 0.60), w=G["w"] * 0.30, n=5)
    d_led(s, *s.fpt(G, 0.90, 0.22), r=4)
    ax, ay = s.spt(G, 0.5, 0.5)
    s.poly([(ax, ay), (ax + 22, ay - 30), (ax + 28, ay - 26), (ax + 8, ay + 4)],
           fill="#2a2a2a", stroke=INK, sw=1)
    # belly pod: sensor pod + nav cam + optical flow + dock pogos
    s.rect(cx - 46, fy + 62, 92, 30, fill="#31413a", stroke=INK, sw=1.2, r=10)
    d_cam(s, cx - 18, fy + 78, r=7)
    s.rect(cx + 4, fy + 72, 14, 10, fill="#0b0e12", stroke=INK, sw=0.8, r=2)
    s.t(cx + 26, fy + 80, "FLOW", 7, color=SOFT)
    d_pogo(s, cx - 58, fy + 84, r=5)
    d_pogo(s, cx + 60, fy + 84, r=5)
    # perch legs — two front + one rear (partial, behind body)
    d_leg(s, cx - 78, fy + 58, span=74, drop=60, flip=-1)
    d_leg(s, cx + 78, fy + 58, span=74, drop=60, flip=1)
    lx, ly = s.spt(G, 0.75, 0.9)
    d_leg(s, lx, ly, span=54, drop=48, flip=1)
    # callouts
    s.callout(*s.tpt(G, -0.60, 1.45), 95, 110,
              "DUCTED ROTOR ×4 — 2″ prop, printed guard")
    s.callout(*s.tpt(G, 1.62, -0.62), 950, 130,
              "HOVER 60–90 W — flight is the rare, expensive mode")
    s.callout(*s.tpt(G, 0.5, 0.30), 950, 200,
              "SOLAR DECK — trickle charge at perch")
    s.callout(*s.tpt(G, 0.9, 0.62), 950, 300,
              "MISSION-POD BAY — swappable (AF-S-107)")
    s.callout(ax + 16, ay - 22, 950, 390, "LORA ANTENNA — 915 MHz mesh")
    s.callout(cx - 18, fy + 82, 95, 545,
              "NAV CAM + OPTICAL FLOW — blind-land on dock")
    s.callout(cx - 118, fy + 108, 55, 700,
              "PERCH LEG ×4 — claw grips Ø10–40, crawls to aim")
    s.callout(cx + 138, fy + 96, 950, 545,
              "POGO PADS — dock charge + tasking")
    figcap(s, cx, 668, 1, "S MITE — hop-flight approach to perch (isometric)")

    # ===== Fig. 2 — plan view: X-frame quad =====
    t2x, t2y = 1060, 130
    pod_x, pod_y, pod_w = t2x + 155, t2y + 140, 140
    ring_xy = [(t2x + 70, t2y + 60), (t2x + 420, t2y + 60),
               (t2x + 70, t2y + 340), (t2x + 420, t2y + 340)]
    for rx, ry in ring_xy:
        px = pod_x + pod_w / 2 + (1 if rx > pod_x else -1) * pod_w * 0.42
        py = pod_y + pod_w / 2 + (1 if ry > pod_y else -1) * pod_w * 0.42
        s.ln(px, py, rx, ry, "#3a4340", 7)
        s.circ(px, py, 5, fill="#3a4340")
    for rx, ry in ring_xy:
        d_rotor_top(s, rx, ry, r=58)
    s.rect(pod_x, pod_y, pod_w, pod_w, fill=FILL, stroke=INK, sw=1.6, r=22)
    d_solar(s, pod_x + 22, pod_y + 22, pod_w - 44, pod_w * 0.52, nx=3, ny=2)
    s.rect(pod_x + 22, pod_y + pod_w * 0.62, pod_w - 44, pod_w * 0.28,
           fill="none", stroke=SOFT, sw=0.9, dash="6 4")
    s.t(pod_x + pod_w / 2, pod_y + pod_w * 0.78, "POD BAY", 9, "middle", SOFT,
        spacing="0.5")
    for a, b in ((0.12, 0.12), (0.88, 0.12)):
        d_screw(s, pod_x + a * pod_w, pod_y + b * pod_w, r=4)
    d_led(s, pod_x + pod_w * 0.85, pod_y + pod_w * 0.15, r=4)
    s.t(pod_x + pod_w / 2, pod_y + pod_w + 136,
        "legs fold ±25° for perch — spread for ground stand",
        10, "middle", SOFT)
    s.dimh(t2x + 15, t2x + 475, t2y + 445, "210 mm rotor diagonal")
    s.dimv(t2x + 15 - 34, t2y + 60, t2y + 340, "150")
    figcap(s, t2x + 245, t2y + 470, 2, "Plan view — X-frame quad layout")

    # ===== Fig. 3 — side elevation: standing on legs =====
    f3x, f3y = 70, 750
    s.ln(f3x, f3y + 150, f3x + 400, f3y + 150, SOFT, 1.2)
    s.t(f3x + 200, f3y + 170, "GROUND LINE", 9, "middle", SOFT)
    # pod + belly + edge-on rotor rings + splayed legs
    s.rect(f3x + 110, f3y, 180, 54, fill=FILL, stroke=INK, sw=1.5, r=14)
    s.rect(f3x + 146, f3y + 54, 108, 26, fill="#31413a", stroke=INK, sw=1.1,
           r=8)
    for rdx in (f3x + 66, f3x + 334):
        s.el.append(f'<ellipse cx="{rdx}" cy="{f3y + 8}" rx="32" ry="11" '
                    f'fill="none" stroke="{INK}" stroke-width="1.8"/>')
        s.circ(rdx, f3y + 8, 4, fill="#2c3e50", stroke=INK, sw=0.8)
    d_leg(s, f3x + 126, f3y + 80, span=60, drop=70, flip=-1)
    d_leg(s, f3x + 274, f3y + 80, span=60, drop=70, flip=1)
    d_cam(s, f3x + 200, f3y + 66, r=6)
    s.dimv(f3x + 30, f3y - 3, f3y + 150, "~75")
    s.dimh(f3x + 110, f3x + 290, f3y - 26, "~110 pod")
    figcap(s, f3x + 200, f3y + 214, 3, "Side elevation — ground stance")

    # ===== Fig. 4 — the two resting states: perch ↔ dock =====
    p4x, p4y = 510, 730
    # left: perched on branch
    d_branch(s, p4x, p4y + 128, 210, r=20)
    s.rect(p4x + 30, p4y + 40, 120, 40, fill=FILL, stroke=INK, sw=1.4, r=12)
    s.rect(p4x + 58, p4y + 80, 64, 18, fill="#31413a", stroke=INK, sw=1, r=6)
    for lx in (p4x + 44, p4x + 138):
        s.poly([(lx, p4y + 80), (lx - 4, p4y + 98), (lx + 0, p4y + 122),
                (lx + 8, p4y + 136), (lx + 16, p4y + 130), (lx + 12, p4y + 108),
                (lx + 16, p4y + 86)], fill="#e9e9e9", stroke=INK, sw=1.1)
    s.t(p4x + 105, p4y + 182, "SENSE — perched for days", 10, "middle", SOFT)
    s.t(p4x + 105, p4y + 200, "solar trickle · legs grip", 9, "middle", SOFT)
    # right: docked on Anchor rail
    s.rect(p4x + 330, p4y + 118, 150, 18, fill="#d8d8d8", stroke=INK, sw=1.2)
    s.t(p4x + 405, p4y + 152, "ANCHOR DOCK RAIL", 8, "middle", SOFT)
    s.rect(p4x + 355, p4y + 78, 100, 36, fill="#3d4a42", stroke=INK, sw=1.3,
           r=10)
    for rdx in (p4x + 322, p4x + 488):
        s.el.append(f'<ellipse cx="{rdx}" cy="{p4y + 82}" rx="22" ry="6" '
                    f'fill="none" stroke="{INK}" stroke-width="1.3"/>')
    s.ln(p4x + 385, p4y + 114, p4x + 385, p4y + 124, INK, 2)
    s.ln(p4x + 425, p4y + 114, p4x + 425, p4y + 124, INK, 2)
    d_pogo(s, p4x + 385, p4y + 128, r=4)
    d_pogo(s, p4x + 425, p4y + 128, r=4)
    s.t(p4x + 405, p4y + 182, "CHARGE + TASKING", 10, "middle", SOFT)
    s.t(p4x + 405, p4y + 200, "pogo pads meet — hive refuels", 9, "middle", SOFT)
    # bidirectional hop arrow between scenes
    s.arrow(p4x + 165, p4y + 90, p4x + 335, p4y + 60, ACC, 1.3)
    s.t(p4x + 250, p4y + 58, "≤2 km hop — legs fold in flight", 9, "middle", ACC)
    figcap(s, p4x + 240, p4y + 240, 4,
           "Resting states — perch to sense, dock to charge")

    # ===== Fig. 5 — exploded stack =====
    e5x, e5y = 1080, 660
    explode(s, e5x, e5y, 190, [
        ("TOP SHELL + SOLAR", "#dbe7f4", "deck + cell film + pod-bay lid"),
        ("ARM + DUCT ASSY ×4", "#d8d8d8", "printed ducts, 1104 motors, 2″ props"),
        ("FC + CARRIER PCB", "#e4ede0", "ESP32-S3 + IMU + SX1262 + 4-in-1 ESC"),
        ("BATTERY 2S", "#f0e8d8", "3000 mAh, slide tray, JST"),
        ("SENSOR POD", "#e4ede0", "ENS160+SHT41 + nav cam + flow + pogos"),
        ("PERCH LEGS ×4", "#e9e9e9", "2-segment claws, spring knees"),
    ], d=18, h=13, gap=18, callx=e5x + 250)
    figcap(s, e5x + 95, e5y + 185, 5, "Exploded — 6 assemblies, hand tools")

    # concept line — free band under Fig.1 caption, left of Fig.5
    s.t(520, 700, "Fly hops ≤2 km · perch for days ·", 10, color=SOFT)
    s.t(520, 718, "crawl to aim · dock to charge.", 10, color=SOFT)
    out.append(s.svg(1, 8))

    # ---------------- 102 PARTS & POWER ----------------
    s = Sheet("AF-S-102", "PARTS LIST & POWER",
              "BILL OF MATERIALS · POWER BUDGET · PIN MAP", "S · MITE")
    s.h(ML + 10, 150, "PARTS LIST — GEN-1 (ALL ORDERABLE IN CANADA)")
    s.table(ML + 10, 168, [36, 400, 230, 160, 70],
            ["#", "Part", "Supplier", "Approx CAD", "Qty"], [
        ["1", "ESP32-S3-WROOM — mesh brain + flight supervisor", "PiShop / DigiKey", "$8–15", "1"],
        ["2", "ICM-42688-P IMU + BMP390 baro (flight)", "DigiKey / Mouser", "$4–8", "1"],
        ["3", "PMW3901 optical flow + VL53L5CX ToF", "Pimoroni / DigiKey", "$10–18", "1"],
        ["4", "1104/1106 brushless + 4-in-1 20 A ESC + 2″ props", "RC supplier", "$35–55", "1"],
        ["5", "EBYTE E22-900M30S SX1262 LoRa 915 MHz", "DFRobot / AliExpress", "$15–25", "1"],
        ["6", "Sensirion ENS160 VOC/AIQ + SHT41 temp/RH", "DigiKey / Mouser", "$10–17", "1"],
        ["7", "60×60 mm ~1 W solar deck + CN3791 MPPT", "Amazon.ca / supplier", "$8–16", "1"],
        ["8", "2S LiPo 3000 mAh (850–1050 mAh class) + JST", "RC supplier", "$18–28", "1"],
        ["9", "Carrier PCB ~38×38 mm 4-layer (JLCPCB)", "JLCPCB / PCBWay", "$15–30", "1"],
        ["10", "Printed frame, ducts, shell + perch legs", "Print farm", "$8–15", "1"],
    ], rh=28)

    # power budget
    py = 560
    s.h(ML + 10, py, "POWER BUDGET (ESTIMATES — VERIFY ON BENCH)")
    s.table(ML + 10, py + 18, [250, 140, 130, 200], ["State", "Current", "Duty", "Energy/day"], [
        ["Deep sleep (perched)", "~10 µA", "~90%+", "~0.003 Wh"],
        ["Sense + process", "~80 mA @3.3 V", "~4%", "~0.013 Wh"],
        ["LoRa TX burst", "~120 mA @3.3 V", "~1%", "~0.010 Wh"],
        ["Flight — hover", "~8 A @7.4 V ≈ 60 W", "≤2% · 4 hops", "~3 Wh"],
        ["TOTAL (perch-only)", "", "", "≈0.03 Wh/day"],
        ["TOTAL (4 hops/day)", "", "", "≈3 Wh/day"],
    ], rh=30)
    s.note(ML + 10, py + 238,
          "2S 3000 mAh ≈ 22 Wh → ~5 days at 4 hops/day; perch-only → 60–90 days + solar trickle. "
          "Flight is precious — the perch is the sensor.",
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
        ["IMU_SPI", "14–17", "ICM-42688 + BMP390 flight sensors"],
        ["FLOW_UART", "20–21", "PMW3901 flow + VL53L5CX ToF"],
        ["ESC_DSHOT", "6 / 7 / 15 / 16", "4-in-1 ESC motor commands"],
        ["LEG_PWM", "18–19", "perch-leg micro servos (aim/crawl)"],
    ], rh=26)

    # block diagram
    by = 850
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
    s.t(ML + 495, by + 38, "2S LiPo", 13, "middle", weight="bold")
    s.t(ML + 495, by + 56, "3000 mAh · 22 Wh", 11, "middle", SOFT)
    s.arrow(ML + 580, by + 41, ML + 610, by + 41)
    s.rect(ML + 610, by + 16, 170, 50, fill=FILL, stroke=INK, sw=1.2)
    s.t(ML + 695, by + 38, "LDO 3V3", 13, "middle", weight="bold")
    s.t(ML + 695, by + 56, "always-on", 11, "middle", SOFT)
    s.note(ML + 10, by + 90,
          "ESP32-S3 supervises: SX1262 mesh + sensors on shared buses; 4-in-1 ESC draws straight "
          "from 2S and is power-gated at perch. Flight controller firmware supervises the quad.",
          size=12)
    out.append(s.svg(2, 8))

    # ---------------- 103 ASSEMBLY & ROLES ----------------
    s = Sheet("AF-S-103", "ASSEMBLY, FIRMWARE & ROLES",
              "BUILD SEQUENCE · DUTY CYCLE · ACCEPTANCE", "S · MITE")
    s.h(ML + 10, 150, "ASSEMBLY SEQUENCE")
    steps = [
        "Print frame, rotor ducts, shell, pod bay, perch legs — ASA/PC-ABS.",
        "Mount 4× motors + 4-in-1 ESC; wire DSHOT + power; prop direction check.",
        "Populate carrier: ESP32-S3, IMU+baro, flow cam, SX1262, ENS160, SHT41.",
        "Seat 2S battery; verify charge path (bench supply, solar sim, pogo dock).",
        "Close pod — gasket bead; install legs; IMU cal + static hover test (tethered).",
        "Field trial: 3 units — hop 50 m → perch → sense → return → dock, log 7 days.",
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
        ["Flight", "supervised quad loop — IMU/baro hold, flow-cam precision land"],
        ["Envelope", "same signed format as fleet — MUST match mesh-net"],
        ["Duty cycle", "perch-sleep 90%+ · sense 5 min · fly ≤2% · TX anomaly/sched"],
        ["Data", "pose + temp/RH/VOC + battery + RSSI + role → <200 B frame"],
        ["OTA", "signed updates over mesh (rev-C); USB/SD bench flash"],
    ], rh=34)

    s.h(760, 420, "ROLE ASSIGNMENT (SKETCH)")
    s.bullets(760, 446, [
        "All Mites broadcast hello + battery + capability every N hours.",
        "Anchor/Brick AI computes coverage gaps → assigns roles via signed cmd.",
        "Mites FLY to assigned perch sites — then hold position for days.",
        "Low battery (<20%) → unit flies home to an Anchor dock, charges, relaunches.",
        "Roles are soft state — units self-organize if coordinator is gone.",
    ], width=100)

    s.h(ML + 10, 560, "ACCEPTANCE / TEST CRITERIA")
    s.table(ML + 10, 578, [340, 660], ["Test", "Pass condition"], [
        ["Mesh range", "signed observations A→B via Brick/Anchor ≥3 km LOS"],
        ["Flight", "hop 50 m → perch → return → dock, hands-off, 10/10"],
        ["Autonomy", "≥60 days perch-only; ≥5 days at 4 hops/day"],
        ["Cold", "operates -30 °C; flight reserve protected below -15 °C"],
        ["Perch", "legs hold Ø25 mm branch through wind-shake test"],
        ["False positive", "<1 smoke alarm/week/unit in dust/inversion"],
    ], rh=34)
    out.append(s.svg(3, 8))
    return out


# ============================================================ E TOTEM =====
def totem():
    out = []

    # ---------------- 101 GA ----------------
    s = Sheet("AF-E-101", "GENERAL ARRANGEMENT — COMMUNITY BOARD",
              "POLE-MOUNTED PUBLIC E-INKE NOTICEBOARD + MESH NODE", "E · TOTEM")

    # ===== Fig. 1 — hero: totem on pole, board readable =====
    hx, hy = 500, 330
    # pole
    s.rect(hx + 210, hy - 190, 16, 620, fill="#d8d8d8", stroke=INK, sw=1.6)
    # solar eyebrow on top of board
    s.el.append(
        f'<g transform="rotate(-14 {hx} {hy - 150})">'
        f'<rect x="{hx - 150}" y="{hy - 176}" width="330" height="34" '
        f'fill="#dbe7f4" stroke="{INK}" stroke-width="1.4"/>'
        + "".join(
            f'<line x1="{hx - 150 + i * 66}" y1="{hy - 176}" '
            f'x2="{hx - 150 + i * 66}" y2="{hy - 142}" '
            f'stroke="{SOFT}" stroke-width="0.8"/>'
            for i in range(1, 5))
        + '</g>')
    # board cabinet — product shot
    G = s.device(hx, hy, 380, 265, 60, "#3a3f45", rad=12)
    # e-ink face on front — a real notice rendered
    s.rect(*s.fpt(G, 0.07, 0.10), G["w"] * 0.86, G["h"] * 0.62,
           fill="#e8ecdf", stroke=INK, sw=1.2)
    nx, ny = s.fpt(G, 0.11, 0.14)
    s.t(nx, ny + 14, "COMMUNITY NOTICE", 13, weight="bold", color="#2f3a2f")
    s.t(nx, ny + 34, "Wildfire smoke advisory —", 10, color="#3a4a3a")
    s.t(nx, ny + 50, "limit outdoor work today.", 10, color="#3a4a3a")
    s.ln(nx, ny + 62, nx + G["w"] * 0.70, ny + 62, "#9aa89a", 0.8)
    s.t(nx, ny + 78, "Posted: Band Office · verified", 9, color="#6b7c6b")
    # vent + status LED + speaker
    d_vent(s, *s.fpt(G, 0.10, 0.82), w=G["w"] * 0.3, n=7)
    d_led(s, *s.fpt(G, 0.88, 0.86), r=4)
    d_grille(s, *s.fpt(G, 0.62, 0.83), w=40, rows=2)
    # mount arms to pole
    for b in (0.18, 0.82):
        mx, my = s.spt(G, 1.0, b)
        s.rect(mx - 2, my - 9, hx + 226 - mx + 4, 18, fill="#e9e9e9",
               stroke=INK, sw=1.2, r=5)
        s.circ(hx + 218, my, 7, fill="none", stroke=INK, sw=1.2)
    # whip + gland
    awx, awy = s.tpt(G, 0.10, 0.10)
    d_whip(s, awx, awy, 60, lean=-8)
    for i in range(2):
        d_gland(s, *s.fpt(G, 0.36 + i * 0.22, 0.99))
    # callouts
    s.callout(*s.fpt(G, 0.5, 0.40), 60, 130, "E-INK NOTICE — signed content only")
    s.callout(hx - 150, hy - 176, 60, 190, "20-30 W PANEL — the eyebrow")
    s.callout(awx, awy - 55, 950, 120, "LORA WHIP — it routes, it repeats")
    s.callout(*s.fpt(G, 0.88, 0.86), 950, 460, "STATUS LED — mesh health")
    s.callout(hx + 218, hy - 265, 950, 260, "STRAP MOUNTS — any pole")
    s.callout(*s.fpt(G, 0.5, 0.99), 950, 580, "GLANDS — solar in, backhaul in")
    s.callout(*s.fpt(G, 0.10, 0.85), 60, 560, "VENT — drip edge, no condensation")
    figcap(s, hx + 30, 690, 1, "E TOTEM — the public surface IS a node")

    # ===== Fig. 2 — door open: interior =====
    i2x, i2y, i2w, i2h = 1130, 150, 330, 230
    s.rect(i2x, i2y, i2w, i2h, fill=FILL, stroke=INK, sw=1.6, r=8)
    s.rect(i2x + 14, i2y + 14, i2w - 28, i2h * 0.42, fill="#e8ecdf",
           stroke=INK, sw=1.0)
    s.t(i2x + i2w / 2, i2y + i2h * 0.26, "E-INK HAT (behind window)", 10,
        "middle", SOFT)
    d_pcb(s, i2x + 14, i2y + i2h * 0.52, i2w * 0.44, i2h * 0.34, "CM5 + LORA")
    s.rect(i2x + i2w * 0.55, i2y + i2h * 0.52, i2w * 0.40, i2h * 0.34,
           fill="#e9e9e9", stroke=INK, sw=1.0)
    s.t(i2x + i2w * 0.75, i2y + i2h * 0.66, "LiFePO4 20 Ah", 10, "middle",
        weight="bold")
    s.t(i2x + i2w * 0.75, i2y + i2h * 0.76, "+ MPPT", 9, "middle", SOFT)
    s.callout(i2x + 60, i2y + i2h * 0.6, 930, 230, "SAME CM5 AS L1 — common")
    s.callout(i2x + i2w * 0.75, i2y + i2h * 0.6, 930, 330, "AUTONOMY CELL")
    figcap(s, i2x + i2w / 2, i2y + i2h + 30, 2, "Door open — common guts")

    # ===== Fig. 3 — exploded =====
    e3x, e3y = 90, 780
    explode(s, e3x, e3y, 210, [
        ("DOOR + E-INK FACE", "#e8ecdf", "window + seal + notice"),
        ("ELECTRONICS TRAY", "#e4ede0", "CM5 + LoRa + MPPT"),
        ("BATTERY", "#f0e8d8", "LiFePO4 20 Ah"),
        ("CABINET + MOUNTS", "#3a3f45", "PC IP66 + strap brackets"),
    ], d=18, h=14, gap=19, callx=e3x + 280)
    figcap(s, e3x + 105, e3y + 170, 3, "Exploded — four assemblies")

    # ===== Fig. 4 — mount detail =====
    m4x, m4y = 660, 770
    s.h(m4x, m4y - 24, "POLE MOUNT DETAIL", 13)
    s.rect(m4x + 60, m4y, 60, 150, fill="#d8d8d8", stroke=INK, sw=1.4)
    for b in (20, 70, 120):
        s.rect(m4x + 16, m4y + b, 130, 16, fill="#e9e9e9", stroke=INK, sw=1.2,
               r=5)
        d_screw(s, m4x + 26, m4y + b + 8, r=4.5)
        d_screw(s, m4x + 136, m4y + b + 8, r=4.5)
    s.t(m4x + 90, m4y + 176, "band clamps x3 — two-person install", 10,
        "middle", SOFT)
    figcap(s, m4x + 90, m4y + 214, 4, "Mount — no concrete, no auger")

    # right column — what it is
    s.h(1130, 560, "WHY IT'S UNIQUE")
    s.bullets(1130, 586, [
        "Only noticeboard that IS a network node — routes, repeats, stores.",
        "Every notice signed — no anonymous flyers, publisher identity carried.",
        "Works when grid AND cell are down — the blackout case.",
        "EN/FR pipeline; the community controls what appears.",
    ], width=52)
    s.t(1130, 810, "Council, school, clinic, RCMP bulletins —", 10, color=SOFT)
    s.t(1130, 828, "the digital general-store board, owned", 10, color=SOFT)
    s.t(1130, 846, "by the community.", 10, color=SOFT)
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

    # ===== Fig. 1 — hero: station on pole, mites docked =====
    hx, hy = 500, 300
    # pole behind cabinet
    s.rect(hx + 240, hy - 120, 18, 560, fill="#d8d8d8", stroke=INK, sw=1.6)
    s.rect(hx + 236, hy - 120, 26, 14, fill="#e9e9e9", stroke=INK, sw=1.1, r=4)
    # solar panel arm + panel (tilted)
    s.ln(hx + 249, hy - 120, hx + 60, hy - 160, INK, 3)
    s.el.append(
        f'<g transform="rotate(-16 {hx + 60} {hy - 160})">'
        f'<rect x="{hx - 140}" y="{hy - 186}" width="400" height="52" '
        f'fill="#dbe7f4" stroke="{INK}" stroke-width="1.5"/>'
        + "".join(
            f'<line x1="{hx - 140 + i * 66}" y1="{hy - 186}" '
            f'x2="{hx - 140 + i * 66}" y2="{hy - 134}" '
            f'stroke="{SOFT}" stroke-width="0.9"/>'
            for i in range(1, 6))
        + f'</g>')
    # cabinet body — product shot
    G = s.device(hx, hy + 60, 300, 240, 70, "#3a4148", rad=10)
    fx, fy = G["fx"], G["fy"]
    # door seam + latches + hinges on front face
    s.seam(G, 0.05, 0.05, 0.90, 0.90)
    for yy in (0.28, 0.72):
        d_latch(s, *s.fpt(G, 0.06, yy))
    for yy in (0.25, 0.5, 0.75):
        d_hinge(s, *s.fpt(G, 0.90, yy))
    # vent louver + status LED + e-ink status window
    d_vent(s, *s.fpt(G, 0.14, 0.80), w=G["w"] * 0.30, n=7)
    d_led(s, *s.fpt(G, 0.80, 0.14), r=4)
    s.rect(*s.fpt(G, 0.14, 0.12), G["w"] * 0.34, G["h"] * 0.14,
           fill="#e8ecdf", stroke=INK, sw=0.9)
    sx0, sy0 = s.fpt(G, 0.14, 0.12)
    s.t(sx0 + G["w"] * 0.17, sy0 + G["h"] * 0.10, "MESH OK · 4 NODES", 9,
        "middle", "#3a4a3a", "bold")
    # dock rail on top face + 2 mites perched — quad silhouettes on pogo bays
    dtx, dty = s.tpt(G, 0.08, 0.30)
    dtx2, dty2 = s.tpt(G, 0.92, 0.30)
    s.ln(dtx, dty, dtx2, dty2, INK, 2.5)
    for i in (0, 1):
        mx, my = s.tpt(G, 0.22 + i * 0.40, 0.30)
        # rotor rings edge-on, pod between them, leg stubs down to rail
        for rdx in (-40, 40):
            s.el.append(f'<ellipse cx="{mx + rdx:.1f}" cy="{my - 34:.1f}" rx="26" '
                        f'ry="8" fill="#e8eef5" fill-opacity="0.4" '
                        f'stroke="{INK}" stroke-width="1.4"/>')
        s.rect(mx - 28, my - 46, 56, 22, fill="#3d4a42", stroke=INK, sw=1.2, r=7)
        s.ln(mx - 10, my - 24, mx - 10, my - 4, INK, 2)
        s.ln(mx + 10, my - 24, mx + 10, my - 4, INK, 2)
        s.circ(mx - 10, my - 2, 2.5, fill=INK)
        s.circ(mx + 10, my - 2, 2.5, fill=INK)
        s.ln(mx - 20, my - 46, mx + 20, my - 46, "#dbe7f4", 3)
    # third mite inbound — small silhouette with motion arrow
    imx, imy = s.tpt(G, 0.62, 1.35)
    s.rect(imx - 18, imy - 12, 36, 14, fill="#3d4a42", stroke=INK, sw=1, r=5)
    for rdx in (-26, 26):
        s.el.append(f'<ellipse cx="{imx + rdx:.1f}" cy="{imy - 6:.1f}" rx="17" '
                    f'ry="5" fill="none" stroke="{INK}" stroke-width="1.1"/>')
    s.arrow(imx, imy + 14, imx - 30, imy + 66, ACC, 1.2)
    # antennas on top edge
    a1x, a1y = s.tpt(G, 0.10, 0.05)
    a2x, a2y = s.tpt(G, 0.88, 0.05)
    d_whip(s, a1x, a1y, 64, lean=-8)
    d_whip(s, a2x, a2y, 64, lean=8)
    # cable glands bottom edge
    for i in range(3):
        d_gland(s, *s.fpt(G, 0.30 + i * 0.2, 0.99))
    # pole clamps behind (visible at side)
    for yy in (0.15, 0.80):
        px, py = s.spt(G, 1.0, yy)
        s.rect(px - 4, py - 8, 30, 16, fill="#e9e9e9", stroke=INK, sw=1.1, r=4)
    # callouts
    s.callout(*s.tpt(G, 0.42, 0.30), 60, 170, "SWARM DOCK RAIL — 4 pogo bays")
    s.callout(a1x, a1y - 60, 60, 110, "LORA WHIP ×2 — node + backbone")
    s.callout(hx - 140, hy - 186, 60, 200, "20–60 W PANEL — December-sized")
    s.callout(*s.fpt(G, 0.80, 0.14), 880, 140, "STATUS LED + E-INK health")
    s.callout(*s.fpt(G, 0.06, 0.28), 880, 300, "DRAW LATCH ×2 — glove-operable")
    s.callout(*s.fpt(G, 0.30, 0.80), 880, 440, "VENT LOUVER — bottom, no top")
    s.callout(*s.fpt(G, 0.5, 0.99), 880, 560, "CABLE GLANDS — solar/backhaul/power")
    s.callout(*s.spt(G, 1.05, 0.5), 60, 640, "U-BOLT POLE MOUNT — 76 mm pole")
    figcap(s, hx + 40, 690, 1, "A ANCHOR — field-deployed, two mites docked")

    # ===== Fig. 2 — door open: interior layout =====
    i2x, i2y, i2w, i2h = 1130, 150, 330, 250
    s.rect(i2x, i2y, i2w, i2h, fill=FILL, stroke=INK, sw=1.6, r=8)
    s.rect(i2x + 12, i2y + 12, i2w - 24, i2h * 0.52, fill="#e4ede0",
           stroke=INK, sw=1.1)
    s.t(i2x + 24, i2y + 32, "DIN RAIL", 10, weight="bold", color=SOFT)
    for i, nm in enumerate(("CM5", "LORA ×2", "MPPT", "CHARGE ×4", "TERM")):
        w2 = 52
        s.rect(i2x + 24 + i * 60, i2y + 44, w2, 60, fill="#cdd6ca",
               stroke=INK, sw=0.9)
        s.t(i2x + 24 + i * 60 + w2 / 2, i2y + 78, nm, 8, "middle", INK)
    s.rect(i2x + 12, i2y + i2h * 0.60, i2w - 24, i2h * 0.30,
           fill="#e9e9e9", stroke=INK, sw=1.1)
    s.t(i2x + i2w / 2, i2y + i2h * 0.72, "LiFePO4 50–100 Ah + BMS", 12,
        "middle", weight="bold")
    s.t(i2x + i2w / 2, i2y + i2h * 0.80, "tray — slide-out on rails", 10,
        "middle", SOFT)
    for i in range(3):
        d_gland(s, i2x + i2w * (0.3 + i * 0.2), i2y + i2h - 2)
    s.callout(i2x + 60, i2y + 70, 930, 165, "COMPUTE + RADIOS on DIN rail")
    s.callout(i2x + 30, i2y + i2h * 0.75, 930, 350,
              "BATTERY TRAY — hot-swap")
    figcap(s, i2x + i2w / 2, i2y + i2h + 30, 2, "Door open — serviceable guts")

    # ===== Fig. 3 — exploded =====
    e3x, e3y = 90, 720
    explode(s, e3x, e3y, 210, [
        ("DOOR + GASKET", "#e9e9e9", "2 latches, 3 hinges, TPU seal"),
        ("DOCK RAIL ASSY", "#d8d8d8", "4 pogo bays + CN3791 controllers"),
        ("DIN CHASSIS", "#e4ede0", "CM5 + radios + MPPT + terminals"),
        ("BATTERY TRAY", "#f0e8d8", "LiFePO4 + BMS on slide rails"),
        ("CABINET SHELL", "#3a4148", "powder-coat, pole U-bolts"),
    ], d=18, h=14, gap=19, callx=e3x + 280)
    figcap(s, e3x + 105, e3y + 200, 3, "Exploded — five assemblies")

    # ===== Fig. 4 — site install elevation =====
    s4x, s4y = 700, 740
    s.rect(s4x + 60, s4y + 30, 12, 170, fill="#d8d8d8", stroke=INK, sw=1.3)
    s.el.append(
        f'<g transform="rotate(-20 {s4x + 66} {s4y + 40})">'
        f'<rect x="{s4x - 20}" y="{s4y + 26}" width="172" height="26" '
        f'fill="#dbe7f4" stroke="{INK}" stroke-width="1.2"/></g>')
    s.rect(s4x + 20, s4y + 66, 90, 70, fill="#3a4148", stroke=INK, sw=1.4, r=6)
    s.ln(s4x + 66, s4y + 66, s4x + 66, s4y + 30, INK, 1.5)
    d_whip(s, s4x + 30, s4y + 66, 34)
    s.rect(s4x + 30, s4y + 190, 74, 8, fill="#b5a284", stroke=INK, sw=1)
    s.dimv(s4x + 8, s4y + 30, s4y + 200, "3 m pole")
    s.t(s4x + 190, s4y + 150, "cabinet chest-height —", 10, color=SOFT)
    s.t(s4x + 190, s4y + 166, "service without a ladder", 10, color=SOFT)
    figcap(s, s4x + 150, s4y + 230, 4, "Site install — pole + panel + cabinet")

    # ===== right column — role text =====
    s.h(1130, 560, "WHAT THE ANCHOR DOES")
    s.table(1130, 586, [140, 300], ["Function", "Detail"], [
        ["Swarm dock", "4 pogo bays — land, charge, rebroadcast"],
        ["Relay", "SX1262 at height — over ridges"],
        ["Gateway", "LTE/Wi-Fi/sat — the mesh's door out"],
        ["Beacon", "E-Ink status — readable infrastructure"],
    ], rh=42)
    s.t(1130, 810, "Docked mites top off → perpetual patrol.", 10, color=SOFT)
    s.t(1130, 828, "The visible, maintainable heart of the", 10, color=SOFT)
    s.t(1130, 846, "local mesh — communities pay for the", 10, color=SOFT)
    s.t(1130, 864, "gateway; the swarm rides on top.", 10, color=SOFT)
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
        ["ArctikChain sats", "future", "the mesh IS the ground segment"],
    ], rh=34)

    # dock protocol + acceptance — left column stack
    s.h(ML + 10, 700, "FIELD ACCEPTANCE")
    s.bullets(ML + 10, 726, [
        "4 Miters dock, charge, undock on schedule — 72 h soak.",
        "≥10 signed msgs/min relayed through Anchor at 5 km spacing.",
        "LTE failover: drop → store-forward continues → auto-reconnect.",
        "Winter: -30 °C, panel snow-covered 3 days → still docks + relays.",
    ], width=95, lh=17)

    s.h(ML + 10, 830, "DOCK PROTOCOL")
    s.bullets(ML + 10, 856, [
        "Mite lands on pogo pads → charge-detect line pulled low.",
        "Dock controller broadcasts slot assignment over LoRa.",
        "Charge until >80% or timeout; release + 'charged' beacon.",
        "Rotating priority: lowest-battery docked unit gets next slot.",
        "All dock events signed + logged — swarm energy is mesh data.",
    ], width=118)
    out.append(s.svg(2, 3))
    return out


# ============================================================ P PHONE =====
def phone():
    out = []

    # ---------------- 101 CONCEPT ----------------
    s = Sheet("AF-P-101", "CONCEPT — RURAL COMMS DEVICE",
              "MESH-NATIVE PHONE FOR RURAL & REMOTE CANADA", "P · ARCTICPHONE",
              rev="0", status="CONCEPT — NOT FROZEN", public=True)

    # ===== Fig. 1 — hero front, 3/4 slab with live AMOLED UI =====
    cx, cy = 470, 385
    G = s.device(cx, cy, 215, 440, 20, "#2b3440", rad=22)
    fx, fy, fw, fh = G["fx"], G["fy"], G["w"], G["h"]
    # integrated armor — thin corner accents molded into the frame, not pods
    for bx, by in ((0.0, 0.0), (0.90, 0.0), (0.0, 0.965), (0.90, 0.965)):
        px, py = s.fpt(G, bx, by)
        s.rect(px, py, fw * 0.10, fh * 0.030, fill="#3a4654",
               stroke=INK, sw=0.9, r=6)
    # screen: edge-to-edge LTPO AMOLED — status bar + mesh board + SOS tile
    scrx, scry = s.fpt(G, 0.045, 0.030)
    scrw, scrh = fw * 0.91, fh * 0.935
    s.rect(scrx, scry, scrw, scrh, fill="#0c1118", stroke=INK, sw=1.0, r=14)
    s.t(scrx + 10, scry + 18, "9:41", 11, color="#8fa3b5", weight="bold")
    s.t(scrx + scrw - 10, scry + 18, "5G · NTN · MESH 78%", 9, "end",
        color="#8fa3b5")
    s.ln(scrx + 10, scry + 30, scrx + scrw - 10, scry + 30, "#26303c", 0.8)
    s.rect(scrx + 10, scry + 44, scrw - 20, 148, fill="#131c26", r=10)
    s.t(scrx + scrw / 2, scry + 66, "COMMUNITY MESH", 11, "middle", "#5fb878",
        weight="bold", spacing="1")
    for i, (nm, dist) in enumerate((("L1-BRICK-04", "0.4 km"),
                                    ("E-TOTEM-01", "1.1 km"),
                                    ("A-ANCHOR-02", "2.7 km"))):
        ry = scry + 92 + i * 28
        s.circ(scrx + 22, ry - 4, 3.5, fill="#5fb878")
        s.t(scrx + 34, ry, nm, 10, color="#c9d4de")
        s.t(scrx + scrw - 18, ry, dist, 9, "end", color="#8fa3b5")
        s.ln(scrx + 16, ry + 8, scrx + scrw - 16, ry + 8, "#26303c", 0.7)
    s.rect(scrx + 10, scry + 204, (scrw - 28) / 2, 76, fill="#16222c", r=10)
    s.rect(scrx + 18 + (scrw - 28) / 2, scry + 204, (scrw - 28) / 2, 76,
           fill="#16222c", r=10)
    s.t(scrx + 10 + (scrw - 28) / 4, scry + 232, "GRID", 9, "middle", "#8fa3b5")
    s.t(scrx + 10 + (scrw - 28) / 4, scry + 258, "4 d", 14, "middle", "#c9d4de",
        weight="bold")
    s.t(scrx + 18 + (scrw - 28) * 0.75, scry + 232, "SAT SOS", 9, "middle",
        "#8fa3b5")
    s.t(scrx + 18 + (scrw - 28) * 0.75, scry + 258, "READY", 13, "middle",
        "#5fb878", weight="bold")
    s.rect(scrx + 10, scry + scrh - 74, scrw - 20, 54, fill="#7a2418",
           stroke=INK, sw=1, r=12)
    s.t(scrx + scrw / 2, scry + scrh - 42, "SOS — HOLD 3 S", 13, "middle",
        "#f4d7d2", weight="bold")
    s.rect(scrx + scrw * 0.38, scry + scrh - 12, scrw * 0.24, 4,
           fill="#3a4a5a", r=2)
    # hole-punch selfie camera + slim earpiece slit
    d_punch(s, *s.fpt(G, 0.5, 0.062), r=4.5)
    s.rect(*s.fpt(G, 0.38, 0.008), fw * 0.24, 4, fill="#15181d", r=2)
    # side face keys: vol rocker + power (right), SOS key (far edge, red)
    vx0, vy0 = s.spt(G, 0.55, 0.20)
    d_btn(s, vx0 - 2, vy0, G["dx"] + 8, 44)
    vx1, vy1 = s.spt(G, 0.55, 0.33)
    d_btn(s, vx1 - 2, vy1, G["dx"] + 8, 26)
    vx2, vy2 = s.spt(G, 0.10, 0.26)
    d_btn(s, vx2 - 2, vy2, 8, 52, color="#a83c2e")
    # bottom edge on side face: USB-C + speaker
    bx_, by_ = s.spt(G, 0.5, 0.92)
    d_usbc(s, bx_ + 4, by_, 0.7)
    s.callout(*s.fpt(G, 0.5, 0.34), 120, 200,
              "6.5″ AMOLED 120 HZ — glove-touch")
    s.callout(*s.fpt(G, 0.5, 0.062), 120, 130, "PUNCH-HOLE SELFIE — 12 MP AF")
    s.callout(*s.fpt(G, 0.88, 0.02), 845, 165,
              "INTEGRATED ARMOR — crush zones inside")
    s.callout(*s.fpt(G, 0.5, 0.88), 870, 615, "SOS TILE — one gloved press")
    s.callout(vx2 + 3, vy2 + 20, 890, 350, "SOS KEY — hardware path")
    s.callout(bx_ + 4, by_, 890, 530, "USB-C 45 W — gasketed")
    s.callout(*s.fpt(G, 0.14, 0.55), 120, 540,
              "MESH BOARD — nodes, no towers")
    figcap(s, cx, 655, 1, "ArcticPhone — front, edge-to-edge mesh UI")

    # ===== Fig. 2 — rear view: camera island + inset module bay =====
    r2x, r2y, r2w, r2h = 1075, 150, 200, 390
    s.rect(r2x, r2y, r2w, r2h, fill="#2b3440", stroke=INK, sw=1.6, r=24)
    # antenna seams — flagship frame detail
    s.ln(r2x + 8, r2y + r2h * 0.075, r2x + r2w - 8, r2y + r2h * 0.075,
         "#4a5563", 1.6)
    s.ln(r2x + 8, r2y + r2h * 0.93, r2x + r2w - 8, r2y + r2h * 0.93,
         "#4a5563", 1.6)
    # camera island — squircle bump, triple lens + flash + mic
    d_camisle(s, r2x + r2w * 0.09, r2y + r2h * 0.11, r2w * 0.44, r2h * 0.20)
    # module bay — inset panel, slimmer footprint, flush thumb screws
    s.rect(r2x + r2w * 0.14, r2y + r2h * 0.36, r2w * 0.72, r2h * 0.46,
           fill="#232c38", stroke=INK, sw=1.2, r=12)
    s.t(r2x + r2w * 0.5, r2y + r2h * 0.43, "MODULE BAY", 11, "middle",
        "#8fa3b5", weight="bold", spacing="1")
    s.t(r2x + r2w * 0.5, r2y + r2h * 0.485, "sat · batt · sensor pod", 8,
        "middle", "#6b7c8c")
    for i in range(4):
        d_pogo(s, r2x + r2w * (0.28 + i * 0.15), r2y + r2h * 0.56, r=3.5)
    s.t(r2x + r2w * 0.5, r2y + r2h * 0.62, "pogo bus ×4", 8, "middle", SOFT)
    d_thumbs(s, r2x + r2w * 0.24, r2y + r2h * 0.76, r=7)
    d_thumbs(s, r2x + r2w * 0.76, r2y + r2h * 0.76, r=7)
    s.t(r2x + r2w * 0.5, r2y + r2h * 0.885, "ARCTIKCHAIN", 11, "middle",
        "#8fa3b5", weight="bold", spacing="2")
    s.t(r2x + r2w * 0.5, r2y + r2h * 0.915, "EMEBET INC.", 7, "middle", "#5b6a78",
        spacing="1.5")
    s.callout(r2x + r2w * 0.30, r2y + r2h * 0.16, 920, 110,
              "CAMERA ISLAND — 50 MP OIS + UW + FLIR")
    s.callout(r2x + r2w * 0.5, r2y + r2h * 0.46, 880, 320,
              "BAY COVER — inset ~45% rear")
    s.callout(r2x + r2w * 0.76, r2y + r2h * 0.76, 1320, 130,
              "THUMB SCREWS ×2 — flush, tool-light")
    figcap(s, r2x + r2w / 2, r2y + r2h + 30, 2,
           "Rear — camera island + inset module bay")

    # ===== Fig. 3 — side profiles (L/R) =====
    p3x, p3y = 1380, 210
    for k, (lbl, keys) in enumerate((("L", "sos"), ("R", "vol"))):
        px = p3x + k * 100
        s.rect(px, p3y, 36, 330, fill="#2b3440", stroke=INK, sw=1.4, r=12)
        if keys == "sos":
            d_btn(s, px - 7, p3y + 70, 8, 56, color="#a83c2e")
            s.t(px + 18, p3y + 240, "SOS", 9, "middle", "#a83c2e", "bold")
        else:
            d_btn(s, px + 35, p3y + 60, 8, 44)
            d_btn(s, px + 35, p3y + 118, 8, 26)
            s.t(px + 18, p3y + 240, "VOL·PWR", 8, "middle", "#8fa3b5")
        s.ln(px + 8, p3y + 318, px + 28, p3y + 318, SOFT, 0.8)
        s.t(px + 18, p3y + 352, ["LEFT", "RIGHT"][k], 10, "middle", SOFT, "bold")
    s.t(p3x + 50, p3y + 386, "flat rails · keys proud — gloved hands", 9,
        "middle", SOFT)
    figcap(s, p3x + 50, p3y + 424, 3, "Edge profiles — hardware keys")

    # ===== Fig. 4 — exploded assembly =====
    e4x, e4y = 90, 680
    explode(s, e4x, e4y, 170, [
        ("GLASS + LTPO AMOLED", "#10151c", "6.5″ panel, bonded to midframe"),
        ("MIDFRAME + PCB", "#e4ede0", "SoC + mesh radio + NTN + antennas"),
        ("CAMERA ISLAND ASSY", "#232c38", "50 MP OIS + UW + thermal, 4 screws"),
        ("SI/C BATTERY", "#f0e8d8", "5500 mAh — 2 screws, tool-light swap"),
        ("REAR SHELL", "#e9e9e9", "matte PC+TPU, no glass back"),
        ("BAY COVER", "#d8d8d8", "thumb screws + gasket + pogo bus"),
    ], d=16, h=13, gap=17, callx=e4x + 226)
    figcap(s, e4x + 85, e4y + 232, 4, "Exploded — repairable, not glued")

    # ===== Fig. 5 — corner section: internal armor + gasket =====
    c5x, c5y = 640, 690
    s.h(c5x, c5y - 26, "CORNER SECTION — DROP PROTECTION", 13)
    s.rect(c5x + 40, c5y + 10, 200, 110, fill="#2b3440", stroke=INK, sw=1.3,
           r=10)
    s.rect(c5x + 58, c5y + 28, 164, 74, fill="#10151c", stroke=SOFT, sw=0.9,
           r=6)
    s.poly([(c5x + 40, c5y + 10), (c5x + 66, c5y + 10), (c5x + 66, c5y + 34),
            (c5x + 52, c5y + 40), (c5x + 40, c5y + 40)],
           fill="#4a5563", stroke=INK, sw=1.1)
    d_screw(s, c5x + 70, c5y + 18, r=6)
    s.ln(c5x + 40, c5y + 10, c5x + 40 + 200, c5y + 10, SOFT, 0.8, "4 3")
    s.callout(c5x + 48, c5y + 20, c5x + 20, c5y - 48,
              "ARMOR RIB — molded in, crush zone")
    s.callout(c5x + 130, c5y + 64, c5x + 250, c5y + 150,
              "AMOLED floats 1.2 mm")
    s.callout(c5x + 200, c5y + 118, c5x + 250, c5y + 190,
              "GASKET LIP — IP68/69K")
    figcap(s, c5x + 140, c5y + 215, 5, "Section A — 1.8 m drop target")

    # right column — decision context (kept compact, above title block)
    s.h(1050, 650, "ARCHITECTURE DECISION")
    s.table(1050, 674, [40, 240, 230], ["Opt", "Approach", "Trade"], [
        ["A", "Rugged Android + mesh HAT", "fast — bloat + cert effort"],
        ["B", "Custom Linux + mesh SoC", "clean — OS work"],
        ["C", "Linux core + Android layer", "both — longest dev"],
    ], rh=42)
    s.t(1050, 850, "Flagship look, rural heart: mesh-native,", 10, color=SOFT)
    s.t(1050, 867, "sat-SOS-ready, offline-first, repairable,", 10, color=SOFT)
    s.t(1050, 884, "community-owned.", 10, color=SOFT)
    out.append(s.svg(1, 7))

    # ---------------- 102 SPEC ----------------
    s = Sheet("AF-P-102", "SPECIFICATION SKETCH",
              "TARGET SPEC · BOM CATEGORIES · ROADMAP", "P · ARCTICPHONE",
              rev="0", status="CONCEPT — NOT FROZEN")
    s.h(ML + 10, 150, "TARGET SPECIFICATION")
    s.table(ML + 10, 168, [240, 220, 240, 260], ["Parameter", "Target", "Parameter", "Target"], [
        ["Envelope", "~168×77×11 mm", "Mass", "~240 g"],
        ["Display", "6.5″ LTPO AMOLED 120 Hz", "SoC", "SD-7s/Dimensity-8 class + GNSS"],
        ["Mesh radio", "SX1262 915 + MCU", "Cellular", "5G sub-6 + eSIM"],
        ["Sat SOS", "NTN messaging + L-band", "Camera", "50 MP OIS + UW + thermal opt."],
        ["Battery", "5,500 mAh Si/C swap", "Charging", "USB-C 45 W + pogo dock"],
        ["OS", "hardened Android or Linux", "UI", "glove-first, EN/FR"],
        ["Rating", "IP68/69K · MIL-810H · -30..+55", "Repair", "screws — screen/batt/bay"],
    ], rh=34)

    s.h(ML + 10, 480, "BOM CATEGORIES (NOT FIXED — ARCHITECTURE PENDING)")
    s.table(ML + 10, 506, [190, 560], ["Category", "Options / notes"], [
        ["Compute+display", "rugged 5G module (A) OR custom board (B) — 6.5″ AMOLED"],
        ["Mesh module", "SX1262 + nRF52/ESP32 — same envelope as fleet"],
        ["Sat messenger", "NTN chipset (Skylo-class) or L-band module — rev-A"],
        ["Cellular", "5G sub-6 modem + eSIM — carrier path, mesh fallback"],
        ["Camera", "50 MP OIS main + UW; FLIR-ONE-class thermal on bay module"],
        ["Power", "5500 mAh Si/C pouch + USB-C 45 W PD + pogo dock"],
        ["Enclosure", "Al frame + PC/TPU armor-in — gasketed, captive screws"],
    ], rh=36)

    s.h(ML + 10, 820, "ROADMAP TO FIRST UNIT")
    s.bullets(ML + 10, 848, [
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
              rev="0", status="RESEARCH — NOT A PRODUCT", public=True)

    s.h(ML + 10, 150, "THE IDEA")
    s.bullets(ML + 10, 180, [
        "A ~20 mm mote of printed electronics on biodegradable substrate — seed-dropped over a fuel break or burn scar.",
        "It sprouts into a temporary sensor skin for fire season, reports through cluster heads, and dissolves.",
        "Zero e-waste, no retrieval, no grid to build — sensing that ENDS by design.",
        "Materials/transient-electronics program — fundable R&D, not a product. Every earlier rung must succeed first.",
    ], width=118)

    s.h(ML + 10, 420, "RESEARCH TARGETS")
    s.table(ML + 10, 448, [200, 560], ["Target", "Goal"], [
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
    s.table(900, 178, [180, 470], ["Component", "Candidate materials / approach"], [
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
        "TRL ~2 — concept + literature. No ArctikChain mote exists yet.",
        "This sheet is a research brief, not a buildable BOM — deliberately.",
        "Swarm architecture is the same — only the node shrinks.",
        "Do NOT promise motes to funders until Gate 2 demo exists.",
    ], width=92, color=RED)
    out.append(s.svg(1, 4))
    return out


# ============================================================ H MERIDIAN ====
def meridian():
    out = []
    s = Sheet("AF-H-101", "MISSION CONCEPT — SATELLITE PAYLOAD",
              "STORE-AND-FORWARD CONSTELLATION — THE MESH IS THE GROUND SEGMENT",
              "H · MERIDIAN", rev="0", status="VISION — EARNED", public=True)

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
    out.append(s.svg(1, 2))
    return out


def meridian_bus():
    s = Sheet("AF-H-102", "BUS LAYOUT & DEPLOYMENT",
              "CUBESAT CONCEPT — STORE-FORWARD PAYLOAD ON COMMERCIAL BUS",
              "H · MERIDIAN", rev="0", status="VISION — EARNED")

    # ===== Fig. 1 — CubeSat deployed, isometric =====
    cx, cy = 480, 330
    # solar wings
    for sign in (-1, 1):
        wx = cx + sign * 150
        s.poly([(wx, cy - 60), (wx + sign * 190, cy - 60),
                (wx + sign * 190, cy + 60), (wx, cy + 60)],
               fill="#dbe7f4", stroke=INK, sw=1.4)
        for i in range(1, 6):
            gx = wx + sign * i * 31
            s.ln(gx, cy - 60, gx, cy + 60, SOFT, 0.8)
        s.ln(wx, cy - 60, wx, cy + 60, INK, 2)
    # 3U bus — product shot
    G = s.device(cx, cy, 130, 300, 90, "#8a8f96", rad=6)
    # card rails + separation seams
    for b in (0.33, 0.66):
        px0, py0 = s.fpt(G, 0.03, b)
        px1, py1 = s.fpt(G, 0.97, b)
        s.ln(px0, py0, px1, py1, SOFT, 1.2)
    # payload window + antenna + sun sensors + rail screw heads
    s.rect(*s.fpt(G, 0.28, 0.38), G["w"] * 0.44, G["h"] * 0.20,
           fill="#2c3e50", stroke=INK, sw=1.0)
    tx0, ty0 = s.fpt(G, 0.28, 0.38)
    s.t(tx0 + G["w"] * 0.22, ty0 + G["h"] * 0.11, "PAYLOAD", 9, "middle",
        "#aaccee", "bold")
    for a, b in ((0.06, 0.04), (0.94, 0.04), (0.06, 0.96), (0.94, 0.96)):
        d_screw(s, *s.fpt(G, a, b), r=4)
    # UHF dipole + GNSS patch on top face
    ax_, ay_ = s.tpt(G, 0.5, 0.4)
    s.poly([(ax_ - 70, ay_ - 10), (ax_ + 70, ay_ - 10),
            (ax_ + 70, ay_ - 4), (ax_ - 70, ay_ - 4)],
           fill="none", stroke=INK, sw=1.2)
    d_led(s, *s.fpt(G, 0.85, 0.08), r=3.5)
    # callouts
    s.callout(*s.fpt(G, 0.5, 0.48), 60, 130,
              "S/F PAYLOAD — mesh envelopes, store + relay")
    s.callout(*s.tpt(G, 0.5, 0.4), 60, 220,
              "UHF DIPOLE — deployable, talks to the mesh")
    s.callout(*s.fpt(G, 0.5, 0.10), 950, 140,
              "GNSS + BEACON — position + health")
    s.callout(*s.fpt(G, 0.5, 0.80), 700, 470,
              "BATTERIES + ADCS — momentum wheel class")
    s.callout(cx + 340, cy - 60, 950, 500,
              "DEPLOYABLE WINGS — body-mounted + panel pair")
    s.callout(*s.spt(G, 0.9, 0.5), 60, 620,
              "1U/3U BUS — GOMspace/EnduroSat class, not bespoke")
    figcap(s, 560, 575, 1, "H MERIDIAN — store-forward CubeSat, deployed")

    # ===== Fig. 2 — bus interior stack =====
    e2x, e2y = 1050, 150
    s.h(e2x, e2y - 26, "BUS INTERIOR — STACK", 13)
    for i, (nm, sub) in enumerate((
            ("PAYLOAD BOARD", "S/F radio + flash store"),
            ("OBC + EPS", "computer + power mgmt"),
            ("BATTERY PACK", "Li-ion, heater-wrapped"),
            ("ADCS", "magnetorquers + sun sensors"),
            ("STRUCTURE", "rails + separation ring"))):
        yy = e2y + i * 56
        s.rect(e2x, yy, 380, 44, fill=FILL if i % 2 else "#e4ede0",
               stroke=INK, sw=1.1)
        s.t(e2x + 14, yy + 19, nm, 12, weight="bold")
        s.t(e2x + 14, yy + 36, sub, 10, color=SOFT)
    figcap(s, e2x + 190, e2y + 310, 2, "Stack — commercial bus cards")

    # ===== Fig. 3 — ground pass: sat over the mesh =====
    p3x, p3y = 90, 700
    s.h(p3x, p3y - 26, "GROUND PASS — THE MESH IS THE TERMINAL", 13)
    s.el.append(
        f'<path d="M {p3x} {p3y + 60} A 420 120 0 0 1 {p3x + 840} {p3y + 60}" '
        f'fill="none" stroke="{SOFT}" stroke-width="1.2" stroke-dasharray="8 5"/>')
    s.rect(p3x + 390, p3y - 40, 60, 40, fill="#8a8f96", stroke=INK, sw=1.2, r=4)
    s.t(p3x + 420, p3y + 60, "H MERIDIAN", 10, "middle", SOFT, "bold")
    for i in range(4):
        nx_ = p3x + 60 + i * 220
        s.circ(nx_, p3y + 190, 10, fill="#3d4a42", stroke=INK, sw=1.2)
        s.ln(nx_, p3y + 180, nx_, p3y + 150, SOFT, 0.9, "3 3")
    s.t(p3x + 420, p3y + 230,
        "each pass: envelopes up, tasks down — minutes, not months", 11, "middle", SOFT)
    figcap(s, p3x + 420, p3y + 270, 3, "Store-and-forward — one pass = mail run")

    # right column — honest status
    s.h(1130, 560, "WHAT MAKES IT CHEAP")
    s.bullets(1130, 586, [
        "Payload = mesh radio + flash — no bespoke instruments.",
        "Bus = commercial 1U/3U — rideshare-ready.",
        "Ground segment already deployed — the mesh is the terminal layer.",
        "Coverage-first, not bandwidth — text/sensor tier only.",
    ], width=52)
    s.t(1130, 810, "Pathfinder: hosted payload → university", 10, color=SOFT)
    s.t(1130, 828, "CubeSat (CSA) → dedicated smallsat.", 10, color=SOFT)
    s.t(1130, 846, "Earned, not promised.", 10, color=SOFT)
    return [s.svg(2, 2)]


# ============================================================ D SEED FIGURE ==
def seed_anatomy():
    s = Sheet("AF-D-104", "MOTE ANATOMY & DEPLOYMENT",
              "PRINTED MOTE — LAYER STACK · POD · FIELD DEPLOYMENT",
              "D · SEED", rev="0", status="RESEARCH — NOT A PRODUCT")

    # ===== Fig. 1 — exploded printed layer stack =====
    e1x, e1y = 90, 160
    s.h(e1x, e1y - 30, "MOTE LAYER STACK — ALL PRINTED", 13)
    layers = [
        ("ENCAPSULATION", "#e9e9e9", "biofilm — degrades on schedule"),
        ("PRINTED ANTENNA", "#dbe7f4", "915 MHz coil or backscatter patch"),
        ("SENSOR INK LAYER", "#e4ede0", "temp/RH/VOC printed sensors"),
        ("LOGIC + COMMS", "#f0e8d8", "organic TFT or discrete µW die"),
        ("PRINTED BATTERY", "#dcd0c0", "Zn/MnO2 + PV/TEG harvest"),
        ("SUBSTRATE", "#d8d8d8", "cellulose / silk fibroin"),
    ]
    yy = e1y
    for i, (nm, color, det) in enumerate(layers):
        d_slab(s, e1x, yy, 300, d=18, h=13, color=color)
        s.t(e1x + 400, yy + 11, nm, 11.5, weight="bold")
        s.t(e1x + 400, yy + 27, det, 10, color=SOFT)
        s.ln(e1x + 318, yy + 6, e1x + 392, yy + 10, SOFT, 0.7)
        if i < len(layers) - 1:
            s.ln(e1x + 150, yy + 13, e1x + 150, yy + 33, SOFT, 0.8, "3 3")
        yy += 33
    figcap(s, e1x + 150, yy + 34, 1, "Mote anatomy — six printed layers")

    # ===== Fig. 2 — mote top view =====
    m2x, m2y = 760, 170
    s.h(m2x, m2y - 30, "TOP VIEW — Ø ~20 mm", 13)
    s.circ(m2x + 110, m2y + 110, 100, fill="#efe9dd", stroke=INK, sw=1.4)
    for r_ in (86, 66, 46):
        s.circ(m2x + 110, m2y + 110, r_, fill="none", stroke=SOFT, sw=0.8)
    s.circ(m2x + 110, m2y + 110, 26, fill="#e4ede0", stroke=INK, sw=1.0)
    s.t(m2x + 110, m2y + 114, "DIE", 10, "middle", weight="bold")
    s.callout(m2x + 110 + 66, m2y + 110 - 66, 1030, 120,
              "PRINTED COIL ANTENNA")
    s.callout(m2x + 110, m2y + 110, 1030, 240, "SENSOR + µW DIE")
    s.dimh(m2x + 10, m2x + 210, m2y + 234, "20")
    figcap(s, m2x + 110, m2y + 270, 2, "Mote face — coil, window, die")

    # ===== Fig. 3 — deployment sequence =====
    p3x, p3y = 90, 560
    s.h(p3x, p3y - 30, "DEPLOYMENT — SEED → SPROUT → SENSOR", 13)
    stages = [
        ("POD DROP", "coated pod — ground/air drop"),
        ("GERMINATION", "moisture opens pod — mote out"),
        ("WAKE + SENSE", "harvest starts — reports to head"),
        ("DEGRADE", "dissolves in <12 mo"),
    ]
    for i, (nm, sub) in enumerate(stages):
        bx = p3x + i * 236
        s.rect(bx, p3y, 210, 60, fill=FILL, stroke=INK, sw=1.1)
        s.t(bx + 12, p3y + 25, nm, 12, weight="bold")
        s.t(bx + 12, p3y + 44, sub, 9, color=SOFT)
        if i < 3:
            s.arrow(bx + 210, p3y + 30, bx + 234, p3y + 30)
    figcap(s, p3x + 465, p3y + 130, 3, "Lifecycle — one fire season, then gone")

    # ===== Fig. 4 — cluster relay =====
    c4x, c4y = 90, 800
    s.h(c4x, c4y - 28, "FIELD TOPOLOGY — MOTES → HEAD → MESH", 13)
    for i in range(8):
        mx = c4x + i * 78
        s.circ(mx, c4y + 50, 9, fill="#efe9dd", stroke=INK, sw=1.0)
    s.circ(c4x + 300, c4y + 130, 16, fill="#3d4a42", stroke=INK, sw=1.3)
    s.t(c4x + 300, c4y + 168, "CLUSTER HEAD", 10, "middle", SOFT, "bold")
    for i in range(8):
        s.ln(c4x + i * 78, c4y + 58, c4x + 300, c4y + 118, SOFT, 0.5, "3 4")
    s.t(c4x + 700, c4y + 130, "→ Anchor/Brick backbone", 12, color=SOFT)
    s.t(c4x + 700, c4y + 165, "Motes whisper to heads; only", 11, color=SOFT)
    s.t(c4x + 700, c4y + 183, "anomalies reach the backbone.", 11, color=SOFT)
    s.t(c4x + 700, c4y + 201, "Density is free; backhaul is precious.", 11, color=SOFT)

    # right column — honest status
    s.h(1130, 560, "WHY THIS IS RESEARCH")
    s.bullets(1130, 586, [
        "TRL ~2 — concept + literature; no ArctikChain mote exists yet.",
        "Precedent: DARPA/NSF computational-dust programs prove the physics.",
        "Swarm architecture unchanged — only the node shrinks.",
        "Do NOT promise motes to funders until Gate 2 lab demo exists.",
    ], width=52, color=RED)
    s.t(1130, 800, "Targets: <1 g · <$1 · one fire season", 10, color=SOFT)
    s.t(1130, 818, "· degrade <12 mo. Earlier rungs first.", 10, color=SOFT)
    return s.svg(4, 4)


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
    return s.svg(4, 5)


# ============================================================ L1 FINISH ======
def finish_sheet(dwg, title, subtitle, node, sheet_no, sheets_total,
                 renders, materials, finishes, notes, public=False):
    """Shared FINISH & MATERIALS sheet builder.
    renders: list of (iso-callable spec dict)
    materials: table rows [component, material, finish, note]
    finishes: list of (color_hex, name, sub) swatches
    notes: bullet list"""
    s = Sheet(dwg, "FINISH & MATERIALS — FINAL LOOK",
              subtitle, node, status="APPEARANCE REV A", public=public)

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
            elif kind == "ring":
                _, fxr, fyr, frx = det[:4]
                x, y = s.fpt(G, fxr, fyr)
                rr_ = frx * G["w"] / 2
                s.el.append(f'<ellipse cx="{x:.1f}" cy="{y:.1f}" rx="{rr_:.1f}" '
                            f'ry="{rr_ * 0.38:.1f}" fill="#e8eef5" fill-opacity="0.35" '
                            f'stroke="{INK}" stroke-width="1.7"/>')
                s.circ(x, y, rr_ * 0.14, fill="#2c3e50", stroke=INK, sw=0.8)
            elif kind == "leg":
                _, fx0, fy0, fx1, fy1 = det[:5]
                x0, y0 = s.fpt(G, fx0, fy0)
                x1, y1 = s.fpt(G, fx1, fy1)
                mx = (x0 + x1) / 2 + (x1 - x0) * 0.25
                my = (y0 + y1) / 2 + 8
                s.ln(x0, y0, mx, my, INK, 2.6)
                s.ln(mx, my, x1, y1, INK, 2.2)
                s.circ(mx, my, 3, fill="#e9e9e9", stroke=INK, sw=0.8)
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
                ("logo", "ARCTIKCHAIN", 0.5, 0.90, 9),
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
            "No painted logos — laser-etched 'ARCTIKCHAIN · EMEBET INC.' on rear.",
            "Color does NOT change internals — same BOM, different filament only.",
            "Rev-B: soft-touch TPU overmold option for consumer feel.",
        ], public=True)


# ============================================================ MITE ELECTRONICS =
def mite_electronics():
    s = Sheet("AF-S-104", "CARRIER ELECTRONICS DETAIL",
              "BLOCK DIAGRAM · SLEEP DOMAINS · RF CHAIN", "S · MITE")

    # block diagram
    bx, by = ML + 10, 215
    s.h(bx, 130, "CARRIER BLOCK DIAGRAM (38×38 mm)")
    blocks = [
        (bx + 10, by, 170, 56, "ESP32-S3", "mesh + flight supervisor", "#dfe9f5"),
        (bx + 230, by - 75, 180, 52, "SX1262", "LoRa 915 · SPI", "#dfe9f5"),
        (bx + 230, by + 10, 180, 52, "IMU + BARO", "ICM-42688 + BMP390", "#f5e6d0"),
        (bx + 230, by + 115, 180, 52, "ENS160+SHT41", "I2C · gas+env", "#dfe9f5"),
        (bx + 230, by + 190, 180, 52, "FLOW + TOF", "PMW3901 + VL53L5CX", "#f5e6d0"),
        (bx + 450, by - 35, 170, 56, "CN3791", "solar charge · MPPT", "#dfe9f5"),
        (bx + 450, by + 95, 170, 56, "4-IN-1 ESC", "DSHOT · gated at perch", "#f0d0d0"),
        (bx + 660, by - 75, 160, 50, "2S LiPo 3000", "22 Wh · JST", "#f5e6d0"),
        (bx + 660, by + 55, 160, 56, "POGO DOCK", "2-pad + notch", "#dfe9f5"),
        (bx + 450, by + 170, 170, 50, "MOTORS ×4 + LEGS", "1104 BLDC · micro servos", "#f0d0d0"),
        (bx + 660, by + 170, 160, 50, "ANTENNA", "PCB meander / whip", "#dfe9f5"),
    ]
    for x, y, w, h, t1, t2, col in blocks:
        s.rect(x, y, w, h, fill=col, stroke=INK, sw=1.2)
        s.t(x + w / 2, y + h / 2 - 4, t1, 13, "middle", weight="bold")
        s.t(x + w / 2, y + h / 2 + 14, t2, 10, "middle", SOFT)
    # links
    s.arrow(bx + 180, by + 10, bx + 230, by - 45)
    s.arrow(bx + 180, by + 28, bx + 230, by + 36)
    s.arrow(bx + 180, by + 46, bx + 230, by + 140)
    s.arrow(bx + 180, by + 55, bx + 230, by + 215)
    s.arrow(bx + 410, by + 36, bx + 450, by + 60)
    s.ln(bx + 620, by - 15, bx + 660, by - 45, SOFT, 1)
    s.ln(bx + 620, by + 83, bx + 660, by + 80, SOFT, 1)
    s.ln(bx + 620, by + 195, bx + 660, by + 195, SOFT, 1)
    s.ln(bx + 535, by + 122, bx + 535, by + 170, SOFT, 1)
    s.note(bx, by + 262, "ESP32-S3 = brain · SX1262 = voice · ESC + motors gated "
         "— stone dead at perch.", size=12)

    # sleep domains — left bottom
    s.h(bx, 512, "SLEEP DOMAINS (WHO STAYS ON)")
    s.table(bx, 538, [200, 320, 300], ["Domain", "State in deep sleep", "Wake source"], [
        ["ESP32-S3", "ULP RISC-V only", "RTC timer / GPIO"],
        ["SX1262", "sleep (~µA) + CAD armed", "DIO1 / host poll"],
        ["ENS160+SHT41", "power-gated OFF", "ESP32 rail control"],
        ["IMU + flow/ToF", "OFF — flight sensors", "flight mode only"],
        ["ESC + motors", "UNPOWERED at perch", "mission command"],
        ["Leg servos", "hold position, unpowered", "aim/crawl task"],
        ["CN3791", "always (harvesting)", "— hardware"],
        ["RTC", "always", "32 kHz crystal"],
    ], rh=30)

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
        "Mission command → spin-up self-check → fly or decline (reserve).",
        "Dock pogo detect → charge mode + beacon boost.",
        "IMU motion detect → tamper/perch-slip alert.",
        "All wake sources logged — swarm energy is mesh data.",
    ], width=88)
    return s.svg(4, 8)


# ============================================================ MITE VARIANTS ====
def mite_variants():
    s = Sheet("AF-S-105", "SWARM VARIANTS — ROLE PAYLOADS",
              "ONE PLATFORM · FOUR ROLES · DIFFERENT BOM DELTAS", "S · MITE")

    s.h(ML + 10, 150, "VARIANT MATRIX")
    s.table(ML + 10, 178, [105, 240, 300, 175],
            ["Variant", "Payload delta", "Extra parts", "Cost / detection role"], [
        ["SENSOR-BEE", "ENS160 + SHT41 (base)", "— none —", "+$0 · primary gas/temp anomaly"],
        ["EYE-BEE", "thermal IR pod (rev-C)", "AMG8833/MLX90640 + lens in pod", "+$25–45 · confirm fixes visually"],
        ["RELAY-BEE", "high-gain whip pod", "915 MHz whip 8 dBi", "+$8–15 · flies to ridge, holds relay"],
        ["SCOUT-BEE", "extra 2S pack, no pod", "double flight reserve", "+$20–30 · patrol / convoy / retrieval"],
    ], rh=52)

    s.h(ML + 10, 480, "ROLE SELECTION LOGIC")
    s.bullets(ML + 10, 508, [
        "All variants share: quad ducts + legs + ESP32-S3 + SX1262 + solar + 2S + pogo dock.",
        "Coordinator (Anchor/Brick) assigns role via signed command — soft state, self-heals.",
        "Fire season: 70% sensor-bees at fuel breaks, 20% relay on ridgelines, 10% scouts.",
        "Units fly to assigned perches; hop only when retasked, perching is the job.",
        "Eye-bees are rev-C — thermal pod needs carrier respin; sensor-bees fly first.",
    ], width=110)

    s.h(ML + 10, 720, "COST AT VOLUME (EST.)")
    s.table(ML + 10, 748, [200, 200, 200, 200], ["Volume", "Sensor", "Relay", "All variants blended"], [
        ["1–10 units", "$150–200 ea", "$160–210 ea", "≈$180 avg"],
        ["100 units", "$90–130 ea", "$95–140 ea", "≈$110 avg"],
        ["1,000 units", "$65–90 ea", "$70–95 ea", "≈$80 avg"],
        ["10,000+", "$45–65 ea", "$50–70 ea", "≈$55 avg — seed-drop economics"],
    ], rh=38)

    s.h(880, 150, "PHYSICAL DIFFERENCES")
    s.table(880, 178, [160, 460], ["Variant", "What changes physically"], [
        ["SENSOR-BEE", "base build — solar deck + belly sensor pod"],
        ["EYE-BEE", "thermal pod on top bay; nav cam stays (rev-C)"],
        ["RELAY-BEE", "tall whip pod on top bay; belly pod removed"],
        ["SCOUT-BEE", "2× battery sled in pod bay; high-viz shell"],
    ], rh=44)

    s.h(880, 480, "FIELD HIRING (HOW ROLES GET FILLED)")
    s.bullets(880, 510, [
        "Swarm joins mesh → coordinator reads capability flags.",
        "Gap analysis: coverage map × season threat model → role demand.",
        "Unit flies to its assigned perch, confirms position, reports ready.",
        "Returns to Anchor dock to charge + swap pods — the hive refuels.",
        "Reassignment on battery/sensor failure — automatic fly-home.",
    ], width=85)
    return s.svg(5, 8)


# ============================================================ MITE MECHANICAL =
def mite_mechanical():
    s = Sheet("AF-S-106", "MECHANICAL DETAIL",
              "PERCH LEG SECTION · ENCLOSURE STACK · SEAL", "S · MITE")

    # perch leg section drawing — two-segment articulated leg gripping branch
    vx, vy = 90, 170
    s.h(vx, vy - 40, "PERCH LEG — SECTION (1 OF 4)")
    # pod edge + hip
    s.rect(vx + 60, vy - 30, 180, 80, fill=FILL, stroke=INK, sw=1.4)
    s.t(vx + 150, vy + 14, "POD SHELL", 11, "middle", weight="bold")
    # hip servo
    s.circ(vx + 240, vy + 60, 20, fill="#e9e9e9", stroke=INK, sw=1.4)
    s.circ(vx + 240, vy + 60, 7, fill=INK)
    s.t(vx + 240, vy + 98, "HIP SERVO", 9, "middle", SOFT)
    # thigh link → knee
    s.ln(vx + 240, vy + 60, vx + 160, vy + 150, INK, 5)
    # knee joint + torsion spring hint
    s.circ(vx + 160, vy + 150, 14, fill="#e9e9e9", stroke=INK, sw=1.4)
    s.circ(vx + 160, vy + 150, 5, fill=INK)
    s.el.append(f'<path d="M {vx+146} {vy+150} A 14 14 0 0 1 {vx+160} {vy+136}" '
                f'fill="none" stroke="{SOFT}" stroke-width="1.4"/>')
    # shin link → claw
    s.ln(vx + 160, vy + 150, vx + 110, vy + 240, INK, 4)
    # branch
    s.circ(vx + 120, vy + 285, 42, fill="#cdbba0", stroke=INK, sw=1.3)
    s.circ(vx + 120, vy + 285, 26, fill="none", stroke="#a89478", sw=1)
    s.t(vx + 120, vy + 345, "BRANCH Ø10–40", 10, "middle", SOFT)
    # claw pads wrapping the branch
    s.poly([(vx + 100, vy + 240), (vx + 82, vy + 268), (vx + 78, vy + 300),
            (vx + 92, vy + 310), (vx + 96, vy + 282), (vx + 110, vy + 256)],
           fill="#e9e9e9", stroke=INK, sw=1.3)
    s.poly([(vx + 150, vy + 250), (vx + 164, vy + 280), (vx + 162, vy + 308),
            (vx + 148, vy + 314), (vx + 146, vy + 284), (vx + 138, vy + 258)],
           fill="#e9e9e9", stroke=INK, sw=1.3)
    s.t(vx + 330, vy + 180, "claw toes — TPU pads,\nspring-loaded grip", 10, color=SOFT)
    s.t(vx + 330, vy + 240, "micro-steps ratchet\nalong branch to aim", 10, color=SOFT)
    s.dimv(vx + 30, vy - 30, vy + 330, "~120 leg")

    # enclosure stack — updated for flight frame
    sx, sy = 620, 160
    s.h(sx, sy - 40, "ENCLOSURE STACK-UP")
    layers = [
        ("TOP SHELL + SOLAR", "2.0 mm", "deck + pod-bay lid + gasket"),
        ("ARM + DUCT ASSY", "printed", "carbon-filled ducts, prop guards"),
        ("CARRIER PCB — FR4", "1.6 mm", "38×38 + FC sensors + ESC"),
        ("BATTERY SLED — 2S", "3.0 mm", "slide tray, JST, strap"),
        ("LOWER POD — SENSOR", "2.5 mm", "ePTFE vent + nav cam window"),
    ]
    yy = sy
    for name, th, note in layers:
        s.rect(sx, yy, 380, 44, fill=FILL, stroke=INK, sw=1.1)
        s.t(sx + 12, yy + 19, name, 12, weight="bold")
        s.t(sx + 12, yy + 36, f"{th} — {note}", 10, color=SOFT)
        yy += 54
    s.note(sx, yy + 10, "Pod Z ≈ 40 mm · legs add ~80 mm reach · fold flat for dock.",
           size=12)

    # sealing + service
    gx = 1020
    s.h(gx, 160, "SEALING & SERVICE")
    s.table(gx, 184, [150, 420], ["Feature", "Detail"], [
        ["Gasket", "TPU bead around pod — IP54 splash (flight frame)"],
        ["Vent", "ePTFE membrane — gas exchange, no water"],
        ["Rotors", "ducted + guarded — branch-strike survivable"],
        ["Battery", "slide sled — swap in field, no tools"],
        ["Legs", "2 screws each — sacrificial, field spare"],
        ["Motors", "plug-in — replace per motor, no soldering"],
    ], rh=36)

    s.h(gx, 480, "DIMENSIONS")
    s.table(gx, 504, [150, 420], ["Dim", "Value"], [
        ["Envelope", "Ø210 mm rotor diagonal × ~75 mm perched"],
        ["Pod", "~110 × 110 × 40 mm"],
        ["Mass", "~420 g with 2S battery"],
        ["Grip", "Ø10–40 mm branch; ground-stand on flat"],
        ["Carrier PCB", "38 × 38 mm, 4-layer"],
        ["Operating", "-30..+50 °C (rev-A); flight derated <-15 °C"],
    ], rh=36)

    s.h(110, 600, "PERCH & CRAWL BEHAVIOR")
    s.bullets(110, 626, [
        "Lands blind on flow cam + ToF — legs wrap and ratchet until stable.",
        "Holds through wind-shake on Ø25 mm branch; claws take the load, not props.",
        "Micro-steps along branch to aim the sensor pod — 'crawl' is leg walking.",
        "Ground mode: legs spread to a tripod stance — landing pad anywhere.",
    ], width=105)

    s.h(110, 800, "MANUFACTURING")
    s.bullets(110, 826, [
        "Frame/ducts/legs: FDM print carbon-nylon or ASA — molded at volume.",
        "Claw pads: cast TPU or die-cut — consumable spares.",
        "Gasket: die-cut TPU sheet or printed-in-place.",
        "Carrier PCB: JLCPCB 4-layer ENIG — $15–30/pc at 10+.",
        "Assembly: hand-solderable — no BGA; ESC/motors plug-in.",
    ], width=105)
    return s.svg(6, 8)


# ============================================================ MITE FINISH =====
# ============================================================ MITE MISSIONS ====
def mite_missions():
    s = Sheet("AF-S-107", "MISSION PAYLOADS — MULTI-ROLE SWARM",
              "ONE CARRIER · SWAPPABLE MISSION PODS · SENSE · ACT · REACH",
              "S · MITE", rev="0", status="REV-C RESEARCH — SENSING FIRST", public=True)

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
          "Carrier is FIXED: quad ducts + perch legs + ESP32-S3 + SX1262 + solar deck + "
          "2S sled + pogo dock. Mission pods hot-swap on the top bay — same open-bay "
          "philosophy as the ArcticPhone. A bee re-tasks by flying home and swapping "
          "a pod, not buying a new bee.",
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
            "w": 300, "h": 300, "d": 110, "color": "#4a6741", "rad": 20,
            "caption": "S MITE — SENSOR-BEE",
            "sub": "Ø210 rotor × ~75 mm · ~420 g · micro-robot",
            "details": [
                ("ring", -0.16, -0.06, 0.30),
                ("ring", 1.16, -0.06, 0.30),
                ("ring", -0.16, 0.94, 0.30),
                ("ring", 1.16, 0.94, 0.30),
                ("solar", 0.12, 0.88, 0.10, 0.55),
                ("rect", 0.20, 0.60, 0.60, 0.30, "SENSOR POD"),
                ("circle", 0.50, 0.42, 0.040, "#22301f", None),
                ("circle", 0.50, 0.42, 0.016, "#5eead4", None),
                ("vents", 0.40, 0.72, 0.20, 0.09, 4),
                ("whip", 0.92, 0.85, 30),
                ("leg", 0.10, 0.90, -0.12, 1.16),
                ("leg", 0.90, 0.90, 1.12, 1.16),
                ("logo", "S MITE", 0.5, 0.52, 9, "#8fa3b5"),
            ],
        }],
        materials=[
            ["Shell + frame", "ASA / carbon-nylon print", "matte — forest tones", "UV stable, -30 °C"],
            ["Ducts + props", "carbon-nylon + 2″ props", "guarded", "branch-strike survivable"],
            ["Solar deck", "poly cell + PC window", "anti-reflective", "replaceable film"],
            ["Legs + claws", "nylon + TPU pads", "spring knees", "sacrificial spares"],
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
            "Role variants share the frame — only the mission pod differs.",
            "Rotor ducts carry the color band — visible ID at 20 m in flight.",
            "No logos on top face — solar deck is sacred.",
        ], public=True)


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
        ], public=True)


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
        ], public=True)


# ============================================================ PHONE: SPECIAL =====
def phone_definition():
    s = Sheet("AF-P-103", "PRODUCT DEFINITION — WHY IT STANDS OUT",
              "THE ONLY PHONE THAT IS A CITIZEN OF YOUR COMMUNITY'S NETWORK",
              "P · ARCTICPHONE", rev="0", status="CONCEPT — NOT FROZEN", public=True)

    s.h(ML + 10, 150, "THE ONE-LINE PITCH")
    s.t(ML + 10, 190, "“A phone that joins YOUR network — not just the carrier's.”", 22, weight="bold")
    s.t(ML + 10, 224, "Every ArcticPhone is a mesh node, a repeater, a satellite SOS beacon, "
       "and an offline-first computer — in one rugged, repairable, community-owned device.",
       14, color=SOFT)

    s.h(ML + 10, 300, "SIX THINGS NO OTHER PHONE DOES")
    s.table(ML + 10, 328, [40, 250, 450], ["#", "Feature", "Why it matters"], [
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
        "The phone is the user terminal for the whole ArctikChain stack — "
        "mesh, swarm, Totem, satellites. One device, the entire ecosystem.",
    ], width=80)

    s.h(880, 640, "WHAT IT IS NOT")
    s.bullets(880, 668, [
        "NOT a smartphone killer — it's for places smartphones fail.",
        "NOT a Starlink terminal — L-band messenger class for SOS/short messages.",
        "NOT a toy mesh radio — it's certified cellular + satellite + mesh, carrier-grade.",
        "NOT locked to one community — joins any ArctikChain mesh, carries identity.",
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
        (ML + 310, "CELLULAR — 5G sub-6", "n1/2/5/66/71 + eSIM", "50–500 Mbps", "tower range", "~1–2 W", "#dfe9f5"),
        (ML + 610, "SATELLITE — NTN + L-band", "NTN msg / Certus class", "~22 kbps", "global", "~3–5 W", "#f5e6d0"),
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

    # antenna layout — flagship frame: LDS/flex antennas in the rails, no whips
    s.h(1000, 140, "ANTENNA LAYOUT (TARGET)")
    px_, py_ = 1050, 210
    s.rect(px_, py_, 180, 350, fill=FILL, stroke=INK, sw=1.5, r=18)
    s.rect(px_ + 12, py_ + 24, 156, 290, fill="none", stroke=SOFT, sw=0.8, r=6)
    s.t(px_ + 90, py_ + 175, "DISPLAY", 12, "middle", SOFT)
    # frame antennas — antenna seams in the rails (flagship style)
    s.ln(px_ + 30, py_, px_ + 70, py_, ACC, 3)
    s.ln(px_ + 110, py_, px_ + 150, py_, ACC, 3)
    s.t(px_ + 50, py_ - 12, "5G ×2", 9, "middle", SOFT)
    s.t(px_ + 130, py_ - 12, "LoRa mesh", 9, "middle", SOFT)
    s.ln(px_, py_ + 60, px_, py_ + 110, ACC, 3)
    s.t(px_ - 14, py_ + 88, "5G", 9, "end", SOFT)
    s.ln(px_ + 180, py_ + 120, px_ + 180, py_ + 170, ACC, 3)
    s.t(px_ + 194, py_ + 148, "mesh", 9, "start", SOFT)
    s.rect(px_ + 30, py_ + 318, 120, 8, fill=ACC)
    s.t(px_ + 90, py_ + 344, "L-band PIFA (bottom edge)", 10, "middle", SOFT)
    s.t(px_ + 90, py_ + 368, "GNSS/BT: ceramic patch rear", 10, "middle", SOFT)

    # coexistence + failover
    s.h(ML + 10, 400, "COEXISTENCE & FAILOVER")
    s.table(ML + 10, 428, [180, 300, 340], ["Scenario", "Radio used", "Behavior"], [
        ["In community mesh range", "LoRa primary", "calls/texts route peer-to-peer signed"],
        ["No mesh, cell exists", "5G", "normal cellular + mesh backhaul opportunistic"],
        ["No cell, no mesh", "NTN/L-band sat", "SOS + short messages only (22 kbps)"],
        ["All three present", "mesh→5G→sat priority", "mesh for local, 5G for internet, sat reserved SOS"],
        ["Simultaneous TX", "TDM scheduler", "cellular TX pauses LoRa RX windows"],
    ], rh=44)

    s.h(ML + 10, 716, "LINK BUDGET (LoRa, typical)")
    s.table(ML + 10, 742, [200, 170, 170, 200], ["Path", "Range", "Data", "Use"], [
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
    s.table(ML + 10, 178, [130, 260, 170, 170, 120],
            ["Module", "Function", "Interface", "Power", "Est. cost"], [
        ["SAT-TERM", "full Iridium/Globalstar terminal", "USB3 + pogo", "5 V 2 A", "$80–150"],
        ["THERMAL", "FLIR Lepton-class camera", "MIPI + pogo", "5 V 1 A", "$120–250"],
        ["EXT-BATT", "second 5500 mAh Si/C cell", "pogo charge", "pass-through", "$30–45"],
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
              "P · ARCTICPHONE", rev="0", status="CONCEPT — NOT FROZEN", public=True)

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

    s.h(880, 150, "GLOVE-FIRST HARDWARE")
    s.table(880, 178, [160, 460], ["Element", "Design choice"], [
        ["SOS key", "dedicated hardware button, 3 mm travel, textured"],
        ["Display", "LTPO AMOLED — sun-boost mode + glove-touch IC"],
        ["UI", "high contrast, large targets, haptic confirm"],
        ["Buttons", "3 physical (vol/pwr) + SOS — no touchscreen-only"],
        ["Audio", "loud speaker + mic — works with mask/glove"],
        ["Charging", "USB-C 45 W + pogo — one-hand dock charge"],
    ], rh=42)

    s.h(880, 496, "COMMUNITY INTEGRATION")
    s.bullets(880, 524, [
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
            "w": 170, "h": 340, "d": 18, "color": "#2b3440", "rad": 20,
            "caption": "P ARCTICPHONE — FRONT",
            "sub": "~168 × 77 × 11 mm · ~240 g · IP68/69K",
            "details": [
                ("rect", 0.38, 0.010, 0.24, 0.010, "#0d1117", None, 2),
                ("cam", 0.50, 0.055, 0.016),
                ("screen", 0.045, 0.030, 0.91, 0.935, "lcd"),
                ("sidebtn", 0.55, 0.97, 0.20, 0.33),
                ("sidebtn", 0.55, 0.97, 0.37, 0.48),
                ("sidebtn", 0.55, 0.97, 0.55, 0.74, "#c0392b"),
                ("port", 0.5, 0.985, 0.9),
            ],
        }, {
            "w": 170, "h": 340, "d": 18, "color": "#2b3440", "rad": 20,
            "caption": "REAR — CAMERA ISLAND + BAY",
            "sub": "triple camera · bay ~45% of rear",
            "details": [
                ("rect", 0.08, 0.10, 0.44, 0.20, "#1f2833", None, 12),
                ("cam", 0.20, 0.16, 0.045),
                ("cam", 0.38, 0.16, 0.034),
                ("cam", 0.20, 0.255, 0.034),
                ("circle", 0.38, 0.255, 0.012, "#f0e0a0", None),
                ("rect", 0.02, 0.075, 0.96, 0.006, "#4a5563", None, 0),
                ("rect", 0.02, 0.925, 0.96, 0.006, "#4a5563", None, 0),
                ("seam", 0.14, 0.36, 0.72, 0.46),
                ("rect", 0.17, 0.39, 0.66, 0.40, "#232c38", None, 10),
                ("logo", "MODULE BAY", 0.5, 0.45, 8, "#8fa3b5"),
                ("circle", 0.30, 0.56, 0.011, "#8fa3b5", None),
                ("circle", 0.42, 0.56, 0.011, "#8fa3b5", None),
                ("circle", 0.58, 0.56, 0.011, "#8fa3b5", None),
                ("circle", 0.70, 0.56, 0.011, "#8fa3b5", None),
                ("circle", 0.24, 0.76, 0.020, "#c9a227", None),
                ("circle", 0.76, 0.76, 0.020, "#c9a227", None),
                ("logo", "ARCTIKCHAIN", 0.5, 0.885, 7, "#8fa3b5"),
            ],
        }],
        materials=[
            ["Frame + armor", "Al rail + PC/TPU overmold", "textured matte", "armor inside — IP68/69K"],
            ["Display", "6.5″ LTPO AMOLED 120 Hz", "sun-boost + glove-touch", "modern panel, not transflective"],
            ["Camera", "50 MP OIS + UW + thermal pod", "sapphire covers", "flagship-grade imaging"],
            ["Buttons", "metal, 3 mm travel", "tactile", "glove-proof"],
            ["Bay cover", "PC + TPU gasket", "flush thumb screws", "tool-light swap"],
        ],
        finishes=[
            ("#2b3440", "GRAPHITE", "default — professional"),
            ("#3d5a45", "FOREST", "field/rural identity"),
            ("#c96a1e", "HI-VIS", "SAR / search roles"),
        ],
        notes=[
            "Flagship silhouette — reads 2026 premium, not 'rugged brick'.",
            "Armor is inside the frame — no bolt-on pods, no forehead bezels.",
            "Camera island is the modern signature; the module bay sits below it.",
            "LTPO AMOLED with sun-boost + glove-touch — rural-real, not a compromise.",
            "No glass back — matte PC+TPU shrugs off drops and -30 °C.",
            "Color options are finish only — same internal BOM.",
        ], public=True)


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

    s.h(ML + 10, 534, "DEGRADATION TIMELINE")
    tl = [("0–2 mo", "ACTIVE", "sensing + reporting season", "#dfe9f5"),
          ("2–6 mo", "DORMANT", "low-power sentinel, minimal TX", "#f5e6d0"),
          ("6–12 mo", "DEGRADING", "encapsulant fails, electronics dissolve", "#f0d0d0"),
          ("12+ mo", "GONE", "biodegraded residue — no e-waste", "#d0e8d0")]
    xx = ML + 10
    for i, (t, phase, desc, col) in enumerate(tl):
        bx = xx + i * 205
        s.rect(bx, 570, 185, 68, fill=col, stroke=INK, sw=1.2)
        s.t(bx + 92, 598, t, 14, "middle", weight="bold")
        s.t(bx + 92, 618, phase, 11, "middle", weight="bold")
        s.t(bx + 92, 637, desc, 9, "middle", SOFT)
        if i < 3:
            s.arrow(bx + 185, 604, bx + 205, 604, SOFT)

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
        "No working ArctikChain mote exists — this is a research brief.",
        "Printed batteries at µW scale are lab-grade, not field-grade.",
        "LoRa radios don't degrade — antenna/comms is the hard part.",
        "Cluster heads must be durable — motes feed THEM, not the backbone.",
        "Gate: lab demo (temp + 10 m report) before ANY field promise.",
    ], width=82, color=RED)
    return s.svg(2, 4)


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
    s.note(ML + 10, 372,
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
    return s.svg(3, 4)


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
        "Cellular-only 'solution' — fails exactly where ArctikChain lives.",
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
              "ARCTIKCHAIN RURAL NODE FAMILY — COMPLETE PRINT SET", "COVER",
              status="MASTER INDEX", public=True)

    s.h(ML + 10, 150, "THE FLEET — ONE NETWORK, MANY SHAPES")
    s.table(ML + 10, 178, [50, 90, 250, 170, 160, 120, 190],
            ["Node", "Name", "Role", "Envelope", "Power", "Finish", "Status"], [
        ["L1", "Brick", "field node — mailbox+repeater+bulletin+SOS", "160×80×24 mm", "4×18650/solar", "graphite PETG matte", "CAD ready"],
        ["E", "Totem", "community board — public E-Ink + mesh node", "~320×220×80+pole", "solar+LiFePO4", "charcoal PC IP66", "spec"],
        ["S", "Mite", "micro-robot — fly·crawl·perch·dock swarm", "Ø210×~75 mm", "2S LiPo+solar", "forest ASA matte", "prototype"],
        ["A", "Anchor", "charging station — dock+relay+backhaul", "~350×250×400+array", "20–60 W+LiFePO4", "charcoal powder-coat", "spec"],
        ["P", "ArcticPhone", "rural comms — mesh-native, sat SOS", "~168×77×11 mm", "5500 mAh swap", "graphite PC+TPU", "concept"],
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
        ("AF-D-101…104", "D Seed — R&D brief, materials, cluster protocol, mote anatomy"),
        ("AF-H-101…102", "H Meridian — satellite mission + bus layout concept"),
        ("AF-X-101…102", "Component matrices — radios, compute, power, displays, enclosures"),
    ]
    yy = 590
    for dwg, desc in idx:
        s.t(860, yy, dwg, 13, weight="bold", color=ACC)
        s.t(1000, yy, desc, 13, color=SOFT)
        yy += 32

    s.h(ML + 10, 748, "HOW TO READ THIS SET")
    s.bullets(ML + 10, 776, [
        "L1 Brick = build-ready (BOM, wiring, electronics, assembly, acceptance test).",
        "S Mite = prototype-ready (orderable parts, 4 swarm variants, CAD scripted).",
        "Totem/Anchor = spec-level · Phone = concept · Seed/Meridian = R&D/vision.",
        "Every product has a FINISH & MATERIALS sheet — final look + materials spec.",
        "AF-X matrices = every electronic decision — radios, compute, power, displays.",
        "Every sheet: SURAFEL NEGUSSIE drew it · EMEBET INC. owns it.",
        "Sheets marked PUBLIC PRESENTATION may be shared; fabrication sheets are NDA-only.",
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
    "06_D_Seed": seed() + [seed_materials(), seed_protocol(), seed_anatomy()],
    "07_H_Meridian": meridian() + meridian_bus(),
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
