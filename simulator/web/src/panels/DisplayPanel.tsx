import { useEffect, useRef, useState } from 'react'
import { j, Sim } from '../engine'

export default function DisplayPanel({ sim, hal }: { sim: Sim; hal: any }) {
  const [tilt, setTilt] = useState(25)
  const [faceUp, setFaceUp] = useState(true)
  const [shake, setShake] = useState(false)
  const [obstruct, setObstruct] = useState(false)
  const [frame, setFrame] = useState<any>(null)
  const [plan, setPlan] = useState<any>(null)
  const [proj, setProj] = useState({ h: 40, d: 20, lm: 30 })
  const jerk = useRef(0)

  useEffect(() => {
    const id = setInterval(() => {
      const jk = jerk.current; jerk.current = 0
      setFrame(j(sim.imu(tilt, faceUp, jk, shake ? 0.3 : 0, 50)))
    }, 50)
    return () => clearInterval(id)
  }, [sim, tilt, faceUp, shake])
  useEffect(() => { sim.obstruct(obstruct) }, [obstruct, sim])

  const report = j(sim.projection(proj.h, proj.d, proj.lm))
  const transitions = j(sim.transitions()).slice(-8).reverse()
  const projector = hal.slots.find((s: any) => s && s.class === 'ProjectorEngine')
  if (!frame) return null
  const st = frame.state

  return (
    <div className="grid-2">
      <section className="card tall">
        <h2>Compositor state: <span className={`pill st-${st}`}>{st}</span> <small>{frame.layout} · {frame.logical_w}×{frame.logical_h} · ~{frame.power_mw} mW</small></h2>
        <div className="display-stage">
          {(st === 'EInk' || st === 'Arming') && <EInkMock arming={st === 'Arming'} plan={plan} />}
          {st === 'RearPanel' && <div className="rear-eink"><div className="eink-text big">12:41</div><div className="eink-text">2 mesh messages · farmhouse: pump fixed</div><div className="eink-text dim">rear mono e-ink · face-down glance mode</div></div>}
          {(st === 'Projection' || st === 'Interlocked') && <Tabletop report={report} interlocked={st === 'Interlocked'} />}
        </div>
        <div className="sliders">
          <label>Tilt from horizontal <b>{tilt}°</b><input type="range" min={0} max={45} value={tilt} onChange={e => setTilt(+e.target.value)} /></label>
        </div>
        <div className="btns">
          <button onClick={() => setTilt(1)}>Lay flat on table</button>
          <button onClick={() => setFaceUp(!faceUp)}>{faceUp ? 'Flip face-down' : 'Flip face-up'}</button>
          <button onClick={() => { jerk.current = 3.5; setTilt(25) }}>Pick up</button>
          <label className="check"><input type="checkbox" checked={shake} onChange={e => setShake(e.target.checked)} /> wobbly table</label>
          <label className="check"><input type="checkbox" checked={obstruct} onChange={e => setObstruct(e.target.checked)} /> face in beam (IR depth)</label>
        </div>
        <p className="hint">Projector module: {projector ? <b>docked in slot {projector.slot} ({projector.alloc.state})</b> : <b className="warn">not docked, so tabletop mode is unavailable</b>}. Tabletop mode needs the phone flat (&lt;5°), still, and face-up for 1.5 s, then a 300 ms laser warm-up. It exits within one IMU sample when the phone is picked up or tilted past 12° (hysteresis).</p>
      </section>
      <section className="card">
        <h2>E-Ink waveform scheduler</h2>
        <div className="btns">
          {['scroll', 'typing', 'text', 'map', 'image'].map(c => <button key={c} onClick={() => setPlan(j(sim.eink_submit(c)) ?? { busy: true })}>{c}</button>)}
        </div>
        {plan && (plan.busy ? <div className="report">Panel busy: dirty region coalesced for the next waveform.</div> :
          <div className="report ok">{plan.panel}: <b>{plan.waveform}</b> · {plan.duration_ms} ms ({(1000 / plan.duration_ms).toFixed(1)} fps) · {plan.energy_mj.toFixed(1)} mJ · ghost {plan.ghost_level}{plan.forced_clear ? ' · forced full clear' : ''}</div>)}
        <h2>Tabletop projection optics</h2>
        <div className="sliders">
          <label>Exit-pupil height <b>{proj.h} mm</b><input type="range" min={10} max={300} value={proj.h} onChange={e => setProj({ ...proj, h: +e.target.value })} /></label>
          <label>Diagonal <b>{proj.d}″</b><input type="range" min={8} max={30} value={proj.d} onChange={e => setProj({ ...proj, d: +e.target.value })} /></label>
          <label>Laser flux <b>{proj.lm} lm</b><input type="range" min={5} max={150} value={proj.lm} onChange={e => setProj({ ...proj, lm: +e.target.value })} /></label>
        </div>
        <table className="kv"><tbody>
          <tr><td>workspace</td><td>{report.workspace_w_mm.toFixed(0)} × {report.workspace_h_mm.toFixed(0)} mm</td></tr>
          <tr><td>raster used after keystone</td><td>{(report.raster_utilization * 100).toFixed(1)} %</td></tr>
          <tr><td>resolution near / far</td><td>{report.px_per_mm_near.toFixed(2)} / {report.px_per_mm_far.toFixed(2)} px/mm</td></tr>
          <tr><td>far-edge incidence</td><td>{report.incidence_far_deg.toFixed(1)}° from vertical</td></tr>
          <tr><td>brightness uniformity</td><td className={report.uniformity < 0.3 ? 'warn' : ''}>{(report.uniformity * 100).toFixed(1)} %</td></tr>
          <tr><td>uniform image</td><td className={report.uniform_lux < 150 ? 'warn' : ''}><b>{report.uniform_lux.toFixed(0)} lux</b> (peak {report.peak_lux.toFixed(0)}; office ≈ 400)</td></tr>
        </tbody></table>
        <h3>Transitions</h3>
        <div className="log">{transitions.map((t: any, i: number) => <div key={i}><span className="t">{(t.t_ms / 1000).toFixed(2)} s</span> {t.from} → <b>{t.to}</b> <span className="dim">{t.cause}</span></div>)}</div>
      </section>
    </div>
  )
}

function EInkMock({ arming, plan }: any) {
  return (
    <div className={`eink ${plan?.waveform === 'A2' ? 'a2' : ''}`}>
      <div className="eink-bar">09:41 · mesh 7 nodes · 87%</div>
      <div className="eink-text big">Reading mode</div>
      <div className="eink-text">Reflective colour e-ink stays readable in direct sunlight and uses no power between refreshes. Scrolling uses the 1-bit A2 waveform (~11 fps), and a periodic full colour refresh clears ghosting.</div>
      <div className="eink-map" />
      {arming && <div className="arming">Laser warming up… tabletop mode</div>}
    </div>
  )
}

function Tabletop({ report, interlocked }: any) {
  const W = 520, H = 330
  const s = Math.min((W - 40) / report.workspace_w_mm, (H - 70) / report.workspace_h_mm)
  const w = report.workspace_w_mm * s, h = report.workspace_h_mm * s
  const x0 = (W - w) / 2, y0 = 12
  const qs = 0.16
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="tabletop">
      <defs>
        <linearGradient id="falloff" x1="0" y1="1" x2="0" y2="0">
          <stop offset="0" stopColor="#bfe9ff" stopOpacity={0.95} />
          <stop offset="1" stopColor="#bfe9ff" stopOpacity={Math.max(0.05, report.uniformity)} />
        </linearGradient>
      </defs>
      <rect width={W} height={H} fill="#3a2a1d" />
      {!interlocked && <rect x={x0} y={y0} width={w} height={h} fill="url(#falloff)" />}
      {!interlocked && Array.from({ length: 6 }, (_, i) => <rect key={i} x={x0 + 14 + i * (w - 28) / 6} y={y0 + h * 0.55} width={(w - 28) / 6 - 8} height={h * 0.3} rx={4} fill="#0b1a2a" opacity={0.35} />)}
      <rect x={x0} y={y0} width={w} height={h} fill="none" stroke="#4fc3f7" strokeDasharray="4 4" />
      <text x={W / 2} y={y0 + 24} textAnchor="middle" className="legend dark">{interlocked ? 'LASER INTERLOCKED: object in beam path' : '20″ interactive workspace (IR touch)'}</text>
      <rect x={W / 2 - 36} y={y0 + h + 6} width={72} height={34} rx={6} fill="#a9b0ba" />
      <text x={W / 2} y={y0 + h + 28} textAnchor="middle" className="tick dark">phone</text>
      <g transform={`translate(${W - 1280 * qs - 8}, ${H - 720 * qs - 8})`}>
        <rect width={1280 * qs} height={720 * qs} fill="#000" stroke="#555" />
        <polygon points={report.panel_quad.map((p: number[]) => `${p[0] * qs},${p[1] * qs}`).join(' ')} fill="#4fc3f7" opacity={0.6} />
        <text x={4} y={12} className="tick">MEMS raster (keystone pre-warp)</text>
      </g>
    </svg>
  )
}
