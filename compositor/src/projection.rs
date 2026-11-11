//! Ultra-short-throw tabletop projection geometry.
//!
//! The projector sits at the phone's top edge, `lens_height_mm` above the table, and
//! throws a 16:9 workspace onto the table starting `near_mm` beyond the lens. We compute
//! the table->panel homography (keystone pre-warp), how much of the MEMS raster is used,
//! and the brightness non-uniformity caused by grazing incidence: illuminance at a table
//! point is proportional to local pixel density, so the far edge is much dimmer and the
//! image must be dimmed to the far-edge level to look uniform.

use serde::{Deserialize, Serialize};

pub type Mat3 = [f64; 9];

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProjectorConfig {
    pub lens_height_mm: f64,
    pub near_mm: f64,
    pub diagonal_in: f64,
    pub panel_w: u32,
    pub panel_h: u32,
    pub lumens: f64,
}

impl Default for ProjectorConfig {
    fn default() -> Self {
        // flip-up periscope mirror lifts the effective exit pupil to ~40 mm
        Self { lens_height_mm: 40.0, near_mm: 30.0, diagonal_in: 20.0, panel_w: 1280, panel_h: 720, lumens: 30.0 }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProjectionReport {
    pub workspace_w_mm: f64,
    pub workspace_h_mm: f64,
    /// Table (mm) -> panel (px) homography, row-major.
    pub table_to_panel: Mat3,
    pub panel_to_table: Mat3,
    /// Workspace corners in panel pixels: near-left, near-right, far-right, far-left.
    pub panel_quad: [[f64; 2]; 4],
    pub raster_utilization: f64,
    pub px_per_mm_near: f64,
    pub px_per_mm_far: f64,
    pub uniformity: f64,
    pub uniform_lux: f64,
    pub peak_lux: f64,
    pub incidence_far_deg: f64,
}

pub fn apply(h: &Mat3, x: f64, y: f64) -> (f64, f64) {
    let w = h[6] * x + h[7] * y + h[8];
    ((h[0] * x + h[1] * y + h[2]) / w, (h[3] * x + h[4] * y + h[5]) / w)
}

/// Direct linear transform from 4 point correspondences.
pub fn homography(src: &[[f64; 2]; 4], dst: &[[f64; 2]; 4]) -> Option<Mat3> {
    let mut a = [[0.0f64; 9]; 8];
    for i in 0..4 {
        let (x, y) = (src[i][0], src[i][1]);
        let (u, v) = (dst[i][0], dst[i][1]);
        a[2 * i] = [x, y, 1.0, 0.0, 0.0, 0.0, -u * x, -u * y, u];
        a[2 * i + 1] = [0.0, 0.0, 0.0, x, y, 1.0, -v * x, -v * y, v];
    }
    for c in 0..8 {
        let p = (c..8).max_by(|&i, &j| a[i][c].abs().partial_cmp(&a[j][c].abs()).unwrap())?;
        if a[p][c].abs() < 1e-12 {
            return None;
        }
        a.swap(c, p);
        for r in 0..8 {
            if r != c {
                let f = a[r][c] / a[c][c];
                for k in c..9 {
                    a[r][k] -= f * a[c][k];
                }
            }
        }
    }
    let mut h = [0.0; 9];
    for i in 0..8 {
        h[i] = a[i][8] / a[i][i];
    }
    h[8] = 1.0;
    Some(h)
}

pub fn invert(m: &Mat3) -> Option<Mat3> {
    let [a, b, c, d, e, f, g, h, i] = *m;
    let det = a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g);
    if det.abs() < 1e-15 {
        return None;
    }
    let inv = [e * i - f * h, c * h - b * i, b * f - c * e, f * g - d * i, a * i - c * g, c * d - a * f, d * h - e * g, b * g - a * h, a * e - b * d];
    Some(inv.map(|v| v / det))
}

impl ProjectorConfig {
    pub fn workspace_mm(&self) -> (f64, f64) {
        let d = self.diagonal_in * 25.4;
        let k = (16.0f64 * 16.0 + 9.0 * 9.0).sqrt();
        (d * 16.0 / k, d * 9.0 / k)
    }

    /// Pinhole projector at (0, 0, h) looking along +y, tilted down so the optical axis
    /// hits the workspace centre. Returns panel coordinates (unnormalised) for a table point.
    fn pinhole(&self, x: f64, y: f64) -> (f64, f64) {
        let (_, wh) = self.workspace_mm();
        let h = self.lens_height_mm;
        let yc = self.near_mm + wh / 2.0;
        let tilt = (h / yc).atan();
        let (s, c) = tilt.sin_cos();
        // camera frame: forward f, right r, up u
        let (dx, dy, dz) = (x, y, -h);
        let fwd = dy * c - dz * s;
        let up = dy * s + dz * c;
        (dx / fwd, -up / fwd)
    }

    pub fn analyze(&self) -> ProjectionReport {
        let (ww, wh) = self.workspace_mm();
        let near = self.near_mm;
        let far = near + wh;
        let table = [[-ww / 2.0, near], [ww / 2.0, near], [ww / 2.0, far], [-ww / 2.0, far]];
        let raw: Vec<(f64, f64)> = table.iter().map(|p| self.pinhole(p[0], p[1])).collect();
        let (minx, maxx) = raw.iter().fold((f64::MAX, f64::MIN), |(a, b), p| (a.min(p.0), b.max(p.0)));
        let (miny, maxy) = raw.iter().fold((f64::MAX, f64::MIN), |(a, b), p| (a.min(p.1), b.max(p.1)));
        let (pw, ph) = (self.panel_w as f64, self.panel_h as f64);
        let scale = (pw / (maxx - minx)).min(ph / (maxy - miny));
        let ox = (pw - (maxx - minx) * scale) / 2.0;
        let oy = (ph - (maxy - miny) * scale) / 2.0;
        let quad: [[f64; 2]; 4] = std::array::from_fn(|i| [ox + (raw[i].0 - minx) * scale, oy + (raw[i].1 - miny) * scale]);
        let t2p = homography(&table, &quad).expect("non-degenerate workspace");
        let p2t = invert(&t2p).unwrap();

        // shoelace area of the used quad
        let area: f64 = (0..4).map(|i| { let j = (i + 1) % 4; quad[i][0] * quad[j][1] - quad[j][0] * quad[i][1] }).sum::<f64>().abs() / 2.0;
        let util = area / (pw * ph);

        // pixel density (px/mm^2) = |det J| of table->panel mapping, sampled over workspace
        let dens = |x: f64, y: f64| {
            let e = 0.5;
            let (u0, v0) = apply(&t2p, x, y);
            let (u1, v1) = apply(&t2p, x + e, y);
            let (u2, v2) = apply(&t2p, x, y + e);
            (((u1 - u0) * (v2 - v0) - (u2 - u0) * (v1 - v0)) / (e * e)).abs()
        };
        let mut dmin = f64::MAX;
        let mut dmax: f64 = 0.0;
        for i in 0..=20 {
            for j in 0..=20 {
                let x = -ww / 2.0 + ww * i as f64 / 20.0;
                let y = near + wh * j as f64 / 20.0;
                let d = dens(x, y);
                dmin = dmin.min(d);
                dmax = dmax.max(d);
            }
        }
        let lm_per_px = self.lumens / (pw * ph);
        let lin = |y: f64| {
            let (_, v0) = apply(&t2p, 0.0, y);
            let (_, v1) = apply(&t2p, 0.0, y + 1.0);
            (v1 - v0).abs()
        };
        ProjectionReport {
            workspace_w_mm: ww,
            workspace_h_mm: wh,
            table_to_panel: t2p,
            panel_to_table: p2t,
            panel_quad: quad,
            raster_utilization: util,
            px_per_mm_near: lin(near),
            px_per_mm_far: lin(far - 1.0),
            uniformity: dmin / dmax,
            uniform_lux: lm_per_px * dmin * 1e6,
            peak_lux: lm_per_px * dmax * 1e6,
            incidence_far_deg: (far / self.lens_height_mm).atan().to_degrees(),
        }
    }
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq)]
pub struct TouchEvent {
    pub x_mm: f64,
    pub y_mm: f64,
    /// Workspace-normalised coordinates (0..1, origin far-left as seen by the user).
    pub u: f64,
    pub v: f64,
    pub down: bool,
}

/// IR depth camera co-located with the projector shares its homography. A fingertip is a
/// touch when it is within `touch_mm` of the table plane.
pub fn detect_touch(report: &ProjectionReport, cfg: &ProjectorConfig, panel_px: (f64, f64), fingertip_height_mm: f64, touch_mm: f64) -> Option<TouchEvent> {
    let (x, y) = apply(&report.panel_to_table, panel_px.0, panel_px.1);
    let (ww, wh) = (report.workspace_w_mm, report.workspace_h_mm);
    let u = (x + ww / 2.0) / ww;
    let v = 1.0 - (y - cfg.near_mm) / wh;
    if !(0.0..=1.0).contains(&u) || !(0.0..=1.0).contains(&v) {
        return None;
    }
    Some(TouchEvent { x_mm: x, y_mm: y, u, v, down: fingertip_height_mm <= touch_mm })
}
