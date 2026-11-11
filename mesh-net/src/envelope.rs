//! End-to-end envelopes.
//!
//! Payloads are encrypted with ChaCha20-Poly1305 under a key derived from X25519(src, dst)
//! and signed by the sender, so relays can drop forged/spam traffic without being able to
//! read it. (Static-static DH has no forward secrecy; a production stack would run a Noise
//! IK handshake per session on top of the same identities.)

use crate::identity::{Identity, NodeId, PublicIdentity};
use chacha20poly1305::aead::{Aead, KeyInit, Payload};
use chacha20poly1305::{ChaCha20Poly1305, Key, Nonce};
use sha2::{Digest, Sha256};

#[derive(Debug, Clone, PartialEq)]
pub struct Envelope {
    pub src: NodeId,
    pub dst: NodeId,
    pub msg_id: u64,
    pub ttl: u8,
    pub nonce: [u8; 12],
    pub ciphertext: Vec<u8>,
    pub signature: [u8; 64],
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum EnvelopeError {
    BadSignature,
    DecryptFailed,
    NotForMe,
    TtlExpired,
}

fn header(src: &NodeId, dst: &NodeId, msg_id: u64) -> Vec<u8> {
    let mut h = b"MONOLITH-E2E-v1".to_vec();
    h.extend_from_slice(&src.0);
    h.extend_from_slice(&dst.0);
    h.extend_from_slice(&msg_id.to_le_bytes());
    h
}

fn signed_bytes(e: &Envelope) -> Vec<u8> {
    let mut m = header(&e.src, &e.dst, e.msg_id);
    m.extend_from_slice(&e.nonce);
    m.extend_from_slice(&e.ciphertext);
    m
}

fn derive_key(shared: &[u8; 32], a: &NodeId, b: &NodeId) -> Key {
    let (lo, hi) = if a <= b { (a, b) } else { (b, a) };
    let k = Sha256::new().chain_update(b"monolith-e2e-key").chain_update(shared).chain_update(lo.0).chain_update(hi.0).finalize();
    *Key::from_slice(&k)
}

impl Envelope {
    pub fn seal(sender: &Identity, recipient: &PublicIdentity, msg_id: u64, nonce: [u8; 12], ttl: u8, plaintext: &[u8]) -> Self {
        let key = derive_key(&sender.shared_secret(&recipient.dh_pk), &sender.id(), &recipient.id);
        let aad = header(&sender.id(), &recipient.id, msg_id);
        let ciphertext = ChaCha20Poly1305::new(&key)
            .encrypt(Nonce::from_slice(&nonce), Payload { msg: plaintext, aad: &aad })
            .expect("encryption cannot fail for in-memory buffers");
        let mut e = Envelope { src: sender.id(), dst: recipient.id, msg_id, ttl, nonce, ciphertext, signature: [0; 64] };
        e.signature = sender.sign(&signed_bytes(&e));
        e
    }

    /// What every relay does: check the sender's signature, decrement TTL.
    pub fn relay_check(&mut self, sender: &PublicIdentity) -> Result<(), EnvelopeError> {
        if !sender.verify(&signed_bytes(self), &self.signature) {
            return Err(EnvelopeError::BadSignature);
        }
        if self.ttl == 0 {
            return Err(EnvelopeError::TtlExpired);
        }
        self.ttl -= 1;
        Ok(())
    }

    pub fn open(&self, me: &Identity, sender: &PublicIdentity) -> Result<Vec<u8>, EnvelopeError> {
        if self.dst != me.id() {
            return Err(EnvelopeError::NotForMe);
        }
        if !sender.verify(&signed_bytes(self), &self.signature) {
            return Err(EnvelopeError::BadSignature);
        }
        let key = derive_key(&me.shared_secret(&sender.dh_pk), &self.src, &self.dst);
        let aad = header(&self.src, &self.dst, self.msg_id);
        ChaCha20Poly1305::new(&key)
            .decrypt(Nonce::from_slice(&self.nonce), Payload { msg: &self.ciphertext, aad: &aad })
            .map_err(|_| EnvelopeError::DecryptFailed)
    }

    /// A relay trying to read traffic it forwards (must fail).
    pub fn try_open_as(&self, relay: &Identity, sender: &PublicIdentity) -> Option<Vec<u8>> {
        let key = derive_key(&relay.shared_secret(&sender.dh_pk), &self.src, &self.dst);
        let aad = header(&self.src, &self.dst, self.msg_id);
        ChaCha20Poly1305::new(&key).decrypt(Nonce::from_slice(&self.nonce), Payload { msg: &self.ciphertext, aad: &aad }).ok()
    }

    pub fn wire_len(&self) -> usize {
        16 + 16 + 8 + 1 + 12 + self.ciphertext.len() + 64
    }
}
