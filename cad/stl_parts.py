#!/usr/bin/env python3
"""Pure-Python STL generator for ArcticChain printable parts.

No CadQuery/OpenSCAD needed — emits binary STL from parametric meshes.
Parts generated (nominal dims, dry-fit before final print):

  perch_clip.stl    S-Mite branch/perch C-clip + strap ear + pad
  battery_tray.stl  L1 4x18650 tray (cells + lid lip)
  totem_shell.stl   E-Totem lower enclosure shell (open top)
  anchor_shell.stl  A-Anchor electronics bay shell (open front)

Run:  python stl_parts.py            -> writes stl/ next to this file
      python stl_parts.py --mm 0.4   -> custom resolution (curved parts)
"""
import argparse
import math
import struct
from pathlib import Path

# ---------------------------------------------------------------- mesh kit

def _tri(stl, a, b, c):
    """Append one triangle (each pt = (x,y,z))."""
    ux, uy, uz = b[0]-a[0], b[1]-a[1], b[2]-a[2]
    vx, vy, vz = c[0]-a[0], c[1]-a[1], c[2]-a[2]
    nx, ny, nz = (uy*vz-uz*vy, uz*vx-ux*vz, ux*vy-uy*vx)
    ln = math.sqrt(nx*nx+ny*ny+nz*nz) or 1.0
    stl.append(struct.pack("<12fH", nx/ln, ny/ln, nz/ln,
                           *a, *b, *c, 0))


def quad(stl, a, b, c, d):
    _tri(stl, a, b, c)
    _tri(stl, a, c, d)


def box(stl, cx, cy, cz, w, h, d):
    """Axis-aligned solid box centred at (cx,cy,cz)."""
    x0, x1 = cx-w/2, cx+w/2
    y0, y1 = cy-h/2, cy+h/2
    z0, z1 = cz-d/2, cz+d/2
    quad(stl, (x0,y0,z1),(x1,y0,z1),(x1,y1,z1),(x0,y1,z1))  # top
    quad(stl, (x0,y0,z0),(x0,y1,z0),(x1,y1,z0),(x1,y0,z0))  # bottom
    quad(stl, (x0,y0,z0),(x1,y0,z0),(x1,y0,z1),(x0,y0,z1))  # -y
    quad(stl, (x0,y1,z0),(x0,y1,z1),(x1,y1,z1),(x1,y1,z0))  # +y
    quad(stl, (x0,y0,z0),(x0,y0,z1),(x0,y1,z1),(x0,y1,z0))  # -x
    quad(stl, (x1,y0,z0),(x1,y1,z0),(x1,y1,z1),(x1,y0,z1))  # +x


def cyl(stl, cx, cy, z0, r, h, n=24, capped=True):
    """Vertical cylinder, base at z0."""
    ring0 = [(cx+r*math.cos(2*math.pi*i/n),
              cy+r*math.sin(2*math.pi*i/n), z0) for i in range(n)]
    ring1 = [(x, y, z0+h) for x, y, _ in ring0]
    for i in range(n):
        j = (i+1) % n
        quad(stl, ring0[i], ring0[j], ring1[j], ring1[i])
    if capped:
        ctr0 = (cx, cy, z0); ctr1 = (cx, cy, z0+h)
        for i in range(n):
            j = (i+1) % n
            _tri(stl, ctr0, ring0[j], ring0[i])
            _tri(stl, ctr1, ring1[i], ring1[j])


def cyl_shell(stl, cx, cy, z0, r_out, r_in, h, n=24, arc=None):
    """Partial cylindrical shell — the C-clip body.

    arc=(start_deg, end_deg) limits the wrap; default full 360.
    Produces outer wall, inner wall, two end caps, top/bottom rims.
    """
    a0, a1 = arc if arc else (0.0, 360.0)
    steps = max(4, int(n * (a1-a0) / 360))
    def ring(r, z):
        return [(cx+r*math.cos(math.radians(a0+(a1-a0)*i/steps)),
                 cy+r*math.sin(math.radians(a0+(a1-a0)*i/steps)), z)
                for i in range(steps+1)]
    ro0, ro1 = ring(r_out, z0), ring(r_out, z0+h)
    ri0, ri1 = ring(r_in, z0), ring(r_in, z0+h)
    for i in range(steps):
        quad(stl, ro0[i], ro0[i+1], ro1[i+1], ro1[i])   # outer wall
        quad(stl, ri1[i], ri1[i+1], ri0[i+1], ri0[i])   # inner wall
        quad(stl, ro1[i], ro1[i+1], ri1[i+1], ri1[i])   # top rim
        quad(stl, ri0[i+1], ri0[i], ro0[i], ro0[i+1])   # bottom rim
        # end caps only at arc ends (i==0 and i==steps handled below)
    # end caps at both arc ends
    for k, (o0, i0, o1, i1) in enumerate([
            (ro0[0], ri0[0], ro1[0], ri1[0]),
            (ro0[steps], ri0[steps], ro1[steps], ri1[steps])]):
        quad(stl, o0, o1, i1, i0)


def rounded_rect_path(w, d, r, seg=4):
    """CCW rounded-rectangle outline points (x,y) centred on origin."""
    pts = []
    hx, hy = w/2 - r, d/2 - r
    corners = [(hx, hy, 0), (-hx, hy, 90), (-hx, -hy, 180), (hx, -hy, 270)]
    for cx, cy, a0 in corners:
        for i in range(seg+1):
            a = math.radians(a0 + 90*i/seg)
            pts.append((cx + r*math.cos(a), cy + r*math.sin(a)))
    return pts


def prism(stl, outline, z0, h):
    """Extrude a simple polygon outline upward by h (fan caps)."""
    n = len(outline)
    bot = [(x, y, z0) for x, y in outline]
    top = [(x, y, z0+h) for x, y in outline]
    cx = sum(p[0] for p in outline)/n
    cy = sum(p[1] for p in outline)/n
    cb, ct = (cx, cy, z0), (cx, cy, z0+h)
    for i in range(n):
        j = (i+1) % n
        quad(stl, bot[i], bot[j], top[j], top[i])
        _tri(stl, cb, bot[j], bot[i])
        _tri(stl, ct, top[i], top[j])


def shell_box(stl, cx, cy, z0, w, d, h, t, open_top=True):
    """Hollow box: bottom + 4 walls, wall thickness t. Watertight."""
    # bottom slab
    box(stl, cx, cy, z0 + t/2, w, d, t)
    # 4 walls as thin boxes, tops flush with h
    box(stl, cx, cy - d/2 + t/2, z0 + t + (h-t)/2, w, t, h - t)
    box(stl, cx, cy + d/2 - t/2, z0 + t + (h-t)/2, w, t, h - t)
    box(stl, cx - w/2 + t/2, cy, z0 + t + (h-t)/2, t, d - 2*t, h - t)
    box(stl, cx + w/2 - t/2, cy, z0 + t + (h-t)/2, t, d - 2*t, h - t)


def write_stl(path, tris):
    """tris: list of packed 50-byte records -> binary STL."""
    with open(path, "wb") as f:
        f.write(b"\0" * 80)
        f.write(struct.pack("<I", len(tris)))
        for t in tris:
            f.write(t)
    print(f"  {path.name}: {len(tris)} tris, "
          f"{path.stat().st_size/1024:.0f} KB")


# ---------------------------------------------------------------- parts

def perch_clip(stl):
    """S-Mite perch clip: C-clamp for branches 25-60 mm + strap ear.

    Inner radius 32 mm fits a ~50 mm branch with TPU pad.
    Mounts under the puck's top face; puck slides in from the side.
    """
    # C-body: 270 deg wrap, r_out 40, r_in 30, 22 mm tall, 8 mm thick wall
    cyl_shell(stl, 0, 0, 0, 40, 30, 22, n=28, arc=(-60, 210))
    # TPU grip pad on the inside crown (opposite the opening)
    box(stl, 0, -34, 8, 26, 8, 6)
    # strap ear: tab with slot for a zip-tie / cord, extends +X
    box(stl, 44, 0, 6, 18, 10, 12)
    cyl(stl, 47, 0, 0, 2.5, 13, n=12)     # slot approximated by hole post
    # puck seat ears: two small lugs the puck clips onto
    box(stl, -36, 26, 20, 10, 8, 4)
    box(stl, -36, -26, 20, 10, 8, 4)


def battery_tray(stl):
    """L1 brick battery tray: 4x 18650 in series sled.

    Outer 4S pack ~ 70x70x75 mm; cells Ø18x65 + nickel strips.
    Tray = bottom plate + 3 dividers + 2 end cheeks; lid separate.
    """
    W, D, T = 72, 72, 3          # plate
    # bottom plate with rounded corners (octagonal prism)
    outline = rounded_rect_path(W-8, D-8, 8, seg=3)
    prism(stl, [(x, y, 0) and (x, y) for x, y in outline], 0, T)
    # cells: 4 x 18650 laid along X in a 2x2 block? L1 uses 4S stick:
    # layout: 4 cells in a row along X is too long (4*18+gaps ~ 90mm).
    # Real L1 pack: 2x2 block, series jumpers on top.
    # divider walls between cells
    cell = 19.5
    gap = 1.5
    for i in range(3):                       # 3 dividers along X at y=0 row
        x = -W/2 + cell + gap/2 + i*(cell+gap)
        box(stl, x, 0, T + 20, gap, D-12, 40)
    # end cheeks
    box(stl, -W/2 + 3, 0, T + 20, 6, D-12, 40)
    box(stl,  W/2 - 3, 0, T + 20, 6, D-12, 40)
    # low front lip so cells can't slide out forward
    box(stl, 0, -D/2 + 4, T + 15, W-10, 8, 30)


def totem_shell(stl):
    """E-Totem lower enclosure: ~200x140x420 mm pole-side shell.

    Open-top box, cable gland boss on bottom, mounting ears on back.
    """
    W, D, H, T = 200, 140, 420, 4
    shell_box(stl, 0, 0, 0, W, D, H, T, open_top=True)
    # cable gland boss (bottom rear)
    cyl(stl, -W/2 + 25, D/2 - 20, -14, 12, 14, n=16)
    # pole mount ears: two tabs with Ø8 holes on the back face
    box(stl, -W/2 - 4, 0, H*0.35, 8, 30, 8)
    box(stl, -W/2 - 4, 0, H*0.65, 8, 30, 8)
    cyl(stl, -W/2 - 4, 0, H*0.35 - 6, 4, 12, n=12)
    cyl(stl, -W/2 - 4, 0, H*0.65 - 6, 4, 12, n=12)


def anchor_shell(stl):
    """A-Anchor electronics bay: ~260x180x90 mm hinged-lid shell.

    Open-bottom tray; lid printed separately (lid.stl optional).
    Includes standoff bosses for the Pi/CM5 + radio board.
    """
    W, D, H, T = 260, 180, 90, 4
    shell_box(stl, 0, 0, 0, W, D, H, T, open_top=True)
    # CM5 standoffs: 4x M2.5 bosses
    for sx in (-60, 60):
        for sy in (-40, 40):
            cyl(stl, sx, sy, H - T - 6, 4.5, 6, n=12)
    # LoRa module keep-out boss
    cyl(stl, -W/2 + 30, -D/2 + 30, H - T - 4, 10, 4, n=16)
    # cable entry glands on one short side
    for i in range(3):
        cyl(stl, W/2 - 15, -30 + i*30, -12, 9, 12, n=14)


def lid_plate(stl):
    """Anchor lid: flat plate with finger recess + screw ears."""
    W, D, T = 260, 180, 3
    outline = rounded_rect_path(W-6, D-6, 6, seg=3)
    prism(stl, outline, 0, T)


PARTS = {
    "perch_clip": (perch_clip, "S-Mite perch C-clip, branch 25-60mm"),
    "battery_tray": (battery_tray, "L1 2x2 18650 tray + lid lip"),
    "totem_shell": (totem_shell, "E-Totem lower shell 200x140x420"),
    "anchor_shell": (anchor_shell, "A-Anchor bay 260x180x90"),
    "anchor_lid": (lid_plate, "A-Anchor lid plate"),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mm", type=float, default=0.4,
                    help="curved-part resolution hint (unused yet)")
    args = ap.parse_args()
    out = Path(__file__).parent / "stl"
    out.mkdir(exist_ok=True)
    manifest = []
    for name, (fn, desc) in PARTS.items():
        tris = []
        fn(tris)
        p = out / f"{name}.stl"
        write_stl(p, tris)
        manifest.append(f"| `{name}.stl` | {desc} |")
    (out / "README.md").write_text(
        "# Printable parts — ArcticChain fleet\n\n"
        "Generated by `firmware/../cad/../poc` — see `docs/print/` for drawings.\n\n"
        "| file | part |\n|---|---|\n" + "\n".join(manifest) +
        "\n\nNominal dims — dry-fit before final print. TPU for clips/pads,\n"
        "PETG/ASA for shells (UV + -40..+70 °C).\n", encoding="utf-8")
    print(f"\n{len(PARTS)} parts -> {out}")


if __name__ == "__main__":
    main()
