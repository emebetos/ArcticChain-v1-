import { useState } from 'react'
import { j, Sim } from '../engine'

const proj = (v: number) => Math.sign(v) * Math.sqrt(Math.abs(v))

export default function MeshPanel({ sim }: { sim: Sim }) {
  const [, force] = useState(0)
  const [src, setSrc] = useState(0)
  const [dst, setDst] = useState(7)
  const [bytes, setBytes] = useState(64)
  const [lora, setLora] = useState(true)
  const [mmw, setMmw] = useState(true)
  const [rep, setRep] = useState<any>(null)
  const m = j(sim.mesh_state())
  const xs = m.nodes.map((n: any) => proj(n.x)), ys = m.nodes.map((n: any) => proj(n.y))
  const [x0, x1, y0, y1] = [Math.min(...xs) - 5, Math.max(...xs) + 5, Math.min(...ys) - 8, Math.max(...ys) + 8]
  const W = 760, H = 420
  const P = (n: any) => [30 + ((proj(n.x) - x0) / (x1 - x0)) * (W - 60), H - 30 - ((proj(n.y) - y0) / (y1 - y0)) * (H - 60)]
  const onPath = (a: number, b: number) => rep?.path && rep.path.some((p: number, i: number) => i > 0 && ((rep.path[i - 1] === a && p === b) || (rep.path[i - 1] === b && p === a)))
  const send = () => setRep(j(sim.mesh_send(src, dst, bytes, lora, mmw)))
  return (
    <div className="grid-2">
      <section className="card tall">
        <h2>Carrier-free mesh: LoRa (long range) + 60 GHz mmWave (beamformed)</h2>
        <svg viewBox={`0 0 ${W} ${H}`} className="mesh">
          {m.walls.map((w: any, i: number) => { const a = P({ x: w.x0, y: w.y0 }), b = P({ x: w.x1, y: w.y1 }); return <line key={i} x1={a[0]} y1={a[1]} x2={b[0]} y2={b[1]} className="wall" /> })}
          {m.links.map((l: any, i: number) => {
            const a = P(m.nodes[l.a]), b = P(m.nodes[l.b])
            const mm = l.metrics.phy === 'MmWave'
            const hot = onPath(l.a, l.b) && rep.hops.some((h: any) => h.phy === l.metrics.phy && ((h.from === l.a && h.to === l.b) || (h.from === l.b && h.to === l.a)))
            return <line key={i} x1={a[0]} y1={a[1] + (mm ? -2 : 2)} x2={b[0]} y2={b[1] + (mm ? -2 : 2)} stroke={mm ? '#4fc3f7' : '#e3b341'} strokeDasharray={mm ? undefined : '4 4'} strokeWidth={hot ? 4 : 1} opacity={hot ? 1 : 0.45} />
          })}
          {m.nodes.map((n: any) => {
            const [x, y] = P(n)
            return (
              <g key={n.index} className="node" onClick={() => { sim.mesh_toggle(n.index); setRep(null); force(v => v + 1) }}>
                <circle cx={x} cy={y} r={n.index === src || n.index === dst ? 11 : 8} fill={!n.online ? '#333' : n.index === src ? '#3fb37f' : n.index === dst ? '#ff6b6b' : '#1d4f78'} stroke="#cfe8ff" />
                <text x={x} y={y - 15} textAnchor="middle" className="legend">{n.name}</text>
                <text x={x} y={y + 24} textAnchor="middle" className="tick">{n.id}{n.mmwave ? '' : ' · LoRa only'}</text>
              </g>
            )
          })}
        </svg>
        <p className="hint">Square-root distance scale; the farmhouse is about 7.7 km out. <span style={{ color: '#4fc3f7' }}>━</span> mmWave · <span style={{ color: '#e3b341' }}>┅</span> LoRa · grey lines are walls. Click a node to take it offline or bring it back; the signed link-state database re-converges.</p>
      </section>
      <section className="card">
        <h2>Send an end-to-end encrypted envelope</h2>
        <div className="btns">
          <label>from <select value={src} onChange={e => setSrc(+e.target.value)}>{m.nodes.map((n: any) => <option key={n.index} value={n.index}>{n.name}</option>)}</select></label>
          <label>to <select value={dst} onChange={e => setDst(+e.target.value)}>{m.nodes.map((n: any) => <option key={n.index} value={n.index}>{n.name}</option>)}</select></label>
          <label>payload <select value={bytes} onChange={e => setBytes(+e.target.value)}>
            <option value={64}>64 B text</option><option value={4096}>4 KB photo thumb</option><option value={5000000}>5 MB video</option></select></label>
        </div>
        <div className="btns">
          <label className="check"><input type="checkbox" checked={lora} onChange={e => setLora(e.target.checked)} /> LoRa</label>
          <label className="check"><input type="checkbox" checked={mmw} onChange={e => setMmw(e.target.checked)} /> mmWave</label>
          <button className="primary" onClick={send}>Route &amp; send</button>
          <button onClick={() => { sim.mesh_reset(); setRep(null); force(v => v + 1) }}>Reset mesh</button>
        </div>
        {rep && (
          <div className={`report ${rep.delivered ? 'ok' : 'bad'}`}>
            {rep.delivered ? <>Delivered in <b>{fmtMs(rep.latency_ms)}</b> over {rep.hops.length} hop(s). Plaintext intact: {String(rep.plaintext_matches)}. Envelope {rep.envelope_bytes.toLocaleString()} B.</> : <>Not delivered: {rep.error}</>}
          </div>
        )}
        {rep?.hops?.length > 0 && (
          <table className="list"><thead><tr><th>hop</th><th>phy</th><th>rate</th><th>cost</th><th>beam / SF</th><th>relay sig ✓</th><th>relay can read?</th></tr></thead><tbody>
            {rep.hops.map((h: any, i: number) => <tr key={i}>
              <td>{m.nodes[h.from].name} → {m.nodes[h.to].name}</td><td>{h.phy}</td><td>{fmtRate(h.rate_bps)}</td><td>{fmtMs(h.cost_ms)}</td>
              <td>{h.sector != null ? `sector ${h.sector}/32` : `SF${h.sf}`}</td><td>{h.to === rep.path[rep.path.length - 1] ? '—' : h.relay_signature_ok ? 'yes' : 'NO'}</td><td>{h.to === rep.path[rep.path.length - 1] ? 'recipient' : h.relay_could_decrypt ? 'YES' : 'no'}</td>
            </tr>)}
          </tbody></table>
        )}
        <p className="hint">Each node signs an Ed25519 link-state advert, and a link is only used if both ends advertise it. Payloads are sealed with X25519 + ChaCha20-Poly1305 and signed by the sender, so relays can verify them but cannot read them. Routing is payload-aware: a small SOS can ride LoRa to the farmhouse, while 5 MB of video only moves over mmWave hops.</p>
      </section>
    </div>
  )
}

const fmtMs = (ms: number) => (ms > 60000 ? `${(ms / 60000).toFixed(1)} min` : ms > 1000 ? `${(ms / 1000).toFixed(2)} s` : `${ms.toFixed(1)} ms`)
const fmtRate = (b: number) => (b > 1e9 ? `${(b / 1e9).toFixed(2)} Gb/s` : b > 1e6 ? `${(b / 1e6).toFixed(0)} Mb/s` : `${(b / 1e3).toFixed(2)} kb/s`)
