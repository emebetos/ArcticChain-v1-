//! Physical-layer link budgets.
//!
//! LoRa (915 MHz, 125 kHz): picks the fastest spreading factor that closes the link with
//! margin. Duty-cycle limits (1 %) make it a control/messaging channel, not a data pipe.
//!
//! 60 GHz mmWave (802.11ad/ay-like, 2.16 GHz channel): free-space loss + oxygen absorption,
//! phased-array gain on both ends, Shannon-capped rate. Walls/bodies effectively block it.

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, PartialOrd, Ord, Serialize, Deserialize)]
pub enum Phy {
    LoRa,
    MmWave,
}

#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct LinkMetrics {
    pub phy: Phy,
    pub rate_bps: f64,
    /// Effective long-run throughput after duty-cycle / MAC overhead.
    pub goodput_bps: f64,
    pub snr_db: f64,
    pub rx_dbm: f64,
    /// LoRa spreading factor, if applicable.
    pub sf: Option<u8>,
    /// mmWave beam sector toward the peer (0..BEAM_SECTORS).
    pub sector: Option<u8>,
    pub walls: u32,
}

pub const BEAM_SECTORS: u8 = 32;

// LoRa SX126x-class figures (BW 125 kHz)
const LORA_TX_DBM: f64 = 14.0;
const LORA_ANT_DBI: f64 = 0.0;
const LORA_FSPL_1M: f64 = 31.7;
const LORA_PL_EXP: f64 = 2.9;
const LORA_WALL_DB: f64 = 8.0;
const LORA_MARGIN_DB: f64 = 3.0;
const LORA_DUTY: f64 = 0.01;
/// (SF, sensitivity dBm, raw bit rate)
const LORA_SF: [(u8, f64, f64); 6] = [
    (7, -123.0, 5470.0),
    (8, -126.0, 3125.0),
    (9, -129.0, 1760.0),
    (10, -132.0, 980.0),
    (11, -134.5, 440.0),
    (12, -137.0, 250.0),
];

// 60 GHz
const MMW_TX_DBM: f64 = 10.0;
const MMW_ARRAY_DBI: f64 = 20.0;
const MMW_LAMBDA_M: f64 = 0.005;
const MMW_O2_DB_PER_M: f64 = 0.015;
const MMW_WALL_DB: f64 = 30.0;
const MMW_BW_HZ: f64 = 2.16e9;
const MMW_NF_DB: f64 = 10.0;
const MMW_MIN_SNR_DB: f64 = 3.0;
const MMW_MAX_BPS: f64 = 4.6e9;

pub fn lora(distance_m: f64, walls: u32) -> Option<LinkMetrics> {
    let d = distance_m.max(1.0);
    let pl = LORA_FSPL_1M + 10.0 * LORA_PL_EXP * d.log10() + walls as f64 * LORA_WALL_DB;
    let rx = LORA_TX_DBM + 2.0 * LORA_ANT_DBI - pl;
    let noise = -174.0 + 10.0 * 125e3f64.log10() + 6.0;
    LORA_SF.iter().find(|(_, sens, _)| rx >= sens + LORA_MARGIN_DB).map(|&(sf, _, rate)| LinkMetrics {
        phy: Phy::LoRa,
        rate_bps: rate,
        goodput_bps: rate * LORA_DUTY,
        snr_db: rx - noise,
        rx_dbm: rx,
        sf: Some(sf),
        sector: None,
        walls,
    })
}

pub fn mmwave(distance_m: f64, walls: u32, bearing_rad: f64) -> Option<LinkMetrics> {
    let d = distance_m.max(0.1);
    let fspl = 20.0 * (4.0 * std::f64::consts::PI * d / MMW_LAMBDA_M).log10();
    let pl = fspl + MMW_O2_DB_PER_M * d + walls as f64 * MMW_WALL_DB;
    let rx = MMW_TX_DBM + 2.0 * MMW_ARRAY_DBI - pl;
    let noise = -174.0 + 10.0 * MMW_BW_HZ.log10() + MMW_NF_DB;
    let snr = rx - noise;
    if snr < MMW_MIN_SNR_DB {
        return None;
    }
    let rate = (0.6 * MMW_BW_HZ * (1.0 + 10f64.powf(snr / 10.0)).log2()).min(MMW_MAX_BPS);
    let tau = std::f64::consts::TAU;
    let sector = ((bearing_rad.rem_euclid(tau) / tau) * BEAM_SECTORS as f64) as u8 % BEAM_SECTORS;
    Some(LinkMetrics { phy: Phy::MmWave, rate_bps: rate, goodput_bps: rate * 0.7, snr_db: snr, rx_dbm: rx, sf: None, sector: Some(sector), walls })
}

/// LoRa time-on-air (ms) for `bytes` of payload (explicit header, CR 4/5, 8-symbol preamble).
pub fn lora_airtime_ms(sf: u8, bytes: usize) -> f64 {
    let bw = 125e3;
    let t_sym = (1u32 << sf) as f64 / bw * 1000.0;
    let de = if sf >= 11 { 1.0 } else { 0.0 };
    let n = 8.0 + ((8.0 * bytes as f64 - 4.0 * sf as f64 + 28.0 + 16.0) / (4.0 * (sf as f64 - 2.0 * de))).ceil().max(0.0) * 5.0;
    (8.0 + 4.25) * t_sym + n * t_sym
}

/// Time (ms) to move `bytes` across a link, including MAC/duty-cycle effects.
pub fn transfer_ms(m: &LinkMetrics, bytes: usize) -> f64 {
    match m.phy {
        Phy::LoRa => {
            let sf = m.sf.unwrap_or(12);
            let frames = bytes.div_ceil(222).max(1);
            let air = lora_airtime_ms(sf, bytes.min(222)) * frames as f64;
            // after the first frame, duty cycle forces an off-time of 99x airtime
            air + (frames as f64 - 1.0) * air / frames as f64 * (1.0 / LORA_DUTY - 1.0)
        }
        // 1 ms beam-tracking refinement + serialization
        Phy::MmWave => 1.0 + bytes as f64 * 8.0 / m.goodput_bps * 1000.0,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn lora_reaches_kilometres_with_rising_sf() {
        let near = lora(200.0, 0).unwrap();
        let far = lora(8_000.0, 0).unwrap();
        assert_eq!(near.sf, Some(7));
        assert!(far.sf.unwrap() > 9);
        assert!(lora(60_000.0, 0).is_none());
    }

    #[test]
    fn mmwave_is_fast_short_and_blocked_by_walls() {
        let m = mmwave(30.0, 0, 0.0).unwrap();
        assert!(m.rate_bps > 1e9);
        assert!(mmwave(30.0, 1, 0.0).is_none() || mmwave(30.0, 1, 0.0).unwrap().rate_bps < m.rate_bps / 2.0);
        assert!(mmwave(400.0, 0, 0.0).is_none());
    }

    #[test]
    fn airtime_matches_semtech_calculator_ballpark() {
        // Semtech calculator: SF7/125k, 20 B -> ~56.6 ms; SF12 -> ~1318 ms
        let a7 = lora_airtime_ms(7, 20);
        let a12 = lora_airtime_ms(12, 20);
        assert!((45.0..70.0).contains(&a7), "{a7}");
        assert!((1100.0..1500.0).contains(&a12), "{a12}");
    }
}
