//! Module authentication.
//!
//! Each module carries an Ed25519 key pair burned at manufacture and an *endorsement*:
//! the Monolith root key's signature over `(uid, class, module_public_key)`. On attach the
//! HAL checks the endorsement against its trust root, then issues a fresh nonce bound to
//! the slot number; the module must sign it with its private key. This defeats cloned
//! descriptors (no private key) and replay into a different slot.

use crate::module::{ModuleClass, ModuleDescriptor};
use ed25519_dalek::{Signature, Signer, SigningKey, Verifier, VerifyingKey};
use std::collections::HashSet;

const ENDORSE_TAG: &[u8] = b"MONOLITH-MODULE-ENDORSEMENT-v1";
const CHALLENGE_TAG: &[u8] = b"MONOLITH-SLOT-CHALLENGE-v1";

pub fn endorsement_message(uid: u64, class: ModuleClass, pk: &[u8; 32]) -> Vec<u8> {
    let mut m = Vec::with_capacity(ENDORSE_TAG.len() + 41);
    m.extend_from_slice(ENDORSE_TAG);
    m.extend_from_slice(&uid.to_le_bytes());
    m.push(class as u8);
    m.extend_from_slice(pk);
    m
}

pub fn challenge_message(nonce: &[u8; 32], slot: u8, uid: u64) -> Vec<u8> {
    let mut m = Vec::with_capacity(CHALLENGE_TAG.len() + 41);
    m.extend_from_slice(CHALLENGE_TAG);
    m.extend_from_slice(nonce);
    m.push(slot);
    m.extend_from_slice(&uid.to_le_bytes());
    m
}

/// The manufacturer CA (only used by factories and the simulator).
pub struct Manufacturer {
    key: SigningKey,
}

impl Manufacturer {
    pub fn from_seed(seed: [u8; 32]) -> Self {
        Self { key: SigningKey::from_bytes(&seed) }
    }

    pub fn trust_root(&self) -> TrustRoot {
        TrustRoot::new(self.key.verifying_key().to_bytes())
    }

    pub fn endorse(&self, uid: u64, class: ModuleClass, module_pk: &[u8; 32]) -> [u8; 64] {
        self.key.sign(&endorsement_message(uid, class, module_pk)).to_bytes()
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AuthError {
    BadPublicKey,
    BadEndorsement,
    BadResponse,
    Revoked,
}

#[derive(Clone)]
pub struct TrustRoot {
    root: [u8; 32],
    revoked: HashSet<u64>,
}

impl TrustRoot {
    pub fn new(root_public_key: [u8; 32]) -> Self {
        Self { root: root_public_key, revoked: HashSet::new() }
    }

    pub fn revoke(&mut self, uid: u64) {
        self.revoked.insert(uid);
    }

    pub fn verify_endorsement(&self, d: &ModuleDescriptor) -> Result<(), AuthError> {
        if self.revoked.contains(&d.uid) {
            return Err(AuthError::Revoked);
        }
        let root = VerifyingKey::from_bytes(&self.root).map_err(|_| AuthError::BadPublicKey)?;
        let sig = Signature::from_bytes(&d.endorsement);
        root.verify(&endorsement_message(d.uid, d.class, &d.public_key), &sig)
            .map_err(|_| AuthError::BadEndorsement)
    }

    pub fn verify_response(&self, d: &ModuleDescriptor, nonce: &[u8; 32], slot: u8, sig: &[u8; 64]) -> Result<(), AuthError> {
        let pk = VerifyingKey::from_bytes(&d.public_key).map_err(|_| AuthError::BadPublicKey)?;
        pk.verify(&challenge_message(nonce, slot, d.uid), &Signature::from_bytes(sig))
            .map_err(|_| AuthError::BadResponse)
    }
}
