//! "Zero-charge" energy-harvesting daemon.
//!
//! Models a thermoelectric generator (skin-to-ambient gradient) and a resonant
//! piezoelectric kinetic harvester feeding a solid-state buffer cell, plus a predictive
//! scheduler that keeps neuromorphic-NPU and background workloads energy-neutral.
//!
//! Parameters are deliberately realistic: expect tens to hundreds of microwatts. That is
//! enough for always-on sensing / NPU wake-word style workloads, not for a phone's
//! display + radios (several Wh per day). See `docs/feasibility.md`.

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TegParams {
    pub couples: u32,
    /// Seebeck coefficient per p-n couple (V/K).
    pub seebeck_v_per_k: f64,
    pub r_internal_ohm: f64,
    /// Fraction of the skin-ambient difference that appears across the TEG legs.
    pub thermal_coupling: f64,
    pub converter_eff: f64,
    /// Boost converter cold-start threshold (V).
    pub cold_start_v: f64,
}

impl Default for TegParams {
    fn default() -> Self {
        Self { couples: 127, seebeck_v_per_k: 400e-6, r_internal_ohm: 2.5, thermal_coupling: 0.12, converter_eff: 0.55, cold_start_v: 0.02 }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PiezoParams {
    pub proof_mass_kg: f64,
    pub resonant_hz: f64,
    /// Electromechanical coupling x mechanical efficiency.
    pub coupling_eff: f64,
    pub converter_eff: f64,
}

impl Default for PiezoParams {
    fn default() -> Self {
        Self { proof_mass_kg: 0.005, resonant_hz: 2.0, coupling_eff: 0.02, converter_eff: 0.7 }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BufferCell {
    pub capacity_mwh: f64,
    pub soc: f64,
    pub charge_eff: f64,
    pub leakage_uw: f64,
}

impl Default for BufferCell {
    fn default() -> Self {
        Self { capacity_mwh: 150.0, soc: 0.5, charge_eff: 0.95, leakage_uw: 2.0 }
    }
}

impl BufferCell {
    /// Apply net power (µW, positive = charging) for `dt_s`. Returns energy actually moved (µWh).
    pub fn apply(&mut self, net_uw: f64, dt_s: f64) -> f64 {
        let cap_uwh = self.capacity_mwh * 1000.0;
        let mut e_uwh = (net_uw - self.leakage_uw) * dt_s / 3600.0;
        if e_uwh > 0.0 {
            e_uwh *= self.charge_eff;
        }
        let before = self.soc;
        self.soc = (self.soc + e_uwh / cap_uwh).clamp(0.0, 1.0);
        (self.soc - before) * cap_uwh
    }
}

pub fn teg_power_uw(p: &TegParams, skin_c: f64, ambient_c: f64, on_body: bool) -> f64 {
    if !on_body {
        return 0.0;
    }
    let dt = (skin_c - ambient_c).max(0.0) * p.thermal_coupling;
    let v_oc = p.couples as f64 * p.seebeck_v_per_k * dt;
    if v_oc < p.cold_start_v {
        return 0.0;
    }
    // matched load
    v_oc * v_oc / (4.0 * p.r_internal_ohm) * p.converter_eff * 1e6
}

pub fn piezo_power_uw(p: &PiezoParams, accel_rms: f64, excitation_hz: f64) -> f64 {
    if accel_rms <= 0.0 || excitation_hz <= 0.0 {
        return 0.0;
    }
    // detuning penalty (Lorentzian, Q ~ 4 for a broadband harvester)
    let r = excitation_hz / p.resonant_hz;
    let q = 4.0;
    let tune = 1.0 / (1.0 + q * q * (r - 1.0 / r).powi(2));
    let w = 2.0 * std::f64::consts::PI * excitation_hz;
    0.5 * p.proof_mass_kg * accel_rms * accel_rms / w * p.coupling_eff * tune * p.converter_eff * 1e6
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
pub enum TaskClass {
    Critical,
    Interactive,
    Background,
    Deferrable,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Task {
    pub name: String,
    pub class: TaskClass,
    pub power_uw: f64,
    /// Runs on the neuromorphic NPU (event-driven: cost scales with input activity).
    pub npu: bool,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub struct Environment {
    pub skin_c: f64,
    pub ambient_c: f64,
    pub on_body: bool,
    pub accel_rms: f64,
    pub step_hz: f64,
    /// 0..1 sensor activity driving spiking-NPU cost.
    pub activity: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Forecaster {
    pub alpha: f64,
    pub ewma_uw: f64,
    /// Learned harvest per hour-of-day (µW).
    pub hourly: Vec<f64>,
}

impl Default for Forecaster {
    fn default() -> Self {
        Self { alpha: 0.05, ewma_uw: 0.0, hourly: vec![0.0; 24] }
    }
}

impl Forecaster {
    pub fn observe(&mut self, t_s: f64, uw: f64) {
        self.ewma_uw += self.alpha * (uw - self.ewma_uw);
        let h = ((t_s / 3600.0) as usize) % 24;
        self.hourly[h] += 0.02 * (uw - self.hourly[h]);
    }

    /// Mean expected harvest over the next `horizon_h` hours.
    pub fn forecast(&self, t_s: f64, horizon_h: usize) -> f64 {
        let h0 = (t_s / 3600.0) as usize;
        let learned: f64 = (0..horizon_h).map(|k| self.hourly[(h0 + k) % 24]).sum::<f64>() / horizon_h as f64;
        0.5 * self.ewma_uw + 0.5 * learned
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TickReport {
    pub t_s: f64,
    pub teg_uw: f64,
    pub piezo_uw: f64,
    pub harvest_uw: f64,
    pub forecast_uw: f64,
    pub budget_uw: f64,
    pub consumption_uw: f64,
    pub soc: f64,
    pub running: Vec<String>,
    pub throttled: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HarvestDaemon {
    pub teg: TegParams,
    pub piezo: PiezoParams,
    pub cell: BufferCell,
    pub tasks: Vec<Task>,
    pub reserve_soc: f64,
    pub horizon_h: usize,
    pub forecaster: Forecaster,
    pub t_s: f64,
}

pub fn default_tasks() -> Vec<Task> {
    let t = |name: &str, class, power_uw, npu| Task { name: name.into(), class, power_uw, npu };
    vec![
        t("rtc+pmic", TaskClass::Critical, 8.0, false),
        t("mesh-beacon (LoRa RX duty 0.1%)", TaskClass::Critical, 25.0, false),
        t("npu wake-word", TaskClass::Interactive, 60.0, true),
        t("npu gesture/IMU", TaskClass::Interactive, 40.0, true),
        t("e-ink partial refresh", TaskClass::Interactive, 90.0, false),
        t("mesh store-and-forward", TaskClass::Background, 120.0, false),
        t("npu photo indexing", TaskClass::Deferrable, 400.0, true),
        t("encrypted backup sync (mmWave)", TaskClass::Deferrable, 900.0, false),
    ]
}

impl Default for HarvestDaemon {
    fn default() -> Self {
        Self {
            teg: TegParams::default(),
            piezo: PiezoParams::default(),
            cell: BufferCell::default(),
            tasks: default_tasks(),
            reserve_soc: 0.15,
            horizon_h: 6,
            forecaster: Forecaster::default(),
            t_s: 0.0,
        }
    }
}

impl HarvestDaemon {
    fn task_cost(t: &Task, env: &Environment) -> f64 {
        if t.npu {
            // spiking NPU: static leakage + activity-proportional dynamic power
            t.power_uw * (0.15 + 0.85 * env.activity.clamp(0.0, 1.0))
        } else {
            t.power_uw
        }
    }

    pub fn tick(&mut self, env: &Environment, dt_s: f64) -> TickReport {
        let teg = teg_power_uw(&self.teg, env.skin_c, env.ambient_c, env.on_body);
        let piezo = piezo_power_uw(&self.piezo, env.accel_rms, env.step_hz);
        let harvest = teg + piezo;
        self.forecaster.observe(self.t_s, harvest);
        let forecast = self.forecaster.forecast(self.t_s, self.horizon_h);

        // energy-neutral budget: expected income + spendable stored energy over the horizon
        let cap_uwh = self.cell.capacity_mwh * 1000.0;
        let spendable_uwh = (self.cell.soc - self.reserve_soc).max(0.0) * cap_uwh;
        let budget = forecast.max(harvest) + spendable_uwh / self.horizon_h as f64;

        let mut order: Vec<usize> = (0..self.tasks.len()).collect();
        order.sort_by(|&a, &b| self.tasks[a].class.cmp(&self.tasks[b].class));
        let mut used = 0.0;
        let mut running = vec![];
        let mut throttled = vec![];
        for i in order {
            let t = &self.tasks[i];
            let c = Self::task_cost(t, env);
            let critical = t.class == TaskClass::Critical;
            let empty = self.cell.soc <= 0.0 && c > harvest - used;
            if (critical && !empty) || used + c <= budget {
                used += c;
                running.push(t.name.clone());
            } else {
                throttled.push(t.name.clone());
            }
        }
        self.cell.apply(harvest - used, dt_s);
        let r = TickReport {
            t_s: self.t_s,
            teg_uw: teg,
            piezo_uw: piezo,
            harvest_uw: harvest,
            forecast_uw: forecast,
            budget_uw: budget,
            consumption_uw: used,
            soc: self.cell.soc,
            running,
            throttled,
        };
        self.t_s += dt_s;
        r
    }
}

/// A representative day (minute resolution) for the dashboard and tests.
pub fn day_environment(minute: u32, ambient_c: f64) -> Environment {
    let h = minute as f64 / 60.0;
    let base = Environment { skin_c: 33.5, ambient_c, on_body: true, accel_rms: 0.3, step_hz: 0.0, activity: 0.2 };
    match h {
        h if h < 7.0 => Environment { on_body: false, accel_rms: 0.0, activity: 0.02, ..base },
        h if h < 8.0 => Environment { accel_rms: 4.0, step_hz: 1.9, activity: 0.5, ..base },   // commute walk
        h if h < 12.0 => Environment { activity: 0.3, ..base },                               // desk
        h if h < 12.5 => Environment { accel_rms: 4.5, step_hz: 2.0, activity: 0.5, ..base },
        h if h < 17.5 => Environment { activity: 0.3, ..base },
        h if h < 18.5 => Environment { skin_c: 35.0, accel_rms: 12.0, step_hz: 2.8, activity: 0.6, ..base }, // run
        h if h < 23.0 => Environment { activity: 0.25, accel_rms: 0.5, ..base },
        _ => Environment { on_body: false, accel_rms: 0.0, activity: 0.02, ..base },
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DaySummary {
    pub harvested_mwh: f64,
    pub consumed_mwh: f64,
    pub final_soc: f64,
    pub min_soc: f64,
    pub throttled_minutes: u32,
}

pub fn simulate_day(d: &mut HarvestDaemon, ambient_c: f64, days: u32) -> (Vec<TickReport>, DaySummary) {
    let mut out = Vec::with_capacity(1440 * days as usize);
    let (mut h, mut c, mut min_soc, mut thr) = (0.0, 0.0, 1.0f64, 0u32);
    for _ in 0..days {
        for m in 0..1440 {
            let r = d.tick(&day_environment(m, ambient_c), 60.0);
            h += r.harvest_uw / 60.0 / 1000.0;
            c += r.consumption_uw / 60.0 / 1000.0;
            min_soc = min_soc.min(r.soc);
            if !r.throttled.is_empty() {
                thr += 1;
            }
            out.push(r);
        }
    }
    let s = DaySummary { harvested_mwh: h, consumed_mwh: c, final_soc: d.cell.soc, min_soc, throttled_minutes: thr };
    (out, s)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn teg_output_is_microwatt_scale() {
        let p = teg_power_uw(&TegParams::default(), 34.0, 22.0, true);
        assert!(p > 50.0 && p < 2000.0, "{p}");
        assert_eq!(teg_power_uw(&TegParams::default(), 34.0, 22.0, false), 0.0);
        assert_eq!(teg_power_uw(&TegParams::default(), 30.0, 35.0, true), 0.0);
    }

    #[test]
    fn piezo_peaks_near_resonance() {
        let p = PiezoParams::default();
        let on = piezo_power_uw(&p, 4.0, 2.0);
        let off = piezo_power_uw(&p, 4.0, 6.0);
        assert!(on > 5.0 * off);
    }

    #[test]
    fn day_is_energy_neutral_and_never_drains() {
        let mut d = HarvestDaemon::default();
        let (_, s) = simulate_day(&mut d, 22.0, 3);
        assert!(s.min_soc > 0.05, "{s:?}");
        assert!(s.consumed_mwh <= s.harvested_mwh * 1.1 + 0.5 * d.cell.capacity_mwh, "{s:?}");
    }

    #[test]
    fn deferrable_work_throttled_when_idle_and_low() {
        let mut d = HarvestDaemon::default();
        d.cell.soc = 0.16;
        let night = day_environment(60, 22.0);
        let r = d.tick(&night, 60.0);
        assert!(r.throttled.iter().any(|t| t.contains("backup")));
        assert!(r.running.iter().any(|t| t.contains("rtc")));
    }
}
