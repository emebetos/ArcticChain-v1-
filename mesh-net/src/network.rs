//! Multi-node mesh simulator: positions, walls, neighbour discovery, LSA flooding,
//! payload-aware routing and hop-by-hop forwarding of real encrypted envelopes.

use crate::envelope::Envelope;
use crate::identity::{Identity, NodeId};
use crate::phy::{self, LinkMetrics, Phy};
use crate::routing::{LinkStateAdvert, LinkStateDb, LsaVerdict, Route};
use rand_chacha::ChaCha20Rng;
use rand_core::{RngCore, SeedableRng};
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet, VecDeque};

#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub struct Wall {
    pub x0: f64,
    pub y0: f64,
    pub x1: f64,
    pub y1: f64,
}

pub struct Node {
    pub name: String,
    pub identity: Identity,
    pub x: f64,
    pub y: f64,
    pub online: bool,
    pub lora: bool,
    pub mmwave: bool,
    pub seq: u64,
    pub lsdb: LinkStateDb,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NodeView {
    pub index: usize,
    pub name: String,
    pub id: String,
    pub x: f64,
    pub y: f64,
    pub online: bool,
    pub lora: bool,
    pub mmwave: bool,
    pub known_nodes: usize,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LinkView {
    pub a: usize,
    pub b: usize,
    pub metrics: LinkMetrics,
    pub distance_m: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HopTrace {
    pub from: usize,
    pub to: usize,
    pub phy: Phy,
    pub rate_bps: f64,
    pub cost_ms: f64,
    pub sf: Option<u8>,
    pub sector: Option<u8>,
    pub relay_signature_ok: bool,
    pub relay_could_decrypt: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DeliveryReport {
    pub delivered: bool,
    pub error: Option<String>,
    pub path: Vec<usize>,
    pub hops: Vec<HopTrace>,
    pub latency_ms: f64,
    pub payload_bytes: usize,
    pub envelope_bytes: usize,
    pub plaintext_matches: bool,
}

pub struct MeshNetwork {
    pub nodes: Vec<Node>,
    pub walls: Vec<Wall>,
    rng: ChaCha20Rng,
    msg_id: u64,
}

fn segments_intersect(a: (f64, f64), b: (f64, f64), w: &Wall) -> bool {
    let c = (w.x0, w.y0);
    let d = (w.x1, w.y1);
    let o = |p: (f64, f64), q: (f64, f64), r: (f64, f64)| (q.0 - p.0) * (r.1 - p.1) - (q.1 - p.1) * (r.0 - p.0);
    let d1 = o(c, d, a);
    let d2 = o(c, d, b);
    let d3 = o(a, b, c);
    let d4 = o(a, b, d);
    d1 * d2 < 0.0 && d3 * d4 < 0.0
}

impl MeshNetwork {
    pub fn new(seed: u64) -> Self {
        Self { nodes: vec![], walls: vec![], rng: ChaCha20Rng::seed_from_u64(seed), msg_id: 0 }
    }

    pub fn add_node(&mut self, name: &str, x: f64, y: f64, lora: bool, mmwave: bool) -> usize {
        let mut seed = [0u8; 32];
        self.rng.fill_bytes(&mut seed);
        self.nodes.push(Node { name: name.into(), identity: Identity::from_seed(seed), x, y, online: true, lora, mmwave, seq: 0, lsdb: LinkStateDb::default() });
        self.nodes.len() - 1
    }

    pub fn index_of(&self, id: &NodeId) -> Option<usize> {
        self.nodes.iter().position(|n| n.identity.id() == *id)
    }

    fn walls_between(&self, a: usize, b: usize) -> u32 {
        let pa = (self.nodes[a].x, self.nodes[a].y);
        let pb = (self.nodes[b].x, self.nodes[b].y);
        self.walls.iter().filter(|w| segments_intersect(pa, pb, w)).count() as u32
    }

    /// Physical links between two nodes (what neighbour discovery would measure).
    pub fn measure(&self, a: usize, b: usize) -> Vec<LinkMetrics> {
        let (na, nb) = (&self.nodes[a], &self.nodes[b]);
        if !na.online || !nb.online || a == b {
            return vec![];
        }
        let dx = nb.x - na.x;
        let dy = nb.y - na.y;
        let d = (dx * dx + dy * dy).sqrt();
        let walls = self.walls_between(a, b);
        let mut v = vec![];
        if na.mmwave && nb.mmwave {
            if let Some(m) = phy::mmwave(d, walls, dy.atan2(dx)) {
                v.push(m);
            }
        }
        if na.lora && nb.lora {
            if let Some(m) = phy::lora(d, walls) {
                v.push(m);
            }
        }
        v
    }

    pub fn links(&self) -> Vec<LinkView> {
        let mut out = vec![];
        for a in 0..self.nodes.len() {
            for b in a + 1..self.nodes.len() {
                let d = ((self.nodes[a].x - self.nodes[b].x).powi(2) + (self.nodes[a].y - self.nodes[b].y).powi(2)).sqrt();
                for m in self.measure(a, b) {
                    out.push(LinkView { a, b, metrics: m, distance_m: d });
                }
            }
        }
        out
    }

    /// Every online node builds a fresh signed LSA; LSAs are flooded hop-by-hop over any
    /// physical link and each node verifies before storing.
    pub fn converge(&mut self) {
        let n = self.nodes.len();
        let mut lsas = vec![];
        for a in 0..n {
            if !self.nodes[a].online {
                continue;
            }
            let mut links = vec![];
            for b in 0..n {
                for m in self.measure(a, b) {
                    links.push((self.nodes[b].identity.id(), m));
                }
            }
            self.nodes[a].seq += 1;
            lsas.push((a, LinkStateAdvert::new(&self.nodes[a].identity, self.nodes[a].seq, links)));
        }
        let adj: Vec<BTreeSet<usize>> = (0..n).map(|a| (0..n).filter(|&b| !self.measure(a, b).is_empty()).collect()).collect();
        for node in self.nodes.iter_mut() {
            node.lsdb = LinkStateDb::default();
        }
        for (origin, lsa) in lsas {
            let mut seen = BTreeSet::from([origin]);
            let mut q = VecDeque::from([origin]);
            while let Some(u) = q.pop_front() {
                let _ = self.nodes[u].lsdb.ingest(lsa.clone());
                for &v in &adj[u] {
                    if seen.insert(v) {
                        q.push_back(v);
                    }
                }
            }
        }
    }

    /// Inject an advert at a node (used to test forged / replayed LSAs).
    pub fn inject_lsa(&mut self, at: usize, lsa: LinkStateAdvert) -> LsaVerdict {
        self.nodes[at].lsdb.ingest(lsa)
    }

    pub fn route(&self, src: usize, dst: usize, bytes: usize, allow: &[Phy]) -> Option<Route> {
        self.nodes[src].lsdb.route(self.nodes[src].identity.id(), self.nodes[dst].identity.id(), bytes, allow)
    }

    pub fn send(&mut self, src: usize, dst: usize, payload: &[u8], allow: &[Phy]) -> DeliveryReport {
        let mut rep = DeliveryReport { delivered: false, error: None, path: vec![src], hops: vec![], latency_ms: 0.0, payload_bytes: payload.len(), envelope_bytes: 0, plaintext_matches: false };
        let Some(dst_pub) = self.nodes[src].lsdb.identity(&self.nodes[dst].identity.id()).cloned() else {
            rep.error = Some("destination unknown (not in link-state database)".into());
            return rep;
        };
        let wire = payload.len() + 129;
        let Some(route) = self.route(src, dst, wire, allow) else {
            rep.error = Some("no route".into());
            return rep;
        };
        self.msg_id += 1;
        let mut nonce = [0u8; 12];
        self.rng.fill_bytes(&mut nonce);
        let mut env = Envelope::seal(&self.nodes[src].identity, &dst_pub, self.msg_id, nonce, 16, payload);
        rep.envelope_bytes = env.wire_len();
        let src_pub = self.nodes[src].identity.public().clone();
        for h in &route.hops {
            let to = self.index_of(&h.to).unwrap();
            let from = self.index_of(&h.from).unwrap();
            rep.path.push(to);
            rep.latency_ms += h.cost_ms;
            let is_dst = to == dst;
            let sig_ok = if is_dst { true } else { env.relay_check(&src_pub).is_ok() };
            let peek = if is_dst { false } else { env.try_open_as(&self.nodes[to].identity, &src_pub).is_some() };
            rep.hops.push(HopTrace { from, to, phy: h.phy, rate_bps: h.rate_bps, cost_ms: h.cost_ms, sf: h.sf, sector: h.sector, relay_signature_ok: sig_ok, relay_could_decrypt: peek });
            if !sig_ok {
                rep.error = Some(format!("relay {to} dropped envelope: bad signature / ttl"));
                return rep;
            }
        }
        match env.open(&self.nodes[dst].identity, &src_pub) {
            Ok(pt) => {
                rep.delivered = true;
                rep.plaintext_matches = pt == payload;
            }
            Err(e) => rep.error = Some(format!("{e:?}")),
        }
        rep
    }

    pub fn views(&self) -> Vec<NodeView> {
        self.nodes
            .iter()
            .enumerate()
            .map(|(i, n)| NodeView { index: i, name: n.name.clone(), id: n.identity.id().short(), x: n.x, y: n.y, online: n.online, lora: n.lora, mmwave: n.mmwave, known_nodes: n.lsdb.len() })
            .collect()
    }

    /// A town-scale demo topology: an apartment cluster (mmWave), a park, and a farmhouse
    /// several km away reachable only over LoRa.
    pub fn demo(seed: u64) -> Self {
        let mut m = MeshNetwork::new(seed);
        m.add_node("you", 0.0, 0.0, true, true);
        m.add_node("roommate", 40.0, 10.0, true, true);
        m.add_node("neighbor", 110.0, -20.0, true, true);
        m.add_node("cafe", 220.0, 30.0, true, true);
        m.add_node("library", 330.0, -10.0, true, true);
        m.add_node("park-relay", 1200.0, 400.0, true, false);
        m.add_node("school", 2600.0, 900.0, true, true);
        m.add_node("farmhouse", 7400.0, 2100.0, true, false);
        m.walls.push(Wall { x0: 70.0, y0: -60.0, x1: 70.0, y1: -5.0 });
        m.walls.push(Wall { x0: 160.0, y0: 60.0, x1: 280.0, y1: 60.0 });
        m.converge();
        m
    }

    pub fn summary(&self) -> BTreeMap<&'static str, usize> {
        let l = self.links();
        BTreeMap::from([
            ("nodes", self.nodes.len()),
            ("online", self.nodes.iter().filter(|n| n.online).count()),
            ("lora_links", l.iter().filter(|x| x.metrics.phy == Phy::LoRa).count()),
            ("mmwave_links", l.iter().filter(|x| x.metrics.phy == Phy::MmWave).count()),
        ])
    }
}
