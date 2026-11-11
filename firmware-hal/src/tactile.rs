//! Programmable surface ("clay") driver.
//!
//! The display is backed by a grid of actuator zones. Fast, small displacements (key
//! clicks, detents, scroll ridges) use electro-active polymer (EAP) cells; slow, tall,
//! sustained shapes (key rims, slider channels) use microfluidic cavities fed by a
//! micro-pump with a finite volume budget. The driver turns UI elements into a target
//! height map, then slews each zone toward it at its actuator's physical rate.

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum Actuator {
    Idle,
    Eap,
    Microfluidic,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type")]
pub enum UiElement {
    Key { x: f32, y: f32, w: f32, h: f32, pressed: bool },
    Slider { x: f32, y: f32, w: f32, h: f32, value: f32 },
    ScrollRidge { y: f32, x0: f32, x1: f32 },
    Button { x: f32, y: f32, w: f32, h: f32, pressed: bool },
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SurfaceConfig {
    pub cols: usize,
    pub rows: usize,
    pub width_mm: f32,
    pub height_mm: f32,
    pub eap_max_um: f32,
    pub fluid_max_um: f32,
    pub eap_slew_um_per_ms: f32,
    pub fluid_slew_um_per_ms: f32,
    pub pump_budget_ul: f32,
    pub eap_full_scale_v: f32,
}

impl Default for SurfaceConfig {
    fn default() -> Self {
        Self {
            cols: 18,
            rows: 38,
            width_mm: 66.0,
            height_mm: 140.0,
            eap_max_um: 80.0,
            fluid_max_um: 400.0,
            eap_slew_um_per_ms: 40.0,
            fluid_slew_um_per_ms: 2.0,
            pump_budget_ul: 60.0,
            eap_full_scale_v: 1200.0,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct Zone {
    pub height_um: f32,
    pub target_um: f32,
    pub actuator: Actuator,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TactileFrame {
    pub cols: usize,
    pub rows: usize,
    pub zones: Vec<Zone>,
    pub fluid_volume_ul: f32,
    pub fluid_scale: f32,
    pub max_eap_v: f32,
    pub settled: bool,
}

pub struct TactileDriver {
    pub cfg: SurfaceConfig,
    zones: Vec<Zone>,
    fluid_scale: f32,
}

impl TactileDriver {
    pub fn new(cfg: SurfaceConfig) -> Self {
        let zones = vec![Zone { height_um: 0.0, target_um: 0.0, actuator: Actuator::Idle }; cfg.cols * cfg.rows];
        Self { cfg, zones, fluid_scale: 1.0 }
    }

    fn pitch(&self) -> (f32, f32) {
        (self.cfg.width_mm / self.cfg.cols as f32, self.cfg.height_mm / self.cfg.rows as f32)
    }

    fn zone_center(&self, c: usize, r: usize) -> (f32, f32) {
        let (px, py) = self.pitch();
        ((c as f32 + 0.5) * px, (r as f32 + 0.5) * py)
    }

    /// Set the UI layout; computes new per-zone targets (mm coordinates, origin top-left).
    pub fn set_layout(&mut self, elements: &[UiElement]) {
        let (px, py) = self.pitch();
        let mut tgt = vec![(0.0f32, Actuator::Idle); self.zones.len()];
        let put = |t: &mut Vec<(f32, Actuator)>, i: usize, h: f32, a: Actuator| {
            if h > t[i].0 {
                t[i] = (h, a);
            }
        };
        for r in 0..self.cfg.rows {
            for c in 0..self.cfg.cols {
                let (x, y) = self.zone_center(c, r);
                let i = r * self.cfg.cols + c;
                for e in elements {
                    match *e {
                        UiElement::Key { x: kx, y: ky, w, h, pressed } => {
                            if x >= kx && x <= kx + w && y >= ky && y <= ky + h {
                                let edge = x - kx < px || kx + w - x < px || y - ky < py || ky + h - y < py;
                                if edge {
                                    put(&mut tgt, i, 0.6 * self.cfg.fluid_max_um, Actuator::Microfluidic);
                                } else {
                                    let click = if pressed { 0.0 } else { self.cfg.eap_max_um };
                                    put(&mut tgt, i, click, Actuator::Eap);
                                }
                            }
                        }
                        UiElement::Slider { x: sx, y: sy, w, h, value } => {
                            if x >= sx && x <= sx + w && y >= sy && y <= sy + h {
                                let rail = y - sy < py || sy + h - y < py;
                                let thumb_x = sx + value.clamp(0.0, 1.0) * w;
                                if (x - thumb_x).abs() < px {
                                    put(&mut tgt, i, self.cfg.fluid_max_um, Actuator::Microfluidic);
                                } else if rail {
                                    put(&mut tgt, i, 0.4 * self.cfg.fluid_max_um, Actuator::Microfluidic);
                                }
                            }
                        }
                        UiElement::ScrollRidge { y: ry, x0, x1 } => {
                            if (y - ry).abs() < py / 2.0 && x >= x0 && x <= x1 {
                                put(&mut tgt, i, 0.75 * self.cfg.eap_max_um, Actuator::Eap);
                            }
                        }
                        UiElement::Button { x: bx, y: by, w, h, pressed } => {
                            if x >= bx && x <= bx + w && y >= by && y <= by + h {
                                let hgt = if pressed { 0.25 } else { 0.8 } * self.cfg.fluid_max_um;
                                put(&mut tgt, i, hgt, Actuator::Microfluidic);
                            }
                        }
                    }
                }
            }
        }
        // pump volume budget: scale fluid heights uniformly if the layout needs too much
        let area_mm2 = px * py;
        let vol: f32 = tgt.iter().filter(|t| t.1 == Actuator::Microfluidic).map(|t| t.0 / 1000.0 * area_mm2).sum();
        self.fluid_scale = if vol > self.cfg.pump_budget_ul { self.cfg.pump_budget_ul / vol } else { 1.0 };
        for (z, (h, a)) in self.zones.iter_mut().zip(tgt) {
            z.target_um = if a == Actuator::Microfluidic { h * self.fluid_scale } else { h };
            if a != Actuator::Idle {
                z.actuator = a;
            }
        }
    }

    /// Advance the physical model by `dt_ms`.
    pub fn step(&mut self, dt_ms: f32) -> TactileFrame {
        for z in &mut self.zones {
            let rate = match z.actuator {
                Actuator::Eap => self.cfg.eap_slew_um_per_ms,
                Actuator::Microfluidic => self.cfg.fluid_slew_um_per_ms,
                Actuator::Idle => f32::INFINITY,
            };
            let d = z.target_um - z.height_um;
            let maxd = rate * dt_ms;
            z.height_um += d.clamp(-maxd, maxd);
            if z.height_um <= 0.01 && z.target_um == 0.0 {
                z.height_um = 0.0;
                z.actuator = Actuator::Idle;
            }
        }
        self.frame()
    }

    pub fn frame(&self) -> TactileFrame {
        let (px, py) = self.pitch();
        let fluid: f32 = self.zones.iter().filter(|z| z.actuator == Actuator::Microfluidic).map(|z| z.height_um / 1000.0 * px * py).sum();
        let max_eap = self.zones.iter().filter(|z| z.actuator == Actuator::Eap).map(|z| z.height_um).fold(0.0, f32::max);
        TactileFrame {
            cols: self.cfg.cols,
            rows: self.cfg.rows,
            zones: self.zones.clone(),
            fluid_volume_ul: fluid,
            fluid_scale: self.fluid_scale,
            // dielectric-elastomer strain ~ V^2
            max_eap_v: self.cfg.eap_full_scale_v * (max_eap / self.cfg.eap_max_um).sqrt(),
            settled: self.zones.iter().all(|z| (z.height_um - z.target_um).abs() < 0.5),
        }
    }
}

/// QWERTY keyboard occupying the lower part of the surface.
pub fn keyboard_layout(cfg: &SurfaceConfig) -> Vec<UiElement> {
    let rows = [10usize, 9, 7];
    let kw = cfg.width_mm / 10.0;
    let kh = 9.0;
    let top = cfg.height_mm - 3.0 * kh - 12.0;
    let mut v = vec![];
    for (ri, &n) in rows.iter().enumerate() {
        let off = (cfg.width_mm - n as f32 * kw) / 2.0;
        for k in 0..n {
            v.push(UiElement::Key { x: off + k as f32 * kw, y: top + ri as f32 * kh, w: kw, h: kh, pressed: false });
        }
    }
    v.push(UiElement::Key { x: cfg.width_mm * 0.25, y: top + 3.0 * kh, w: cfg.width_mm * 0.5, h: kh, pressed: false });
    v
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn eap_settles_fast_fluid_slow() {
        let mut d = TactileDriver::new(SurfaceConfig::default());
        d.set_layout(&[UiElement::ScrollRidge { y: 30.0, x0: 0.0, x1: 66.0 }]);
        assert!(d.step(5.0).settled, "EAP ridge should settle in 5 ms");
        d.set_layout(&[UiElement::Button { x: 10.0, y: 10.0, w: 20.0, h: 10.0, pressed: false }]);
        assert!(!d.step(5.0).settled, "fluid button cannot rise 320 um in 5 ms");
        let mut f = d.step(5.0);
        for _ in 0..40 {
            f = d.step(5.0);
        }
        assert!(f.settled);
    }

    #[test]
    fn pump_budget_respected() {
        let cfg = SurfaceConfig { pump_budget_ul: 5.0, ..Default::default() };
        let mut d = TactileDriver::new(cfg.clone());
        d.set_layout(&keyboard_layout(&cfg));
        let mut f = d.step(1.0);
        for _ in 0..500 {
            f = d.step(1.0);
        }
        assert!(f.fluid_scale < 1.0);
        assert!(f.fluid_volume_ul <= cfg.pump_budget_ul * 1.01, "{}", f.fluid_volume_ul);
    }
}
