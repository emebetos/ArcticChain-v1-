# ArcticChain — Two-Node Field Test Checklist

**Purpose:** prove the mesh works end-to-end before any public deployment.
**Equipment:** 2× L1 Brick (or 1 Brick + 1 phone running `arcticchain_agent2.py`),
USB-C PD supplies, the printed BOM, this checklist, a phone with the dashboard open.

**Estimated time:** half a day. **Pass bar:** every MUST item green.

---

## 0. Bench bring-up (indoor, ~1 h)

| # | Step | Pass criteria |
|---|------|---------------|
| 0.1 | Flash CM5 image; `systemctl enable arcticchain-agent` | service active, `curl localhost:8080/health` returns JSON |
| 0.2 | `journalctl -u arcticchain-agent -f` | sees `[lora]` init OK or clean "SPI unavailable" fallback |
| 0.3 | Open `http://<node-ip>:8080/` on a laptop | dashboard renders: health card, inbox, peers, queue |
| 0.4 | `POST /send {"to":"*","text":"bench test"}` | appears in own `/queue` within 5 s |

## 1. Same-room mesh (~15 min)

| # | Step | Pass criteria |
|---|------|---------------|
| 1.1 | Power both nodes, wait 30 s | each `/peers` lists the other with `age_s < 15` |
| 1.2 | Node A: send unicast to node B's ID | B's `/inbox` shows it, `state=delivered` |
| 1.3 | Node B: broadcast "mesh alive" | A's inbox receives it |
| 1.4 | Kill node B, send A→B message, restart B after 2 min | message still delivers (store-forward) |
| 1.5 | `/stats` on both | `delivered` count increments; `tx`/`rx` sane |

## 2. Range & obstructions (~1 h)

| # | Step | Pass criteria |
|---|------|---------------|
| 2.1 | Line-of-sight test, open field, 100 m steps | record max reliable range (expect 2–10 km LoRa) |
| 2.2 | Repeat through one building / treeline | note degradation; mesh should still route via second node |
| 2.3 | 3-node chain A—B—C, move B out of A's range | A→C message delivers via B (multihop) |
| 2.4 | RSSI logging at each distance | values plausible (-60..-120 dBm) |

## 3. Power & environment (~half day)

| # | Step | Pass criteria |
|---|------|---------------|
| 3.1 | Unplug AC, run on battery | `/health` uptime climbs; estimated runtime ≥ spec |
| 3.2 | Leave overnight on solar (if available) | battery trends up or stable by morning |
| 3.3 | Cold test (if winter): -20 °C+ ambient | boots, LoRa locks, dashboard responsive |
| 3.4 | E-ink display updates on new message | status line changes within one refresh |
| 3.5 | Enclosure: spray test or damp cloth | no moisture ingress after 30 min |

## 4. Soak & failure (~overnight)

| # | Step | Pass criteria |
|---|------|---------------|
| 4.1 | 12 h soak, beacon traffic only | no crashes; `/health` uptime ≈ wall time |
| 4.2 | Unplug node B for 1 h mid-soak, restore | queue drains, no message loss |
| 4.3 | `journalctl` review | zero unhandled exceptions |
| 4.4 | SD-card / SQLite integrity | `messages.db` opens clean after power-cycle mid-write |

## 5. Data & security spot-check

| # | Step | Pass criteria |
|---|------|---------------|
| 5.1 | Confirm zero outbound internet traffic (router log / `tcpdump`) | only LAN + mesh frames leave the node |
| 5.2 | Wrong-community frame injection (test build) | ignored — `community` tag filters |
| 5.3 | Replay an old message | dedup by `id` prevents double-delivery |

---

## Results log

| Date | Operator | Nodes | Range found | Issues |
|------|----------|-------|-------------|--------|
|      |          |       |             |        |

## Sign-off

- [ ] All MUST items pass → node pair is **field-deployable**
- [ ] Any FAIL → file issue, do not deploy; fix and retest that item only
