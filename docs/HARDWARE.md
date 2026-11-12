# ArcticChain Hardware Family — designed for rural & remote Canada

Status: design brief · supersedes Monolith-era assumptions for the product line
Owner: Emebet Inc. / ArcticChain

> The old blueprint (`docs/blueprint.svg`, `cad/monolith_cad.py`) was a flagship
> research device — titanium spine, optical docks, 10 Gb/s lanes. That program
> still exists as advanced R&D. **The product line is different**: every node
> below is designed from scratch for the places carriers won't serve — cold,
> remote, community-owned, offline-first.

---

## 1. Design DNA — the non-negotiables

Every ArcticChain node inherits this spec. A part that fails one of these isn't
ArcticChain hardware.

### Climate envelope (Alberta → territories)

- **-45 °C to +70 °C** ambient operating range. Thermal cycling, condensation,
  freeze-thaw.
- **IP65 minimum**; IP67 target for anything pole- or ground-mounted.
- **UV-stable materials** — PETG/PC only, no PLA, no vinyl labels that chalk.
- **Cold-rated power** — LiFePO4 preferred over NMC Li-ion (better cold
  tolerance, safer, longer cycle life). No consumer cells that die at -20 °C.
- **Solar sized for December** — northern winter sun is ~8 h at low angle,
  possibly snow-covered. Panels oversized; autonomy target **30–90 days**
  unattended.

### Bear country & physical abuse

- Enclosures shrug off bears, ATVs, hail, gravel-road vibration, marine spray.
- Pole/band/clamp mounts — **no concrete, no special tools, two-person install**.
- Tamper-resistant but field-serviceable. No proprietary screws, no glued
  shells — a local tech fixes it with hand tools and a multimeter.

### Culture & sovereignty

- **Community-owned** — the mesh belongs to the community co-op, municipality,
  or First Nation. Not a foreign corporation's network with a local sticker.
- **Data stays home** — store-and-forward local by default; nothing leaves the
  community without explicit consent. OCAP principles for Indigenous data.
- **Privacy by design** — no telemetry off-device, no cameras where the
  community doesn't want them, no surveillance-by-default.
- **EN/FR minimum** UI; Indigenous language packs where communities ask.
- **Offline dignity** — the device works when everything else has failed.
  That is the product.

### Appropriate technology

- **Right-sized cost** — a $500 node that works beats a $3,000 flagship that
  needs a specialist.
- **Repairable > sealed.** Standard fasteners, accessible battery tray, SD-card
  access, swap-able radio module.
- **Open docs** — hardware and firmware documentation open enough for the
  community to verify and repair.

### Deployment reality

- Shipped far, installed by non-specialists: pole clamp, barn wall, boat rail,
  truck box, fence line.
- Everything must survive being left alone for a season.

---

## 2. The fleet

One network, many shapes. Every node speaks the same signed mesh
(`mesh-net`: Ed25519 envelopes, ChaCha20-Poly1305), does store-and-forward,
and runs solar-first. They differ in *role*, not in trust model.

| Node | Codename | Role | Envelope (mm) | Power | Comms | Status |
|------|----------|------|---------------|-------|-------|--------|
| Field node | **L1 "Brick"** | Handheld mailbox + repeater + bulletin + SOS | 160×80×24 | 4×18650 / solar | LoRa + LTE | **CAD ready** — needs cold-weather BOM pass |
| Community board | **E "Totem"** | Public E-Ink noticeboard + mesh node | ~320×220×80 + pole | Solar | LoRa (+LTE opt) | Spec — CAD next |
| Swarm unit | **S "Mite"** | Perchable environmental sensor (collective aperture) | ~90×90×35 | Solar + tiny cell | LoRa | **CAD scripted** (`cad/swarm_node.py`) |
| Charging station | **A "Anchor"** | Renewable station: swarm dock, relay, backhaul | ~350×250×400 + array | 20–60 W solar + LiFePO4 | LoRa + backhaul | Spec — CAD queued |
| Rural phone | **P "ArcticPhone"** | Mesh-native comms device, satellite SOS-ready | ~145×72×14 | Replaceable + solar | LoRa + cellular/sat | **Re-design** (see §4) |
| Sensor mote | **D "Seed"** | Degradable seasonal sensor (seed-drop) | ~20×20×5 | Printed solar | LoRa (rare TX) | R&D — materials program |
| Satellite payload | **H "Meridian"** | Store-and-forward sat — the mesh IS its ground segment | 1U/3U CubeSat | Solar array | S-band | Vision — rideshare path |

---

## 3. Each node, and what makes it *unique to ArcticChain*

### L1 "Brick" — the field node *(CAD ready)*

The proof-of-life product. A hand-held brick that is simultaneously mailbox,
repeater, public bulletin (E-Ink), and SOS beacon. Nothing off the shelf does
all four.

- **Unique:** the only handheld that is a first-class mesh citizen *and* a
  public display *and* an emergency beacon.
- **Needed revision:** cold-weather BOM pass — LiFePO4 or cold-rated cells
  (NMC 18650s lose most capacity below 0 °C), IP65 gasket, conformal coat,
  glove-friendly SOS button, E-Ink (works fine cold — a real advantage).
- **Files:** `cad/level1_chassis.py`, `cad/level1/`, `poc/` (agent + wiring).

### E "Totem" — the community board *(spec)*

The town square in a box. Pole- or post-mounted public E-Ink board that is
also a mesh node — emergency alerts, community notices, local information,
agency bulletins. Readable at arm's length, zero power to display, works when
the grid and cell network are both down.

- **Unique:** the only public noticeboard that *is* a network node — it doesn't
  just display, it routes. A general-store board, updated wirelessly.
- **Cultural fit:** the community noticeboard is familiar, trusted rural
  technology. Nobody fears a sign.
- **Design notes:** 7–13″ E-Ink, solar + LiFePO4, LoRa primary, optional LTE
  backhaul, tamper-resistant but readable, EN/FR content pipeline.

### S "Mite" — the swarm unit *(CAD scripted)*

One member of the fire-watch swarm — but remember the architecture: **the
swarm is the sensor**, not the individual. Each Mite is minimal on purpose:
solar top, LoRa radio, temp/RH/VOC sensing, perch clip. A hundred perched
Miters form a distributed aperture that follows the fire season — fuel
breaks in August, snowpack telemetry in April.

- **Unique:** not a standalone sensor — a *mesh-native swarm member* with the
  same signed identity as every other node. Perch-and-report; flight is a
  later role, not the default state.
- **Gen-1 honest size:** ~90 mm — achievable with orderable parts. Sub-bee
  motes are the R&D destination, reached through iteration, not the launch
  spec.
- **Files:** `cad/swarm_node.py` (this design pass).

### A "Anchor" — the charging station *(spec)*

The fixed, renewable-powered infrastructure the swarm needs: a station where
Miters top off, relay traffic, and where the mesh gets backhaul when it
exists. Sited at the community hub, fire lookout, well site, or band office.

- **Unique:** the only node whose job is *charging other nodes* — it turns the
  swarm from battery-limited visitors into a persistent network.
- **Design notes:** 20–60 W array, LiFePO4 pack sized for winter, LoRa +
  optional LTE/satellite backhaul, charging contacts for docked units,
  status display, tamper-resistant enclosure.

### P "ArcticPhone" — the rural comms device *(re-design)*

See §4 — this is the biggest conceptual change.

### D "Seed" — the degradable mote *(R&D)*

The end-state: a ~20 mm mote of printed electronics on biodegradable substrate,
seed-dropped over a fuel break or burn scar each season. It sprouts into a
temporary sensor skin, reports through cluster heads, and dissolves. Zero
e-waste, no retrieval, no grid.

- **Unique:** sensing that *ends*. Seasonal by design.
- **Honest status:** materials/transient-electronics program — fundable R&D
  (SR&ED, university partners), not a product yet. Every earlier rung must
  succeed first.

### H "Meridian" — the satellite payload *(vision)*

When the mesh needs backhaul beyond terrestrial reach, our own store-and-
forward payload flies — and the ground segment already exists: **the mesh is
the satellite's user-terminal layer**. Nobody else launching smallsats has a
deployed rural ground network waiting for them.

---

## 4. The phone, re-conceived

**Monolith was the wrong phone for this mission.** A titanium flagship with
optical module docks is a beautiful research platform — and completely wrong
for a rancher in a -35 °C truck cab or a fly-in community with one charging
outlet.

The product phone — working title **ArcticPhone** — is designed around rural
Canada first:

- **Mesh-native** — every ArcticPhone is a node. Calls, texts, and data ride
  the community mesh when there's no cell signal; the phone *is* the network.
- **Satellite SOS-ready** — emergency beacon path via existing L-band
  services now, our own constellation later. SOS works where nothing else does.
- **Offline-first apps** — maps, manuals, forms, messaging in EN/FR, all
  useful with zero connectivity. The phone respects that rural life is often
  offline life.
- **Rugged by default** — glove-friendly UI, works to -30 °C, replaceable
  battery, solar-charge capable, survives a truck cab and a boat rail.
- **Repairable & community-owned** — standard parts, open docs, the community
  owns the network it runs on.

The Monolith CAD/blueprint is retained as the advanced R&D reference — the
ceiling the program grows toward. The ArcticPhone is what ships first.

---

## 5. Design sequence

| Order | Node | Why now |
|-------|------|---------|
| 1 | L1 Brick | CAD ready — build the 2-unit acceptance test |
| 2 | S Mite | CAD scripted — the swarm's gen-1 unit |
| 3 | E Totem | Public interface — makes the mesh visible to a town |
| 4 | A Anchor | Completes the swarm power story |
| 5 | P ArcticPhone | Re-design pass after L1 proves the mesh |
| 6 | D Seed / H Meridian | R&D and vision — earned, not skipped |

Every CAD piece follows the `level1_chassis.py` convention: parametric
CadQuery → STEP + STL + `dimensions.json`.

**Print set:** `docs/print/` contains the full blueprint PDF set — one
multi-page PDF per node on ANSI B landscape (17×11 in) sheets, generated by
`docs/make_fleet_pdfs.py`. Every sheet carries the attribution block:
Surafel Negussie (planner/maker) · Emebet Inc. / emebetos.ca (sole
proprietary owner) · PROPRIETARY & CONFIDENTIAL.
