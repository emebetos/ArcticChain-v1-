//! WASM entry point. Every method returns JSON so the dashboard stays a thin view over
//! the exact Rust code that the firmware tests exercise.

use arcticchain_compositor::eink::{Content, Region};
use arcticchain_compositor::imu::ImuSample;
use arcticchain_compositor::projection::ProjectorConfig;
use arcticchain_compositor::Compositor;
use arcticchain_hal::allocator::AllocState;
use arcticchain_hal::auth::Manufacturer;
use arcticchain_hal::harvest::{simulate_day, HarvestDaemon};
use arcticchain_hal::privacy::{PrivacyConfig, PrivacyController, Vec3};
use arcticchain_hal::sim::{Fault, SimModule, SimState};
use arcticchain_hal::tactile::{keyboard_layout, SurfaceConfig, TactileDriver, UiElement};
use arcticchain_hal::{Hal, HalConfig, ModuleClass};
use arcticchain_mesh::network::MeshNetwork;
use arcticchain_mesh::Phy;
use serde::Serialize;
use serde_json::json;
use std::cell::RefCell;
use std::rc::Rc;
use wasm_bindgen::prelude::*;

fn class_from(s: &str) -> Option<ModuleClass> {
    ModuleClass::ALL.into_iter().find(|c| c.dt_name() == s)
}

fn fault_from(s: &str) -> Fault {
    match s {
        "bad-signature" => Fault::BadSignature,
        "forged-endorsement" => Fault::ForgedEndorsement,
        "unresponsive" => Fault::Unresponsive,
        "corrupt" => Fault::CorruptFrames,
        "overdraw" => Fault::Overdraw(2),
        _ => Fault::None,
    }
}

fn to_json<T: Serialize>(v: &T) -> String {
    serde_json::to_string(v).unwrap_or_else(|e| format!("{{\"error\":\"{e}\"}}"))
}

#[wasm_bindgen]
pub struct Simulator {
    mfr: Manufacturer,
    hal: Hal,
    handles: Vec<Option<(Rc<RefCell<SimState>>, ModuleClass)>>,
    uid: u64,
    harvest: HarvestDaemon,
    tactile: TactileDriver,
    privacy: PrivacyController,
    mesh: MeshNetwork,
    compositor: Compositor,
    imu_t: u64,
}

impl Default for Simulator {
    fn default() -> Self {
        Self::new()
    }
}

#[wasm_bindgen]
impl Simulator {
    #[wasm_bindgen(constructor)]
    pub fn new() -> Simulator {
        let mfr = Manufacturer::from_seed([0x4D; 32]);
        let hal = Hal::new(HalConfig::default(), mfr.trust_root());
        let mut s = Simulator {
            mfr,
            hal,
            handles: vec![None; 6],
            uid: 0x1000,
            harvest: HarvestDaemon::default(),
            tactile: TactileDriver::new(SurfaceConfig::default()),
            privacy: PrivacyController::new(PrivacyConfig::default()),
            mesh: MeshNetwork::demo(7),
            compositor: Compositor::new(ProjectorConfig::default()),
            imu_t: 0,
        };
        s.hal.set_system_load(2500);
        s
    }

    fn sync_projector(&mut self) {
        let present = (0..6u8).any(|i| {
            matches!(&self.handles[i as usize], Some((_, ModuleClass::ProjectorEngine)))
                && self.hal.allocation(i).map(|a| a.state != AllocState::Suspended).unwrap_or(false)
        });
        self.compositor.set_projector_present(present);
    }

    // ---------------- spine / HAL ----------------
    pub fn attach(&mut self, slot: u8, class: &str, fault: &str) -> String {
        let Some(c) = class_from(class) else { return json!({"error": "unknown class"}).to_string() };
        self.uid += 1;
        let m = SimModule::new(&self.mfr, self.uid, c).with_fault(fault_from(fault));
        let h = m.handle();
        let out = match self.hal.attach(slot, m.boxed()) {
            Ok(r) => {
                if r.accepted {
                    self.handles[slot as usize] = Some((h, c));
                }
                to_json(&r)
            }
            Err(e) => json!({"error": format!("{e:?}")}).to_string(),
        };
        self.sync_projector();
        out
    }

    pub fn detach(&mut self, slot: u8, surprise: bool) -> String {
        let r = if surprise { self.hal.surprise_remove(slot) } else { self.hal.detach(slot) };
        self.handles[slot as usize] = None;
        self.sync_projector();
        match r {
            Ok(r) => to_json(&r),
            Err(e) => json!({"error": format!("{e:?}")}).to_string(),
        }
    }

    pub fn set_fault(&mut self, slot: u8, fault: &str) {
        if let Some((h, _)) = &self.handles[slot as usize] {
            h.borrow_mut().fault = fault_from(fault);
        }
    }

    pub fn reset_trip(&mut self, slot: u8) {
        self.hal.reset_trip(slot);
        self.sync_projector();
    }

    pub fn set_system_load(&mut self, mw: u32) {
        self.hal.set_system_load(mw);
        self.sync_projector();
    }

    pub fn tick_hal(&mut self, ms: u32) {
        self.hal.tick(ms as u64 * 1000);
        for i in 0..6 {
            if self.handles[i].is_some() && !self.hal.is_occupied(i as u8) {
                self.handles[i] = None;
            }
        }
        self.sync_projector();
    }

    pub fn hal_state(&self) -> String {
        json!({
            "snapshot": self.hal.snapshot(),
            "dts": self.hal.device_tree().to_dts(),
            "config": self.hal.config(),
        })
        .to_string()
    }

    pub fn drain_events(&mut self) -> String {
        to_json(&self.hal.drain_events())
    }

    // ---------------- power harvesting ----------------
    pub fn harvest_day(&mut self, ambient_c: f64, couples: u32, proof_mass_g: f64, capacity_mwh: f64, days: u32) -> String {
        let mut d = HarvestDaemon::default();
        d.teg.couples = couples;
        d.piezo.proof_mass_kg = proof_mass_g / 1000.0;
        d.cell.capacity_mwh = capacity_mwh;
        let (series, summary) = simulate_day(&mut d, ambient_c, days.clamp(1, 7));
        let pts: Vec<_> = series
            .iter()
            .step_by(5)
            .map(|r| json!({"t": r.t_s / 3600.0, "teg": r.teg_uw, "piezo": r.piezo_uw, "harvest": r.harvest_uw,
                            "use": r.consumption_uw, "budget": r.budget_uw, "soc": r.soc, "throttled": r.throttled.len(),
                            "running": r.running}))
            .collect();
        self.harvest = d;
        json!({"series": pts, "summary": summary, "tasks": self.harvest.tasks}).to_string()
    }

    // ---------------- programmable surface ----------------
    pub fn tactile_layout(&mut self, kind: &str, value: f32, pressed: bool) {
        let cfg = self.tactile.cfg.clone();
        let els = match kind {
            "keyboard" => {
                let mut k = keyboard_layout(&cfg);
                if pressed {
                    if let Some(UiElement::Key { pressed: p, .. }) = k.get_mut(14) {
                        *p = true;
                    }
                }
                k
            }
            "slider" => vec![
                UiElement::Slider { x: 6.0, y: 60.0, w: 54.0, h: 10.0, value },
                UiElement::Slider { x: 6.0, y: 90.0, w: 54.0, h: 10.0, value: 1.0 - value },
            ],
            "scroll" => (0..8).map(|i| UiElement::ScrollRidge { y: 10.0 + i as f32 * 16.0 + value * 16.0, x0: 4.0, x1: 62.0 }).collect(),
            "buttons" => vec![
                UiElement::Button { x: 6.0, y: 100.0, w: 24.0, h: 24.0, pressed },
                UiElement::Button { x: 36.0, y: 100.0, w: 24.0, h: 24.0, pressed: false },
                UiElement::Key { x: 10.0, y: 20.0, w: 46.0, h: 20.0, pressed: false },
            ],
            _ => vec![],
        };
        self.tactile.set_layout(&els);
    }

    pub fn tactile_step(&mut self, dt_ms: f32) -> String {
        to_json(&self.tactile.step(dt_ms))
    }

    pub fn privacy(&mut self, user_x: f32, user_z: f32, obs_x: f32, obs_z: f32, enabled: bool) -> String {
        let l = Vec3::new(user_x - 32.0, 0.0, user_z);
        let r = Vec3::new(user_x + 32.0, 0.0, user_z);
        to_json(&self.privacy.update(l, r, &[Vec3::new(obs_x, 0.0, obs_z)], enabled))
    }

    // ---------------- mesh ----------------
    pub fn mesh_state(&self) -> String {
        json!({"nodes": self.mesh.views(), "links": self.mesh.links(), "walls": self.mesh.walls, "summary": self.mesh.summary()}).to_string()
    }

    pub fn mesh_send(&mut self, src: usize, dst: usize, bytes: usize, lora: bool, mmwave: bool) -> String {
        let mut allow = vec![];
        if lora {
            allow.push(Phy::LoRa);
        }
        if mmwave {
            allow.push(Phy::MmWave);
        }
        let payload: Vec<u8> = (0..bytes).map(|i| (i * 31 % 251) as u8).collect();
        to_json(&self.mesh.send(src, dst, &payload, &allow))
    }

    pub fn mesh_toggle(&mut self, i: usize) {
        if let Some(n) = self.mesh.nodes.get_mut(i) {
            n.online = !n.online;
        }
        self.mesh.converge();
    }

    pub fn mesh_move(&mut self, i: usize, x: f64, y: f64) {
        if let Some(n) = self.mesh.nodes.get_mut(i) {
            n.x = x;
            n.y = y;
        }
        self.mesh.converge();
    }

    pub fn mesh_reset(&mut self) {
        self.mesh = MeshNetwork::demo(7);
    }

    // ---------------- compositor ----------------
    /// Feed `dt_ms` of IMU samples at 100 Hz.
    pub fn imu(&mut self, tilt_deg: f32, face_up: bool, jerk: f32, shake: f32, dt_ms: u32) -> String {
        let end = self.imu_t + dt_ms as u64;
        while self.imu_t < end {
            self.imu_t += 10;
            let mut s = ImuSample::at_rest(self.imu_t, tilt_deg, face_up);
            s.accel[2] += jerk;
            s.gyro[2] = if (self.imu_t / 10) % 2 == 0 { shake } else { -shake };
            self.compositor.on_imu(&s);
        }
        to_json(&self.compositor.frame())
    }

    pub fn obstruct(&mut self, on: bool) {
        self.compositor.on_beam_obstruction(on);
    }

    pub fn eink_submit(&mut self, content: &str) -> String {
        let c = match content {
            "scroll" => Content::Scroll,
            "typing" => Content::Typing,
            "image" => Content::Image,
            "map" => Content::Map,
            _ => Content::Text,
        };
        let r = Region { x: 0, y: 200, w: 1072, h: 400 };
        to_json(&self.compositor.submit(self.imu_t, c, r))
    }

    pub fn transitions(&self) -> String {
        to_json(&self.compositor.transitions)
    }

    pub fn projection(&mut self, lens_height_mm: f64, diagonal_in: f64, lumens: f64) -> String {
        let cfg = ProjectorConfig { lens_height_mm, diagonal_in, lumens, ..ProjectorConfig::default() };
        self.compositor.set_projector_config(cfg);
        to_json(self.compositor.projection())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn engine_smoke() {
        let mut s = Simulator::new();
        let r: serde_json::Value = serde_json::from_str(&s.attach(1, "projector", "none")).unwrap();
        assert_eq!(r["accepted"], true);
        let f: serde_json::Value = serde_json::from_str(&s.imu(1.0, true, 0.0, 0.0, 2500)).unwrap();
        assert_eq!(f["state"], "Projection");
        s.detach(1, true);
        let f: serde_json::Value = serde_json::from_str(&s.imu(1.0, true, 0.0, 0.0, 10)).unwrap();
        assert_eq!(f["state"], "EInk");
        let m: serde_json::Value = serde_json::from_str(&s.mesh_send(0, 7, 64, true, true)).unwrap();
        assert_eq!(m["delivered"], true);
        let h: serde_json::Value = serde_json::from_str(&s.harvest_day(22.0, 127, 5.0, 150.0, 1)).unwrap();
        assert!(h["series"].as_array().unwrap().len() > 200);
        s.tactile_layout("keyboard", 0.0, false);
        let t: serde_json::Value = serde_json::from_str(&s.tactile_step(5.0)).unwrap();
        assert!(t["zones"].as_array().unwrap().len() > 100);
    }
}
