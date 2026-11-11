//! Project Monolith display compositor.
//!
//! * [`imu`] – flat-surface / pickup / face-down detection with dwell + hysteresis.
//! * [`eink`] – waveform scheduler for the front colour and rear mono E-Ink panels.
//! * [`projection`] – ultra-short-throw keystone homography, brightness uniformity and
//!   IR touch mapping for the 20-inch tabletop workspace.
//! * [`compositor`] – the state machine that ties them together.

pub mod compositor;
pub mod eink;
pub mod imu;
pub mod projection;

pub use compositor::{Compositor, CompositorFrame, DisplayState};
