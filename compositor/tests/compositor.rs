use arcticchain_compositor::eink::{Content, EinkScheduler, Panel, Region, Waveform};
use arcticchain_compositor::imu::ImuSample;
use arcticchain_compositor::projection::{apply, detect_touch, homography, ProjectorConfig};
use arcticchain_compositor::{Compositor, DisplayState};

fn settle(c: &mut Compositor, t0: u64, ms: u64, tilt: f32, face_up: bool) -> u64 {
    let mut t = t0;
    while t < t0 + ms {
        c.on_imu(&ImuSample::at_rest(t, tilt, face_up));
        t += 10;
    }
    t
}

#[test]
fn enters_projection_after_dwell_and_warmup() {
    let mut c = Compositor::new(ProjectorConfig::default());
    let t = settle(&mut c, 0, 1400, 2.0, true);
    assert_eq!(c.state(), DisplayState::EInk, "must not arm before dwell");
    let t = settle(&mut c, t, 200, 2.0, true);
    assert_eq!(c.state(), DisplayState::Arming);
    settle(&mut c, t, 400, 2.0, true);
    assert_eq!(c.state(), DisplayState::Projection);
    assert!(c.frame().laser_on);
}

#[test]
fn hysteresis_and_instant_pickup_exit() {
    let mut c = Compositor::new(ProjectorConfig::default());
    let t = settle(&mut c, 0, 2200, 1.0, true);
    assert_eq!(c.state(), DisplayState::Projection);
    let t = settle(&mut c, t, 300, 8.0, true); // inside 5..12 deg band: stay
    assert_eq!(c.state(), DisplayState::Projection);
    let mut lift = ImuSample::at_rest(t, 1.0, true);
    lift.accel[2] += 3.0; // vertical jerk of picking up
    c.on_imu(&lift);
    assert_eq!(c.state(), DisplayState::EInk, "one sample (10 ms) is enough to exit");
}

#[test]
fn moving_table_never_arms() {
    let mut c = Compositor::new(ProjectorConfig::default());
    for k in 0..400u64 {
        let mut s = ImuSample::at_rest(k * 10, 1.0, true);
        s.gyro = [0.0, 0.0, if k % 2 == 0 { 0.2 } else { -0.2 }];
        c.on_imu(&s);
    }
    assert_eq!(c.state(), DisplayState::EInk);
}

#[test]
fn laser_interlock_on_obstruction() {
    let mut c = Compositor::new(ProjectorConfig::default());
    settle(&mut c, 0, 2200, 1.0, true);
    c.on_beam_obstruction(true);
    assert_eq!(c.state(), DisplayState::Interlocked);
    assert!(!c.frame().laser_on);
    c.on_beam_obstruction(false);
    assert_eq!(c.state(), DisplayState::Projection);
}

#[test]
fn face_down_uses_rear_panel_and_projector_removal_cancels() {
    let mut c = Compositor::new(ProjectorConfig::default());
    settle(&mut c, 0, 1700, 1.0, false);
    assert_eq!(c.state(), DisplayState::RearPanel);
    let plan = c.submit(1800, Content::Text, Region { x: 0, y: 0, w: 10, h: 10 }).unwrap();
    assert_eq!(plan.panel, "rear-mono-eink");

    let mut c = Compositor::new(ProjectorConfig::default());
    settle(&mut c, 0, 2200, 1.0, true);
    c.set_projector_present(false);
    assert_eq!(c.state(), DisplayState::EInk);
    settle(&mut c, 2200, 3000, 1.0, true);
    assert_eq!(c.state(), DisplayState::EInk, "no projector module, no tabletop mode");
}

#[test]
fn eink_waveforms_and_ghost_clearing() {
    let mut s = EinkScheduler::new(Panel::front_color());
    let r = Region { x: 0, y: 100, w: 1072, h: 200 };
    let p = s.submit(0, Content::Scroll, r).unwrap();
    assert_eq!(p.waveform, Waveform::A2);
    assert!(s.submit(10, Content::Scroll, r).is_none(), "panel busy");
    let mut t = 100;
    let mut forced = false;
    for _ in 0..20 {
        if let Some(p) = s.submit(t, Content::Typing, r) {
            forced |= p.forced_clear;
            if p.forced_clear {
                assert_eq!(p.waveform, Waveform::ColorFull);
                assert_eq!(s.ghost_level(), 0);
            }
        }
        t += 1000;
    }
    assert!(forced, "ghost limit must force a full colour refresh");
    let fps = 1000.0 / Waveform::A2.duration_ms() as f32;
    assert!(fps > 10.0);
}

#[test]
fn homography_roundtrip_and_touch_mapping() {
    let src = [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]];
    let dst = [[10.0, 20.0], [200.0, 25.0], [180.0, 300.0], [5.0, 280.0]];
    let h = homography(&src, &dst).unwrap();
    for i in 0..4 {
        let (u, v) = apply(&h, src[i][0], src[i][1]);
        assert!((u - dst[i][0]).abs() < 1e-6 && (v - dst[i][1]).abs() < 1e-6);
    }

    let cfg = ProjectorConfig::default();
    let r = cfg.analyze();
    assert!((r.workspace_w_mm - 442.7).abs() < 0.5 && (r.workspace_h_mm - 249.0).abs() < 0.5);
    // finger at the workspace centre
    let (cx, cy) = (0.0, cfg.near_mm + r.workspace_h_mm / 2.0);
    let px = apply(&r.table_to_panel, cx, cy);
    let t = detect_touch(&r, &cfg, px, 4.0, 8.0).unwrap();
    assert!(t.down && (t.u - 0.5).abs() < 1e-6 && (t.v - 0.5).abs() < 1e-6);
    assert!(!detect_touch(&r, &cfg, px, 25.0, 8.0).unwrap().down, "hovering finger");
}

#[test]
fn grazing_incidence_physics_is_reported_honestly() {
    let r = ProjectorConfig::default().analyze();
    assert!(r.uniformity < 0.2, "far edge must be much dimmer: {}", r.uniformity);
    assert!(r.px_per_mm_near > r.px_per_mm_far);
    assert!(r.uniform_lux < 300.0, "{} lux", r.uniform_lux);
    let tall = ProjectorConfig { lens_height_mm: 250.0, ..Default::default() }.analyze();
    assert!(tall.uniformity > r.uniformity);
}
