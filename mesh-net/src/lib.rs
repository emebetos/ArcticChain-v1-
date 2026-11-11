//! Project Monolith "Node" mesh networking stack.
//!
//! * [`identity`] – Ed25519 signing identity + X25519 key-agreement key; node id = H(pk).
//! * [`phy`] – link budgets for LoRa (sub-GHz, long range) and 60 GHz beamformed mmWave.
//! * [`routing`] – signed link-state adverts, bidirectional link confirmation, Dijkstra
//!   with payload-aware cost so small messages may ride LoRa and bulk data prefers mmWave.
//! * [`envelope`] – end-to-end encrypted, signed envelopes; relays can verify but not read.
//! * [`network`] – multi-node simulator used by tests and the dashboard.

pub mod envelope;
pub mod identity;
pub mod network;
pub mod phy;
pub mod routing;

pub use identity::{Identity, NodeId, PublicIdentity};
pub use network::{DeliveryReport, MeshNetwork};
pub use phy::Phy;
