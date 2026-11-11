//! E-Ink waveform scheduling.
//!
//! Timings follow published figures for current colour (Kaleido 3 class) and mono
//! (Carta 1300 class) panels. "High refresh" here means the fast 1-bit A2/DU modes
//! (~8-12 fps) for scrolling and typing, with periodic full refreshes to clear ghosting.

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum Waveform {
    /// 1-bit, fastest, used for scrolling/animation.
    A2,
    /// Direct update to black/white, typing / pen.
    Du,
    /// 16-level greyscale, text and UI.
    Gc16,
    /// Full colour refresh with flash, images and ghost clearing.
    ColorFull,
}

impl Waveform {
    pub fn duration_ms(self) -> u32 {
        match self {
            Waveform::A2 => 90,
            Waveform::Du => 260,
            Waveform::Gc16 => 450,
            Waveform::ColorFull => 900,
        }
    }

    /// Ghosting contributed by one update (arbitrary units; full refresh clears).
    fn ghost(self) -> u32 {
        match self {
            Waveform::A2 => 3,
            Waveform::Du => 2,
            Waveform::Gc16 => 1,
            Waveform::ColorFull => 0,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum Content {
    Scroll,
    Typing,
    Text,
    Image,
    Map,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub struct Region {
    pub x: u32,
    pub y: u32,
    pub w: u32,
    pub h: u32,
}

impl Region {
    pub fn area(&self) -> u64 { self.w as u64 * self.h as u64 }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Panel {
    pub name: String,
    pub width: u32,
    pub height: u32,
    pub color: bool,
    /// Energy for a full-screen update (mJ).
    pub full_update_mj: f32,
}

impl Panel {
    pub fn front_color() -> Self {
        Self { name: "front-color-eink".into(), width: 1072, height: 1448, color: true, full_update_mj: 60.0 }
    }
    pub fn rear_mono() -> Self {
        Self { name: "rear-mono-eink".into(), width: 600, height: 800, color: false, full_update_mj: 20.0 }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UpdatePlan {
    pub panel: String,
    pub waveform: Waveform,
    pub region: Region,
    pub duration_ms: u32,
    pub energy_mj: f32,
    pub ghost_level: u32,
    pub forced_clear: bool,
}

#[derive(Debug, Clone)]
pub struct EinkScheduler {
    pub panel: Panel,
    pub ghost_limit: u32,
    ghost: u32,
    busy_until_ms: u64,
}

impl EinkScheduler {
    pub fn new(panel: Panel) -> Self {
        Self { panel, ghost_limit: 24, ghost: 0, busy_until_ms: 0 }
    }

    pub fn ghost_level(&self) -> u32 { self.ghost }

    pub fn choose(&self, content: Content) -> Waveform {
        match content {
            Content::Scroll => Waveform::A2,
            Content::Typing => Waveform::Du,
            Content::Text | Content::Map => Waveform::Gc16,
            Content::Image => if self.panel.color { Waveform::ColorFull } else { Waveform::Gc16 },
        }
    }

    /// Plan an update. Returns None if the panel is still busy with a previous waveform
    /// (callers coalesce dirty regions and retry).
    pub fn submit(&mut self, now_ms: u64, content: Content, region: Region) -> Option<UpdatePlan> {
        if now_ms < self.busy_until_ms {
            return None;
        }
        let mut wf = self.choose(content);
        let mut region = region;
        let mut forced = false;
        if self.ghost + wf.ghost() > self.ghost_limit && !matches!(content, Content::Scroll) {
            wf = if self.panel.color { Waveform::ColorFull } else { Waveform::Gc16 };
            region = Region { x: 0, y: 0, w: self.panel.width, h: self.panel.height };
            forced = true;
        }
        let full = region.w >= self.panel.width && region.h >= self.panel.height;
        if wf == Waveform::ColorFull || (wf == Waveform::Gc16 && full) {
            self.ghost = 0;
        } else {
            self.ghost += wf.ghost();
        }
        let frac = region.area() as f32 / (self.panel.width as u64 * self.panel.height as u64) as f32;
        let scale = match wf {
            Waveform::A2 => 0.3,
            Waveform::Du => 0.5,
            Waveform::Gc16 => 1.0,
            Waveform::ColorFull => 1.6,
        };
        let d = wf.duration_ms();
        self.busy_until_ms = now_ms + d as u64;
        Some(UpdatePlan {
            panel: self.panel.name.clone(),
            waveform: wf,
            region,
            duration_ms: d,
            energy_mj: self.panel.full_update_mj * frac.max(0.05) * scale,
            ghost_level: self.ghost,
            forced_clear: forced,
        })
    }
}
