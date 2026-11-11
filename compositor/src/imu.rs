use serde::{Deserialize, Serialize};

pub const G: f32 = 9.81;

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq)]
pub struct ImuSample {
    pub t_ms: u64,
    /// m/s^2 in device frame; +z points out of the front display.
    pub accel: [f32; 3],
    /// rad/s
    pub gyro: [f32; 3],
}

impl ImuSample {
    pub fn at_rest(t_ms: u64, tilt_deg: f32, face_up: bool) -> Self {
        let t = tilt_deg.to_radians();
        let z = if face_up { G * t.cos() } else { -G * t.cos() };
        Self { t_ms, accel: [0.0, G * t.sin(), z], gyro: [0.0; 3] }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum Pose {
    Handheld,
    FlatFaceUp,
    FlatFaceDown,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PoseConfig {
    pub enter_tilt_deg: f32,
    pub exit_tilt_deg: f32,
    pub still_gyro: f32,
    pub still_accel_dev: f32,
    pub pickup_accel_dev: f32,
    pub dwell_ms: u64,
}

impl Default for PoseConfig {
    fn default() -> Self {
        Self { enter_tilt_deg: 5.0, exit_tilt_deg: 12.0, still_gyro: 0.05, still_accel_dev: 0.3, pickup_accel_dev: 1.5, dwell_ms: 1500 }
    }
}

#[derive(Debug, Clone)]
pub struct PoseDetector {
    pub cfg: PoseConfig,
    pose: Pose,
    candidate_since: Option<(Pose, u64)>,
}

impl PoseDetector {
    pub fn new(cfg: PoseConfig) -> Self {
        Self { cfg, pose: Pose::Handheld, candidate_since: None }
    }

    pub fn pose(&self) -> Pose { self.pose }

    pub fn tilt_deg(s: &ImuSample) -> f32 {
        let [x, y, z] = s.accel;
        let n = (x * x + y * y + z * z).sqrt().max(1e-3);
        (z.abs() / n).clamp(-1.0, 1.0).acos().to_degrees()
    }

    pub fn update(&mut self, s: &ImuSample) -> Pose {
        let [x, y, z] = s.accel;
        let a = (x * x + y * y + z * z).sqrt();
        let dev = (a - G).abs();
        let w = s.gyro.iter().map(|g| g * g).sum::<f32>().sqrt();
        let tilt = Self::tilt_deg(s);
        let facing = if z >= 0.0 { Pose::FlatFaceUp } else { Pose::FlatFaceDown };

        if self.pose != Pose::Handheld {
            // fast exit: picked up or tipped past hysteresis band
            if dev > self.cfg.pickup_accel_dev || tilt > self.cfg.exit_tilt_deg || facing != self.pose {
                self.pose = Pose::Handheld;
                self.candidate_since = None;
            }
            return self.pose;
        }
        let still = w < self.cfg.still_gyro && dev < self.cfg.still_accel_dev;
        if still && tilt < self.cfg.enter_tilt_deg {
            match self.candidate_since {
                Some((p, t0)) if p == facing => {
                    if s.t_ms.saturating_sub(t0) >= self.cfg.dwell_ms {
                        self.pose = facing;
                        self.candidate_since = None;
                    }
                }
                _ => self.candidate_since = Some((facing, s.t_ms)),
            }
        } else {
            self.candidate_since = None;
        }
        self.pose
    }
}
