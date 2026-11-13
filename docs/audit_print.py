#!/usr/bin/env python3
"""Overlap + bounds audit for the fleet print PDFs (PyMuPDF).

Extracts every text span's bounding box and flags:
  - pairwise overlaps between distinct spans on the same page
  - spans extending past the drawing border margin

Run:  python audit_print.py [pdf ...]   (default: all in docs/print)
"""
import sys
from pathlib import Path
import pymupdf

PRINT = Path(__file__).parent / "print"
BORDER = 8  # pt — footer lives in the bottom margin by design


def spans(page):
    out = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                t = span["text"].strip()
                if t:
                    out.append((span["bbox"][0], span["bbox"][1],
                                span["bbox"][2], span["bbox"][3], t))
    return out


def iover(a, b):
    ix = min(a[2], b[2]) - max(a[0], b[0])
    iy = min(a[3], b[3]) - max(a[1], b[1])
    if ix <= 0 or iy <= 0:
        return 0.0
    small = min((a[2]-a[0])*(a[3]-a[1]), (b[2]-b[0])*(b[3]-b[1]))
    return ix * iy / small if small else 0.0


def audit(pdf):
    bad = []
    doc = pymupdf.open(str(pdf))
    for pno, page in enumerate(doc, 1):
        W, H = page.rect.width, page.rect.height
        sp = spans(page)
        # group chars into word-ish clusters: merge spans on same baseline
        words = []
        for s in sorted(sp, key=lambda s: (s[1], s[0])):
            merged = False
            for w in words:
                if abs(s[1] - w[1]) < 4 and s[0] - w[2] < 30:
                    w[2] = max(w[2], s[2]); w[3] = max(w[3], s[3])
                    w[4] += " " + s[4]; merged = True; break
            if not merged:
                words.append(list(s))
        for i in range(len(words)):
            for j in range(i + 1, len(words)):
                a, b = words[i], words[j]
                # same-line adjacency is normal; only flag real collisions
                if abs(a[1] - b[1]) < 5 and (a[2] <= b[0] + 2 or b[2] <= a[0] + 2):
                    continue
                r = iover(a, b)
                if r > 0.30:
                    bad.append(f"p{pno}: '{a[4][:28]}' <> '{b[4][:28]}' ({r:.0%})")
        for s in sp:
            if s[0] < BORDER or s[2] > W - BORDER or s[1] < BORDER or s[3] > H - BORDER:
                bad.append(f"p{pno}: OOB '{s[4][:24]}' @({s[0]:.0f},{s[1]:.0f})")
    doc.close()
    return bad


def main():
    pdfs = [Path(p) for p in sys.argv[1:]] or sorted(PRINT.glob("*.pdf"))
    total = 0
    for pdf in pdfs:
        bad = audit(pdf)
        total += len(bad)
        status = "CLEAN" if not bad else f"{len(bad)} issues"
        print(f"{pdf.name}: {status}")
        for b in bad[:15]:
            print(f"   {b}")
        if len(bad) > 15:
            print(f"   ... +{len(bad)-15} more")
    print(f"\nTOTAL issues: {total}")


if __name__ == "__main__":
    main()
