# ArcticChain — Key Lifecycle & Identity Design

**Status:** DESIGN — not yet implemented · **Owner:** Emebet Inc.
**Scope:** device identity, provisioning, rotation, revocation, admin
authorization. Implements Directive §11 requirements.

---

## 1. Identity model (target)

Every device holds a **device identity** = the Rust `Identity` pair:

- **Ed25519 signing key** — proves origin of every frame/LSA/envelope.
- **X25519 agreement key** — pairwise E2E encryption (ChaCha20-Poly1305).
- `NodeId = SHA256(sign_pk)[..16]` — stable, self-certifying.
- The X25519 key is **bound** to the Ed25519 key by a self-signature
  (`ARCTIC-DH-BINDING-v1`) — already implemented in `identity.rs`.

Private keys live in a **secure element** where available (ATECC608 /
OPTIGA / TPM 2.0 on CM5; ESP32-S3 eFuse-backed key on Mite). Where no SE
exists, keys are generated on-device at first boot from the hardware TRNG
and stored in encrypted flash — weaker, documented honestly.

## 2. Provisioning (manufacture → field)

```
[Factory]  Emebet burns a per-device seed into the SE at programming.
           Public identity printed on the device label (QR).
           Device ships with NO community membership.

[Enrollment]  First boot: device broadcasts an enrollment request
           (signed by device key, containing public identity + claimed
           role). A community admin device approves via a signed
           `enroll` control frame → device joins `community` roster.
           Enrollment is OFFLINE-CAPABLE: admin signs on-device,
           transfers via mesh/USB/NFC — no internet needed.
```

Enrollment approval is a **signed roster delta**, not a database entry —
the roster is itself mesh-replicated data (gossip class `control`).

## 3. Community roster (membership)

- Roster = signed, versioned list of `(NodeId, role, enrolled_ts,
  status)` maintained by admin devices.
- Gossip protocol replicates roster deltas like any control message.
- Nodes accept mail/tasks only from rostered identities (plus a small
  "pending" window for enrollment).
- Conflicting admin signatures → highest roster `seq` wins; admins are
  themselves rostered with an `admin` role bit.

## 4. Rotation

- **Scheduled:** device rotates its X25519 key every N days (config,
  default 30) by broadcasting a signed `keyupdate` frame; peers cache
  `(NodeId → current dh_pk, valid_from)` — old key honored for a grace
  window (7 days) to avoid partition.
- **Compromise:** admin-issued signed `rotate-now` frame; device
  generates fresh keypair, re-binds, floods `keyupdate`.
- Ed25519 signing keys rotate only on physical re-key (device RMA /
  reflash) — rotation of the *signing* identity changes NodeId, treated
  as a new device + roster update.

## 5. Revocation

- Admin signs `revoke(NodeId, reason, ts)` → floods on mesh + backhaul.
- Revoked NodeIds are rejected at `_verify`/`relay_check` — frames drop.
- Revocation is **permanent until re-enrolled** (new enrollment cycle).
- Revocation list is append-only, versioned by roster seq — a stale
  node cannot un-revoke itself because it cannot forge the admin sig.

## 6. Replay & freshness

- `msg_id` monotonic per sender + permanent `seen` set (already in
  agent2). Envelopes add `ttl` absolute deadline.
- Beacons carry `ts`; receivers reject beacons older than 5 min
  (clock-skew tolerant — mesh has no trusted time source; documented
  limitation: replayed *old* beacons only poison neighbor tables, which
  self-heals).

## 7. Admin authorization

- Admin actions (enroll, revoke, rotate, tasking) require a signature
  from a rostered `admin` identity — NOT the community HMAC key.
- `ARCTIC_KEY` HMAC remains a **dev/lab mode only**; field builds MUST
  run with per-device keys. A node with `ARCTIC_KEY` set refuses to
  join a rostered community (prevents downgrade attacks).
- Break-glass: physical button-press + local serial = factory reset;
  remote admin cannot be locked out because roster admins are plural
  (M-of-N threshold signing is a v2 item — documented, not built).

## 8. What exists today vs. this design

| Piece | Status |
|---|---|
| Ed25519/X25519/ChaCha20-Poly1305 envelope + binding | IMPLEMENTED (Rust, tested statically) |
| HMAC community signing | IMPLEMENTED (agent2) — dev mode per this doc |
| Per-device key provisioning | **PLANNED** — no SE integration yet |
| Roster replication | **PLANNED** — gossip exists; roster schema doesn't |
| Rotation/revocation frames | **PLANNED** — control-frame types reserved in PROTOCOL_v1 |
| Secure update | **PLANNED** — signed firmware manifest + A/B partitions on CM5; ESP32-S3 OTA later |
| Tamper-evident log | **PLANNED** — hash-chained SQLite (`log_hash` column) — small, do next |

## 9. Honest gaps

- **No forward secrecy** (static-static X25519, documented in
  `envelope.rs`) — Noise IK handshake is the upgrade path.
- **Clock is untrusted** — `ts`-based replay windows are approximate;
  `msg_id` monotonicity is the real defense.
- **HMAC dev mode is symmetric** — acceptable for bench mesh, never
  for field units.
- **Supply chain:** CM5/ESP32 come from global fabs — "Canadian
  sovereignty" here means operational/data sovereignty, not silicon
  origin. Documented per Directive §11.
