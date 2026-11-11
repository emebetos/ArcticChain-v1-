//! Hardware-in-the-loop style tests: real OBP frames, real Ed25519 auth, simulated modules.

use arcticchain_hal::allocator::AllocState;
use arcticchain_hal::auth::Manufacturer;
use arcticchain_hal::hotplug::{Hal, HalConfig, HalEvent};
use arcticchain_hal::protocol::RejectReason;
use arcticchain_hal::sim::{Fault, SimModule};
use arcticchain_hal::ModuleClass::{self, *};
use rand_chacha::ChaCha8Rng;
use rand_core::{RngCore, SeedableRng};
use std::time::Instant;

const DEADLINE_US: u64 = 50_000;

fn setup() -> (Manufacturer, Hal) {
    let mfr = Manufacturer::from_seed([0x11; 32]);
    let hal = Hal::new(HalConfig::default(), mfr.trust_root());
    (mfr, hal)
}

fn plug(hal: &mut Hal, mfr: &Manufacturer, slot: u8, uid: u64, class: ModuleClass) -> arcticchain_hal::AttachReport {
    let r = hal.attach(slot, SimModule::new(mfr, uid, class).boxed()).unwrap();
    hal.check_invariants().unwrap();
    r
}

#[test]
fn single_module_attaches_under_50ms() {
    let (mfr, mut hal) = setup();
    let wall = Instant::now();
    let r = plug(&mut hal, &mfr, 0, 1, CameraSensor);
    assert!(r.accepted, "{r:?}");
    assert!(r.elapsed_us < DEADLINE_US, "attach took {} us", r.elapsed_us);
    assert!(wall.elapsed().as_millis() < 50, "host-side negotiation too slow");
    let g = r.grant.unwrap();
    assert_eq!((g.power_mw, g.mbps, g.lanes), (1200, 12_000, 2));
    assert!(hal.device_tree().to_dts().contains("arcticchain,camera-tri-v1"));
}

#[test]
fn full_complement_each_under_deadline() {
    let (mfr, mut hal) = setup();
    let classes = [CameraSensor, ProjectorEngine, NeuromorphicCore, SatelliteTransceiver, BatteryBlock, BatteryBlock];
    let mut gen = hal.device_tree().generation;
    for (slot, c) in classes.into_iter().enumerate() {
        let r = plug(&mut hal, &mfr, slot as u8, 100 + slot as u64, c);
        assert!(r.accepted, "{c:?}: {r:?}");
        assert!(r.elapsed_us < DEADLINE_US, "{c:?} took {} us", r.elapsed_us);
        assert!(hal.device_tree().generation > gen);
        gen = hal.device_tree().generation;
    }
    assert_eq!(hal.device_tree().nodes.len(), 6);
    let s = hal.snapshot();
    assert_eq!(s.power_supply_mw, 6000 + 2 * 4000);
}

#[test]
fn occupied_and_invalid_slots_error() {
    let (mfr, mut hal) = setup();
    plug(&mut hal, &mfr, 0, 1, MeshRadio);
    assert!(hal.attach(0, SimModule::new(&mfr, 2, MeshRadio).boxed()).is_err());
    assert!(hal.attach(9, SimModule::new(&mfr, 3, MeshRadio).boxed()).is_err());
    assert!(hal.detach(1).is_err());
}

#[test]
fn forged_cloned_and_revoked_modules_rejected() {
    let (mfr, mut hal) = setup();
    let cases = [
        (Fault::ForgedEndorsement, RejectReason::Unauthenticated),
        (Fault::BadSignature, RejectReason::Unauthenticated),
        (Fault::CorruptFrames, RejectReason::Protocol),
        (Fault::Unresponsive, RejectReason::Timeout),
    ];
    for (i, (fault, want)) in cases.into_iter().enumerate() {
        let r = hal.attach(0, SimModule::new(&mfr, 50 + i as u64, CameraSensor).with_fault(fault).boxed()).unwrap();
        assert!(!r.accepted);
        assert_eq!(r.reason, Some(want), "{fault:?}");
        assert!(!hal.is_occupied(0));
    }
    hal.trust_mut().revoke(77);
    let r = hal.attach(0, SimModule::new(&mfr, 77, CameraSensor).boxed()).unwrap();
    assert_eq!(r.reason, Some(RejectReason::Revoked));
    assert_eq!(hal.device_tree().nodes.len(), 0);
    hal.check_invariants().unwrap();
}

#[test]
fn slow_optical_link_misses_deadline() {
    let mfr = Manufacturer::from_seed([0x11; 32]);
    let cfg = HalConfig { response_timeout_us: 15_000, ..HalConfig::default() };
    let mut hal = Hal::new(cfg, mfr.trust_root());
    // every round trip is within the per-message timeout, but the sum blows the 50 ms budget
    let r = hal.attach(2, SimModule::new(&mfr, 9, NeuromorphicCore).with_latency(12_000).boxed()).unwrap();
    assert!(!r.accepted);
    assert_eq!(r.reason, Some(RejectReason::Timeout));
    assert!(r.elapsed_us > DEADLINE_US);
    assert!(!hal.is_occupied(2));
}

#[test]
fn battery_hot_swap_under_load_sheds_and_restores_projector() {
    let (mfr, mut hal) = setup();
    hal.set_system_load(3_000); // SoC + display + radios
    plug(&mut hal, &mfr, 4, 10, BatteryBlock);
    plug(&mut hal, &mfr, 2, 11, NeuromorphicCore);
    plug(&mut hal, &mfr, 0, 12, CameraSensor);
    let r = plug(&mut hal, &mfr, 1, 13, ProjectorEngine);
    assert!(r.accepted);
    assert_eq!(hal.allocation(1).unwrap().state, AllocState::Full);

    // yank the battery while everything is running
    hal.drain_events();
    let d = hal.surprise_remove(4).unwrap();
    hal.check_invariants().unwrap();
    assert!(d.elapsed_us < DEADLINE_US);
    let ev = hal.drain_events();
    assert!(ev.iter().any(|e| e.event == HalEvent::LoadShed { slot: 1, uid: 13 }), "{ev:#?}");
    assert_ne!(hal.allocation(2).unwrap().state, AllocState::Suspended, "NPU (high priority) must survive");
    assert_eq!(hal.allocation(1).unwrap().state, AllocState::Suspended);

    // hot-swap a fresh battery into another dock: projector comes back without a reboot
    let r = plug(&mut hal, &mfr, 5, 14, BatteryBlock);
    assert!(r.accepted && r.elapsed_us < DEADLINE_US);
    let ev = hal.drain_events();
    assert!(ev.iter().any(|e| e.event == HalEvent::Restored { slot: 1, uid: 13 }), "{ev:#?}");
    assert_eq!(hal.allocation(1).unwrap().state, AllocState::Full);
}

#[test]
fn newcomer_rejected_when_power_exhausted() {
    let (mfr, mut hal) = setup();
    hal.set_system_load(4_000);
    plug(&mut hal, &mfr, 0, 1, NeuromorphicCore); // budget 1600: npu takes 1500 (min 300)
    let r = plug(&mut hal, &mfr, 1, 2, ProjectorEngine); // min 1800 > 1600 - 300
    assert!(!r.accepted);
    assert_eq!(r.reason, Some(RejectReason::InsufficientPower));
    assert_eq!(hal.allocation(0).unwrap().state, AllocState::Full);
}

#[test]
fn bandwidth_contention_and_graceful_detach() {
    let (mfr, mut hal) = setup();
    plug(&mut hal, &mfr, 4, 1, BatteryBlock);
    plug(&mut hal, &mfr, 2, 2, NeuromorphicCore);
    plug(&mut hal, &mfr, 3, 3, NeuromorphicCore);
    plug(&mut hal, &mfr, 0, 4, CameraSensor);
    let cam = hal.allocation(0).unwrap();
    assert_eq!(cam.state, AllocState::Degraded);
    assert_eq!(cam.mbps, 8_000);
    let d = hal.detach(3).unwrap();
    assert!(!d.surprise && d.elapsed_us < DEADLINE_US);
    hal.check_invariants().unwrap();
    assert_eq!(hal.allocation(0).unwrap().state, AllocState::Full);
}

#[test]
fn heartbeat_loss_triggers_surprise_removal() {
    let (mfr, mut hal) = setup();
    let m = SimModule::new(&mfr, 5, SatelliteTransceiver);
    let h = m.handle();
    hal.attach(3, m.boxed()).unwrap();
    hal.tick(25_000);
    assert!(h.borrow().heartbeats >= 2);
    assert!(hal.is_occupied(3));
    h.borrow_mut().fault = Fault::Unresponsive;
    let t_fail = hal.clock_us();
    hal.tick(60_000);
    assert!(!hal.is_occupied(3));
    let lost = hal.events().iter().find(|e| matches!(e.event, HalEvent::HeartbeatLost { slot: 3, .. })).unwrap();
    assert!(lost.t_us - t_fail <= 3 * 10_000 + 10_000, "detected after {} us", lost.t_us - t_fail);
    hal.check_invariants().unwrap();
}

#[test]
fn overcurrent_trips_module_off_rail() {
    let (mfr, mut hal) = setup();
    let m = SimModule::new(&mfr, 6, CameraSensor);
    let h = m.handle();
    hal.attach(0, m.boxed()).unwrap();
    h.borrow_mut().fault = Fault::Overdraw(2);
    hal.tick(10_000);
    assert!(hal.events().iter().any(|e| matches!(e.event, HalEvent::OvercurrentTrip { slot: 0, .. })));
    assert_eq!(hal.allocation(0).unwrap().state, AllocState::Suspended);
    assert_eq!(h.borrow().grant.unwrap().power_mw, 0);
    h.borrow_mut().fault = Fault::None;
    hal.reset_trip(0);
    assert_eq!(hal.allocation(0).unwrap().state, AllocState::Full);
}

#[test]
fn randomized_hot_swap_soak_preserves_invariants() {
    let (mfr, mut hal) = setup();
    let mut rng = ChaCha8Rng::seed_from_u64(42);
    let mut uid = 1000u64;
    let mut worst = 0u64;
    for step in 0..2_000 {
        let slot = (rng.next_u32() % 6) as u8;
        match rng.next_u32() % 10 {
            0..=4 if !hal.is_occupied(slot) => {
                uid += 1;
                let class = ModuleClass::ALL[(rng.next_u32() % 6) as usize];
                let r = hal.attach(slot, SimModule::new(&mfr, uid, class).boxed()).unwrap();
                if r.accepted {
                    worst = worst.max(r.elapsed_us);
                }
            }
            5..=6 if hal.is_occupied(slot) => {
                hal.detach(slot).unwrap();
            }
            7 if hal.is_occupied(slot) => {
                hal.surprise_remove(slot).unwrap();
            }
            8 => hal.set_system_load(rng.next_u32() % 9_000),
            _ => hal.tick((rng.next_u32() % 20_000) as u64),
        }
        hal.check_invariants().unwrap_or_else(|e| panic!("step {step}: {e}"));
    }
    assert!(worst < DEADLINE_US, "worst accepted attach {worst} us");
}
