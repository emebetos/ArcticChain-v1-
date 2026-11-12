# ArcticChain Level-1 — Order List & Build Checklist

Everything needed to build **two** nodes (the acceptance test requires two units
mesh-messaging with LTE disabled). Prices are CAD, approximate — verify at checkout.
Based on `poc/WIRING.md`; this is the "order today" version with quantities for 2 units.

## Parts — per unit ×2

| # | Part | Where (Canada) | Approx CAD | Qty |
|---|------|----------------|-----------|-----|
| 1 | Raspberry Pi Compute Module 5 (4GB) + CM5 IO Board | [pishop.ca](https://www.pishop.ca) or Canada Computers | $90–130 | 2 |
| 2 | 7.5" e-Paper HAT (Waveshare 800×480, SPI) | waveshare.com / DFRobot / Amazon.ca | $80–110 | 2 |
| 3 | SIM7600 4G/LTE HAT (GNSS + BT variants fine) | DFRobot / Waveshare / Amazon.ca | $60–90 | 2 |
| 4 | SX1262 LoRa breakout (915 MHz, SPI) — e.g. EBYTE E22-900M30S or generic | DFRobot / AliExpress / Amazon.ca | $15–25 | 2 |
| 5 | Magnetic pogo-pin connector pairs ×6 sets | AliExpress / Amazon.ca | $30–60 | 2 |
| 6 | 4× 18650 cells (flat-top, protected) + 14.8 V→5 V 3 A buck (USB-C PD trigger) | Electronics supplier / Amazon.ca | $40–70 | 2 |
| 7 | PETG filament 1 kg (prints both shells + trays, ~200 g total) | Any filament supplier | $25–35 | 1 |
| | **Parts subtotal** | | **≈ $670–1,050** | |

## Tools & consumables (one-time)

| Item | Approx CAD |
|------|-----------|
| Soldering iron + solder + flux | $40–80 |
| Wire strippers, flush cutters, helping hands | $30–50 |
| M2.5 nylon standoffs + screws assortment | $15–25 |
| 2.54 mm header pins (male/female strips) | $10 |
| Multimeter | $25–60 |
| 32 GB microSD cards ×2 (Pi OS Lite 64-bit) | $20–30 |
| USB-C PD power supply 27 W (bench flashing/testing) | $25–40 |
| Kapton tape, silicone sealant, hot glue | $15 |
| **Tools subtotal** | **≈ $180–310** |

## Build sequence (maps to `docs/BUILD_GUIDE.md` weeks 1–2)

1. **Print** `cad/level1/chassis_shell.stl` + `battery_tray.stl` — PETG,
   40% infill, 4 walls, no supports needed (verify in slicer).
2. **Flash** Raspberry Pi OS Lite 64-bit to both SD cards (Imager → enable SSH,
   user `arctic`, Wi-Fi for first boot). Follow `poc/SETUP.md` §1–3 exactly —
   the `config.txt` overlays (`spi1-3cs`, `i2c_arm`, `uart0`, `gpio-shutdown`)
   are what make the HATs coexist.
3. **Bench-test bare CM5 first** — boot, SSH in, `i2cdetect -y 1` before adding
   any HAT. Confirm the board is alive before stacking hardware.
4. **Stack** per `poc/WIRING.md`: CM5 IO board → LTE HAT → E-Ink HAT → LoRa
   breakout on GPIO 16–21 (second SPI bus — do NOT share spi0 with E-Ink).
5. **Wire** power path: 4×18650 → 14.8 V→5 V buck → USB-C into CM5; fuse the
   5 V rail; keep antennas 15 mm+ from battery/buck metal (keep-out rule).
6. **Flash agent**: copy `poc/arcticchain_agent.py` + systemd unit per
   `poc/SETUP.md` §5; `journalctl -u arcticchain-agent -f` should show clean boot.
7. **Acceptance test** (`poc/SETUP.md` §6): unit A `POST /message`, unit B
   `GET /inbox` — then airplane-mode the LTE and repeat. Mesh delivery with
   no towers = the whole pitch in one test.

## Verified on this machine (2026-11-12)

- `poc/arcticchain_agent.py` runs clean on stdlib Python; `/health`, `/message`,
  `/inbox`, `/signal` all respond; SQLite store verified end-to-end.
- `cad/level1/*.stl` validated (540 + 2012 triangles, binary STL intact);
  `dimensions.json`: 160×80 mm envelope, ~100 g PETG shell.
- Rust workspace: 46 tests passing (verified on build VM; cargo not installed locally).

## Known Level-1 gaps (by design — see `docs/BUILD_GUIDE.md`)

- `LoRaRadio.send_frame/poll` are TODOs — plaintext beacon until the SX1262
  driver + `mesh-net` envelope land (week 3 task).
- E-Ink rendering is a stub file-write; real Waveshare driver is Level-2.
- No power-path controller yet — battery swap reboots the CM5 (acceptable PoC).
