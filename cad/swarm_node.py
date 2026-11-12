#!/usr/bin/env python3
"""ArcticChain S "Mite" — swarm node parametric CAD.

Perchable environmental sensor for the fire-watch swarm. The swarm is the
sensor; each Mite is minimal: solar top, LoRa radio, temp/RH/VOC sensing,
perch clip for branches/poles/fences.

Envelope: 90 x 90 x 35 mm rounded-square puck (gen-1 achievable size —
miniaturization is the outcome of scale, not the launch spec).

Outputs STEP + STL + dimensions.json under cad/swarm/, matching
cad/level1_chassis.py conventions. Requires a CadQuery-capable host
(Linux/macOS or CI — OCP is blocked on the Windows dev box).
"""

import json
from pathlib import Path

import cadquery as cq

HERE = Path(__file__).resolve().parent
OUT = HERE / "swarm"
OUT.mkdir(exist_ok=True)


class MiteParams:
    length = 90.0       # X, mm — rounded-square puck
    width = 90.0        # Y, mm
    height = 35.0       # Z, mm total envelope
    wall = 2.0          # shell wall
    floor_t = 1.6       # internal floor
    corner_r = 12.0     # corner radius
    lid_t = 3.0         # top lid thickness
    solar_l = 62.0      # solar cell area recess (panel ~60x60x1.6)
    solar_w = 62.0
    solar_depth = 2.2   # recess depth below lid top
    pcb_l = 38.0        # carrier PCB (ESP32-S3 + SX1262 + ENS160/SHT41)
    pcb_w = 38.0
    batt_l = 54.0       # battery bay (503450 LiPo pouch 50x34x6 + margin)
    batt_w = 38.0
    batt_h = 9.0
    clip_r = 16.0       # perch clip cradle radius (grips branches/poles)
    clip_t = 2.4        # clip wall
    clip_drop = 10.0    # how far clip hangs below floor


def rounded_box(l, w, h, r):
    return (
        cq.Workplane("XY")
        .box(l, w, h, centered=(True, True, False))
        .edges("|Z")
        .fillet(r)
    )


def make_shell(p: MiteParams):
    """Bottom shell: hollow puck open at top, with battery + PCB floor."""
    outer = rounded_box(p.length, p.width, p.height - p.lid_t, p.corner_r)
    inner = cq.Workplane("XY").box(
        p.length - 2 * p.wall,
        p.width - 2 * p.wall,
        p.height - p.lid_t - p.floor_t,
        centered=(True, True, False),
    ).translate((0, 0, p.floor_t))
    shell = outer.cut(inner)
    return shell


def make_lid(p: MiteParams):
    """Top lid with solar-cell recess and gasket groove."""
    lid = rounded_box(p.length, p.width, p.lid_t, p.corner_r)
    recess = (
        cq.Workplane("XY")
        .box(p.solar_l, p.solar_w, p.solar_depth + 0.4, centered=(True, True, False))
        .translate((0, 0, p.height - p.lid_t - 0.2))
    )
    lid = lid.cut(recess)
    # gasket groove around perimeter (rectangular, inset from edge)
    groove = (
        cq.Workplane("XY")
        .box(p.length - 2 * p.wall - 4, p.width - 2 * p.wall - 4, 1.2,
             centered=(True, True, False))
        .cut(cq.Workplane("XY").box(
            p.length - 2 * p.wall - 8, p.width - 2 * p.wall - 8, 1.6,
            centered=(True, True, False)))
        .translate((0, 0, p.height - p.lid_t - 0.4))
    )
    return lid.union(groove)


def make_battery_bay(p: MiteParams):
    """Slide-in tray for a single LiPo pouch (503450) or 2x 16340."""
    bay = (
        cq.Workplane("XY")
        .box(p.batt_l + 2, p.batt_w + 2, p.batt_h, centered=(True, True, False))
        .translate((0, 0, p.floor_t + 0.4))
    )
    pocket = (
        cq.Workplane("XY")
        .box(p.batt_l, p.batt_w, p.batt_h + 1,
             centered=(True, True, False))
        .translate((0, 0, p.floor_t + 0.3))
    )
    return bay.cut(pocket)


def make_perch_clip(p: MiteParams):
    """C-clip cradle under the puck — grips branches/poles/fence wire.

    A partial cylinder shell open at the bottom; a steel spring strip or
    printed flexure provides the clamp. Mounts the node 'perched' so the
    solar top still sees sky.
    """
    outer = (
        cq.Workplane("XZ")
        .circle(p.clip_r + p.clip_t)
        .extrude(p.clip_t)
    )
    inner = (
        cq.Workplane("XZ")
        .circle(p.clip_r)
        .extrude(p.clip_t * 3)
    )
    clip = outer.cut(inner)
    # keep only lower ~200 degrees of the ring (opening faces down)
    clip = clip.intersect(
        cq.Workplane("XY").box(80, 80, 40).translate((0, -8, -p.clip_drop))
    )
    clip = clip.translate((0, 0, -p.clip_drop))
    # two small standoffs tying clip to shell floor
    for sx in (-p.clip_r, p.clip_r):
        post = (
            cq.Workplane("XY")
            .circle(3.0)
            .extrude(p.clip_drop)
            .translate((sx, 0, -p.clip_drop))
        )
        clip = clip.union(post)
    return clip


def main():
    p = MiteParams()
    shell = make_shell(p)
    lid = make_lid(p)
    bay = make_battery_bay(p)
    clip = make_perch_clip(p)

    cq.exporters.export(shell, str(OUT / "mite_shell.step"))
    cq.exporters.export(shell, str(OUT / "mite_shell.stl"))
    cq.exporters.export(lid, str(OUT / "mite_lid.step"))
    cq.exporters.export(lid, str(OUT / "mite_lid.stl"))
    cq.exporters.export(bay, str(OUT / "mite_battery_bay.step"))
    cq.exporters.export(bay, str(OUT / "mite_battery_bay.stl"))
    cq.exporters.export(clip, str(OUT / "mite_perch_clip.step"))
    cq.exporters.export(clip, str(OUT / "mite_perch_clip.stl"))

    report = {
        "params": {k: getattr(p, k) for k in dir(p)
                   if not k.startswith("_") and not callable(getattr(p, k))},
        "shell_mass_g_petg": shell.val().Volume() * 1.27 / 1000.0,
        "lid_mass_g_petg": lid.val().Volume() * 1.27 / 1000.0,
        "notes": [
            "ASA or PC-ABS preferred over PETG for UV + cold (-45 C) service",
            "Solar panel: ~60x60mm 0.5-1W 5V poly, under optical window film",
            "Perch clip: printed cradle + steel spring strip (see SWARM_NODE.md)",
            "Carrier PCB ~38x38mm: ESP32-S3 + SX1262 + ENS160 + SHT41",
            "Battery: 503450 LiPo ~2000mAh; CN3791-class solar charge path",
            "Envelope target ~90x90x35mm + clip drop 10mm",
        ],
    }
    (OUT / "dimensions.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report["params"], indent=2))
    print(f"shell: {report['shell_mass_g_petg']:.1f} g, lid: {report['lid_mass_g_petg']:.1f} g")


if __name__ == "__main__":
    main()
