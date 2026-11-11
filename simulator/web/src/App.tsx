import { useEffect, useState } from 'react'
import { j, loadEngine, Sim } from './engine'
import SpinePanel from './panels/SpinePanel'
import PowerPanel from './panels/PowerPanel'
import SurfacePanel from './panels/SurfacePanel'
import MeshPanel from './panels/MeshPanel'
import DisplayPanel from './panels/DisplayPanel'

const TABS = [
  ['spine', '1 · Spine & Optical Bus'],
  ['surface', '2 · Programmable Surface'],
  ['power', '3 · Zero-Charge Power'],
  ['mesh', '4 · Node Mesh'],
  ['display', '5 · E-Ink / Projection'],
] as const

export default function App() {
  const [sim, setSim] = useState<Sim | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [tab, setTab] = useState<string>('spine')
  const [, setPulse] = useState(0)

  useEffect(() => { loadEngine().then(setSim).catch(e => setErr(String(e))) }, [])

  // global heartbeat: HAL supervision + compositor IMU keep running whichever tab is open
  useEffect(() => {
    if (!sim) return
    const id = setInterval(() => { sim.tick_hal(100); setPulse(p => p + 1) }, 100)
    return () => clearInterval(id)
  }, [sim])

  if (err) return <div className="loading">Failed to load WASM engine: {err}</div>
  if (!sim) return <div className="loading">Booting Monolith HAL (WASM)…</div>

  const hal = j(sim.hal_state()).snapshot
  const mesh = j(sim.mesh_state())
  const disp = j(sim.imu(0, true, 0, 0, 0))
  const mods = hal.slots.filter(Boolean)

  return (
    <div className="app">
      <header>
        <div className="brand"><span className="logo">▣</span> PROJECT MONOLITH <small>hardware-in-the-loop simulator · running the real Rust firmware in WASM</small></div>
        <div className="status">
          <Stat k="modules" v={`${mods.length}/6`} />
          <Stat k="rail budget" v={`${hal.power_allocated_mw}/${hal.power_budget_mw} mW`} />
          <Stat k="backplane" v={`${(hal.bandwidth_allocated_mbps / 1000).toFixed(1)}/${hal.backplane_mbps / 1000} Gb/s`} />
          <Stat k="dt gen" v={hal.dt_generation} />
          <Stat k="mesh" v={`${mesh.summary.online}/${mesh.summary.nodes} nodes`} />
          <Stat k="display" v={disp.state} />
        </div>
      </header>
      <nav>
        {TABS.map(([id, label]) => <button key={id} className={tab === id ? 'active' : ''} onClick={() => setTab(id)}>{label}</button>)}
      </nav>
      <main>
        {tab === 'spine' && <SpinePanel sim={sim} hal={hal} />}
        {tab === 'surface' && <SurfacePanel sim={sim} />}
        {tab === 'power' && <PowerPanel sim={sim} />}
        {tab === 'mesh' && <MeshPanel sim={sim} />}
        {tab === 'display' && <DisplayPanel sim={sim} hal={hal} />}
      </main>
    </div>
  )
}

function Stat({ k, v }: { k: string; v: any }) {
  return <div className="stat"><span>{k}</span><b>{v}</b></div>
}
