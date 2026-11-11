import { useEffect, useRef, useState } from 'react'
import { j, Sim } from '../engine'

export default function SurfacePanel({ sim }: { sim: Sim }) {
  const [kind, setKind] = useState('keyboard')
  const [value, setValue] = useState(0.3)
  const [pressed, setPressed] = useState(false)
  const [frame, setFrame] = useState<any>(null)
  const canvas = useRef<HTMLCanvasElement>(null)

  useEffect(() => { sim.tactile_layout(kind, value, pressed) }, [kind, value, pressed, sim])
  useEffect(() => {
    let raf = 0
    const loop = () => { setFrame(j(sim.tactile_step(16))); raf = requestAnimationFrame(loop) }
    raf = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(raf)
  }, [sim])

  useEffect(() => {
    if (!frame || !canvas.current) return
    const c = canvas.current.getContext('2d')!
    const cw = canvas.current.width / frame.cols, ch = canvas.current.height / frame.rows
    c.fillStyle = '#081420'; c.fillRect(0, 0, canvas.current.width, canvas.current.height)
    frame.zones.forEach((z: any, i: number) => {
      const col = i % frame.cols, row = Math.floor(i / frame.cols)
      const t = Math.min(1, z.height_um / 400)
      if (z.actuator === 'Eap') c.fillStyle = `rgba(155,108,255,${0.15 + Math.min(1, z.height_um / 80) * 0.85})`
      else if (z.actuator === 'Microfluidic') c.fillStyle = `rgba(79,195,247,${0.15 + t * 0.85})`
      else c.fillStyle = '#0e2234'
      c.fillRect(col * cw + 1, row * ch + 1, cw - 2, ch - 2)
    })
  }, [frame])

  return (
    <div className="grid-2">
      <section className="card">
        <h2>Programmable surface: EAP + microfluidic actuator map</h2>
        <div className="surface-wrap">
          <canvas ref={canvas} width={234} height={494} className="surface" />
          <div>
            <div className="btns col">
              {['keyboard', 'slider', 'scroll', 'buttons', 'none'].map(k => <button key={k} className={kind === k ? 'primary' : ''} onClick={() => setKind(k)}>{k}</button>)}
            </div>
            <label className="slider">value / scroll offset <input type="range" min={0} max={1} step={0.01} value={value} onChange={e => setValue(+e.target.value)} /></label>
            <button onMouseDown={() => setPressed(true)} onMouseUp={() => setPressed(false)} onMouseLeave={() => setPressed(false)}>Hold to press key / button</button>
            {frame && <table className="kv"><tbody>
              <tr><td>grid</td><td>{frame.cols}×{frame.rows} zones (~3.7 mm pitch)</td></tr>
              <tr><td>fluid volume</td><td>{frame.fluid_volume_ul.toFixed(1)} µL (pump scale {(frame.fluid_scale * 100).toFixed(0)}%)</td></tr>
              <tr><td>EAP drive</td><td>{frame.max_eap_v.toFixed(0)} V peak</td></tr>
              <tr><td>settled</td><td>{frame.settled ? 'yes' : 'slewing…'}</td></tr>
            </tbody></table>}
            <p className="hint"><span style={{ color: '#9b6cff' }}>■</span> EAP: fast, ≤80 µm (clicks, ridges) · <span style={{ color: '#4fc3f7' }}>■</span> microfluidic: slow, ≤400 µm (rims, slider rails)</p>
          </div>
        </div>
      </section>
      <PrivacyCard sim={sim} />
    </div>
  )
}

function PrivacyCard({ sim }: { sim: Sim }) {
  const [u, setU] = useState({ ux: 0, uz: 350, ox: 300, oz: 450, on: true })
  const f = j(sim.privacy(u.ux, u.uz, u.ox, u.oz, u.on))
  const W = 520, H = 360, sc = 0.45, ox0 = W / 2, oy0 = H - 20
  const P = (x: number, z: number) => [ox0 + x * sc, oy0 - z * sc]
  const mid = f.regions.slice(6 * 6, 6 * 7)
  const set = (k: string) => (e: any) => setU({ ...u, [k]: +e.target.value })
  return (
    <section className="card">
      <h2>Light-field privacy: viewing cone steered to the primary user</h2>
      <svg viewBox={`0 0 ${W} ${H}`} className="privacy">
        {mid.map((r: any, i: number) => {
          const [x0, y0] = P(r.cx, 0)
          const L = 900
          const a1 = ((r.yaw_deg - r.half_angle_deg) * Math.PI) / 180, a2 = ((r.yaw_deg + r.half_angle_deg) * Math.PI) / 180
          return <polygon key={i} points={`${x0},${y0} ${x0 + Math.sin(a1) * L * sc},${y0 - Math.cos(a1) * L * sc} ${x0 + Math.sin(a2) * L * sc},${y0 - Math.cos(a2) * L * sc}`} fill={u.on ? '#4fc3f7' : '#e3b341'} opacity={0.07} stroke={u.on ? '#4fc3f7' : '#e3b341'} strokeOpacity={0.3} />
        })}
        <rect x={P(-33, 0)[0]} y={oy0} width={66 * sc} height={8} fill="#a9b0ba" />
        <circle cx={P(u.ux - 32, u.uz)[0]} cy={P(u.ux, u.uz)[1]} r={5} fill="#3fb37f" />
        <circle cx={P(u.ux + 32, u.uz)[0]} cy={P(u.ux, u.uz)[1]} r={5} fill="#3fb37f" />
        <text x={P(u.ux, u.uz)[0]} y={P(u.ux, u.uz)[1] - 12} textAnchor="middle" className="legend">you ({(f.primary_visibility * 100).toFixed(0)}% visible)</text>
        <circle cx={P(u.ox, u.oz)[0]} cy={P(u.ox, u.oz)[1]} r={7} fill="#ff6b6b" />
        <text x={P(u.ox, u.oz)[0]} y={P(u.ox, u.oz)[1] - 12} textAnchor="middle" className="legend">shoulder-surfer ({(f.observer_visibility[0] * 100).toFixed(0)}%)</text>
      </svg>
      <div className="sliders">
        <label>You: x <b>{u.ux} mm</b><input type="range" min={-300} max={300} value={u.ux} onChange={set('ux')} /></label>
        <label>You: distance <b>{u.uz} mm</b><input type="range" min={150} max={700} value={u.uz} onChange={set('uz')} /></label>
        <label>Observer: x <b>{u.ox} mm</b><input type="range" min={-550} max={550} value={u.ox} onChange={set('ox')} /></label>
        <label>Observer: distance <b>{u.oz} mm</b><input type="range" min={100} max={750} value={u.oz} onChange={set('oz')} /></label>
      </div>
      <label className="check"><input type="checkbox" checked={u.on} onChange={e => setU({ ...u, on: e.target.checked })} /> privacy steering enabled</label>
      <p className="hint">Top-down view of one row of steerable micro-lens regions (6×12 regions in total). Each cone is aimed at the midpoint between the tracked eyes and narrowed to cover just both pupils. Steering saturates at ±30°.</p>
    </section>
  )
}
