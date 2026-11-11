use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, PartialOrd, Ord, Serialize, Deserialize)]
#[repr(u8)]
pub enum ModuleClass {
    BatteryBlock = 1,
    NeuromorphicCore = 2,
    CameraSensor = 3,
    SatelliteTransceiver = 4,
    ProjectorEngine = 5,
    MeshRadio = 6,
}

impl ModuleClass {
    pub const ALL: [ModuleClass; 6] = [
        ModuleClass::BatteryBlock,
        ModuleClass::NeuromorphicCore,
        ModuleClass::CameraSensor,
        ModuleClass::SatelliteTransceiver,
        ModuleClass::ProjectorEngine,
        ModuleClass::MeshRadio,
    ];

    pub fn from_u8(v: u8) -> Option<Self> {
        Self::ALL.into_iter().find(|c| *c as u8 == v)
    }

    /// Device-tree node name.
    pub fn dt_name(self) -> &'static str {
        match self {
            ModuleClass::BatteryBlock => "battery",
            ModuleClass::NeuromorphicCore => "npu",
            ModuleClass::CameraSensor => "camera",
            ModuleClass::SatelliteTransceiver => "satcom",
            ModuleClass::ProjectorEngine => "projector",
            ModuleClass::MeshRadio => "mesh-radio",
        }
    }

    pub fn compatible(self) -> &'static str {
        match self {
            ModuleClass::BatteryBlock => "arcticchain,ss-battery-v1",
            ModuleClass::NeuromorphicCore => "arcticchain,npu-snn-v1",
            ModuleClass::CameraSensor => "arcticchain,camera-tri-v1",
            ModuleClass::SatelliteTransceiver => "arcticchain,satcom-ntn-v1",
            ModuleClass::ProjectorEngine => "arcticchain,laser-mems-v1",
            ModuleClass::MeshRadio => "arcticchain,lora-mmwave-v1",
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]
#[repr(u8)]
pub enum Priority {
    Low = 0,
    Normal = 1,
    High = 2,
    Critical = 3,
}

impl Priority {
    pub fn from_u8(v: u8) -> Option<Self> {
        match v {
            0 => Some(Priority::Low),
            1 => Some(Priority::Normal),
            2 => Some(Priority::High),
            3 => Some(Priority::Critical),
            _ => None,
        }
    }
}

/// Identity block a module reports in its `Hello` frame.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ModuleDescriptor {
    pub uid: u64,
    pub class: ModuleClass,
    pub vendor_id: u16,
    pub fw_version: u32,
    /// Power the module can *source* onto the shared rail (battery blocks), in mW.
    pub supply_mw: u32,
    pub capacity_mwh: u32,
    pub public_key: [u8; 32],
    /// Manufacturer signature over (uid, class, public_key).
    pub endorsement: [u8; 64],
}
