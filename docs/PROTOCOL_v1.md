# ArcticChain Protocol v1 — Unified Wire Specification

**Status:** DRAFT for approval · **Owner:** Emebet Inc. · **Supersedes:**
nothing yet — this reconciles the two existing stacks.

This document is the decision record required by the Engineering
Assessment (§C). It defines ONE protocol family for all seven device
families, with a migration path that does not break working code.

---

## 1. The problem being solved

Two stacks exist today:

| | `arcticchain_mesh` (Rust) | `arcticchain_agent2` (Python) |
|---|---|---|
| Crypto | per-pair E2E (Ed25519 sign + X25519→ChaCha20-Poly1305) | community HMAC-SHA256 |
| Routing | signed link-state adverts → Dijkstra | epidemic gossip + next-hop |
| Frames | binary `Envelope` | JSON text |
| Runs | simulator/WASM only | real machines, virtual radio proven |

They cannot interoperate. v1 picks a path that keeps both assets.

## 2. Decision: hybrid v1, consolidate to Rust long-term

**v1 (field-prototype gate):**

- **Discovery & neighborhood:** gossip beacons (agent2 model) — cheap,
  robust, works with no topology knowledge.
- **Addressed mail:** adopt the Rust `Envelope` *format and crypto*
  (Ed25519 signature + X25519-derived ChaCha20-Poly1305) as the
  canonical message container, carried inside the agent's JSON-free
  binary frame on LoRa.
- **Routing:** epidemic forwarding for broadcast + last-heard
  next-hop for unicast **now**; link-state LSDB (Rust `routing.rs`
  logic, already written and tested) is the v1.1 upgrade once real
  links exist to measure.
- **Device identity:** every node holds an Ed25519 signing key +
  X25519 agreement key (the Rust `Identity` model). HMAC community
  key remains as a *deployment domain* tag, not the security boundary.

**v1.1 (consolidation target):** port the Rust envelope + LSDB into the
node runtime (Rust agent or FFI), retire the Python crypto shim.
`firmware-hal`/`compositor` remain Monolith-phone IP, invoked only by
ArcticPhone-class devices.

## 3. Frame formats

### 3.1 Beacon (gossip, unauthenticated-content / signed-envelope optional)

```
{ "t":"beacon", "node":<id>, "community":<name>, "ts":<unix>,
  "pos":[lat,lon]|null, "batt":<pct>, "sig":<hmac|ed25519> }
```

Beacons are small, frequent, and may be unsigned in dev mode
(`ARCTIC_KEY` empty). In production they carry an Ed25519 signature
over canonical JSON — beacon forgery only enables bad neighbor tables,
not mail injection, because mail is E2E-encrypted anyway.

### 3.2 Message envelope (canonical, from `mesh-net/src/envelope.rs`)

Binary layout (unchanged from Rust):

```
[header 32B: "ARCTIC-E2E-v1" | src NodeId 16B | dst NodeId 16B | msg_id 8B]
[nonce 12B][ciphertext+tag][signature 64B]
```

- Key = HKDF-SHA256(X25519(src,dst), "arcticchain-e2e-key", src‖dst ordered)
- AEAD = ChaCha20-Poly1305, AAD = header
- Signature = Ed25519 over header‖nonce‖ciphertext
- `ttl`/`hops` carried inside plaintext header (mesh-visible hop count
  for diagnostics, not security-relevant)
- Plaintext payload = UTF-8 JSON `{"class","text","reply_to",...}`

Note: Rust domain separator currently reads `MONOLITH-E2E-v1` —
**must be renamed `ARCTIC-E2E-v1`** when the envelope is adopted on-air
(domain separation is a one-line change; flagged, not silently done).

### 3.3 Control frames (agent2, JSON, HMAC or Ed25519-signed)

| `t` | Purpose | Fields |
|---|---|---|
| `ack` | delivery receipt | `id` (msg), `from` (deliverer), `ts` |
| `task` | swarm/coordinator tasking | `id`, `role`, `target`[x,y], `ttl`, `class:"control"` |
| `status` | node health broadcast | `batt`, `temp`, `queue_depth`, `uptime` |

`task` frames are the swarm coordination primitive — signed, class
`control`, highest priority, small TTL.

## 4. Message classes & priority

Every message carries `class`:

| Class | Examples | Queue behavior |
|---|---|---|
| `alert` | SOS, fire, flood, amber alerts | pre-empt all; never dropped for queue pressure until TTL |
| `control` | tasking, ACKs, beacons-adjacent | high; may pre-empt `data` |
| `data` | mail, files-chunked, notices | normal FIFO |
| `telemetry` | sensor streams, bee readings | bulk; droppable under congestion |

Dequeue order: `alert` > `control` > `data` > `telemetry`.

## 5. Delivery semantics

- `msg_id` = 64-bit per-sender counter (Rust) — replay window per peer.
- Dedup: permanent per-node `seen` set (SQLite) — already implemented.
- ACK: destination emits `ack` frame; origin records `acked` state.
  Unacked messages remain `pending` and re-gossip until TTL/hop expiry —
  **store-and-forward is preserved; ACK is observability, not a
  reliability requirement.**
- Expiry: `hops` decremented per forward; `ttl` inside envelope as
  absolute deadline for alert-class messages.

## 6. Security model (target state)

| Layer | Mechanism |
|---|---|
| Device identity | Ed25519 `Identity` per node (seed in secure element / TPM / sealed flash) |
| Link privacy | X25519 pairwise → ChaCha20-Poly1305 (relays verify sig, cannot read) |
| Community admission | `community` tag + optional community CA-signed node roster |
| Replay | `msg_id` monotonic per sender + `seen` set |
| Key lifecycle | PLANNED: provisioning at manufacture, rotation via signed `keyupdate` control frame, revocation via signed roster delta — **not yet implemented** |
| Dev mode | `ARCTIC_KEY` HMAC = lab convenience only; MUST be absent in field units |

## 7. What changes where

| Component | Change |
|---|---|
| `agent2` | add `class`, priority dequeue, `ack` frames, `pos` beacons, mesh map — **done in this increment** |
| `mesh-net` (Rust) | rename domain separators `MONOLITH-*`→`ARCTIC-*` (one-line each, 3 sites) — pending approval as it's a wire-format change |
| `mite_fw.ino` | add `class`+`pos` fields to 30 B frame; `task` RX handling — pending |
| Backhaul API | unchanged — already transport-agnostic (`/inbox`,`/outbox/{community}`) |

## 8. Open items (need owner decision)

1. Domain-separator rename in Rust (wire-format change).
2. Community CA vs pure pairwise identity for node admission.
3. Whether unicast keeps epidemic flooding until LSDB lands (recommended:
   yes — correctness first, efficiency later).
