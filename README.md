# ArcticChain

A sovereign Canadian rural connectivity platform: a real cell phone that becomes a community mesh node, with offline-first AI, governance tools, and zero cloud dependency. Opposite to Starlink — community-owned, ground-based, and built for the North.

This repo contains everything needed to build the Level-1 proof-of-concept: parametric CAD, a Rust hot-swap HAL, a signed mesh stack, a display compositor, a browser simulator, and a complete student/makerspace build kit.

| Path | What it is |
|------|------------|
| `cad/` | `monolith_cad.py`: parametric spine + snap-in modules (STEP/STL, 42 checks); `level1_chassis.py`: 3D-printable handheld brick (160×80×24mm) |
| `firmware-hal/` | Rust HAL: OBP framing, Ed25519 module auth, power/bandwidth allocator, dynamic device tree, hot-plug state machine |
| `mesh-net/` | Signed link-state routing over LoRa + mmWave PHY models, X25519/ChaCha20-Poly1305 E2E envelopes, multi-node simulation |
| `compositor/` | IMU pose detection, E-Ink waveform scheduler, projector state machine with IR interlock |
| `simulator/` | `engine/` (Rust→WASM) + `web/` (React/Three.js dashboard, 5 tabs) |
| `poc/` | **Level-1 build kit**: `WIRING.md` (BOM + GPIO map), `SETUP.md` (Pi CM5 bring-up + acceptance test), `arcticchain_agent.py` (mesh/cellular agent), systemd unit |
| `docs/` | `BUILD_GUIDE.md` (16-week student build plan), `blueprint.svg`, `feasibility.md` |

## Quick start

```bash
# CAD: spine + modules
python3 cad/monolith_cad.py --web ../simulator/web/public/models

# Level-1 chassis
python3 cad/level1_chassis.py        # -> cad/level1/*.step/.stl

# Firmware / mesh / compositor (46 tests)
cargo test --workspace

# Dashboard
cd simulator/web && npm install && npm run wasm && npm run dev
```

## Build the hardware (Level-1 PoC, 2–4 weeks)

1. Order BOM from `poc/WIRING.md` (≈ $335–525 CAD)
2. Print chassis from `cad/level1/`
3. Wire per `poc/WIRING.md`, flash OS per `poc/SETUP.md`
4. Run acceptance test: two units exchange a mesh message with LTE disabled

Full plan: [`docs/BUILD_GUIDE.md`](docs/BUILD_GUIDE.md)

## Status

Simulation + Level-1 bring-up kit. The spine, mesh, and local-first software are proven in tests; the Level-1 hardware is orderable off-the-shelf. See `docs/feasibility.md` for honest constraints (energy harvesting yields ~4.5 mWh/day; flat-lying projection needs a raised exit pupil).
