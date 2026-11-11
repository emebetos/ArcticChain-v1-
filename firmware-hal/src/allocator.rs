//! Priority-based power and bandwidth allocation for modules sharing the spine's power
//! rail and optical backplane.
//!
//! Two passes: every module (in priority order, then attach order) first receives its
//! minimum; modules whose minimum no longer fits are suspended (load shedding). Remaining
//! headroom is then handed out up to each module's nominal demand, again by priority.

use crate::module::Priority;
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Demand {
    pub key: u8,
    pub priority: Priority,
    pub order: u64,
    pub nominal_mw: u32,
    pub min_mw: u32,
    pub mbps: u32,
    pub min_mbps: u32,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum AllocState {
    Full,
    Degraded,
    Suspended,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct Allocation {
    pub power_mw: u32,
    pub mbps: u32,
    pub state: AllocState,
    /// Which resource caused suspension, if any.
    pub limited_by: Option<Resource>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum Resource {
    Power,
    Bandwidth,
}

pub fn allocate(power_budget_mw: u32, bw_budget_mbps: u32, demands: &[Demand]) -> BTreeMap<u8, Allocation> {
    let mut order: Vec<&Demand> = demands.iter().collect();
    order.sort_by(|a, b| b.priority.cmp(&a.priority).then(a.order.cmp(&b.order)));

    let mut p_left = power_budget_mw;
    let mut b_left = bw_budget_mbps;
    let mut out = BTreeMap::new();

    for d in &order {
        let limited_by = if d.min_mw > p_left {
            Some(Resource::Power)
        } else if d.min_mbps > b_left {
            Some(Resource::Bandwidth)
        } else {
            None
        };
        let a = if limited_by.is_none() {
            p_left -= d.min_mw;
            b_left -= d.min_mbps;
            Allocation { power_mw: d.min_mw, mbps: d.min_mbps, state: AllocState::Degraded, limited_by: None }
        } else {
            Allocation { power_mw: 0, mbps: 0, state: AllocState::Suspended, limited_by }
        };
        out.insert(d.key, a);
    }
    for d in &order {
        let a = out.get_mut(&d.key).unwrap();
        if a.state == AllocState::Suspended {
            continue;
        }
        let extra_p = (d.nominal_mw - d.min_mw).min(p_left);
        let extra_b = (d.mbps - d.min_mbps).min(b_left);
        p_left -= extra_p;
        b_left -= extra_b;
        a.power_mw += extra_p;
        a.mbps += extra_b;
        if a.power_mw == d.nominal_mw && a.mbps == d.mbps {
            a.state = AllocState::Full;
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    fn d(key: u8, priority: Priority, nominal: u32, min: u32) -> Demand {
        Demand { key, priority, order: key as u64, nominal_mw: nominal, min_mw: min, mbps: 10, min_mbps: 1 }
    }

    #[test]
    fn everyone_full_when_budget_allows() {
        let a = allocate(10_000, 100, &[d(0, Priority::Low, 1000, 500), d(1, Priority::High, 2000, 1000)]);
        assert!(a.values().all(|x| x.state == AllocState::Full));
    }

    #[test]
    fn low_priority_shed_first() {
        let a = allocate(1500, 100, &[d(0, Priority::Low, 1000, 600), d(1, Priority::High, 2000, 1000)]);
        assert_eq!(a[&1].state, AllocState::Degraded);
        assert_eq!(a[&1].power_mw, 1500);
        assert_eq!(a[&0].state, AllocState::Suspended);
        assert_eq!(a[&0].limited_by, Some(Resource::Power));
    }

    #[test]
    fn mins_guaranteed_before_extras() {
        let a = allocate(1700, 100, &[d(0, Priority::Low, 1000, 600), d(1, Priority::High, 2000, 1000)]);
        assert_eq!(a[&0].power_mw, 600);
        assert_eq!(a[&1].power_mw, 1100);
    }
}
