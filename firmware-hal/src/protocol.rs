//! Optical Bus Protocol (OBP) framing.
//!
//! ```text
//! | sync "MO" (2) | type (1) | seq (2, LE) | len (2, LE) | payload (len) | crc32 (4, LE) |
//! ```
//! The CRC covers `type..payload`. Frames ride a 10 Gb/s optical lane; the magnetic pogo
//! pins carry VBUS, GND, DETECT (presence) and a low-speed SIDEBAND used before lane lock.

use crate::crc::crc32;
use crate::module::{ModuleClass, ModuleDescriptor, Priority};
use serde::{Deserialize, Serialize};

pub const SYNC: [u8; 2] = *b"MO";
pub const HEADER_LEN: usize = 7;
pub const MAX_PAYLOAD: usize = 1024;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct Requirements {
    pub nominal_mw: u32,
    pub min_mw: u32,
    pub mbps: u32,
    pub min_mbps: u32,
    pub priority: Priority,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Default, Serialize, Deserialize)]
pub struct Grant {
    pub power_mw: u32,
    pub mbps: u32,
    pub lanes: u8,
    pub rail_mv: u16,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[repr(u8)]
pub enum RejectReason {
    Unauthenticated = 1,
    InsufficientPower = 2,
    InsufficientBandwidth = 3,
    Timeout = 4,
    Protocol = 5,
    Revoked = 6,
}

impl RejectReason {
    fn from_u8(v: u8) -> Option<Self> {
        use RejectReason::*;
        [Unauthenticated, InsufficientPower, InsufficientBandwidth, Timeout, Protocol, Revoked]
            .into_iter()
            .find(|r| *r as u8 == v)
    }
}

#[derive(Debug, Clone, PartialEq)]
pub enum Message {
    Enumerate,
    Hello(ModuleDescriptor),
    Challenge { nonce: [u8; 32], slot: u8 },
    Response { signature: [u8; 64] },
    QueryRequirements,
    Requirements(Requirements),
    Grant(Grant),
    Ready,
    Reject { reason: RejectReason },
    Heartbeat { seq: u32 },
    HeartbeatAck { seq: u32, temp_dc: i16, draw_mw: u32 },
    DetachRequest,
    DetachAck,
}

impl Message {
    fn type_id(&self) -> u8 {
        match self {
            Message::Enumerate => 0x01,
            Message::Hello(_) => 0x02,
            Message::Challenge { .. } => 0x03,
            Message::Response { .. } => 0x04,
            Message::QueryRequirements => 0x05,
            Message::Requirements(_) => 0x06,
            Message::Grant(_) => 0x07,
            Message::Ready => 0x08,
            Message::Reject { .. } => 0x09,
            Message::Heartbeat { .. } => 0x0A,
            Message::HeartbeatAck { .. } => 0x0B,
            Message::DetachRequest => 0x0C,
            Message::DetachAck => 0x0D,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum FrameError {
    TooShort,
    BadSync,
    BadLength,
    BadCrc,
    UnknownType(u8),
    Malformed,
}

struct W(Vec<u8>);
impl W {
    fn u8(&mut self, v: u8) { self.0.push(v) }
    fn u16(&mut self, v: u16) { self.0.extend_from_slice(&v.to_le_bytes()) }
    fn u32(&mut self, v: u32) { self.0.extend_from_slice(&v.to_le_bytes()) }
    fn u64(&mut self, v: u64) { self.0.extend_from_slice(&v.to_le_bytes()) }
    fn bytes(&mut self, v: &[u8]) { self.0.extend_from_slice(v) }
}

struct R<'a>(&'a [u8]);
impl<'a> R<'a> {
    fn take(&mut self, n: usize) -> Result<&'a [u8], FrameError> {
        if self.0.len() < n {
            return Err(FrameError::Malformed);
        }
        let (a, b) = self.0.split_at(n);
        self.0 = b;
        Ok(a)
    }
    fn u8(&mut self) -> Result<u8, FrameError> { Ok(self.take(1)?[0]) }
    fn u16(&mut self) -> Result<u16, FrameError> { Ok(u16::from_le_bytes(self.take(2)?.try_into().unwrap())) }
    fn u32(&mut self) -> Result<u32, FrameError> { Ok(u32::from_le_bytes(self.take(4)?.try_into().unwrap())) }
    fn u64(&mut self) -> Result<u64, FrameError> { Ok(u64::from_le_bytes(self.take(8)?.try_into().unwrap())) }
    fn arr<const N: usize>(&mut self) -> Result<[u8; N], FrameError> { Ok(self.take(N)?.try_into().unwrap()) }
}

fn encode_payload(msg: &Message, w: &mut W) {
    match msg {
        Message::Enumerate | Message::QueryRequirements | Message::Ready | Message::DetachRequest
        | Message::DetachAck => {}
        Message::Hello(d) => {
            w.u64(d.uid);
            w.u8(d.class as u8);
            w.u16(d.vendor_id);
            w.u32(d.fw_version);
            w.u32(d.supply_mw);
            w.u32(d.capacity_mwh);
            w.bytes(&d.public_key);
            w.bytes(&d.endorsement);
        }
        Message::Challenge { nonce, slot } => {
            w.bytes(nonce);
            w.u8(*slot);
        }
        Message::Response { signature } => w.bytes(signature),
        Message::Requirements(r) => {
            w.u32(r.nominal_mw);
            w.u32(r.min_mw);
            w.u32(r.mbps);
            w.u32(r.min_mbps);
            w.u8(r.priority as u8);
        }
        Message::Grant(g) => {
            w.u32(g.power_mw);
            w.u32(g.mbps);
            w.u8(g.lanes);
            w.u16(g.rail_mv);
        }
        Message::Reject { reason } => w.u8(*reason as u8),
        Message::Heartbeat { seq } => w.u32(*seq),
        Message::HeartbeatAck { seq, temp_dc, draw_mw } => {
            w.u32(*seq);
            w.u16(*temp_dc as u16);
            w.u32(*draw_mw);
        }
    }
}

pub fn encode(msg: &Message, seq: u16) -> Vec<u8> {
    let mut payload = W(Vec::with_capacity(160));
    encode_payload(msg, &mut payload);
    let mut w = W(Vec::with_capacity(HEADER_LEN + payload.0.len() + 4));
    w.bytes(&SYNC);
    w.u8(msg.type_id());
    w.u16(seq);
    w.u16(payload.0.len() as u16);
    w.bytes(&payload.0);
    let crc = crc32(&w.0[2..]);
    w.u32(crc);
    w.0
}

pub fn decode(frame: &[u8]) -> Result<(Message, u16), FrameError> {
    if frame.len() < HEADER_LEN + 4 {
        return Err(FrameError::TooShort);
    }
    if frame[0..2] != SYNC {
        return Err(FrameError::BadSync);
    }
    let len = u16::from_le_bytes([frame[5], frame[6]]) as usize;
    if len > MAX_PAYLOAD || frame.len() != HEADER_LEN + len + 4 {
        return Err(FrameError::BadLength);
    }
    let body_end = HEADER_LEN + len;
    let crc = u32::from_le_bytes(frame[body_end..body_end + 4].try_into().unwrap());
    if crc32(&frame[2..body_end]) != crc {
        return Err(FrameError::BadCrc);
    }
    let ty = frame[2];
    let seq = u16::from_le_bytes([frame[3], frame[4]]);
    let mut r = R(&frame[HEADER_LEN..body_end]);
    let msg = match ty {
        0x01 => Message::Enumerate,
        0x02 => Message::Hello(ModuleDescriptor {
            uid: r.u64()?,
            class: ModuleClass::from_u8(r.u8()?).ok_or(FrameError::Malformed)?,
            vendor_id: r.u16()?,
            fw_version: r.u32()?,
            supply_mw: r.u32()?,
            capacity_mwh: r.u32()?,
            public_key: r.arr()?,
            endorsement: r.arr()?,
        }),
        0x03 => Message::Challenge { nonce: r.arr()?, slot: r.u8()? },
        0x04 => Message::Response { signature: r.arr()? },
        0x05 => Message::QueryRequirements,
        0x06 => Message::Requirements(Requirements {
            nominal_mw: r.u32()?,
            min_mw: r.u32()?,
            mbps: r.u32()?,
            min_mbps: r.u32()?,
            priority: Priority::from_u8(r.u8()?).ok_or(FrameError::Malformed)?,
        }),
        0x07 => Message::Grant(Grant { power_mw: r.u32()?, mbps: r.u32()?, lanes: r.u8()?, rail_mv: r.u16()? }),
        0x08 => Message::Ready,
        0x09 => Message::Reject { reason: RejectReason::from_u8(r.u8()?).ok_or(FrameError::Malformed)? },
        0x0A => Message::Heartbeat { seq: r.u32()? },
        0x0B => Message::HeartbeatAck { seq: r.u32()?, temp_dc: r.u16()? as i16, draw_mw: r.u32()? },
        0x0C => Message::DetachRequest,
        0x0D => Message::DetachAck,
        t => return Err(FrameError::UnknownType(t)),
    };
    if !r.0.is_empty() {
        return Err(FrameError::Malformed);
    }
    Ok((msg, seq))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample_msgs() -> Vec<Message> {
        vec![
            Message::Enumerate,
            Message::Hello(ModuleDescriptor {
                uid: 0xDEAD_BEEF_0000_0001,
                class: ModuleClass::CameraSensor,
                vendor_id: 0x4D4F,
                fw_version: 0x0001_0203,
                supply_mw: 0,
                capacity_mwh: 0,
                public_key: [7; 32],
                endorsement: [9; 64],
            }),
            Message::Challenge { nonce: [3; 32], slot: 4 },
            Message::Response { signature: [5; 64] },
            Message::Requirements(Requirements { nominal_mw: 1200, min_mw: 600, mbps: 12000, min_mbps: 6000, priority: Priority::Normal }),
            Message::Grant(Grant { power_mw: 1000, mbps: 8000, lanes: 1, rail_mv: 5000 }),
            Message::Reject { reason: RejectReason::Revoked },
            Message::Heartbeat { seq: 99 },
            Message::HeartbeatAck { seq: 99, temp_dc: -105, draw_mw: 777 },
            Message::DetachRequest,
            Message::DetachAck,
            Message::Ready,
            Message::QueryRequirements,
        ]
    }

    #[test]
    fn roundtrip_all_messages() {
        for (i, m) in sample_msgs().into_iter().enumerate() {
            let f = encode(&m, i as u16);
            let (d, seq) = decode(&f).expect("decode");
            assert_eq!(d, m);
            assert_eq!(seq, i as u16);
        }
    }

    #[test]
    fn single_bit_flips_are_detected() {
        for m in sample_msgs() {
            let f = encode(&m, 7);
            for byte in 0..f.len() {
                for bit in 0..8 {
                    let mut g = f.clone();
                    g[byte] ^= 1 << bit;
                    assert!(decode(&g).is_err(), "undetected flip at byte {byte} bit {bit} in {m:?}");
                }
            }
        }
    }

    #[test]
    fn garbage_never_panics() {
        let mut x: u32 = 0x1234_5678;
        for len in 0..300 {
            let mut v = Vec::with_capacity(len);
            for _ in 0..len {
                x ^= x << 13;
                x ^= x >> 17;
                x ^= x << 5;
                v.push(x as u8);
            }
            let _ = decode(&v);
        }
    }
}
