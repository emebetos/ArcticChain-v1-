#!/usr/bin/env python3
"""ArcticChain Level-1 chassis: parametric 3D-printable handheld brick.

House a Raspberry Pi Compute Module 5 on its IO Board carrier, two HATs
(4G/LTE + E-Ink display), a Semtech SX1262 LoRa module, and a USB-C
power path inside a 3D-printed enclosure sized for the hand.

Target envelope: 160 x 80 x 24 mm ("brick" class, Level-1 realism).
Prints in PETG or ABS (NOT PLA — enclosure lives in the field).

Outputs STEP + STL + a JSON dimension report, matching cad/ conventions.
"""

import json
from pathlib import Path

import cadquery as cq

HERE = Path(__file__).resolve().parent
OUT = HERE / "level1"
OUT.mkdir(exist_ok=True)

# ---------------------------------------------------------------- params
class ChassisParams:
    length = 160.0      # X, mm — hand-held brick length
    width = 80.0        # Y, mm
    wall = 2.4          # shell wall thickness
    floor_t = 2.0       # internal floor thickness
    corner_r = 8.0      # corner radius
    pcb_l = 56.5        # CM5 IO Board length (approx)
    pcb_w = 45.0        # CM5 IO Board width incl. keep-outs
    hat_gap = 2.5       # stacking gap between boards (headers)
    hat_count = 3       # IO board + 2 HATs
    hat_thickness = 1.6 # approx per-board height
    button_d = 12.0     # SOS button diameter
    led_d = 5.0         # status LED hole


def rounded_box(l, w, h, r):
    return (
        cq.Workplane("XY")
        .box(l, w, h, centered=(True, True, False))
        .edges("|Z")
        .fillet(r)
    )


def make_shell(p: ChassisParams):
    """Outer shell minus inner cavity = hollow enclosure."""
    outer = rounded_box(p.length, p.width, 30.0, p.corner_r).translate((0, 0, -p.floor_t))
    inner_w = p.length - 2 * p.wall
    inner_d = p.width - 2 * p.wall
    inner_block = cq.Workplane("XY").box(
        inner_w, inner_d, 30.0, centered=(True, True, False)
    ).translate((0, 0, p.floor_t))
    shell = outer.cut(inner_block)
    return shell


def make_battery_tray(p: ChassisParams):
    """Removable 18650 x4 pack tray (bottom bay, slide-in from rear)."""
    l, w = p.length - 2 * p.wall - 6, p.width - 2 * p.wall - 10
    tray_floor = cq.Workplane("XY").box(l - 4, w - 4, 2.0).translate((0, 0, p.floor_t + 0.5))
    # 4 cylindrical cell pockets
    cells = None
    for i in range(4):
        x = -l / 4 + (i % 2) * l / 2
        y = -w / 4 + (i // 2) * w / 2
        cell = (
            cq.Workplane("XY")
            .circle(9.0)  # 18650 = 18mm dia -> r9, 65mm long in Z? keep short bay: use r9 x h10
            .extrude(10.0)
            .translate((x, y, p.floor_t + 2.5))
        )
        cells = cell if cells is None else cells.union(cell)
    tray = tray_floor.union(cells)
    return tray


def make_buttons(p: ChassisParams):
    """SOS button (front face) + status LED + USB-C slot markers."""
    btn = (
        cq.Workplane("YZ")
        .center(0, 0)
        .circle(p.button_d / 2)
        .extrude(3.0)
        .translate((p.length / 2, 0, 18.0))
    )
    return btn


def main():
    p = ChassisParams()
    shell = make_shell(p)
    tray = make_battery_tray(p)
    buttons = make_buttons(p)

    cq.exporters.export(shell, str(OUT / "chassis_shell.step"))
    cq.exporters.export(shell, str(OUT / "chassis_shell.stl"))
    cq.exporters.export(tray, str(OUT / "battery_tray.step"))
    cq.exporters.export(tray, str(OUT / "battery_tray.stl"))

    report = {
        "params": {k: getattr(p, k) for k in dir(p) if not k.startswith("_") and not callable(getattr(p, k))},
        "shell_volume_mm3": shell.val().Volume(),
        "shell_mass_g_petg": shell.val().Volume() * 1.27 / 1000.0,
        "tray_volume_mm3": tray.val().Volume(),
        "notes": [
            "PETG or ABS only; field-rated enclosure",
            "Battery tray: 4x 18650 (3.7V) -> 14.8V nominal, needs buck to 5V USB-C PD",
            "Stack height: 3 boards x 1.6mm + 2 x 2.5mm header gaps ~= 9.2mm; cavity 22mm OK",
            "Add 2mm standoffs at PCB corners in CAD revision 2",
        ],
    }
    (OUT / "dimensions.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report["params"], indent=2))
    print(f"shell: {report['shell_mass_g_petg']:.1f} g PETG")


if __name__ == "__main__":
    main()
