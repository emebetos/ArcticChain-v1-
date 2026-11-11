//! Simulated modules for hardware-in-the-loop testing. Each `SimModule` speaks real OBP
//! frames, signs challenges with its own Ed25519 key and can be told to misbehave.

use crate::auth::{challenge_message, Manufacturer};
use crate::hotplug::{ModuleEndpoint, Reply};
use crate::module::{ModuleClass, ModuleDescriptor, Priority};
use crate::protocol::{decode, encode, Grant, Message, Requirements};
use ed25519_dalek::{Signer, SigningKey};
use std::cell::RefCell;
use std::rc::Rc;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Fault {
    None,
    /// Signs challenges with the wrong key (cloned descriptor, no private key).
    BadSignature,
    /// Endorsement not issued by the trust root.
    ForgedEndorsement,
    /// Stops answering entirely (dead firmware / lost lane).
    Unresponsive,
    /// Corrupts every reply frame.
    CorruptFrames,
    /// Draws this many times its grant.
    Overdraw(u32),
}

#[derive(Debug, Clone)]
pub struct SimState {
    pub grant: Option<Grant>,
    pub fault: Fault,
    pub latency_us: u32,
    pub heartbeats: u32,
    pub detached: bool,
}

pub struct SimModule {
    pub desc: ModuleDescriptor,
    key: SigningKey,
    pub req: Requirements,
    pub state: Rc<RefCell<SimState>>,
}

pub fn class_defaults(class: ModuleClass) -> (Requirements, u32, u32) {
    // (requirements, supply_mw, capacity_mwh)
    let r = |nominal_mw, min_mw, mbps, min_mbps, priority| Requirements { nominal_mw, min_mw, mbps, min_mbps, priority };
    match class {
        ModuleClass::BatteryBlock => (r(40, 20, 0, 0, Priority::Critical), 4000, 4500),
        ModuleClass::NeuromorphicCore => (r(1500, 300, 16_000, 4_000, Priority::High), 0, 0),
        ModuleClass::CameraSensor => (r(1200, 600, 12_000, 6_000, Priority::Normal), 0, 0),
        ModuleClass::SatelliteTransceiver => (r(2500, 800, 2, 1, Priority::Normal), 0, 0),
        ModuleClass::ProjectorEngine => (r(3500, 1800, 6_000, 3_000, Priority::Low), 0, 0),
        ModuleClass::MeshRadio => (r(600, 150, 2_000, 100, Priority::Normal), 0, 0),
    }
}

impl SimModule {
    pub fn new(mfr: &Manufacturer, uid: u64, class: ModuleClass) -> Self {
        let mut seed = [0u8; 32];
        seed[..8].copy_from_slice(&uid.to_le_bytes());
        seed[8] = class as u8;
        seed[31] = 0xA5;
        let key = SigningKey::from_bytes(&seed);
        let pk = key.verifying_key().to_bytes();
        let (req, supply_mw, capacity_mwh) = class_defaults(class);
        let desc = ModuleDescriptor {
            uid,
            class,
            vendor_id: 0x4D4F,
            fw_version: 0x0001_0000,
            supply_mw,
            capacity_mwh,
            public_key: pk,
            endorsement: mfr.endorse(uid, class, &pk),
        };
        Self {
            desc,
            key,
            req,
            state: Rc::new(RefCell::new(SimState { grant: None, fault: Fault::None, latency_us: 400, heartbeats: 0, detached: false })),
        }
    }

    pub fn with_requirements(mut self, req: Requirements) -> Self {
        self.req = req;
        self
    }

    pub fn with_latency(self, us: u32) -> Self {
        self.state.borrow_mut().latency_us = us;
        self
    }

    pub fn with_fault(mut self, f: Fault) -> Self {
        if f == Fault::ForgedEndorsement {
            self.desc.endorsement = Manufacturer::from_seed([0xEE; 32]).endorse(self.desc.uid, self.desc.class, &self.desc.public_key);
        }
        self.state.borrow_mut().fault = f;
        self
    }

    /// Shared handle to poke the module after it is plugged in.
    pub fn handle(&self) -> Rc<RefCell<SimState>> {
        self.state.clone()
    }

    pub fn boxed(self) -> Box<dyn ModuleEndpoint> {
        Box::new(self)
    }
}

impl ModuleEndpoint for SimModule {
    fn handle(&mut self, frame: &[u8]) -> Option<Reply> {
        let mut st = self.state.borrow_mut();
        if st.fault == Fault::Unresponsive {
            return None;
        }
        let (msg, seq) = decode(frame).ok()?;
        let resp = match msg {
            Message::Enumerate => Message::Hello(self.desc.clone()),
            Message::Challenge { nonce, slot } => {
                let m = challenge_message(&nonce, slot, self.desc.uid);
                let sig = if st.fault == Fault::BadSignature {
                    SigningKey::from_bytes(&[0x42; 32]).sign(&m)
                } else {
                    self.key.sign(&m)
                };
                Message::Response { signature: sig.to_bytes() }
            }
            Message::QueryRequirements => Message::Requirements(self.req),
            Message::Grant(g) => {
                st.grant = Some(g);
                Message::Ready
            }
            Message::Heartbeat { seq } => {
                st.heartbeats += 1;
                let granted = st.grant.map(|g| g.power_mw).unwrap_or(0);
                let draw = match st.fault {
                    Fault::Overdraw(k) => granted * k,
                    _ => granted * 9 / 10,
                };
                Message::HeartbeatAck { seq, temp_dc: 300 + (draw / 50) as i16, draw_mw: draw }
            }
            Message::DetachRequest => {
                st.detached = true;
                Message::DetachAck
            }
            Message::Reject { .. } => return None,
            _ => return None,
        };
        let mut out = encode(&resp, seq);
        if st.fault == Fault::CorruptFrames {
            let n = out.len();
            out[n / 2] ^= 0x10;
        }
        Some(Reply { frame: out, latency_us: st.latency_us })
    }
}
