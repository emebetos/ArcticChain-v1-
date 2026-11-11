# Project Monolith: technical and feasibility review

This review covers what the simulator shows, what physics and current components allow, and what has to change before any of this becomes hardware. Ratings:
**Buildable** means it can be built today with off-the-shelf parts. **Hard** means it can be done, but needs real engineering or cost. **Unrealistic as specified** means physics or the market blocks the spec as written.

| # | Subsystem | Rating | Biggest blocker |
|---|-----------|--------|-----------------|
| 1 | Lego spine + optical bus | Hard | Mass, thickness, contact contamination, and Project Ara's history |
| 2 | Programmable surface | Hard (tactile) / Conflicting (privacy on E-Ink) | Dynamic microfluidics aren't commercial; reflective E-Ink can't be light-field steered |
| 3 | Zero-charge power | **Unrealistic as specified** | Harvest is under 0.1% of a phone's daily energy |
| 4 | Node mesh + local-first OS | Buildable (LoRa, OS) / Hard (60 GHz) | 60 GHz is line-of-sight; LoRa duty-cycle limits |
| 5 | E-Ink + tabletop projector | Hard | Grazing-angle projection from a flat phone; colour E-Ink refresh rate |

## 1. Lego spine and optical bus

**What works in the repo:** the CadQuery spine passes all 42 checks: a 154 × 72 × 9.8 mm envelope, 0.15 mm/side fits, flush modules, and zero interference in every dock. The Rust HAL authenticates a module (manufacturer endorsement plus a slot-bound challenge), allocates power and bandwidth, and inserts the module into the live device tree in about 10 ms of simulated time. The 50 ms budget leaves room for a real optical-link training sequence.

**Problems:**
- **Mass.** The solid generated spine weighs **181 g** in Ti-6Al-4V. That is about a whole flagship phone's weight before any modules. The production part needs topology optimisation (pocketed ribs, around 1 mm walls) or a magnesium/aluminium frame with titanium dock inserts. Expect 40–60 g.
- **Battery volume.** A bay is 29.0 × 49.2 × 5.2 mm (7.4 cm³). After module walls, about 5 cm³ is left for the cell. At around 700 Wh/L that is roughly 3.5 Wh per block, so the simulator's 4.5 Wh/block is optimistic. Two blocks hold about 7 Wh, about half of a typical phone battery.
- **Optical contacts.** A free-space 10 Gb/s lane across a 0.1 mm window gap needs about ±50 µm alignment (the Ø2 mm H7/g6 pins provide it) and a clean window. Pocket lint is the main field failure mode. The window needs a sapphire cover and an eye-safe VCSEL power class. Electrical pogo pins carry power only.
- **Precedent.** Google's Project Ara (cancelled in 2016) and the LG G5 failed partly because of thickness, cost, and weak module ecosystems. Fairphone succeeded by focusing on repairability rather than hot-swap. A credible path is a small set of first-party modules first, then an open dock spec.
- **Certification.** Every radio module (satcom, mesh) needs its own modular FCC/CE certification. The HAL's trust root is also where regulatory locking happens. Keep it user-controllable to stay "open".

## 2. Programmable surface ("clay") and privacy layer

- **Tactile:** EAP haptic films (single-digit to tens of µm stroke) are commercial. Microfluidic rising keys were shipped once, by Tactus Phorm in 2014, but only with one *fixed* key layout. Arbitrarily re-routable fluid zones under a display aren't commercial: valves, pump volume, and optical clarity all fight each other. The driver models this by giving microfluidic zones a shared fluid budget and a slow slew rate, while the EAP zones handle clicks.
- **Privacy:** eye-tracked directional backlights exist in research and some laptop privacy screens. **They need an emissive or backlit display.** The front display in this design is reflective E-Ink, which has no light source to steer. The controller is sound for an OLED/LCD variant, or for the projector. For E-Ink, privacy should be a passive louvre film (about ±30°) instead.

## 3. "Zero-charge" power: the hard limit

With the dashboard defaults (body to 22 °C ambient, a 127-couple TEG, a 5 g piezo proof mass, and a normal day of handling and walking), the daemon harvests **4.5 mWh/day**. A phone uses about **12,000 mWh/day**, so harvest covers **0.038%** of it. Even generous assumptions (a 3 K effective ΔT across the TEG, constant contact, running) stay below about 50 mWh/day. That is under 0.5%.

Why: TEG output scales with ΔT², and the effective ΔT across a small module is 1–3 K, not the 15 K skin-to-air difference, because thermal resistances in series eat most of it. Piezo output is limited by proof mass and displacement inside a pocket.

**What it can do:** harvest can't even cover the whole always-on tier, which needs 28 mWh/day with the defaults (harvest supplies about 16% of that). It *can* sustain the critical floor indefinitely: RTC/PMIC plus LoRa beacon RX at about 33 µW, or about 0.8 mWh/day. The E-Ink image holds at zero power. The daemon's job is to keep the critical floor running on harvest and the buffer cell, and to throttle the interactive, background and deferrable tiers. With the defaults, it throttles for 443 minutes over 48 h. Rename the feature "battery-extending harvest", not "zero-charge".

## 4. Node phone: mesh and local-first OS

- **LoRa:** the PHY is legal in ISM bands and proven for phone-adjacent meshes (Meshtastic, goTenna). Note that **LoRaWAN** is a star network with gateways, so the mesh uses the raw LoRa PHY. Limits: 0.3–22 kb/s, airtime of seconds per packet at high spreading factors, and a 1% duty cycle in the EU. It is fine for text, SOS, and location. It can't carry media.
- **60 GHz:** 802.11ad/ay phased arrays have shipped in phones (ASUS ROG Phone). They give Gb/s at about 10 m line-of-sight but are blocked by walls and bodies. The simulator models this: walls kill mmWave edges, and bulk payloads route around them or fail.
- **Security:** link-state adverts are signed, only bidirectional links are used, and payloads are end-to-end sealed (X25519 + ChaCha20-Poly1305, signed by the sender). The prototype uses static-static ECDH. Production should use a Noise IK/XX handshake for forward secrecy, and needs per-hop rate limiting against flooding.
- **Local-first OS:** buildable today. GrapheneOS-style hardening, file-based encryption, and 3–8B quantized models already run on 8–12 GB phones. "Zero telemetry" is a policy plus build-system property. Enforce it with a default-deny egress firewall and reproducible builds.

## 5. Dual E-Ink and tabletop projector

- **Colour E-Ink "high refresh":** colour ePaper (Kaleido 3 / Gallery 3) takes hundreds of ms to over 1 s for full-colour updates. Fast modes (A2/DU) are monochrome and leave ghosting. The waveform scheduler models this: fast modes for typing and scrolling, periodic GC16 clears, and slow colour updates for images. Plan for the "reading/messaging" use case, not video.
- **Projector geometry:** with the phone lying flat, the exit pupil sits only about 40 mm above the table. The dashboard shows what that does to a 20″ image: **81.8° incidence at the far edge, about 8% raster use after keystone correction, and about 1 lux uniform brightness**. It isn't usable. Fixes: a pop-up fold mirror or periscope that raises the exit pupil to 150–250 mm (use the slider), plus ultra-short-throw freeform optics. A 20″ image wants at least 100 lux in a dim room, so around 30 lm with the correct geometry.
- **Laser safety:** RGB MEMS projectors are certified Class 2 or 3R. The compositor's IR-depth beam interlock (laser off within one frame when a face or hand enters the beam path) and its pose-exit hysteresis are required safety features, not extras.
- **IR touch:** a ToF or structured-light sensor beside the projector is standard (e.g. Sony Xperia Touch). The homography in `compositor/src/projection.rs` maps detected touches back to UI coordinates.

## Recommended v1 scope

1. Spine and dock spec with electrical + optical bus, three first-party modules (battery, camera, LoRa/satcom), and topology-optimised frame under 60 g.
2. Colour E-Ink front display with EAP haptics. Defer microfluidics.
3. Harvest as an always-on tier only. Keep a normal battery.
4. LoRa mesh + local-first OS. Make 60 GHz a later module.
5. Projector as a module with a pop-up mirror, not built into a flat phone.
