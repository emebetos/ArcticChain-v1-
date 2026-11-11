//! Project Monolith hardware abstraction layer.
//!
//! * [`hotplug`] – plug-and-play manager for the magnetic-mechanical optical bus ("Lego spine").
//! * [`protocol`] – Optical Bus Protocol (OBP) wire format.
//! * [`auth`] – module endorsement + challenge/response authentication.
//! * [`allocator`] – priority-based power and bandwidth allocation.
//! * [`device_tree`] – dynamic device tree updated on every hot-swap.
//! * [`harvest`] – "zero-charge" thermoelectric/kinetic energy-harvesting daemon.
//! * [`tactile`] – programmable surface ("clay") actuator driver.
//! * [`privacy`] – light-field privacy controller.
//! * [`sim`] – simulated modules for hardware-in-the-loop testing.

pub mod allocator;
pub mod auth;
pub mod crc;
pub mod device_tree;
pub mod harvest;
pub mod hotplug;
pub mod module;
pub mod privacy;
pub mod protocol;
pub mod sim;
pub mod tactile;

pub use hotplug::{AttachReport, Hal, HalConfig, HalError, HalEvent, ModuleEndpoint, Reply};
pub use module::{ModuleClass, ModuleDescriptor, Priority};
