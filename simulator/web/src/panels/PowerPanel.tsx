import { useEffect, useState } from 'react'
import { j, Sim } from '../engine'
import { Chart } from '../Chart'

export default function PowerPanel({ sim }: { sim: Sim }) {
  const [p, setP] = useState({ ambient: 22, couples: 127, mass: 5, cap: 150, days: 2 })
  const [data, setData] = useState<any>(null)
  useEffect(() => { setData(j(sim.harvest_day(p.ambient, p.couples, p.mass, p.cap, p.days))) }, [p, sim])
  if (!data) return null
  const s = data.series
  const x = s.map((r: any) => r.t)
  const sm = data.summary
  const phoneDay = 12000
  const set = (k: string) => (e: any) => setP({ ...p, [k]: +e.target.value })
  return (
    <div className="grid-2">
      <section className="card tall">
        <h2>Energy-harvesting daemon · predictive energy-neutral scheduler</h2>
        <Chart x={x} xLabel="hour" leftLabel="µW" rightLabel="buffer SoC" rightMax={1} series={[
          { label: 'TEG (body heat)', color: '#e0663a', data: s.map((r: any) => r.teg), area: true },
          { label: 'piezo (motion)', color: '#e3b341', data: s.map((r: any) => r.piezo), area: true },
          { label: 'consumption', color: '#4fc3f7', data: s.map((r: any) => r.use) },
          { label: 'buffer SoC', color: '#3fb37f', data: s.map((r: any) => r.soc), axis: 'right', dashed: true },
        ]} />
        <Chart x={x} height={120} xLabel="hour" leftLabel="tasks" series={[
          { label: 'throttled tasks', color: '#ff6b6b', data: s.map((r: any) => r.throttled), area: true },
        ]} leftMax={data.tasks.length} />
        <div className="sliders">
          <label>Ambient <b>{p.ambient} °C</b><input type="range" min={5} max={38} value={p.ambient} onChange={set('ambient')} /></label>
          <label>TEG couples <b>{p.couples}</b><input type="range" min={31} max={511} step={8} value={p.couples} onChange={set('couples')} /></label>
          <label>Piezo proof mass <b>{p.mass} g</b><input type="range" min={1} max={30} value={p.mass} onChange={set('mass')} /></label>
          <label>Solid-state buffer <b>{p.cap} mWh</b><input type="range" min={20} max={1000} step={10} value={p.cap} onChange={set('cap')} /></label>
          <label>Days simulated <b>{p.days}</b><input type="range" min={1} max={7} value={p.days} onChange={set('days')} /></label>
        </div>
      </section>
      <section className="card">
        <h2>Daily energy balance</h2>
        <table className="kv"><tbody>
          <tr><td>harvested / day</td><td><b>{(sm.harvested_mwh / p.days).toFixed(2)} mWh</b></td></tr>
          <tr><td>always-on workload / day</td><td>{(sm.consumed_mwh / p.days).toFixed(2)} mWh</td></tr>
          <tr><td>minimum buffer SoC</td><td>{(sm.min_soc * 100).toFixed(1)} %</td></tr>
          <tr><td>minutes with throttling</td><td>{sm.throttled_minutes}</td></tr>
          <tr><td>typical smartphone / day</td><td>~{phoneDay.toLocaleString()} mWh</td></tr>
          <tr><td>harvest covers</td><td className="warn"><b>{((sm.harvested_mwh / p.days / phoneDay) * 100).toFixed(3)} %</b> of a normal phone day</td></tr>
        </tbody></table>
        <p className="hint">Reality check: body-heat and motion harvesting yield microwatts to about a milliwatt. That runs the always-on tier (RTC, LoRa beacon, spiking-NPU wake-word, e-ink partial refresh). It cannot run a phone, so "zero-charge" is honest only for that tier. Battery blocks on the spine are still the main power source.</p>
        <h3>Workloads (priority order)</h3>
        <table className="list"><thead><tr><th>task</th><th>class</th><th>µW</th><th>NPU</th></tr></thead><tbody>
          {data.tasks.map((t: any) => <tr key={t.name}><td>{t.name}</td><td>{t.class}</td><td>{t.power_uw}</td><td>{t.npu ? 'spiking' : ''}</td></tr>)}
        </tbody></table>
      </section>
    </div>
  )
}
