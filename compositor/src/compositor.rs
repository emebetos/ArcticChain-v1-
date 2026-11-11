//! Display state machine.
//!
//! ```text
//!            flat+still for 1.5 s, face up            laser warm-up done
//!  EInk ───────────────────────────────────▶ Arming ─────────────────▶ Projection
//!   ▲  ▲                                       │                        │   ▲
//!   │  │ picked up / tilted > 12°              │ picked up              │IR │ beam clear
//!   │  └───────────────────────────────────────┘                        ▼   │
//!   │                                                              Interlocked
//!   └────────────── picked up / tilted (from Projection or Interlocked) ─┘
//!  face-down & still → RearPanel (notifications move to the rear mono E-Ink)
//! ```

use crate::eink::{Content, EinkScheduler, Panel, Region, UpdatePlan};
use crate::imu::{ImuSample, Pose, PoseConfig, PoseDetector};
use crate::projection::{ProjectionReport, ProjectorConfig};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum DisplayState {
    EInk,
    RearPanel,
    Arming,
    Projection,
    Interlocked,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Transition {
    pub t_ms: u64,
    pub from: DisplayState,
    pub to: DisplayState,
    pub cause: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CompositorFrame {
    pub t_ms: u64,
    pub state: DisplayState,
    pub pose: Pose,
    pub tilt_deg: f32,
    pub front_eink: bool,
    pub rear_eink: bool,
    pub laser_on: bool,
    pub ir_touch: bool,
    pub layout: String,
    pub logical_w: u32,
    pub logical_h: u32,
    pub power_mw: f32,
    pub front_ghost: u32,
}

pub struct Compositor {
    state: DisplayState,
    pose: PoseDetector,
    pub front: EinkScheduler,
    pub rear: EinkScheduler,
    pub projector: ProjectorConfig,
    projection: ProjectionReport,
    pub laser_warmup_ms: u64,
    arming_since: u64,
    beam_obstructed: bool,
    projector_present: bool,
    now: u64,
    last_tilt: f32,
    pub transitions: Vec<Transition>,
}

impl Compositor {
    pub fn new(projector: ProjectorConfig) -> Self {
        let projection = projector.analyze();
        Self {
            state: DisplayState::EInk,
            pose: PoseDetector::new(PoseConfig::default()),
            front: EinkScheduler::new(Panel::front_color()),
            rear: EinkScheduler::new(Panel::rear_mono()),
            projector,
            projection,
            laser_warmup_ms: 300,
            arming_since: 0,
            beam_obstructed: false,
            projector_present: true,
            now: 0,
            last_tilt: 0.0,
            transitions: vec![],
        }
    }

    pub fn state(&self) -> DisplayState { self.state }
    pub fn projection(&self) -> &ProjectionReport { &self.projection }

    pub fn set_projector_config(&mut self, cfg: ProjectorConfig) {
        self.projection = cfg.analyze();
        self.projector = cfg;
    }

    /// The projector is a hot-swap module; without it tabletop mode is unavailable.
    pub fn set_projector_present(&mut self, present: bool) {
        self.projector_present = present;
        if !present && matches!(self.state, DisplayState::Arming | DisplayState::Projection | DisplayState::Interlocked) {
            self.go(DisplayState::EInk, "projector module detached");
        }
    }

    fn go(&mut self, to: DisplayState, cause: &str) {
        if to != self.state {
            self.transitions.push(Transition { t_ms: self.now, from: self.state, to, cause: cause.into() });
            self.state = to;
        }
    }

    pub fn on_imu(&mut self, s: &ImuSample) -> DisplayState {
        self.now = s.t_ms;
        self.last_tilt = PoseDetector::tilt_deg(s);
        let pose = self.pose.update(s);
        use DisplayState::*;
        match (self.state, pose) {
            (EInk, Pose::FlatFaceUp) if self.projector_present => {
                self.arming_since = s.t_ms;
                self.go(Arming, "flat, still, face-up for dwell period");
            }
            (EInk, Pose::FlatFaceDown) => self.go(RearPanel, "face-down on surface"),
            (RearPanel, Pose::Handheld) => self.go(EInk, "picked up"),
            (Arming | Projection | Interlocked, Pose::Handheld) => self.go(EInk, "picked up / tilted"),
            (Arming, Pose::FlatFaceUp) if s.t_ms - self.arming_since >= self.laser_warmup_ms => {
                if self.beam_obstructed {
                    self.go(Interlocked, "IR depth: object in beam path");
                } else {
                    self.go(Projection, "laser warm-up complete");
                }
            }
            _ => {}
        }
        self.state
    }

    /// IR depth sensor reports something (a face, a hand held high) inside the laser's
    /// keep-out volume. Class-1 eye safety: laser off immediately.
    pub fn on_beam_obstruction(&mut self, obstructed: bool) {
        self.beam_obstructed = obstructed;
        match (self.state, obstructed) {
            (DisplayState::Projection, true) => self.go(DisplayState::Interlocked, "IR depth: object in beam path"),
            (DisplayState::Interlocked, false) => self.go(DisplayState::Projection, "beam path clear"),
            _ => {}
        }
    }

    /// Route a UI update to whichever surface is live.
    pub fn submit(&mut self, t_ms: u64, content: Content, region: Region) -> Option<UpdatePlan> {
        self.now = self.now.max(t_ms);
        match self.state {
            DisplayState::EInk => self.front.submit(t_ms, content, region),
            DisplayState::RearPanel => self.rear.submit(t_ms, content, Region { x: 0, y: 0, w: 600, h: 800 }),
            // projector renders at video rate; e-ink is left showing a static "projecting" card
            _ => None,
        }
    }

    pub fn frame(&self) -> CompositorFrame {
        use DisplayState::*;
        let (layout, w, h) = match self.state {
            EInk | Arming => ("phone-portrait", 1072, 1448),
            RearPanel => ("rear-glance", 600, 800),
            Projection | Interlocked => ("tabletop-20in-16:9", self.projector.panel_w, self.projector.panel_h),
        };
        let power = match self.state {
            EInk => 35.0,
            RearPanel => 12.0,
            Arming => 400.0,
            Projection => 2200.0,
            Interlocked => 300.0,
        };
        CompositorFrame {
            t_ms: self.now,
            state: self.state,
            pose: self.pose.pose(),
            tilt_deg: self.last_tilt,
            front_eink: matches!(self.state, EInk | Arming),
            rear_eink: self.state == RearPanel,
            laser_on: self.state == Projection,
            ir_touch: matches!(self.state, Projection | Interlocked),
            layout: layout.into(),
            logical_w: w,
            logical_h: h,
            power_mw: power,
            front_ghost: self.front.ghost_level(),
        }
    }
}
