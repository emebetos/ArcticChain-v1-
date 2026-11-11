# ArcticChain Level-1 Wiring Guide

Bill of materials (orderable in Canada):

| # | Part | Supplier class | Approx CAD |
|---|------|----------------|-----------|
| 1 | Raspberry Pi Compute Module 5 + IO Board | PiShop / Canada Computers | $90–130 |
| 2 | 7.5" E-Ink HAT (Waveshare-class) | DFRobot / Amazon CA | $80–110 |
| 3 | 4G/LTE HAT (SIM7600-class, with antenna) | DFRobot / Waveshare | $60–90 |
| 4 | SX1262 LoRa breakout (SPI) | DFRobot / Adafruit CA | $15–25 |
| 5 | Magnetic pogo-pin connector pairs ×6 | AliExpress/Amazon | $30–60 |
| 6 | 4× 18650 cells + 14.8V→5V buck module | Electronics supplier | $40–70 |
| 7 | 3D-printed chassis (this repo, `cad/level1/`) | Print farm / makerspace | $20–40 |
| **Total** | | | **≈ $335–525** |

## Stack order (bottom → top)

```
[Bottom]  USB-C power input + battery tray
          CM5 IO Board (power + HDMI + USB + GPIO header)
          4G/LTE HAT            — uses GPIO UART + USB for AT commands
          E-Ink HAT             — uses SPI (GPIO 9–11) + GPIO 25 (busy)
          [Top]    LoRa SX1262 — dedicated SPI1 (GPIO 16–21) or software SPI
```

## GPIO allocation (avoid conflicts)

| Signal | GPIO | Notes |
|--------|------|-------|
| E-Ink SPI | 9 (MOSI), 10 (MISO), 11 (SCLK), 8 (CE0) | HAT default |
| E-Ink busy | 25 | Poll before refresh |
| E-Ink reset | 17 | |
| 4G/LTE | USB (CDC-ACM) or UART PL011 (GPIO 14/15) | Prefer USB — no pin conflicts |
| LoRa SPI1 | 17 (MOSI), 18 (MISO... verify board), 19 (SCLK), 20 (CE) — **move to GPIO 16–21 range per your breakout silkscreen** | Configure in device tree |
| LoRa reset/DIO1 | 24 / 23 | Interrupt-driven RX |
| SOS button | 27 (input, pull-up) | Wire to front button in chassis |
| Status LED | 22 (PWM) | Power + mesh-activity indicator |

> **Conflict warning:** E-Ink and LoRa both want SPI. Use two SPI buses:
> `spi0` for E-Ink (GPIO 7–11), `spi1` for LoRa (GPIO 16–21). Enable both in
> `/boot/firmware/config.txt`: `dtoverlay=spi1-3cs` or equivalent for CM5.

## Power path

```
18650 x4 (14.8V nominal, 16.8V full)
   -> 14.8V→5V 3A buck module (USB-C PD trigger)
      -> CM5 (5V/5A via USB-C) + HATs (5V rail)
```

- Add a **power-path controller** (e.g. BQ24075-class) for Level 2 so the
  battery can hot-swap without resetting the CM5 (see `firmware-hal` docs —
  the Rust HAL assumes this behaviour).
- Fuse: 5A on the 5V rail, 10A on battery input.

## Antennas (critical for field range)

- **4G/LTE:** SMA whip, mounted at chassis top, keep 10mm+ from LoRa antenna
- **LoRa 915MHz:** spring/whip antenna, vertical, at opposite end of chassis
- **Keep-out:** no metal (battery cells, buck inductor) within 15mm of either antenna

## Assembly order

1. Print `chassis_shell.stl` + `battery_tray.stl` (PETG, 40% infill, 4 walls)
2. Seat CM5 IO Board on standoffs; connect battery tray wiring
3. Stack HATs with 2.5mm headers; apply thermal pads on CM5 SoC
4. Wire LoRa breakout to GPIO header per table above
5. Route antennas through top grommets; seal with silicone
6. Flash OS (see `poc/SETUP.md`), then run `poc/arcticchain-agent` service
