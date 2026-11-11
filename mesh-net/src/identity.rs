use ed25519_dalek::{Signature, Signer, SigningKey, Verifier, VerifyingKey};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use x25519_dalek::{PublicKey as DhPublic, StaticSecret};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, PartialOrd, Ord, Serialize, Deserialize)]
pub struct NodeId(pub [u8; 16]);

impl NodeId {
    pub fn from_key(pk: &[u8; 32]) -> Self {
        let h = Sha256::digest(pk);
        let mut id = [0u8; 16];
        id.copy_from_slice(&h[..16]);
        NodeId(id)
    }

    pub fn short(&self) -> String {
        self.0[..4].iter().map(|b| format!("{b:02x}")).collect()
    }
}

impl std::fmt::Display for NodeId {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", self.short())
    }
}

/// Public half of an identity, shareable over the air. The X25519 key is bound to the
/// Ed25519 identity by a self-signature.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PublicIdentity {
    pub id: NodeId,
    pub sign_pk: [u8; 32],
    pub dh_pk: [u8; 32],
    pub binding_sig: [u8; 64],
}

impl PublicIdentity {
    pub fn verify_binding(&self) -> bool {
        if NodeId::from_key(&self.sign_pk) != self.id {
            return false;
        }
        let Ok(vk) = VerifyingKey::from_bytes(&self.sign_pk) else { return false };
        vk.verify(&binding_msg(&self.dh_pk), &Signature::from_bytes(&self.binding_sig)).is_ok()
    }

    pub fn verify(&self, msg: &[u8], sig: &[u8; 64]) -> bool {
        VerifyingKey::from_bytes(&self.sign_pk)
            .map(|vk| vk.verify(msg, &Signature::from_bytes(sig)).is_ok())
            .unwrap_or(false)
    }
}

fn binding_msg(dh_pk: &[u8; 32]) -> Vec<u8> {
    let mut m = b"MONOLITH-DH-BINDING-v1".to_vec();
    m.extend_from_slice(dh_pk);
    m
}

pub struct Identity {
    signing: SigningKey,
    dh: StaticSecret,
    public: PublicIdentity,
}

impl Identity {
    /// Deterministic identity from a 32-byte seed (devices use a hardware TRNG).
    pub fn from_seed(seed: [u8; 32]) -> Self {
        let signing = SigningKey::from_bytes(&seed);
        let mut dh_seed = Sha256::digest([&seed[..], b"dh"].concat());
        let dh = StaticSecret::from(<[u8; 32]>::try_from(&dh_seed[..]).unwrap());
        dh_seed.iter_mut().for_each(|b| *b = 0);
        let sign_pk = signing.verifying_key().to_bytes();
        let dh_pk = DhPublic::from(&dh).to_bytes();
        let binding_sig = signing.sign(&binding_msg(&dh_pk)).to_bytes();
        let public = PublicIdentity { id: NodeId::from_key(&sign_pk), sign_pk, dh_pk, binding_sig };
        Self { signing, dh, public }
    }

    pub fn id(&self) -> NodeId { self.public.id }
    pub fn public(&self) -> &PublicIdentity { &self.public }

    pub fn sign(&self, msg: &[u8]) -> [u8; 64] {
        self.signing.sign(msg).to_bytes()
    }

    pub fn shared_secret(&self, peer_dh_pk: &[u8; 32]) -> [u8; 32] {
        self.dh.diffie_hellman(&DhPublic::from(*peer_dh_pk)).to_bytes()
    }
}
