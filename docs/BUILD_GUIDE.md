# ArcticChain v1 Build Guide

How to take ArcticChain from "promised on paper" to a working Level-1
proof-of-concept in 2–4 weeks with a student team or makerspace.

## What exists today (this repo)

| Layer | Status | Location |
|-------|--------|----------|
| Parametric spine CAD (Grade-5 Ti envelope, 42 checks) | Done | `cad/monolith_cad.py` |
| Level-1 handheld chassis CAD (3D-printable brick) | Done | `cad/level1_chassis.py` → `cad/level1/*.step/.stl` |
| Hot-swap hardware abstraction layer (Rust) | Done, 11 tests | `firmware-hal/` |
| Mesh networking stack — LoRa + mmWave, signed routing (Rust) | Done, 7 tests | `mesh-net/` |
| Display compositor — E-Ink / projector state machine (Rust) | Done, 8 tests | `compositor/` |
| Simulation engine (Rust→WASM) | Done | `simulator/engine` |
| Level-1 wiring guide | Done | `poc/WIRING.md` |
| Pi OS setup + acceptance test | Done | `poc/SETUP.md` |
| Level-1 agent service (Python, HTTP+SQLite+LoRa shim) | Done | `poc/arcticchain_agent.py` |
| systemd unit | Done | `poc/arcticchain-agent.service` |

## What the team builds (the other 50%)

1. **Week 1–2 — Hardware bring-up**
   - Order BOM (`poc/WIRING.md`, ≈ $335–525 CAD)
   - Print chassis (`cad/level1_chassis.py`)
   - Wire per `poc/WIRING.md`; flash OS per `poc/SETUP.md`
   - Run acceptance test: two units exchange a mesh message with LTE disabled

2. **Week 3 — Radio bring-up**
   - Replace the `LoRaRadio` TODOs in `poc/arcticchain_agent.py` with real
     SX1262 SPI transactions (Semtech `sx126x` driver or `lora-packet` crate)
   - Implement the envelope format from `mesh-net/src/envelope.rs` exactly
   - Add Ed25519 signing using keys generated per `firmware-hal/src/auth.rs`

3. **Week 4 — Polish + demo**
   - E-Ink status rendering (Waveshare `waveshare_epaper` Python lib)
   - Store-and-forward inbox UI (simple web page served by the agent)
   - Demo video: hot-swap a battery block live, then mesh message with airplane mode on

## Level-2 path (senior capstone, 1 semester)

- KiCad 4–6 layer PCB in the 10.5mm spine envelope (see `poc/WIRING.md` hard parts)
- Port the Python agent's radio shim to the Rust `mesh-net` crate on-device
- Dual-display driver (OLED + E-Ink) — the compositor already models both states
- Power-path controller for true hot-swap (the HAL assumes it)

## Level-3 (professional, funded by pilot)

- ISED certification, drop/water testing, direct SoC sourcing
- See the government package for the funding path

## Definition of done (Level-1)

- [ ] Two units exchange signed mesh messages with all radios' internet disabled
- [ ] E-Ink shows last message + node health
- [ ] HTTP API serves `/health`, `/inbox`, `/message`
- [ ] Agent survives power pull and reboots clean (systemd + SQLite)
- [ ] Demo video < 3 minutes showing: boot → mesh message → airplane-mode proof
