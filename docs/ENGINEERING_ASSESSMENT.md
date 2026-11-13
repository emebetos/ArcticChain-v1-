# ArcticChain — Engineering Assessment (Master Directive §17)

**Prepared for:** Emebet Inc. / Surafel Negussie — Planner/Maker
**Date:** 2025-11-13 · **Scope:** full repository audit per Directive §5/§17
**Method:** every claim below was checked against the actual repository.
Items that could not be executed on this machine are marked accordingly —
nothing here is claimed beyond its evidence.

**Status legend:** `IMPLEMENTED` · `TEST-VERIFIED` (automated) ·
`SIM-VERIFIED` · `HW-TESTED` · `FIELD-TESTED` · `PLANNED` · `RESEARCH`.

---

## A. Existing system assessment — what is actually in the repo

### A.1 Rust workspace (`Cargo.toml`, 4 crates, ~4,600 LOC Rust)

| Crate | Lines | What it actually is | Status |
|---|---|---|---|
| `mesh-net` (`arcticchain_mesh`) | ~800 | Real mesh **protocol + simulator**: Ed25519 identity, X25519 key agreement, ChaCha20-Poly1305 E2E envelopes, signed link-state adverts, bidirectional-link-confirmed Dijkstra routing, LoRa + 60 GHz mmWave PHY link budgets, airtime model, multi-node message-forwarding simulator with walls/obstacles. | IMPLEMENTED, TEST-VERIFIED (10 `#[test]` fns) — **but simulator-only: no radio driver, no packet I/O** |
| `firmware-hal` (`arcticchain_hal`) | ~2,400 | **Monolith phone HAL**: magnetic optical-bus hotplug module manager, OBP wire protocol, module endorsement auth, power/bandwidth allocator, device tree, thermoelectric/kinetic energy-harvest daemon, tactile surface driver, privacy controller. | IMPLEMENTED, TEST-VERIFIED (~26 tests) — **phone-centric, not fleet-node** |
| `compositor` (`arcticchain_compositor`) | ~650 | E-ink compositor, projection mapping, IMU — the Monolith display stack. | IMPLEMENTED, TEST-VERIFIED (8 tests) — phone display, not fleet |
| `simulator/engine` | ~315 | Rust→WASM entry point driving all of the above for the web dashboard. | IMPLEMENTED — requires wasm toolchain to build |
| `simulator/web` | Vite/TS app | Dashboard frontend (panels, charts) for the WASM engine. | IMPLEMENTED |

**Test count:** exactly **46 `#[test]` attributes** across the workspace —
matches the documented "46 passing tests" claim *statically*. **This machine
has no Rust toolchain (no cargo/rustc installed), so the suite could not be
executed here.** Claim status: TEST-VERIFIED by code inspection only;
re-run required on a Rust-capable machine/CI before citing as passing.

### A.2 Python proof-of-concept (`poc/`)

| File | What it is | Status |
|---|---|---|
| `arcticchain_agent.py` (v1) | CM5 agent: LoRa SPI shim (stub TX/RX), LTE AT-command shim, E-Ink file hook, SQLite store, HTTP :8080 (`/health` `/inbox` `/signal` `/message`). Single-node, no peering/routing. | IMPLEMENTED — LoRa path is a TODO stub |
| `arcticchain_agent2.py` (v2) | Store-and-forward mesh node: SQLite queues, peer table, unicast next-hop + broadcast epidemic, **HMAC-SHA256 frame signing** (`ARCTIC_KEY`), **backhaul bridge** (mesh↔HTTP gateway), embedded dashboard at `:8080`. `VirtualRadio` (UDP broadcast) + `LoRaRadio` (SPI stub). | IMPLEMENTED, **TEST-VERIFIED end-to-end** (see A.3) |
| `test_mesh.py` | Two-node acceptance harness: spawn 2 agents, verify beacons→peers, unicast delivery, broadcast flood, forged-frame rejection, queue drain. | **TEST-VERIFIED — ALL CHECKS PASSED** (signed mode) |
| `SETUP.md`, `WIRING.md`, `arcticchain-agent.service` | CM5 bring-up guide, wiring, systemd unit. | PLANNED (docs only, not field-run) |

### A.3 Simulator (`sim/`)

| File | What it is | Status |
|---|---|---|
| `mesh_sim.py` | Range-limited LoRa model (900 m default), mobile bee nodes with perch-and-report wander + mission tasking (`alert_target`), store-forward gossip, delivery/latency/coverage metrics, 4 scenarios, HTML report → `docs/sim/report.html`. | IMPLEMENTED, **SIM-VERIFIED** (ran: 100% delivery @900 m; 72% @400 m wildfire — model discriminates) |

### A.4 Firmware (`firmware/mite/`)

| File | What it is | Status |
|---|---|---|
| `mite_fw.ino` | ESP32-S3 + SX1262 Arduino sketch: 30-byte CRC16 telemetry frame, BME280/SGP30, perch detect, battery-aware deep sleep (5 min cadence, ×4 low-batt), listen window. | PLANNED — written to pin-map spec, **never compiled or run on hardware** |

### A.5 CAD & printable parts (`cad/`)

| Asset | Status |
|---|---|
| `level1/battery_tray.{step,stl}`, `chassis_shell.{step,stl}`, `dimensions.json` | IMPLEMENTED (CadQuery-generated earlier; regeneration needs Linux/VM — CadQuery blocked on this PC) |
| `out/module_*.stl`, `spine.*`, `monolith_assembly.step` | IMPLEMENTED — **Monolith phone modules**, not fleet parts |
| `stl_parts.py` → `stl/*.stl` (5 parts) | IMPLEMENTED, SIM-VERIFIED (valid binary STL structure checked); nominal dims, dry-fit required |
| `swarm_node.py`, `level1_chassis.py`, `monolith_cad.py` | IMPLEMENTED scripts |

### A.6 Documentation (`docs/`)

33-sheet ANSI-B print set (9 PDFs, audit-verified 0 collisions),
`HARDWARE.md`, `BUILD_GUIDE.md`, `ORDER_LIST.md`, `FIELD_TEST.md`,
`feasibility.md`, `PHONE_SPEC.md`, `ARCTICCHAIN_EXPLAINER.docx`,
`ARCTICCHAIN_PITCH*.docx`, `sim/report.html`, audit tooling.
Status: IMPLEMENTED (documents), PLANNED (anything describing unbuilt hardware).

---

## B. Architecture assessment — does the software support all 7 families?

**Partially — and this is the single most important finding.**

There are **two different mesh architectures** in the repo, and they do
**not** interoperate today:

| | Rust `arcticchain_mesh` | Python `arcticchain_agent2` |
|---|---|---|
| Lineage | Monolith phone project (domain separators still `MONOLITH-*`) | ArcticChain fleet (new) |
| Crypto | Per-pair E2E: X25519 static DH → ChaCha20-Poly1305, Ed25519 signatures, DH-key binding | Community symmetric: HMAC-SHA256 over JSON frames with one shared key |
| Routing | Signed link-state adverts → Dijkstra, payload-aware cost, bidirectional confirmation | Epidemic broadcast + last-heard-next-hop unicast |
| PHY model | LoRa **and 60 GHz mmWave** link budgets | LoRa only (virtual radio for dev) |
| Runs on | Simulator/WASM dashboard + Rust tests | Real PCs/Linux today; LoRa stub for Pi |
| Delivery | Envelope `msg_id`+`ttl`, relay signature check | `id` dedup, `hops` TTL, pending queue, gossip retry |

**Consequences:**

- The Rust stack is genuinely sophisticated (real crypto, real routing
  algorithm) but is a **simulator with no radio I/O** — nothing in it
  talks to an SX1262 or a socket.
- The Python agent **runs** but uses a weaker security model: one
  symmetric community key means any node can forge any node's traffic
  (HMAC proves community membership, not device identity). The Rust
  stack's per-device Ed25519/X25519 identity is the stronger design —
  and the directive (§11) asks for exactly that.
- mmWave exists only in the Rust PHY model; **no fleet device uses
  60 GHz** — it is Monolith phone technology carried over.
- `firmware-hal`, `compositor`, `simulator/web` are **Monolith phone
  OS components** (module hotplug, e-ink compositor, tactile surface,
  energy harvesting). They are valuable IP for the ArcticPhone end-state
  but irrelevant to L1/Mite/Totem/Anchor nodes today.

**Verdict:** the *vision* of one protocol for all families is preserved
in docs, but the *implementation* currently has two protocols. Section I
proposes the smallest path to unify without destabilizing working code.

---

## C. Protocol assessment — can all devices share one protocol?

**Not yet — by construction, not by accident.** Frame formats differ
(JSON text frames vs binary `Envelope`), crypto differs (symmetric vs
pairwise E2E), routing differs (gossip vs link-state). The fleet needs
ONE wire protocol. Three honest options (decision required — §1 of the
directive says do not restructure unilaterally):

1. **Rust protocol becomes canonical; Python agent re-implements its
   wire format.** Strongest crypto, but the agent must port envelope +
   LSA logic to Python (or embed the Rust core via FFI/WASM — heavy).
2. **Hybrid v1:** keep Python agent's simple frames for beacon/gossip,
   adopt the Rust envelope format for addressed messages, bridge the
   two routing planes (gossip for discovery, LSDB for unicast). Fastest
   to a real two-node LoRa link; crypto upgrade path preserved.
3. **Port agent2's proven store-forward loop into Rust** and retire the
   Python node software once the Rust core gains radio I/O. Cleanest
   long-term; slowest to hardware.

Recommendation: **option 2 for the field-prototype gate, option 3 as
the consolidation target** — details in §I.

---

## D. Hardware assessment — what can actually be assembled

| Device | Buildable from docs? | Blockers |
|---|---|---|
| **L1 Brick** | **Yes, closest to real.** BOM ($335–525), wiring doc, assembly steps, CAD shell+tray, power tree, acceptance criteria all exist. | CM5 IO board + SX1262 HAT/RF front-end must be sourced; LTE modem optional; E-Ink HAT driver integration is Level-2; no prototype has been assembled. |
| **S Mite** | Mostly — orderable parts list, pin map, power budget, firmware sketch, perch-clip STL. | ESP32-S3 + SX1262 carrier board must be designed/fabbed (no PCB files yet); firmware uncompiled; sensor calibration unvalidated. |
| **E Totem** | Enclosure STL + pole-mount dims exist. | Needs L1-class compute inside; content pipeline is doc-level only. |
| **A Anchor** | Shell + lid STLs, dock protocol described. | Charging electronics (pogo pins, BMS, MPPT) not designed to build level; backhaul selection logic is doc-level. |
| **P ArcticPhone** | Concept only — spec + blueprints. | Nothing orderable; architecture decision (Android+HAT vs custom Linux) still open. |
| **D Seed** | Research concept (TRL ~2). | Printed transient electronics — not buildable as a product; keep as research. |
| **H Meridian** | Mission concept only. | Payload/ADCS/radio all paper; correctly labeled. |

**Missing for all:** no PCB designs exist anywhere (everything is
module-on-carrier or wired-perfboard level). That is the correct scope
for the current stage but must be named honestly.

---

## E. Security assessment

| Capability | Rust `mesh-net` | Python `agent2` | Gap |
|---|---|---|---|
| Device identity | Ed25519, `NodeId=H(pk)`, deterministic from seed | `ARCTIC_NODE_ID` string only | **agent has no per-device crypto identity** |
| Key agreement | X25519 static-static (honest comment: no forward secrecy; Noise IK suggested) | none | agent needs pairwise or per-device keys |
| Payload encryption | ChaCha20-Poly1305 AEAD, AAD-bound | none (JSON plaintext) | **mesh traffic is currently readable on-air** |
| Message auth | per-message Ed25519 signature, relay-verifiable | HMAC community key | HMAC = symmetric; any node can impersonate any node |
| Replay protection | `msg_id` + `ttl`; LSDB `seq` per origin | `id` dedup (permanent, SQLite) | agent dedup is stronger in practice; no seq/nonce model |
| Forged-frame rejection | tested (`inject_lsa`, `try_open_as`) | tested (`test_mesh.py` forged frame rejected) | both verified at their own layer |
| Key provisioning/rotation/revocation | none | none | **entire lifecycle missing** — needed before real deployment |
| Secure update / admin authz / tamper-evident log | none | none | missing across the board |

**Honest summary:** the *design* is strong (the Rust envelope is
better than most hobby mesh stacks); the *deployed* agent is a PoC with
symmetric auth only. Directive §11's full list (provisioning, rotation,
revocation, secure updates) is **PLANNED**, not started.

---

## F. Swarm assessment

| Layer | Status |
|---|---|
| Role taxonomy (SENSOR/EYE/RELAY/CHARGER) | IMPLEMENTED in docs + blueprint AF-S-107 + sim roles |
| Simulated mobility (patrol wander) | SIM-VERIFIED (`mesh_sim.py`) |
| Simulated mission tasking (converge on ignition, relay midpoint) | SIM-VERIFIED — 7/10 bees on station, delivery stays 100% |
| Coordinator/tasking protocol | **PLANNED** — sim tasks bees directly; no signed tasking message exists yet |
| Firmware role/payload handling | PLANNED — `mite_fw.ino` has role byte + fixed 30 B frame; no tasking RX logic |
| Physical mobility (flight/drive) | **RESEARCH** — nothing built; perch-and-report is the only honest near-term model |
| Charging coordination | PLANNED — CHARGER role + Anchor dock protocol are doc-level |
| Navigation/localization | **RESEARCH** — bees have no positioning; sim uses ideal coordinates |

The swarm is correctly framed everywhere as "the swarm is the sensor" —
the sim demonstrates the *coordinated response* concept, which is the
right thing to prove first.

---

## G. Satellite assessment — what the ground network must expose

For Meridian/borrowed-capacity integration, the ground side needs:

1. **A store-and-forward gateway contract** — already exists:
   `BackhaulBridge` (`ARCTIC_BACKHAUL` env) is transport-agnostic
   (HTTP in/out). A satellite modem service can implement the same two
   endpoints (`/inbox`, `/outbox/{community}`) — **no protocol change
   needed**. This is the correct seam; document it as the official
   backhaul API.
2. **Message-size discipline** — LoRa frames are ~30–222 B; satellite
   L-band messages are ~340 chars. The agent's text-only messages fit;
   file/blob transfer needs a chunked-store-forward layer (PLANNED).
3. **Priority classes** — SOS/alert must pre-empt telemetry in queues.
   Currently all messages are FIFO (PLANNED: add `class` field).
4. **Delay-tolerant custody** — satellites are intermittent; the
   existing pending-queue + `uplinked` flag already models this.
5. **Ground-segment identity** — when per-device crypto lands (option 2/3
   above), satellite payloads should terminate at a named ground
   identity, not a shared community key.

No satellite interface code exists yet beyond the HTTP bridge — that is
honest and correct at this stage.

---

## H. Development roadmap — what to build next, and why

Ordered by "unblocks the most real progress per unit of risk":

1. **Rust toolchain + run the 46 tests** (this machine lacks cargo —
   install or use CI). *Why first:* the protocol claims are unverifiable
   until the suite actually runs; everything downstream cites it.
2. **Unify the two protocols (decision needed)** — §C options. Until
   decided, every new feature risks deepening the split.
3. **Real LoRa path on the Pi** — implement the SX1262 SPI driver that
   `LoRaRadio` stubs (RadioLib has a Python path; or bit-bang the
   datasheet). *This is the gate to Stage 4 (real mesh).*
4. **Two physical L1 Bricks** — BOM exists; buy, assemble, run
   `FIELD_TEST.md`. *The first real milestone of the whole project.*
5. **Delivery ACKs + message priority classes in agent2** — small,
   safe, needed for SOS acceptance criteria (§8 of directive).
6. **Position beacons → real mesh map** in the dashboard (agents
   already exchange beacons; add optional `pos` field).
7. **Swarm tasking as signed mesh traffic** — replace sim-direct
   tasking with a real `task` frame type through agent2.
8. **Key lifecycle design doc** — provisioning/rotation/revocation
   before any public deployment (§11).

Stages 9–10 (external integration, space research) proceed as docs +
the existing backhaul seam; no code needed yet.

---

## I. First implementation — smallest meaningful change set

Per directive §17, awaiting approval before major restructuring. The
proposed **minimal, non-destabilizing** first increment:

| # | Change | Risk | Unblocks |
|---|---|---|---|
| 1 | `docs/PROTOCOL_v1.md` — written spec reconciling the two stacks (frame formats, crypto, routing, migration path). Pure documentation. | none | the §C decision, made explicit |
| 2 | agent2: add `class` field (alert/data/telemetry) + priority dequeue + delivery-ACK frame type. ~80 LOC, backward-compatible. | low | SOS acceptance metrics (§8 directive) |
| 3 | agent2: optional `pos` in beacon + `/peers` returns it → dashboard draws a real mesh map. ~40 LOC. | low | visible proof-of-mesh for demos |
| 4 | Install Rust toolchain (user action or winget) → run `cargo test --workspace` → record real results in this doc. | none | verifies the 46-test claim |
| 5 | LoRa SPI driver spike on Pi — *requires hardware purchase; cannot be done on this PC.* | n/a | Stage 4 |

**Explicitly NOT proposed now** (would be major restructuring, needs
approval): replacing agent2's gossip routing with the Rust LSDB;
porting the Rust envelope into Python; any PCB design; any phone
prototype work.

---

## Verified-claims ledger

| Claim | Verdict |
|---|---|
| 46 Rust tests | **46 `#[test]` fns exist; NOT executed here (no toolchain)** |
| Signed mesh, forged frames rejected | TRUE — `test_mesh.py` passes signed end-to-end |
| Store-and-forward agent | TRUE — queue/gossip verified |
| Backhaul bridge | TRUE — verified vs mock server both directions |
| Simulator w/ mobile bees + tasking | TRUE — ran, metrics sane, discriminates |
| 33-sheet print set | TRUE — regenerated, audit 0 collisions |
| 5 STL parts | TRUE — valid binary STL, nominal dims |
| Mite firmware | WRITTEN — uncompiled, unrun |
| Field-tested anything | **NOT CLAIMED — no hardware has ever been deployed** |
| Satellite SOS operational | **NOT CLAIMED — no modem/service integrated** |
