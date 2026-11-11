//! Signed link-state routing.
//!
//! Each node floods a `LinkStateAdvert` listing the neighbours it can hear on each PHY,
//! signed with its identity key. Routers only accept adverts whose signature verifies
//! against a bound public identity, keep the highest sequence number per origin, and only
//! use links that *both* endpoints advertise, so a single compromised node cannot invent
//! links to attract traffic.

use crate::identity::{Identity, NodeId, PublicIdentity};
use crate::phy::{transfer_ms, LinkMetrics, Phy};
use serde::{Deserialize, Serialize};
use std::cmp::Ordering;
use std::collections::{BTreeMap, BinaryHeap};

#[derive(Debug, Clone, PartialEq)]
pub struct LinkStateAdvert {
    pub origin: PublicIdentity,
    pub seq: u64,
    pub links: Vec<(NodeId, LinkMetrics)>,
    pub signature: [u8; 64],
}

fn lsa_bytes(origin: &NodeId, seq: u64, links: &[(NodeId, LinkMetrics)]) -> Vec<u8> {
    let mut m = b"MONOLITH-LSA-v1".to_vec();
    m.extend_from_slice(&origin.0);
    m.extend_from_slice(&seq.to_le_bytes());
    for (n, l) in links {
        m.extend_from_slice(&n.0);
        m.push(l.phy as u8);
        m.extend_from_slice(&l.rate_bps.to_le_bytes());
        m.extend_from_slice(&l.snr_db.to_le_bytes());
        m.push(l.sf.unwrap_or(0));
        m.push(l.sector.unwrap_or(0xFF));
    }
    m
}

impl LinkStateAdvert {
    pub fn new(id: &Identity, seq: u64, links: Vec<(NodeId, LinkMetrics)>) -> Self {
        let signature = id.sign(&lsa_bytes(&id.id(), seq, &links));
        Self { origin: id.public().clone(), seq, links, signature }
    }

    pub fn verify(&self) -> bool {
        self.origin.verify_binding() && self.origin.verify(&lsa_bytes(&self.origin.id, self.seq, &self.links), &self.signature)
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum LsaVerdict {
    Accepted,
    Stale,
    BadSignature,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Hop {
    pub from: NodeId,
    pub to: NodeId,
    pub phy: Phy,
    pub rate_bps: f64,
    pub cost_ms: f64,
    pub sf: Option<u8>,
    pub sector: Option<u8>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Route {
    pub hops: Vec<Hop>,
    pub total_ms: f64,
}

#[derive(Default, Clone)]
pub struct LinkStateDb {
    lsas: BTreeMap<NodeId, LinkStateAdvert>,
}

#[derive(PartialEq)]
struct QItem(f64, NodeId);
impl Eq for QItem {}
impl PartialOrd for QItem {
    fn partial_cmp(&self, o: &Self) -> Option<Ordering> { Some(self.cmp(o)) }
}
impl Ord for QItem {
    fn cmp(&self, o: &Self) -> Ordering { o.0.partial_cmp(&self.0).unwrap_or(Ordering::Equal).then(o.1.cmp(&self.1)) }
}

/// Fixed per-hop forwarding overhead (queueing, verify signature) in ms.
pub const PER_HOP_MS: f64 = 2.0;

impl LinkStateDb {
    pub fn ingest(&mut self, lsa: LinkStateAdvert) -> LsaVerdict {
        if !lsa.verify() {
            return LsaVerdict::BadSignature;
        }
        if let Some(old) = self.lsas.get(&lsa.origin.id) {
            if old.seq >= lsa.seq {
                return LsaVerdict::Stale;
            }
        }
        self.lsas.insert(lsa.origin.id, lsa);
        LsaVerdict::Accepted
    }

    pub fn identity(&self, id: &NodeId) -> Option<&PublicIdentity> {
        self.lsas.get(id).map(|l| &l.origin)
    }

    pub fn len(&self) -> usize { self.lsas.len() }
    pub fn is_empty(&self) -> bool { self.lsas.is_empty() }

    /// Links advertised by both endpoints on the same PHY (worse of the two metrics).
    pub fn confirmed_links(&self, from: &NodeId) -> Vec<(NodeId, LinkMetrics)> {
        let Some(a) = self.lsas.get(from) else { return vec![] };
        a.links
            .iter()
            .filter_map(|(to, m)| {
                let b = self.lsas.get(to)?;
                let back = b.links.iter().find(|(n, bm)| n == from && bm.phy == m.phy)?;
                Some((*to, if back.1.rate_bps < m.rate_bps { back.1 } else { *m }))
            })
            .collect()
    }

    /// Payload-aware shortest path.
    pub fn route(&self, src: NodeId, dst: NodeId, bytes: usize, allow: &[Phy]) -> Option<Route> {
        let mut dist: BTreeMap<NodeId, f64> = BTreeMap::new();
        let mut prev: BTreeMap<NodeId, Hop> = BTreeMap::new();
        let mut q = BinaryHeap::new();
        dist.insert(src, 0.0);
        q.push(QItem(0.0, src));
        while let Some(QItem(d, u)) = q.pop() {
            if u == dst {
                break;
            }
            if d > *dist.get(&u).unwrap_or(&f64::INFINITY) {
                continue;
            }
            for (v, m) in self.confirmed_links(&u) {
                if !allow.contains(&m.phy) {
                    continue;
                }
                let c = transfer_ms(&m, bytes) + PER_HOP_MS;
                let nd = d + c;
                if nd < *dist.get(&v).unwrap_or(&f64::INFINITY) {
                    dist.insert(v, nd);
                    prev.insert(v, Hop { from: u, to: v, phy: m.phy, rate_bps: m.rate_bps, cost_ms: c, sf: m.sf, sector: m.sector });
                    q.push(QItem(nd, v));
                }
            }
        }
        let total = *dist.get(&dst)?;
        let mut hops = vec![];
        let mut cur = dst;
        while cur != src {
            let h = prev.get(&cur)?.clone();
            cur = h.from;
            hops.push(h);
        }
        hops.reverse();
        Some(Route { hops, total_ms: total })
    }
}
