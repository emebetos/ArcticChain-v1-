//! Light-field privacy controller.
//!
//! The display is divided into regions, each under a steerable micro-lens / liquid-crystal
//! grating that shapes its exit cone. Given eye positions from the front IR eye tracker,
//! the controller aims every region's cone at the primary user's eyes and narrows it to
//! just cover both pupils; anyone outside the cone sees a dark panel.
//! Coordinates: mm, origin at display centre, +x right, +y up, +z out of the screen.

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize, Default)]
pub struct Vec3 {
    pub x: f32,
    pub y: f32,
    pub z: f32,
}

impl Vec3 {
    pub const fn new(x: f32, y: f32, z: f32) -> Self { Self { x, y, z } }
    fn sub(self, o: Vec3) -> Vec3 { Vec3::new(self.x - o.x, self.y - o.y, self.z - o.z) }
    fn add(self, o: Vec3) -> Vec3 { Vec3::new(self.x + o.x, self.y + o.y, self.z + o.z) }
    fn scale(self, k: f32) -> Vec3 { Vec3::new(self.x * k, self.y * k, self.z * k) }
    fn dot(self, o: Vec3) -> f32 { self.x * o.x + self.y * o.y + self.z * o.z }
    fn norm(self) -> f32 { self.dot(self).sqrt() }
    fn unit(self) -> Vec3 { self.scale(1.0 / self.norm().max(1e-6)) }
}

fn angle_deg(a: Vec3, b: Vec3) -> f32 {
    a.unit().dot(b.unit()).clamp(-1.0, 1.0).acos().to_degrees()
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PrivacyConfig {
    pub regions_x: usize,
    pub regions_y: usize,
    pub display_w_mm: f32,
    pub display_h_mm: f32,
    pub max_steer_deg: f32,
    pub min_half_angle_deg: f32,
    pub max_half_angle_deg: f32,
    pub margin_deg: f32,
    /// Exponential smoothing of tracked eye positions (0..1, higher = snappier).
    pub smoothing: f32,
}

impl Default for PrivacyConfig {
    fn default() -> Self {
        Self {
            regions_x: 6,
            regions_y: 12,
            display_w_mm: 66.0,
            display_h_mm: 140.0,
            max_steer_deg: 30.0,
            min_half_angle_deg: 4.0,
            max_half_angle_deg: 20.0,
            margin_deg: 1.5,
            smoothing: 0.6,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RegionSteer {
    pub cx: f32,
    pub cy: f32,
    pub yaw_deg: f32,
    pub pitch_deg: f32,
    pub half_angle_deg: f32,
    pub saturated: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PrivacyFrame {
    pub regions: Vec<RegionSteer>,
    /// Fraction of regions visible to the primary user (both eyes).
    pub primary_visibility: f32,
    /// Fraction of regions visible to each other observer.
    pub observer_visibility: Vec<f32>,
    pub enabled: bool,
}

pub struct PrivacyController {
    pub cfg: PrivacyConfig,
    filtered: Option<(Vec3, Vec3)>,
}

impl PrivacyController {
    pub fn new(cfg: PrivacyConfig) -> Self {
        Self { cfg, filtered: None }
    }

    fn region_center(&self, ix: usize, iy: usize) -> Vec3 {
        let w = self.cfg.display_w_mm / self.cfg.regions_x as f32;
        let h = self.cfg.display_h_mm / self.cfg.regions_y as f32;
        Vec3::new(-self.cfg.display_w_mm / 2.0 + (ix as f32 + 0.5) * w, self.cfg.display_h_mm / 2.0 - (iy as f32 + 0.5) * h, 0.0)
    }

    pub fn update(&mut self, left_eye: Vec3, right_eye: Vec3, observers: &[Vec3], enabled: bool) -> PrivacyFrame {
        let k = self.cfg.smoothing;
        let (l, r) = match self.filtered {
            Some((fl, fr)) => (fl.add(left_eye.sub(fl).scale(k)), fr.add(right_eye.sub(fr).scale(k))),
            None => (left_eye, right_eye),
        };
        self.filtered = Some((l, r));
        let mid = l.add(r).scale(0.5);
        let mut regions = vec![];
        let mut prim = 0;
        let mut obs = vec![0usize; observers.len()];
        for iy in 0..self.cfg.regions_y {
            for ix in 0..self.cfg.regions_x {
                let p = self.region_center(ix, iy);
                let (dir, half, saturated) = if enabled {
                    let v = mid.sub(p);
                    let mut yaw = v.x.atan2(v.z).to_degrees();
                    let mut pitch = v.y.atan2(v.z).to_degrees();
                    let sat = yaw.abs() > self.cfg.max_steer_deg || pitch.abs() > self.cfg.max_steer_deg;
                    yaw = yaw.clamp(-self.cfg.max_steer_deg, self.cfg.max_steer_deg);
                    pitch = pitch.clamp(-self.cfg.max_steer_deg, self.cfg.max_steer_deg);
                    let dir = Vec3::new(yaw.to_radians().tan(), pitch.to_radians().tan(), 1.0).unit();
                    let need = angle_deg(dir, l.sub(p)).max(angle_deg(dir, r.sub(p))) + self.cfg.margin_deg;
                    let half = need.clamp(self.cfg.min_half_angle_deg, self.cfg.max_half_angle_deg);
                    (dir, half, sat)
                } else {
                    (Vec3::new(0.0, 0.0, 1.0), 85.0, false)
                };
                let sees = |e: Vec3| e.z > 0.0 && angle_deg(dir, e.sub(p)) <= half;
                if sees(l) && sees(r) {
                    prim += 1;
                }
                for (j, o) in observers.iter().enumerate() {
                    if sees(*o) {
                        obs[j] += 1;
                    }
                }
                regions.push(RegionSteer {
                    cx: p.x,
                    cy: p.y,
                    yaw_deg: dir.x.atan2(dir.z).to_degrees(),
                    pitch_deg: dir.y.atan2(dir.z).to_degrees(),
                    half_angle_deg: half,
                    saturated,
                });
            }
        }
        let n = regions.len() as f32;
        PrivacyFrame {
            regions,
            primary_visibility: prim as f32 / n,
            observer_visibility: obs.into_iter().map(|c| c as f32 / n).collect(),
            enabled,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn eyes(x: f32, z: f32) -> (Vec3, Vec3) {
        (Vec3::new(x - 32.0, 0.0, z), Vec3::new(x + 32.0, 0.0, z))
    }

    #[test]
    fn primary_sees_everything_shoulder_surfer_sees_nothing() {
        let mut pc = PrivacyController::new(PrivacyConfig::default());
        let (l, r) = eyes(0.0, 350.0);
        let surfer = Vec3::new(350.0, 50.0, 400.0);
        let f = pc.update(l, r, &[surfer], true);
        assert!(f.primary_visibility > 0.99, "{}", f.primary_visibility);
        assert!(f.observer_visibility[0] < 0.01, "{}", f.observer_visibility[0]);
    }

    #[test]
    fn disabled_mode_is_wide_open() {
        let mut pc = PrivacyController::new(PrivacyConfig::default());
        let (l, r) = eyes(0.0, 350.0);
        let f = pc.update(l, r, &[Vec3::new(350.0, 50.0, 400.0)], false);
        assert!(f.observer_visibility[0] > 0.99);
    }

    #[test]
    fn steering_saturates_at_extreme_angles() {
        let mut pc = PrivacyController::new(PrivacyConfig::default());
        let (l, r) = eyes(600.0, 200.0);
        let f = pc.update(l, r, &[], true);
        assert!(f.regions.iter().all(|r| r.saturated));
        assert!(f.primary_visibility < 0.5);
    }
}
