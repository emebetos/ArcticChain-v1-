//! Plug-and-play manager for the magnetic-mechanical optical bus.
//!
//! Attach sequence (virtual-time budget, default deadline 50 ms):
//!
//! ```text
//! DETECT edge -> debounce -> rail precharge (inrush-limited) -> optical lane training
//!   -> Enumerate/Hello -> verify endorsement -> Challenge/Response
//!   -> QueryRequirements -> allocate power + bandwidth (may re-grant / shed others)
//!   -> Grant/Ready -> device-tree insert -> rail ramp to granted power
//! ```
//!
//! Detach is either graceful (release latch -> DetachRequest/DetachAck) or a surprise
//! removal (DETECT drop or 3 missed heartbeats). Either way the module's resources are
//! freed and the remaining modules are rebalanced; removing a battery block shrinks the
//! power budget and may shed low-priority loads without rebooting.

use crate::allocator::{allocate, AllocState, Allocation, Demand};
use crate::auth::{AuthError, TrustRoot};
use crate::device_tree::{DeviceTree, DtNode};
use crate::module::{ModuleClass, ModuleDescriptor};
use crate::protocol::{self, Grant, Message, RejectReason, Requirements};
use rand_chacha::ChaCha20Rng;
use rand_core::{RngCore, SeedableRng};
use serde::Serialize;
use std::collections::BTreeMap;

/// A module reply as seen by the HAL: the response frame plus link round-trip time.
pub struct Reply {
    pub frame: Vec<u8>,
    pub latency_us: u32,
}

/// The far end of one dock's optical lane (a real transceiver driver or a simulator).
pub trait ModuleEndpoint {
    fn handle(&mut self, frame: &[u8]) -> Option<Reply>;
}

#[derive(Debug, Clone, Serialize)]
pub struct HalConfig {
    pub slots: u8,
    /// Internal solid-state buffer cell's continuous discharge capability.
    pub internal_supply_mw: u32,
    pub reserve_mw: u32,
    pub backplane_mbps: u32,
    pub lane_mbps: u32,
    pub lanes_per_slot: u8,
    pub attach_deadline_us: u64,
    pub debounce_us: u64,
    pub precharge_us: u64,
    pub link_training_us: u64,
    /// Modelled cost of one Ed25519 verification on the HAL's MCU.
    pub sig_verify_us: u64,
    pub response_timeout_us: u64,
    pub heartbeat_interval_us: u64,
    pub heartbeat_miss_limit: u8,
    pub overcurrent_ratio: f32,
    pub seed: u64,
}

impl Default for HalConfig {
    fn default() -> Self {
        Self {
            slots: 6,
            internal_supply_mw: 6000,
            reserve_mw: 400,
            backplane_mbps: 40_000,
            lane_mbps: 10_000,
            lanes_per_slot: 2,
            attach_deadline_us: 50_000,
            debounce_us: 2_000,
            precharge_us: 1_000,
            link_training_us: 3_000,
            sig_verify_us: 1_200,
            response_timeout_us: 5_000,
            heartbeat_interval_us: 10_000,
            heartbeat_miss_limit: 3,
            overcurrent_ratio: 1.25,
            seed: 0x4D4F_4E4F_4C49_5448,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
pub enum Phase {
    Debounce,
    Precharge,
    LinkTraining,
    Enumerate,
    Authenticate,
    Negotiate,
    Allocate,
    Grant,
}

#[derive(Debug, Clone, Serialize)]
pub struct AttachReport {
    pub slot: u8,
    pub uid: Option<u64>,
    pub class: Option<ModuleClass>,
    pub accepted: bool,
    pub reason: Option<RejectReason>,
    pub elapsed_us: u64,
    pub phases: Vec<(Phase, u64)>,
    pub grant: Option<Grant>,
}

#[derive(Debug, Clone, Serialize)]
pub struct DetachReport {
    pub slot: u8,
    pub uid: u64,
    pub surprise: bool,
    pub elapsed_us: u64,
}

#[derive(Debug, Clone, PartialEq, Serialize)]
pub enum HalEvent {
    Attached { slot: u8, uid: u64, class: ModuleClass, grant: Grant },
    Rejected { slot: u8, reason: RejectReason },
    Detached { slot: u8, uid: u64, surprise: bool },
    Reallocated { slot: u8, uid: u64, power_mw: u32, mbps: u32, state: AllocState },
    LoadShed { slot: u8, uid: u64 },
    Restored { slot: u8, uid: u64 },
    HeartbeatLost { slot: u8, uid: u64 },
    OvercurrentTrip { slot: u8, uid: u64, draw_mw: u32, granted_mw: u32 },
    BudgetChanged { power_budget_mw: u32 },
}

#[derive(Debug, Clone, Serialize)]
pub struct TimedEvent {
    pub t_us: u64,
    pub event: HalEvent,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum HalError {
    InvalidSlot,
    SlotOccupied,
    SlotEmpty,
}

struct ActiveModule {
    desc: ModuleDescriptor,
    req: Requirements,
    alloc: Allocation,
    endpoint: Box<dyn ModuleEndpoint>,
    order: u64,
    missed: u8,
    tripped: bool,
    path: String,
    draw_mw: u32,
    temp_dc: i16,
}

#[derive(Debug, Clone, Serialize)]
pub struct SlotSnapshot {
    pub slot: u8,
    pub uid: u64,
    pub class: ModuleClass,
    pub priority: crate::module::Priority,
    pub requested_mw: u32,
    pub min_mw: u32,
    pub requested_mbps: u32,
    pub alloc: Allocation,
    pub draw_mw: u32,
    pub supply_mw: u32,
    pub capacity_mwh: u32,
    pub temp_c: f32,
    pub tripped: bool,
    pub path: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct HalSnapshot {
    pub clock_us: u64,
    pub power_supply_mw: u32,
    pub power_budget_mw: u32,
    pub power_allocated_mw: u32,
    pub system_load_mw: u32,
    pub backplane_mbps: u32,
    pub bandwidth_allocated_mbps: u32,
    pub slots: Vec<Option<SlotSnapshot>>,
    pub dt_generation: u64,
}

pub struct Hal {
    cfg: HalConfig,
    trust: TrustRoot,
    slots: Vec<Option<ActiveModule>>,
    tree: DeviceTree,
    clock_us: u64,
    events: Vec<TimedEvent>,
    rng: ChaCha20Rng,
    seq: u16,
    order_ctr: u64,
    system_load_mw: u32,
    next_heartbeat_us: u64,
    hb_seq: u32,
}

enum Xfer {
    Ok(Message),
    Timeout,
    Corrupt,
}

fn exchange(clock: &mut u64, seq: &mut u16, timeout_us: u64, ep: &mut dyn ModuleEndpoint, msg: &Message) -> Xfer {
    *seq = seq.wrapping_add(1);
    let frame = protocol::encode(msg, *seq);
    match ep.handle(&frame) {
        None => {
            *clock += timeout_us;
            Xfer::Timeout
        }
        Some(r) => {
            *clock += r.latency_us as u64;
            if r.latency_us as u64 > timeout_us {
                return Xfer::Timeout;
            }
            match protocol::decode(&r.frame) {
                Ok((m, s)) if s == *seq => Xfer::Ok(m),
                _ => Xfer::Corrupt,
            }
        }
    }
}

impl Hal {
    pub fn new(cfg: HalConfig, trust: TrustRoot) -> Self {
        let rng = ChaCha20Rng::seed_from_u64(cfg.seed);
        let slots = (0..cfg.slots).map(|_| None).collect();
        let hb = cfg.heartbeat_interval_us;
        Self {
            cfg,
            trust,
            slots,
            tree: DeviceTree::default(),
            clock_us: 0,
            events: Vec::new(),
            rng,
            seq: 0,
            order_ctr: 0,
            system_load_mw: 0,
            next_heartbeat_us: hb,
            hb_seq: 0,
        }
    }

    pub fn config(&self) -> &HalConfig { &self.cfg }
    pub fn clock_us(&self) -> u64 { self.clock_us }
    pub fn device_tree(&self) -> &DeviceTree { &self.tree }
    pub fn trust_mut(&mut self) -> &mut TrustRoot { &mut self.trust }
    pub fn events(&self) -> &[TimedEvent] { &self.events }
    pub fn drain_events(&mut self) -> Vec<TimedEvent> { std::mem::take(&mut self.events) }
    pub fn system_load_mw(&self) -> u32 { self.system_load_mw }
    pub fn is_occupied(&self, slot: u8) -> bool {
        self.slots.get(slot as usize).map(|s| s.is_some()).unwrap_or(false)
    }

    fn emit(&mut self, event: HalEvent) {
        self.events.push(TimedEvent { t_us: self.clock_us, event });
    }

    /// Total power on the shared rail: internal cell plus attached battery blocks.
    pub fn power_supply_mw(&self) -> u32 {
        self.cfg.internal_supply_mw + self.slots.iter().flatten().map(|m| m.desc.supply_mw).sum::<u32>()
    }

    fn budget_for(&self, supply_mw: u32) -> u32 {
        supply_mw.saturating_sub(self.system_load_mw + self.cfg.reserve_mw)
    }

    pub fn power_budget_mw(&self) -> u32 {
        self.budget_for(self.power_supply_mw())
    }

    fn slot_cap_mbps(&self) -> u32 {
        self.cfg.lane_mbps * self.cfg.lanes_per_slot as u32
    }

    fn demand(&self, slot: u8, m: &ActiveModule) -> Demand {
        let r = &m.req;
        let cap = self.slot_cap_mbps();
        Demand {
            key: slot,
            priority: r.priority,
            order: m.order,
            nominal_mw: r.nominal_mw,
            min_mw: if m.tripped { r.nominal_mw.max(1) * 1000 } else { r.min_mw },
            mbps: r.mbps.min(cap),
            min_mbps: r.min_mbps.min(cap),
        }
    }

    fn grant_for(&self, a: &Allocation, req: &Requirements) -> Grant {
        let lanes = if a.mbps == 0 { 0 } else { a.mbps.div_ceil(self.cfg.lane_mbps).clamp(1, self.cfg.lanes_per_slot as u32) as u8 };
        let rail_mv = if req.nominal_mw > 4500 { 9000 } else { 5000 };
        Grant { power_mw: a.power_mw, mbps: a.mbps, lanes, rail_mv }
    }

    fn current_demands(&self) -> Vec<Demand> {
        self.slots
            .iter()
            .enumerate()
            .filter_map(|(i, s)| s.as_ref().map(|m| self.demand(i as u8, m)))
            .collect()
    }

    /// Re-run allocation and push new grants to every module whose allocation changed.
    fn rebalance(&mut self) {
        let budget = self.power_budget_mw();
        let alloc = allocate(budget, self.cfg.backplane_mbps, &self.current_demands());
        for (slot, a) in alloc {
            let i = slot as usize;
            let Some(mut m) = self.slots[i].take() else { continue };
            if m.alloc != a {
                let was_suspended = m.alloc.state == AllocState::Suspended;
                m.alloc = a;
                let g = self.grant_for(&a, &m.req);
                let _ = exchange(&mut self.clock_us, &mut self.seq, self.cfg.response_timeout_us, m.endpoint.as_mut(), &Message::Grant(g));
                let uid = m.desc.uid;
                let path = m.path.clone();
                self.tree.set(&path, "power-mw", a.power_mw.to_string());
                self.tree.set(&path, "bandwidth-mbps", a.mbps.to_string());
                self.tree.set(&path, "lanes", g.lanes.to_string());
                let status = match a.state { AllocState::Suspended => "suspended", AllocState::Degraded => "degraded", AllocState::Full => "okay" };
                self.tree.set_status(&path, status);
                self.slots[i] = Some(m);
                self.emit(HalEvent::Reallocated { slot, uid, power_mw: a.power_mw, mbps: a.mbps, state: a.state });
                if a.state == AllocState::Suspended && !was_suspended {
                    self.emit(HalEvent::LoadShed { slot, uid });
                } else if was_suspended && a.state != AllocState::Suspended {
                    self.emit(HalEvent::Restored { slot, uid });
                }
            } else {
                self.slots[i] = Some(m);
            }
        }
    }

    /// Hot-plug a module into `slot`. Returns a report whether it was accepted or not.
    pub fn attach(&mut self, slot: u8, mut ep: Box<dyn ModuleEndpoint>) -> Result<AttachReport, HalError> {
        let i = slot as usize;
        if i >= self.slots.len() {
            return Err(HalError::InvalidSlot);
        }
        if self.slots[i].is_some() {
            return Err(HalError::SlotOccupied);
        }
        let t0 = self.clock_us;
        let mut report = AttachReport { slot, uid: None, class: None, accepted: false, reason: None, elapsed_us: 0, phases: vec![], grant: None };
        let timeout = self.cfg.response_timeout_us;
        let deadline = self.cfg.attach_deadline_us;

        macro_rules! phase {
            ($p:expr) => {
                report.phases.push(($p, self.clock_us - t0));
            };
        }
        macro_rules! reject {
            ($r:expr) => {{
                let reason = $r;
                let _ = exchange(&mut self.clock_us, &mut self.seq, timeout, ep.as_mut(), &Message::Reject { reason });
                report.reason = Some(reason);
                report.elapsed_us = self.clock_us - t0;
                self.emit(HalEvent::Rejected { slot, reason });
                return Ok(report);
            }};
        }
        macro_rules! xfer {
            ($m:expr) => {{
                let r = exchange(&mut self.clock_us, &mut self.seq, timeout, ep.as_mut(), &$m);
                if self.clock_us - t0 > deadline {
                    reject!(RejectReason::Timeout);
                }
                match r {
                    Xfer::Ok(m) => m,
                    Xfer::Timeout => reject!(RejectReason::Timeout),
                    Xfer::Corrupt => reject!(RejectReason::Protocol),
                }
            }};
        }

        phase!(Phase::Debounce);
        self.clock_us += self.cfg.debounce_us;
        phase!(Phase::Precharge);
        self.clock_us += self.cfg.precharge_us;
        phase!(Phase::LinkTraining);
        self.clock_us += self.cfg.link_training_us;

        phase!(Phase::Enumerate);
        let desc = match xfer!(Message::Enumerate) {
            Message::Hello(d) => d,
            _ => reject!(RejectReason::Protocol),
        };
        report.uid = Some(desc.uid);
        report.class = Some(desc.class);

        phase!(Phase::Authenticate);
        self.clock_us += self.cfg.sig_verify_us;
        match self.trust.verify_endorsement(&desc) {
            Ok(()) => {}
            Err(AuthError::Revoked) => reject!(RejectReason::Revoked),
            Err(_) => reject!(RejectReason::Unauthenticated),
        }
        let mut nonce = [0u8; 32];
        self.rng.fill_bytes(&mut nonce);
        let sig = match xfer!(Message::Challenge { nonce, slot }) {
            Message::Response { signature } => signature,
            _ => reject!(RejectReason::Protocol),
        };
        self.clock_us += self.cfg.sig_verify_us;
        if self.trust.verify_response(&desc, &nonce, slot, &sig).is_err() {
            reject!(RejectReason::Unauthenticated);
        }

        phase!(Phase::Negotiate);
        let req = match xfer!(Message::QueryRequirements) {
            Message::Requirements(r) => r,
            _ => reject!(RejectReason::Protocol),
        };
        if req.min_mw > req.nominal_mw || req.min_mbps > req.mbps {
            reject!(RejectReason::Protocol);
        }
        if req.min_mbps > self.slot_cap_mbps() {
            reject!(RejectReason::InsufficientBandwidth);
        }

        phase!(Phase::Allocate);
        let order = self.order_ctr;
        let candidate = ActiveModule {
            path: format!("/spine/dock@{slot}/{}@{:x}", desc.class.dt_name(), desc.uid),
            desc: desc.clone(),
            req,
            alloc: Allocation { power_mw: 0, mbps: 0, state: AllocState::Suspended, limited_by: None },
            endpoint: ep,
            order,
            missed: 0,
            tripped: false,
            draw_mw: 0,
            temp_dc: 250,
        };
        let mut demands = self.current_demands();
        demands.push(self.demand(slot, &candidate));
        let budget = self.budget_for(self.power_supply_mw() + desc.supply_mw);
        let trial = allocate(budget, self.cfg.backplane_mbps, &demands);
        let mine = trial[&slot];
        ep = candidate.endpoint;
        if mine.state == AllocState::Suspended {
            reject!(match mine.limited_by {
                Some(crate::allocator::Resource::Bandwidth) => RejectReason::InsufficientBandwidth,
                _ => RejectReason::InsufficientPower,
            });
        }

        phase!(Phase::Grant);
        let grant = self.grant_for(&mine, &req);
        match xfer!(Message::Grant(grant)) {
            Message::Ready => {}
            _ => reject!(RejectReason::Protocol),
        }

        self.order_ctr += 1;
        let path = format!("/spine/dock@{slot}/{}@{:x}", desc.class.dt_name(), desc.uid);
        let mut props = BTreeMap::new();
        props.insert("reg".into(), format!("{:#x}", desc.uid));
        props.insert("vendor-id".into(), format!("{:#06x}", desc.vendor_id));
        props.insert("fw-version".into(), format!("{:#010x}", desc.fw_version));
        props.insert("power-mw".into(), grant.power_mw.to_string());
        props.insert("bandwidth-mbps".into(), grant.mbps.to_string());
        props.insert("lanes".into(), grant.lanes.to_string());
        props.insert("rail-mv".into(), grant.rail_mv.to_string());
        if desc.supply_mw > 0 {
            props.insert("supply-mw".into(), desc.supply_mw.to_string());
            props.insert("capacity-mwh".into(), desc.capacity_mwh.to_string());
        }
        self.tree.insert(DtNode {
            path: path.clone(),
            compatible: desc.class.compatible().into(),
            slot,
            uid: desc.uid,
            status: if mine.state == AllocState::Full { "okay".into() } else { "degraded".into() },
            props,
        });
        self.slots[i] = Some(ActiveModule {
            desc: desc.clone(),
            req,
            alloc: mine,
            endpoint: ep,
            order,
            missed: 0,
            tripped: false,
            path,
            draw_mw: grant.power_mw,
            temp_dc: 250,
        });
        if desc.supply_mw > 0 {
            let b = self.power_budget_mw();
            self.emit(HalEvent::BudgetChanged { power_budget_mw: b });
        }
        self.emit(HalEvent::Attached { slot, uid: desc.uid, class: desc.class, grant });
        // Other modules may be shed (higher-priority newcomer) or upgraded (new battery).
        self.rebalance();

        report.accepted = true;
        report.grant = Some(grant);
        report.elapsed_us = self.clock_us - t0;
        Ok(report)
    }

    fn remove(&mut self, slot: u8, surprise: bool) -> Option<DetachReport> {
        let t0 = self.clock_us;
        let m = self.slots[slot as usize].take()?;
        self.tree.remove(&m.path);
        self.emit(HalEvent::Detached { slot, uid: m.desc.uid, surprise });
        if m.desc.supply_mw > 0 {
            let b = self.power_budget_mw();
            self.emit(HalEvent::BudgetChanged { power_budget_mw: b });
        }
        self.rebalance();
        Some(DetachReport { slot, uid: m.desc.uid, surprise, elapsed_us: self.clock_us - t0 })
    }

    /// Graceful removal: the user pressed the release latch.
    pub fn detach(&mut self, slot: u8) -> Result<DetachReport, HalError> {
        let i = slot as usize;
        let m = self.slots.get_mut(i).ok_or(HalError::InvalidSlot)?.as_mut().ok_or(HalError::SlotEmpty)?;
        let t0 = self.clock_us;
        let _ = exchange(&mut self.clock_us, &mut self.seq, self.cfg.response_timeout_us, m.endpoint.as_mut(), &Message::DetachRequest);
        let mut r = self.remove(slot, false).unwrap();
        r.elapsed_us = self.clock_us - t0;
        Ok(r)
    }

    /// DETECT pin dropped with no handshake (module yanked). The rail is clamped by
    /// hardware; the HAL only has to free resources and rebalance.
    pub fn surprise_remove(&mut self, slot: u8) -> Result<DetachReport, HalError> {
        if slot as usize >= self.slots.len() {
            return Err(HalError::InvalidSlot);
        }
        self.remove(slot, true).ok_or(HalError::SlotEmpty)
    }

    /// Change the base system load (SoC, display, radios) and rebalance module power.
    pub fn set_system_load(&mut self, mw: u32) {
        if mw != self.system_load_mw {
            self.system_load_mw = mw;
            let b = self.power_budget_mw();
            self.emit(HalEvent::BudgetChanged { power_budget_mw: b });
            self.rebalance();
        }
    }

    /// Clear an overcurrent latch so the module is eligible for power again.
    pub fn reset_trip(&mut self, slot: u8) {
        if let Some(Some(m)) = self.slots.get_mut(slot as usize) {
            if m.tripped {
                m.tripped = false;
                self.rebalance();
            }
        }
    }

    /// Advance virtual time, running heartbeats and overcurrent supervision.
    pub fn tick(&mut self, dt_us: u64) {
        let end = self.clock_us + dt_us;
        while self.next_heartbeat_us <= end {
            self.clock_us = self.clock_us.max(self.next_heartbeat_us);
            self.heartbeat_round();
            self.next_heartbeat_us += self.cfg.heartbeat_interval_us;
        }
        self.clock_us = self.clock_us.max(end);
    }

    fn heartbeat_round(&mut self) {
        self.hb_seq = self.hb_seq.wrapping_add(1);
        let hb = self.hb_seq;
        let start = self.clock_us;
        let mut lost = vec![];
        let mut trips = vec![];
        for i in 0..self.slots.len() {
            let Some(m) = self.slots[i].as_mut() else { continue };
            // heartbeats to different docks go out in parallel; don't serialise their latency
            let mut clk = start;
            match exchange(&mut clk, &mut self.seq, self.cfg.response_timeout_us, m.endpoint.as_mut(), &Message::Heartbeat { seq: hb }) {
                Xfer::Ok(Message::HeartbeatAck { seq, temp_dc, draw_mw }) if seq == hb => {
                    m.missed = 0;
                    m.draw_mw = draw_mw;
                    m.temp_dc = temp_dc;
                    let limit = (m.alloc.power_mw as f32 * self.cfg.overcurrent_ratio) as u32;
                    if !m.tripped && m.alloc.power_mw > 0 && draw_mw > limit {
                        m.tripped = true;
                        trips.push((i as u8, m.desc.uid, draw_mw, m.alloc.power_mw));
                    }
                }
                _ => {
                    m.missed += 1;
                    if m.missed >= self.cfg.heartbeat_miss_limit {
                        lost.push((i as u8, m.desc.uid));
                    }
                }
            }
        }
        for (slot, uid, draw_mw, granted_mw) in trips {
            self.emit(HalEvent::OvercurrentTrip { slot, uid, draw_mw, granted_mw });
        }
        if !self.events.is_empty() && self.events.iter().rev().take(6).any(|e| matches!(e.event, HalEvent::OvercurrentTrip { .. })) {
            self.rebalance();
        }
        for (slot, uid) in lost {
            self.emit(HalEvent::HeartbeatLost { slot, uid });
            self.remove(slot, true);
        }
    }

    pub fn allocation(&self, slot: u8) -> Option<Allocation> {
        self.slots.get(slot as usize)?.as_ref().map(|m| m.alloc)
    }

    pub fn snapshot(&self) -> HalSnapshot {
        let slots: Vec<Option<SlotSnapshot>> = self
            .slots
            .iter()
            .enumerate()
            .map(|(i, s)| {
                s.as_ref().map(|m| SlotSnapshot {
                    slot: i as u8,
                    uid: m.desc.uid,
                    class: m.desc.class,
                    priority: m.req.priority,
                    requested_mw: m.req.nominal_mw,
                    min_mw: m.req.min_mw,
                    requested_mbps: m.req.mbps,
                    alloc: m.alloc,
                    draw_mw: m.draw_mw,
                    supply_mw: m.desc.supply_mw,
                    capacity_mwh: m.desc.capacity_mwh,
                    temp_c: m.temp_dc as f32 / 10.0,
                    tripped: m.tripped,
                    path: m.path.clone(),
                })
            })
            .collect();
        HalSnapshot {
            clock_us: self.clock_us,
            power_supply_mw: self.power_supply_mw(),
            power_budget_mw: self.power_budget_mw(),
            power_allocated_mw: slots.iter().flatten().map(|s| s.alloc.power_mw).sum(),
            system_load_mw: self.system_load_mw,
            backplane_mbps: self.cfg.backplane_mbps,
            bandwidth_allocated_mbps: slots.iter().flatten().map(|s| s.alloc.mbps).sum(),
            slots,
            dt_generation: self.tree.generation,
        }
    }

    /// Invariants that must hold after any sequence of operations.
    pub fn check_invariants(&self) -> Result<(), String> {
        let s = self.snapshot();
        if s.power_allocated_mw > s.power_budget_mw {
            return Err(format!("power over-allocated: {} > {}", s.power_allocated_mw, s.power_budget_mw));
        }
        if s.bandwidth_allocated_mbps > s.backplane_mbps {
            return Err(format!("bandwidth over-allocated: {} > {}", s.bandwidth_allocated_mbps, s.backplane_mbps));
        }
        for m in s.slots.iter().flatten() {
            if m.alloc.state != AllocState::Suspended && m.alloc.power_mw < m.min_mw {
                return Err(format!("slot {} below minimum", m.slot));
            }
            if m.alloc.mbps > self.slot_cap_mbps() {
                return Err(format!("slot {} exceeds lane capacity", m.slot));
            }
            if self.tree.by_slot(m.slot).is_none() {
                return Err(format!("slot {} missing from device tree", m.slot));
            }
        }
        if self.tree.nodes.len() != s.slots.iter().flatten().count() {
            return Err("device tree has stale nodes".into());
        }
        Ok(())
    }
}
