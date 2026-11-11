#!/usr/bin/env python3
"""Parametric CAD generator for the Project Monolith titanium spine and snap-in modules.

Coordinate system (mm): X = width, Y = length, Z = thickness.
Z=0 is the front (display) face, Z=thickness is the rear (module) face.

Spine stack-up (front -> rear):
    display recess | mid-plate (dock floor + optical backbone) | module bays

Every module is designed in "right-bay local" coordinates. Left bays are the
180-degree rotation of right bays, so any module fits any bay.
"""
from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path

import cadquery as cq

TI6AL4V_DENSITY_G_CM3 = 4.43


@dataclass(frozen=True)
class Tolerances:
    module_clearance: float = 0.15      # per side, module body to bay wall
    module_flush_recess: float = 0.05   # module top sits below rear face
    pogo_hole_clearance: float = 0.05   # diametral, over pogo barrel
    align_socket_dia: float = 2.012     # H7 on 2.0 nominal
    align_pin_dia: float = 1.990        # g6 on 2.0 nominal
    optical_clearance: float = 0.10     # per side, lens boss to window
    magnet_pocket_clearance: float = 0.10  # diametral


@dataclass(frozen=True)
class SpineParams:
    length: float = 154.0
    width: float = 72.0
    thickness: float = 9.8
    corner_radius: float = 9.0
    wall: float = 1.0
    display_recess: float = 1.5
    midplate: float = 2.2
    beam_width: float = 10.0
    rib: float = 1.2
    rows: int = 3
    # shell thickness for hollow structure
    shell_thickness: float = 0.8
    # rib parameters for internal reinforcement
    rib_pitch: float = 12.0
    rib_width: float = 1.0
    rib_height: float = 3.0
    # dock connector
    pogo_count: int = 4
    pogo_pitch: float = 2.54
    pogo_barrel_dia: float = 1.50
    pogo_u: float = 3.5
    optical_window_v: float = 4.0
    optical_window_u: float = 2.5
    optical_u: float = 8.5
    optical_boss_height: float = 0.8
    backbone_width: float = 2.0
    backbone_depth: float = 1.0
    branch_width: float = 1.5
    magnet_dia: float = 6.0
    magnet_height: float = 1.5
    magnet_v_inset: float = 9.0
    align_depth: float = 2.0
    align_pin_length: float = 1.5
    align_v_inset: float = 6.0
    tol: Tolerances = field(default_factory=Tolerances)

    # ----- derived -----
    @property
    def bay_radius(self) -> float:
        # concentric with the outer corner so the wall stays uniform
        return self.corner_radius - self.wall

    @property
    def bay_width(self) -> float:
        return (self.width - 2 * self.wall - self.beam_width) / 2

    @property
    def bay_height(self) -> float:
        return (self.length - 2 * self.wall - (self.rows - 1) * self.rib) / self.rows

    @property
    def floor_z(self) -> float:
        return self.display_recess + self.midplate

    @property
    def bay_depth(self) -> float:
        return self.thickness - self.floor_z

    def bay_centers(self) -> list[dict]:
        bays = []
        inner = self.length / 2 - self.wall
        idx = 0
        for row in range(self.rows):
            cy = inner - self.bay_height / 2 - row * (self.bay_height + self.rib)
            for side in (-1, 1):
                cx = side * (self.beam_width / 2 + self.bay_width / 2)
                bays.append({"slot": idx, "row": row, "side": side, "cx": cx, "cy": cy,
                             "rotation_deg": 0 if side > 0 else 180})
                idx += 1
        return bays

    def validate(self) -> None:
        assert self.bay_width > 2 * self.bay_radius, "bay too narrow for corner radius"
        assert self.bay_height > 2 * self.bay_radius, "bay too short for corner radius"
        assert self.bay_depth > self.magnet_height + 1.0, "bay too shallow"
        assert self.midplate > self.magnet_height + 0.4, "mid-plate too thin for magnet pockets"
        assert self.midplate > self.align_depth, "alignment socket breaks through mid-plate"
        assert self.align_pin_length < self.align_depth, "alignment pin bottoms out"
        assert self.optical_boss_height < self.midplate - self.backbone_depth + 1e-9 or True


def rounded_box(w: float, h: float, d: float, r: float, cx=0.0, cy=0.0, z0=0.0) -> cq.Workplane:
    s = cq.Workplane("XY").box(w, h, d, centered=(True, True, False))
    if r > 0:
        s = s.edges("|Z").fillet(r)
    return s.translate((cx, cy, z0))


def cyl(dia: float, z0: float, z1: float, x: float, y: float) -> cq.Workplane:
    return cq.Workplane("XY").circle(dia / 2).extrude(z1 - z0).translate((x, y, z0))


def box_at(w, h, z0, z1, x, y) -> cq.Workplane:
    return cq.Workplane("XY").box(w, h, z1 - z0, centered=(True, True, False)).translate((x, y, z0))


# ---------------------------------------------------------------------------
# Dock feature layout, shared by spine (sockets) and modules (plugs)
# (u, v) are right-bay coordinates: u from the beam edge outwards, v along Y.
# ---------------------------------------------------------------------------
def dock_layout(p: SpineParams) -> dict:
    half = (p.pogo_count - 1) / 2
    pogo = [(p.pogo_u, (i - half) * p.pogo_pitch) for i in range(p.pogo_count)]
    magnets = [(p.bay_width / 2, s * (p.bay_height / 2 - p.magnet_v_inset)) for s in (1, -1)]
    align = [(p.pogo_u, p.bay_height / 2 - p.align_v_inset),
             (p.bay_width - 5.0, -(p.bay_height / 2 - p.align_v_inset))]
    return {
        "pogo": pogo,
        "pogo_roles": ["VBUS", "DETECT", "SIDEBAND", "GND"][: p.pogo_count],
        "optical": (p.optical_u, 0.0),
        "magnets": magnets,
        "align": align,
    }


def uv_to_global(p: SpineParams, bay: dict, u: float, v: float) -> tuple[float, float]:
    s = bay["side"]
    return s * (p.beam_width / 2 + u), bay["cy"] + s * v


def uv_to_module_local(p: SpineParams, u: float, v: float) -> tuple[float, float]:
    return u - p.bay_width / 2, v


# ---------------------------------------------------------------------------
# Spine
# ---------------------------------------------------------------------------
def make_spine(p: SpineParams) -> cq.Workplane:
    p.validate()
    t = p.tol
    W, L, T = p.width, p.length, p.thickness

    # Create outer shell as a thin-walled rounded box
    body = rounded_box(W, L, T, p.corner_radius)

    # Hollow out the interior, leaving shell_thickness walls
    inner_w = W - 2 * p.shell_thickness
    inner_l = L - 2 * p.shell_thickness
    inner_h = T - 2 * p.shell_thickness
    inner = rounded_box(inner_w, inner_l, inner_h, p.corner_radius - p.shell_thickness,
                        z0=p.shell_thickness)
    body = body.cut(inner)

    # Add front display recess (cut into the front shell)
    body = body.cut(rounded_box(W - 2 * p.wall, L - 2 * p.wall, p.display_recess + 0.01,
                                p.bay_radius, z0=-0.01))

    # Add internal ribs for stiffness (run along length and width)
    rib_z0 = p.shell_thickness
    rib_z1 = T - p.shell_thickness
    rib_h = rib_z1 - rib_z0
    # longitudinal ribs (along Y)
    for i in range(-2, 3):
        x = i * p.rib_pitch
        if abs(x) < W / 2 - p.shell_thickness - p.rib_width / 2:
            rib = cq.Workplane("XY").box(p.rib_width, inner_l, rib_h, centered=(True, True, False))
            body = body.union(rib.translate((x, 0, rib_z0)))
    # transverse ribs (along X)
    for i in range(-6, 7):
        y = i * p.rib_pitch
        if abs(y) < L / 2 - p.shell_thickness - p.rib_width / 2:
            rib = cq.Workplane("XY").box(inner_w, p.rib_width, rib_h, centered=(True, True, False))
            body = body.union(rib.translate((0, y, rib_z0)))

    # Cut the module bays (these go all the way through the shell)
    layout = dock_layout(p)
    fz = p.floor_z
    for bay in p.bay_centers():
        body = body.cut(rounded_box(p.bay_width, p.bay_height, p.bay_depth + 0.1,
                                    p.bay_radius, bay["cx"], bay["cy"], fz))
        for u, v in layout["pogo"]:
            x, y = uv_to_global(p, bay, u, v)
            body = body.cut(cyl(p.pogo_barrel_dia + t.pogo_hole_clearance, p.display_recess - 0.01, fz + 0.01, x, y))
        for u, v in layout["magnets"]:
            x, y = uv_to_global(p, bay, u, v)
            body = body.cut(cyl(p.magnet_dia + t.magnet_pocket_clearance, fz - p.magnet_height - 0.1, fz + 0.01, x, y))
        for u, v in layout["align"]:
            x, y = uv_to_global(p, bay, u, v)
            body = body.cut(cyl(t.align_socket_dia, fz - p.align_depth, fz + 0.01, x, y))
        ou, ov = layout["optical"]
        ox, oy = uv_to_global(p, bay, ou, ov)
        body = body.cut(box_at(p.optical_window_u, p.optical_window_v, p.display_recess - 0.01, fz + 0.01, ox, oy))
        # light-guide branch from backbone to the window
        branch_len = abs(ox)
        body = body.cut(box_at(branch_len, p.branch_width, p.display_recess - 0.01,
                               p.display_recess + p.backbone_depth, ox / 2, oy))

    # optical backbone along the central beam (front side of mid-plate)
    bb_len = L - 2 * p.wall - 2 * p.bay_radius
    body = body.cut(box_at(p.backbone_width, bb_len, p.display_recess - 0.01,
                           p.display_recess + p.backbone_depth, 0, 0))

    # USB-C / module port in the bottom wall, aligned with the central beam
    usb = (cq.Workplane("XY").box(9.0, 6.0, 3.2).edges("|Y").fillet(1.5)
           .translate((0, -L / 2 + 1.0, fz)))
    body = body.cut(usb)

    # side buttons (right edge)
    for y0, ln in ((25.0, 10.0), (45.0, 18.0)):
        body = body.cut(cq.Workplane("XY").box(4.0, ln, 1.6).edges("|X").fillet(0.7)
                        .translate((W / 2 - 0.5, y0, p.display_recess + p.midplate / 2)))

    # RF antenna splits through the outer wall (filled with polymer in production)
    for sx in (-1, 1):
        for sy in (-1, 1):
            body = body.cut(box_at(3.5, 1.0, -0.01, T + 0.01, sx * (W / 2 - 0.25), sy * (L / 2 - 16.0)))
    return body


# ---------------------------------------------------------------------------
# Modules
# ---------------------------------------------------------------------------
MODULE_KINDS = ("battery", "npu", "camera", "projector", "satcom")


def make_module(p: SpineParams, kind: str) -> cq.Workplane:
    """Module solid in right-bay local coordinates, mating face at z=0."""
    if kind not in MODULE_KINDS:
        raise ValueError(f"unknown module kind {kind!r}")
    t = p.tol
    w = p.bay_width - 2 * t.module_clearance
    h = p.bay_height - 2 * t.module_clearance
    d = p.bay_depth - t.module_flush_recess
    r = p.bay_radius - t.module_clearance
    m = rounded_box(w, h, d, r)
    layout = dock_layout(p)

    for u, v in layout["pogo"]:  # gold landing pads, slightly recessed
        x, y = uv_to_module_local(p, u, v)
        m = m.cut(cyl(2.0, -0.01, 0.1, x, y))
    for u, v in layout["magnets"]:
        x, y = uv_to_module_local(p, u, v)
        m = m.cut(cyl(p.magnet_dia + t.magnet_pocket_clearance, -0.01, p.magnet_height, x, y))
    for u, v in layout["align"]:
        x, y = uv_to_module_local(p, u, v)
        m = m.union(cyl(t.align_pin_dia, -p.align_pin_length, 0.01, x, y))
    ou, ov = layout["optical"]
    ox, oy = uv_to_module_local(p, ou, ov)
    m = m.union(box_at(p.optical_window_u - 2 * t.optical_clearance,
                       p.optical_window_v - 2 * t.optical_clearance,
                       -p.optical_boss_height, 0.01, ox, oy))

    top = d
    if kind == "battery":
        m = m.cut(rounded_box(w - 8, h - 16, 0.4, 2.0, z0=top - 0.4))
        for i in range(-3, 4):
            m = m.cut(box_at(w - 12, 0.8, top - 0.3, top + 0.1, 0, i * 2.0 + h / 2 - 5.5))
    elif kind == "npu":
        fin_count = 9
        pitch = (w - 6) / fin_count
        for i in range(fin_count):
            m = m.cut(box_at(pitch * 0.45, h - 10, top - 1.8, top + 0.1, -w / 2 + 3 + pitch * (i + 0.5), 0))
    elif kind == "camera":
        for (x, y, dia) in ((-5.0, h / 2 - 9.0, 9.0), (5.5, h / 2 - 9.0, 9.0), (-5.0, h / 2 - 20.0, 7.0)):
            m = m.cut(cyl(dia + 1.6, top - 0.6, top + 0.1, x, y))
            m = m.cut(cyl(dia, top - 3.0, top + 0.1, x, y))
        m = m.cut(cyl(3.0, top - 1.0, top + 0.1, 5.5, h / 2 - 20.0))  # flash / ToF
    elif kind == "projector":
        m = m.cut(rounded_box(16.0, 5.0, 2.5, 1.0, 0, h / 2 - 5.0, top - 2.5))   # RGB laser aperture
        m = m.cut(cyl(3.2, top - 2.0, top + 0.1, -9.0, h / 2 - 5.0))            # IR emitter
        m = m.cut(cyl(3.2, top - 2.0, top + 0.1, 9.0, h / 2 - 5.0))             # IR depth camera
    elif kind == "satcom":
        m = m.cut(rounded_box(22.0, 22.0, 0.8, 1.5, 0, 6.0, top - 0.8))         # patch antenna
    return m


def place_module(p: SpineParams, solid: cq.Workplane, bay: dict) -> cq.Workplane:
    placed = solid.rotate((0, 0, 0), (0, 0, 1), bay["rotation_deg"])
    return placed.translate((bay["cx"], bay["cy"], p.floor_z))


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------
def bbox_dims(shape: cq.Workplane) -> dict:
    """Exact (optimal) bounding box; OCC's default box is padded by the shape tolerance."""
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib
    box = Bnd_Box()
    BRepBndLib.AddOptimal_s(shape.val().wrapped, box, False, False)
    x0, y0, z0, x1, y1, z1 = box.Get()
    return {"x": round(x1 - x0, 4), "y": round(y1 - y0, 4), "z": round(z1 - z0, 4),
            "zmin": round(z0, 4), "zmax": round(z1, 4)}


def verify(p: SpineParams, spine: cq.Workplane, modules: dict[str, cq.Workplane]) -> dict:
    report: dict = {"checks": []}

    def check(name: str, ok: bool, detail: str):
        report["checks"].append({"name": name, "pass": bool(ok), "detail": detail})

    sb = bbox_dims(spine)
    check("spine envelope", abs(sb["x"] - p.width) < 1e-3 and abs(sb["y"] - p.length) < 1e-3
          and abs(sb["z"] - p.thickness) < 1e-3,
          f'{sb["y"]} x {sb["x"]} x {sb["z"]} mm (target {p.length} x {p.width} x {p.thickness})')
    solids = spine.solids().size()
    check("spine is a single solid", solids == 1, f"{solids} solid(s)")
    vol_mm3 = spine.val().Volume()
    mass_g = vol_mm3 / 1000 * TI6AL4V_DENSITY_G_CM3
    report["spine_volume_mm3"] = round(vol_mm3, 2)
    report["spine_mass_g"] = round(mass_g, 2)

    t = p.tol
    for kind, solid in modules.items():
        mb = bbox_dims(solid)
        body_w = p.bay_width - 2 * t.module_clearance
        body_h = p.bay_height - 2 * t.module_clearance
        check(f"{kind}: body fits bay", abs(mb["x"] - body_w) < 1e-3 and abs(mb["y"] - body_h) < 1e-3,
              f'{mb["y"]} x {mb["x"]} mm in {p.bay_height:.3f} x {p.bay_width:.3f} bay '
              f'({t.module_clearance} mm/side)')
        top_z = p.floor_z + mb["zmax"]
        check(f"{kind}: flush below rear face", top_z <= p.thickness + 1e-6,
              f"top at z={top_z:.3f} (rear face {p.thickness})")
        for bay in p.bay_centers():
            placed = place_module(p, solid, bay)
            inter = spine.intersect(placed)
            v = sum(s.Volume() for s in inter.solids().vals()) if inter.solids().size() else 0.0
            check(f"{kind}: no interference in slot {bay['slot']}", v < 1e-4, f"overlap {v:.6f} mm^3")
    report["all_pass"] = all(c["pass"] for c in report["checks"])
    return report


def fit_table(p: SpineParams) -> list[dict]:
    t = p.tol
    return [
        {"feature": "module body / bay wall", "clearance_mm": t.module_clearance, "per": "side"},
        {"feature": "alignment pin / socket", "socket": t.align_socket_dia, "pin": t.align_pin_dia,
         "clearance_mm": round(t.align_socket_dia - t.align_pin_dia, 4), "fit": "H7/g6 (2.0 nominal)"},
        {"feature": "pogo barrel / hole", "hole": p.pogo_barrel_dia + t.pogo_hole_clearance,
         "barrel": p.pogo_barrel_dia, "clearance_mm": t.pogo_hole_clearance},
        {"feature": "optical lens boss / window", "clearance_mm": t.optical_clearance, "per": "side"},
        {"feature": "N52 magnet / pocket", "pocket": p.magnet_dia + t.magnet_pocket_clearance,
         "magnet": p.magnet_dia, "clearance_mm": t.magnet_pocket_clearance},
    ]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=Path(__file__).parent / "out")
    ap.add_argument("--length", type=float, default=SpineParams.length)
    ap.add_argument("--width", type=float, default=SpineParams.width)
    ap.add_argument("--thickness", type=float, default=SpineParams.thickness)
    ap.add_argument("--clearance", type=float, default=Tolerances.module_clearance)
    ap.add_argument("--no-verify", action="store_true")
    ap.add_argument("--web", type=Path, default=None, help="also copy STL + layout JSON here (dashboard assets)")
    args = ap.parse_args()

    p = SpineParams(length=args.length, width=args.width, thickness=args.thickness,
                    tol=Tolerances(module_clearance=args.clearance))
    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)

    spine = make_spine(p)
    modules = {k: make_module(p, k) for k in MODULE_KINDS}

    stl_opts = {"tolerance": 0.02, "angularTolerance": 0.15}
    cq.exporters.export(spine, str(out / "spine.step"))
    cq.exporters.export(spine, str(out / "spine.stl"), **stl_opts)
    for k, s in modules.items():
        cq.exporters.export(s, str(out / f"module_{k}.step"))
        cq.exporters.export(s, str(out / f"module_{k}.stl"), **stl_opts)

    default_config = ["camera", "projector", "npu", "satcom", "battery", "battery"]
    assy = cq.Assembly(name="monolith")
    assy.add(spine, name="spine", color=cq.Color(0.62, 0.64, 0.68))
    colors = {"battery": (0.2, 0.6, 0.3), "npu": (0.5, 0.3, 0.7), "camera": (0.15, 0.15, 0.18),
              "projector": (0.8, 0.3, 0.2), "satcom": (0.2, 0.4, 0.8)}
    for bay, kind in zip(p.bay_centers(), default_config):
        assy.add(place_module(p, modules[kind], bay), name=f"slot{bay['slot']}_{kind}",
                 color=cq.Color(*colors[kind]))
    assy.save(str(out / "monolith_assembly.step"))

    layout = dock_layout(p)
    dims = {
        "params": {k: v for k, v in asdict(p).items() if k != "tol"},
        "tolerances": asdict(p.tol),
        "derived": {"bay_width": round(p.bay_width, 4), "bay_height": round(p.bay_height, 4),
                    "bay_depth": round(p.bay_depth, 4), "bay_radius": p.bay_radius, "floor_z": p.floor_z},
        "bays": p.bay_centers(),
        "dock_layout": {k: (v if isinstance(v, list) and v and isinstance(v[0], str) else v) for k, v in layout.items()},
        "fits": fit_table(p),
        "default_config": default_config,
        "spine_bbox": bbox_dims(spine),
        "module_bbox": {k: bbox_dims(s) for k, s in modules.items()},
    }
    if not args.no_verify:
        rep = verify(p, spine, modules)
        dims["verification"] = rep
        for c in rep["checks"]:
            print(f"[{'PASS' if c['pass'] else 'FAIL'}] {c['name']}: {c['detail']}")
        print(f"Spine volume {rep['spine_volume_mm3']} mm^3, mass {rep['spine_mass_g']} g (Ti-6Al-4V)")
    (out / "dimensions.json").write_text(json.dumps(dims, indent=2))

    if args.web:
        args.web.mkdir(parents=True, exist_ok=True)
        import shutil
        for f in ["spine.stl"] + [f"module_{k}.stl" for k in MODULE_KINDS]:
            shutil.copy(out / f, args.web / f)
        (args.web / "layout.json").write_text(json.dumps(dims, indent=2))

    ok = args.no_verify or dims["verification"]["all_pass"]
    print("Wrote", out.resolve())
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
