export type Series = { label: string; color: string; data: number[]; dashed?: boolean; axis?: 'left' | 'right'; area?: boolean }

export function Chart({ x, series, height = 220, leftMax, rightMax = 1, leftLabel, rightLabel, xLabel }: {
  x: number[]; series: Series[]; height?: number; leftMax?: number; rightMax?: number; leftLabel?: string; rightLabel?: string; xLabel?: string
}) {
  const W = 760, H = height, pl = 56, pr = 44, pt = 10, pb = 28
  const lmax = leftMax ?? Math.max(1, ...series.filter(s => s.axis !== 'right').flatMap(s => s.data)) * 1.1
  const xmin = x[0] ?? 0, xmax = x[x.length - 1] ?? 1
  const sx = (v: number) => pl + ((v - xmin) / (xmax - xmin || 1)) * (W - pl - pr)
  const sy = (v: number, right: boolean) => pt + (1 - v / (right ? rightMax : lmax)) * (H - pt - pb)
  const ticks = [0, 0.25, 0.5, 0.75, 1]
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="chart">
      {ticks.map(t => (
        <g key={t}>
          <line x1={pl} x2={W - pr} y1={sy(t * lmax, false)} y2={sy(t * lmax, false)} className="grid" />
          <text x={pl - 6} y={sy(t * lmax, false) + 4} textAnchor="end" className="tick">{(t * lmax).toFixed(lmax > 10 ? 0 : 1)}</text>
          {series.some(s => s.axis === 'right') && <text x={W - pr + 6} y={sy(t * rightMax, true) + 4} className="tick">{Math.round(t * rightMax * 100)}%</text>}
        </g>
      ))}
      {Array.from({ length: 7 }, (_, i) => xmin + (i * (xmax - xmin)) / 6).map(v => (
        <text key={v} x={sx(v)} y={H - 8} textAnchor="middle" className="tick">{v.toFixed(0)}</text>
      ))}
      {series.map(s => {
        const right = s.axis === 'right'
        const pts = s.data.map((v, i) => `${sx(x[i])},${sy(v, right)}`).join(' ')
        return (
          <g key={s.label}>
            {s.area && <polygon points={`${sx(xmin)},${sy(0, right)} ${pts} ${sx(xmax)},${sy(0, right)}`} fill={s.color} opacity={0.18} />}
            <polyline points={pts} fill="none" stroke={s.color} strokeWidth={1.6} strokeDasharray={s.dashed ? '5 4' : undefined} />
          </g>
        )
      })}
      {leftLabel && <text x={12} y={H / 2} transform={`rotate(-90 12 ${H / 2})`} textAnchor="middle" className="axis">{leftLabel}</text>}
      {rightLabel && <text x={W - 6} y={H / 2} transform={`rotate(90 ${W - 6} ${H / 2})`} textAnchor="middle" className="axis">{rightLabel}</text>}
      {xLabel && <text x={W / 2} y={H} textAnchor="middle" className="axis">{xLabel}</text>}
      <g transform={`translate(${pl + 8}, ${pt + 6})`}>
        {series.map((s, i) => (
          <g key={s.label} transform={`translate(${i * 128}, 0)`}>
            <rect width={12} height={3} y={4} fill={s.color} />
            <text x={16} y={9} className="legend">{s.label}</text>
          </g>
        ))}
      </g>
    </svg>
  )
}

export function Bar({ value, max, color, label, unit }: { value: number; max: number; color: string; label: string; unit: string }) {
  const pct = Math.min(100, (value / (max || 1)) * 100)
  return (
    <div className="bar">
      <div className="bar-label"><span>{label}</span><span>{value.toLocaleString()} / {max.toLocaleString()} {unit}</span></div>
      <div className="bar-track"><div className="bar-fill" style={{ width: `${pct}%`, background: color }} /></div>
    </div>
  )
}
