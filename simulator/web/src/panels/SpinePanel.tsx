import * as THREE from 'three'
import { Suspense, useEffect, useMemo, useState } from 'react'
import { Canvas, useLoader } from '@react-three/fiber'
import { OrbitControls, Html } from '@react-three/drei'
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader.js'
import { CLASSES, CLASS_COLORS, CLASS_STL, j, Sim } from '../engine'
import { Bar } from '../Chart'

const FAULTS = ['none', 'bad-signature', 'forged-endorsement', 'unresponsive', 'corrupt', 'overdraw']

function useLayout() {
  const [layout, setLayout] = useState<any>(null)
  useEffect(() => { fetch('models/layout.json').then(r => r.json()).then(setLayout) }, [])
  return layout
}

function Stl({ url, color, opacity = 1, ...props }: any) {
  const geom = useLoader(STLLoader, url)
  const g = useMemo(() => { const b = geom as THREE.BufferGeometry; b.computeVertexNormals(); return b }, [geom])
  return (
    <mesh geometry={g} {...props} castShadow receiveShadow>
      <meshStandardMaterial color={color} metalness={0.55} roughness={0.38} transparent={opacity < 1} opacity={opacity} />
    </mesh>
  )
}

function Phone({ layout, hal, selected, onSelect }: any) {
  const fz = layout.derived.floor_z
  return (
    <group rotation={[-Math.PI / 2, 0, 0]} scale={0.02}>
      <Stl url="models/spine.stl" color="#a9b0ba" />
      {layout.bays.map((b: any) => {
        const m = hal.slots[b.slot]
        const susp = m && m.alloc.state === 'Suspended'
        return (
          <group key={b.slot} position={[b.cx, b.cy, fz]} rotation={[0, 0, (b.rotation_deg * Math.PI) / 180]}>
            {m ? (
              <Stl url={`models/module_${CLASS_STL[m.class]}.stl`} color={susp ? '#552222' : CLASS_COLORS[m.class]} opacity={susp ? 0.55 : 1}
                position={[0, 0, selected === b.slot ? 4 : 0]} onClick={(e: any) => { e.stopPropagation(); onSelect(b.slot) }} />
            ) : (
              <mesh position={[0, 0, 2.5]} onClick={(e: any) => { e.stopPropagation(); onSelect(b.slot) }}>
                <boxGeometry args={[layout.derived.bay_width - 2, layout.derived.bay_height - 2, 0.2]} />
                <meshBasicMaterial color={selected === b.slot ? '#4fc3f7' : '#1d3b55'} transparent opacity={0.5} />
              </mesh>
            )}
            <Html position={[0, 0, 7]} center style={{ pointerEvents: 'none' }}>
              <div className="slot-tag">{b.slot}{m ? ` · ${m.class.replace(/([A-Z])/g, ' $1').trim().split(' ')[0]}` : ' · empty'}</div>
            </Html>
          </group>
        )
      })}
    </group>
  )
}

export default function SpinePanel({ sim, hal }: { sim: Sim; hal: any }) {
  const layout = useLayout()
  const [selected, setSelected] = useState(0)
  const [cls, setCls] = useState('mesh-radio')
  const [fault, setFault] = useState('none')
  const [report, setReport] = useState<any>(null)
  const [events, setEvents] = useState<any[]>([])
  const [load, setLoad] = useState(hal.system_load_mw)
  const [dts, setDts] = useState('')

  useEffect(() => {
    const ev = j(sim.drain_events())
    if (ev.length) setEvents(e => [...ev.reverse(), ...e].slice(0, 80))
    setDts(j(sim.hal_state()).dts)
  })

  const slot = hal.slots[selected]
  const act = (f: () => string | void) => { const r = f(); if (typeof r === 'string') setReport(j(r)) }

  return (
    <div className="grid-2">
      <section className="card tall">
        <h2>Titanium spine · 154 × 72 × 9.8 mm · Ti-6Al-4V {layout && <small>{layout.verification?.checks?.filter((c: any) => c.pass).length}/{layout.verification?.checks?.length} CAD checks pass</small>}</h2>
        <div className="canvas-wrap">
          {layout ? (
            <Canvas camera={{ position: [0, 3.2, 2.6], fov: 45 }} shadows onPointerMissed={() => {}}>
              <color attach="background" args={['#0b1a2a']} />
              <ambientLight intensity={0.5} />
              <directionalLight position={[3, 5, 2]} intensity={1.6} castShadow />
              <directionalLight position={[-3, 2, -2]} intensity={0.5} />
              <Suspense fallback={null}><Phone layout={layout} hal={hal} selected={selected} onSelect={setSelected} /></Suspense>
              <gridHelper args={[8, 32, '#24476b', '#16314c']} position={[0, -0.12, 0]} />
              <OrbitControls makeDefault />
            </Canvas>
          ) : <div className="loading">loading CAD…</div>}
        </div>
        <p className="hint">Geometry is the CadQuery output (cad/out/*.stl). Click a dock to select it. Suspended modules render dark red.</p>
        <div className="row">
          <Bar label="Shared power rail (modules)" value={hal.power_allocated_mw} max={hal.power_budget_mw} unit="mW" color="#3fb37f" />
          <Bar label="Optical backplane" value={hal.bandwidth_allocated_mbps} max={hal.backplane_mbps} unit="Mb/s" color="#4fc3f7" />
        </div>
        <label className="slider">System base load (SoC + display + radios): <b>{load} mW</b> · supply {hal.power_supply_mw} mW
          <input type="range" min={0} max={12000} step={250} value={load} onChange={e => { const v = +e.target.value; setLoad(v); sim.set_system_load(v) }} />
        </label>
      </section>

      <section className="card">
        <h2>Dock {selected} {slot ? <span className={`pill ${slot.alloc.state}`}>{slot.alloc.state}{slot.tripped ? ' · TRIPPED' : ''}</span> : <span className="pill">empty</span>}</h2>
        {slot ? (
          <>
            <table className="kv"><tbody>
              <tr><td>class</td><td>{slot.class}</td><td>priority</td><td>{slot.priority}</td></tr>
              <tr><td>power</td><td>{slot.alloc.power_mw} / {slot.requested_mw} mW (min {slot.min_mw})</td><td>draw</td><td>{slot.draw_mw} mW · {slot.temp_c.toFixed(1)} °C</td></tr>
              <tr><td>bandwidth</td><td>{slot.alloc.mbps} / {slot.requested_mbps} Mb/s</td><td>supplies</td><td>{slot.supply_mw ? `${slot.supply_mw} mW · ${slot.capacity_mwh} mWh` : '—'}</td></tr>
              <tr><td>dt path</td><td colSpan={3}><code>{slot.path}</code></td></tr>
            </tbody></table>
            <div className="btns">
              <button onClick={() => act(() => sim.detach(selected, false))}>Release latch (graceful)</button>
              <button className="danger" onClick={() => act(() => sim.detach(selected, true))}>Yank (surprise removal)</button>
              <button onClick={() => sim.set_fault(selected, 'unresponsive')}>Kill firmware (heartbeat loss)</button>
              <button onClick={() => sim.set_fault(selected, 'overdraw')}>Short circuit (2× draw)</button>
              {slot.tripped && <button onClick={() => { sim.set_fault(selected, 'none'); sim.reset_trip(selected) }}>Reset trip</button>}
            </div>
          </>
        ) : (
          <div className="btns">
            <select value={cls} onChange={e => setCls(e.target.value)}>{CLASSES.map(c => <option key={c}>{c}</option>)}</select>
            <select value={fault} onChange={e => setFault(e.target.value)}>{FAULTS.map(c => <option key={c} value={c}>{c === 'none' ? 'genuine module' : `fault: ${c}`}</option>)}</select>
            <button className="primary" onClick={() => act(() => sim.attach(selected, cls, fault))}>Snap in module</button>
          </div>
        )}

        {report && <AttachTimeline r={report} />}

        <h3>HAL events</h3>
        <div className="log">
          {events.length === 0 && <div className="dim">Snap in, yank, or change load to generate events.</div>}
          {events.map((e, i) => <div key={i}><span className="t">{(e.t_us / 1000).toFixed(1)} ms</span> {fmtEvent(e.event)}</div>)}
        </div>
        <h3>Live device tree</h3>
        <pre className="dts">{dts}</pre>
      </section>
    </div>
  )
}

function fmtEvent(e: any) {
  const [k, v] = Object.entries(e)[0] as [string, any]
  const parts = Object.entries(v).map(([a, b]) => `${a}=${typeof b === 'object' ? JSON.stringify(b) : b}`).join(' ')
  return <><b className={`ev-${k}`}>{k}</b> {parts}</>
}

function AttachTimeline({ r }: { r: any }) {
  if (r.error) return <div className="report bad">{r.error}</div>
  if (r.phases === undefined) return <div className="report">{r.surprise ? 'Surprise removal' : 'Graceful detach'} handled in {(r.elapsed_us / 1000).toFixed(2)} ms (uid {r.uid?.toString(16)})</div>
  const total = Math.max(50000, r.elapsed_us)
  const phases = [...r.phases, ['done', r.elapsed_us]]
  return (
    <div className={`report ${r.accepted ? 'ok' : 'bad'}`}>
      <div>{r.accepted ? 'ACCEPTED' : `REJECTED: ${r.reason}`} in <b>{(r.elapsed_us / 1000).toFixed(2)} ms</b> (deadline 50 ms){r.grant && <> · grant {r.grant.power_mw} mW, {r.grant.mbps} Mb/s on {r.grant.lanes} lane(s) @ {r.grant.rail_mv} mV</>}</div>
      <div className="timeline">
        {phases.slice(0, -1).map((p: any, i: number) => {
          const w = ((phases[i + 1][1] - p[1]) / total) * 100
          return <div key={i} className={`ph ph-${i}`} style={{ width: `${w}%` }} title={`${p[0]} ${((phases[i + 1][1] - p[1]) / 1000).toFixed(2)} ms`}>{w > 7 ? p[0] : ''}</div>
        })}
        <div className="deadline" style={{ left: `${(50000 / total) * 100}%` }} />
      </div>
    </div>
  )
}
