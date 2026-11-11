use arcticchain_mesh::envelope::{Envelope, EnvelopeError};
use arcticchain_mesh::identity::Identity;
use arcticchain_mesh::network::MeshNetwork;
use arcticchain_mesh::phy::{self, Phy};
use arcticchain_mesh::routing::{LinkStateAdvert, LsaVerdict};

const BOTH: &[Phy] = &[Phy::LoRa, Phy::MmWave];

#[test]
fn identities_bind_dh_keys() {
    let a = Identity::from_seed([1; 32]);
    assert!(a.public().verify_binding());
    let mut forged = a.public().clone();
    forged.dh_pk = Identity::from_seed([2; 32]).public().dh_pk;
    assert!(!forged.verify_binding());
}

#[test]
fn envelope_e2e_relay_cannot_read_and_tamper_detected() {
    let (a, b, relay) = (Identity::from_seed([1; 32]), Identity::from_seed([2; 32]), Identity::from_seed([3; 32]));
    let mut e = Envelope::seal(&a, b.public(), 1, [9; 12], 4, b"meet at the library");
    assert!(e.relay_check(a.public()).is_ok());
    assert!(e.try_open_as(&relay, a.public()).is_none());
    assert_eq!(e.open(&b, a.public()).unwrap(), b"meet at the library");
    assert_eq!(e.open(&relay, a.public()), Err(EnvelopeError::NotForMe));
    let mut t = e.clone();
    t.ciphertext[0] ^= 1;
    assert_eq!(t.open(&b, a.public()), Err(EnvelopeError::BadSignature));
    assert!(t.relay_check(a.public()).is_err());
}

#[test]
fn demo_network_converges_everyone_knows_everyone() {
    let m = MeshNetwork::demo(7);
    for v in m.views() {
        assert_eq!(v.known_nodes, m.nodes.len(), "{} knows {}", v.name, v.known_nodes);
    }
    let s = m.summary();
    assert!(s["lora_links"] > 0 && s["mmwave_links"] > 0, "{s:?}");
}

#[test]
fn bulk_prefers_mmwave_small_message_reaches_farmhouse_over_lora() {
    let mut m = MeshNetwork::demo(7);
    let bulk = m.route(0, 4, 5_000_000, BOTH).expect("route to library");
    assert!(bulk.hops.iter().all(|h| h.phy == Phy::MmWave), "{bulk:?}");
    assert!(bulk.hops.len() >= 2, "library should be multi-hop");

    let r = m.send(0, 7, b"sos: water pump broken", BOTH);
    assert!(r.delivered, "{r:?}");
    assert!(r.plaintext_matches);
    assert!(r.hops.len() >= 2, "farmhouse is beyond single-hop LoRa range: {r:?}");
    assert!(r.hops.iter().any(|h| h.phy == Phy::LoRa));
    assert!(r.hops.iter().all(|h| !h.relay_could_decrypt && h.relay_signature_ok));
}

#[test]
fn reroutes_around_failed_relay() {
    let mut m = MeshNetwork::demo(7);
    let before = m.send(0, 7, b"hello", BOTH);
    assert!(before.delivered);
    let relay = before.path[1];
    m.nodes[relay].online = false;
    m.converge();
    let after = m.send(0, 7, b"hello", BOTH);
    assert!(after.delivered, "{after:?}");
    assert!(!after.path.contains(&relay));
}

#[test]
fn partition_reports_no_route() {
    let mut m = MeshNetwork::demo(7);
    for i in 1..7 {
        m.nodes[i].online = false;
    }
    m.converge();
    let r = m.send(0, 7, b"hello", BOTH);
    assert!(!r.delivered);
}

#[test]
fn forged_and_one_sided_adverts_cannot_hijack_routes() {
    let mut m = MeshNetwork::demo(7);
    // attacker re-signs the farmhouse's advert with its own key
    let farm = m.nodes[7].identity.public().clone();
    let attacker = Identity::from_seed([0xAA; 32]);
    let mut forged = LinkStateAdvert::new(&attacker, 999, vec![]);
    forged.origin = farm;
    assert_eq!(m.inject_lsa(0, forged), LsaVerdict::BadSignature);

    // a real-but-malicious node (school, idx 6) claims a perfect mmWave link to "you"
    let fake = phy::mmwave(1.0, 0, 0.0).unwrap();
    let you = m.nodes[0].identity.id();
    let seq = m.nodes[6].seq + 1;
    let lie = LinkStateAdvert::new(&m.nodes[6].identity, seq, vec![(you, fake)]);
    assert_eq!(m.inject_lsa(0, lie), LsaVerdict::Accepted);
    // the liar's new advert drops its real links, so it simply isolates itself
    if let Some(r) = m.route(0, 6, 1_000_000, BOTH) {
        assert!(!(r.hops.len() == 1 && r.hops[0].phy == Phy::MmWave), "unconfirmed link used: {r:?}");
    }
    assert!(m.route(0, 4, 1_000, BOTH).is_some(), "honest part of the mesh still routes");
}
