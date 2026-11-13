# P · ARCTICPHONE — Requirements & Prototype Plan

**Status:** CONCEPT — NOT FROZEN · **Owner:** Emebet Inc. · **Planner/Maker:** Surafel Negussie
**Blueprints:** `docs/print/05_P_ArcticPhone.pdf` (7 sheets, AF-P-101…107)

The phone is the flagship *product* — the thing a person buys. Everything
else (Brick, Mite, Totem, Anchor) is infrastructure; the phone is how a
community member touches the mesh every day.

---

## 1. Product definition

**One line:** the phone that works where there is no network — and makes
the network better every time someone carries it.

Six differentiators (from AF-P-105):

1. **Tri-radio** — LoRa mesh (community) + LTE (internet when towers
   exist) + L-band satellite (SOS/short messaging always).
2. **Every phone is a repeater** — carries mesh traffic for neighbors;
   the 100th user has better coverage than the 1st.
3. **Satellite SOS as standard** — not a premium tier. In remote Canada
   an SOS that depends on a cell tower is not an SOS.
4. **Offline dignity suite** — maps, manuals, forms, messaging EN/FR
   fully functional with zero bars.
5. **Community sync** — messages/files ride the town mesh first;
   internet backhaul only when the community gateway has it.
6. **Repairable** — standard screws, open back, replaceable battery,
   documented board-level repairs. Designed to be fixed in a truck cab.

## 2. Target specification (v0 targets — to be validated)

| Parameter | Target | Notes |
|---|---|---|
| Dimensions | ~145 × 72 × 14 mm, ~220 g | gloved-hand usable |
| Display | 5.5–6" sunlight-readable, glove mode | e-ink secondary option for status |
| Mesh radio | SX1262 915 MHz, signed envelopes | same protocol as fleet |
| Cellular | LTE Cat-1/4 (not 5G) | rural bands, carrier cert path |
| Satellite | L-band messenger module (borrowed capacity first) | SOS + ≤340-char msgs |
| Battery | removable, ≥ 4000 mAh, USB-C PD | cold-weather derating designed in |
| Environmental | IP68, −30..+55 °C operating | Canadian climate spec |
| Drop | 1.5 m onto gravel/granite | corner bumpers TPU |
| Audio | loud speaker + noise-cancel mic | works with gloves/helmets |

## 3. Architecture decision (OPEN — AF-P-102)

| Option | Approach | Verdict |
|---|---|---|
| A | Rugged Android + ArcticChain mesh HAT | fastest to market; Android bloat + cert effort |
| B | Custom Linux + mesh SoC (integrated SX1262) | clean, sovereign, repairable; OS work |
| C | Hybrid: Linux core + Android layer | best of both; longest dev |

**Recommendation:** prototype on **A** (prove the product/market),
design toward **B** (the sovereign end-state). The mesh HAT carries the
SX1262 + GPS + e-ink strip; the phone body stays a serviceable Android.

## 4. Expansion module bay (AF-P-103)

Pogo-pin + guide-pin bay under the back cover — modules authenticate
with a signed descriptor (EmebetOS module signing). Planned modules:

- satellite comms (L-band)
- thermal camera (AGR/SEARCH)
- extended battery (PATROL)
- LoRa range booster (RELAY)
- e-ink status dock (FIELD)
- storage expansion (SURVEY)
- third-party accessories (community hardware ecosystem)

Security requirement: unsigned/unauthorized modules must not power on —
module signature check at the embedded controller, before power rails.

## 5. Field UX requirements (AF-P-104)

- **Glove mode** — all critical UI ≥ 48 dp touch targets, high contrast.
- **Mesh dashboard** — inbox, peers, queue, community board mirror.
- **SOS flow** — one physical button, one long-press, satellite path
  chosen automatically when no LTE/mesh route exists.
- **EN/FR parity** — every string, offline, no cloud translation needed
  for core functions (translation optional via mesh LLM service later).
- **No account required** — phone works with zero identity; community
  key enrollment is optional and revocable.

## 6) Prototype plan

| Phase | Deliverable | Gate |
|---|---|---|
| P0 | Spec freeze + BOM categories (AF-P-102/106) | this doc + print set |
| P1 | Mesh HAT on dev board + agent2 port to CM5/Android service | two-phone bench mesh test |
| P2 | Rugged reference phone + HAT integration | FIELD_TEST.md adapted for phone |
| P3 | Satellite SOS module (borrowed L-band) | SOS round-trip test |
| P4 | Community pilot (10–50 phones, one community) | retention + support load |
| P5 | Module bay + first-party modules | signed-module security review |
| P6 | Custom-Linux sovereign build decision | based on P4 data |

## 7. Honest risks

- **Certification:** LTE + satellite + LoRa = three radio certs; budget
  real money/time (ISED + carrier PTCRB + satellite operator).
- **Satellite cost:** borrowed L-band is $/message — SOS must be
  free-to-user (absorbed in device price or community plan).
- **Android mesh background limits:** Android kills background radios;
  the mesh service needs foreground-service privileges or moves native.
- **Repairability vs sealing:** IP68 + user-openable is a real
  engineering tension — gasket + captive screws, validated by soak test.
- **Don't compete with flagship phones on specs** — compete on "works
  where nothing else does." That is the entire brand.
