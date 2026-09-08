import { useEffect, useId, useRef, useState } from 'react'
import { chartScale, linePath } from './chartGeometry'

const number = n => Number(n || 0).toLocaleString('uz-UZ')
const compact = n => new Intl.NumberFormat('en', { notation: 'compact', maximumFractionDigits: 1 }).format(n)

function filledPath(points, zero) {
  const runs = []; let run = []
  for (const point of points) {
    if (point) run.push(point)
    else if (run.length) { runs.push(run); run = [] }
  }
  if (run.length) runs.push(run)
  return runs.map(r => `${linePath(r)} L ${r[r.length - 1].x} ${zero} L ${r[0].x} ${zero} Z`).join(' ')
}

/** A true-size SVG keeps type and strokes crisp as the panel resizes. */
export default function InsightChart({ title, subtitle, data = [], series, defaultSeries, unit = '', footnote, aggregate = 'sum' }) {
  const id = useId().replace(/:/g, '')
  const frame = useRef(null)
  const [width, setWidth] = useState(600)
  const [activeSeries, setActiveSeries] = useState(defaultSeries || series[0].key)
  const [hover, setHover] = useState(null)
  const [pinned, setPinned] = useState(false)
  useEffect(() => {
    if (!frame.current) return
    const observer = new ResizeObserver(([entry]) => setWidth(Math.max(260, entry.contentRect.width)))
    observer.observe(frame.current)
    return () => observer.disconnect()
  }, [])
  useEffect(() => { setHover(null); setPinned(false) }, [data, activeSeries])
  const active = series.find(s => s.key === activeSeries) || series[0]
  const values = data.map(d => ({ value: d[active.key] }))
  const scale = chartScale(values)
  const h = 248, left = 43, right = 17, top = 18, bottom = 32
  const plotW = width - left - right, plotH = h - top - bottom
  const step = plotW / Math.max(1, data.length - 1)
  const x = i => left + (data.length === 1 ? plotW / 2 : i * step)
  const y = n => top + scale.y(n) / 100 * plotH
  const points = data.map((d, i) => d[active.key] == null || !Number.isFinite(Number(d[active.key])) ? null : ({ x: x(i), y: y(d[active.key]) }))
  const known = data.filter(d => d[active.key] != null && Number.isFinite(Number(d[active.key])))
  const total = known.reduce((sum, d) => sum + Number(d[active.key]), 0)
  const last = known[known.length - 1]
  const displayValue = aggregate === 'last' && active.key === 'line' ? last?.[active.key] : total
  const selected = hover == null ? null : data[hover]
  const selectedPoint = hover == null ? null : points[hover]
  const pickAt = e => {
    const box = e.currentTarget.getBoundingClientRect()
    setHover(Math.min(data.length - 1, Math.max(0, Math.round(((e.clientX - box.left) / box.width * width - left) / step))))
  }
  return <section className="insight-panel" style={{ '--chart-ink': active.color }} aria-label={title}>
    <header className="insight-head"><div><h2>{title}</h2><p>{subtitle}</p></div><span className="insight-live"><i />{unit || 'talaba'}</span></header>
    <div className="insight-total"><strong key={`${active.key}-${displayValue}`}>{number(displayValue)}</strong><span>{aggregate === 'last' && active.key === 'line' ? 'davr oxirida' : 'davr bo‘yicha'}</span></div>
    <div className="insight-series" role="group" aria-label="Grafik ko‘rsatkichi">
      {series.map(s => <button key={s.key} type="button" aria-pressed={active.key === s.key} onClick={() => setActiveSeries(s.key)}><i style={{ background: s.color }} />{s.label}</button>)}
    </div>
    <div className="insight-frame" ref={frame} onPointerLeave={() => { if (!pinned) setHover(null) }}>
      {known.length ? <>
        <svg width="100%" height={h} viewBox={`0 0 ${width} ${h}`} aria-hidden="true" key={`${active.key}-${data.map(d => d[active.key]).join(',')}`}>
          <defs><linearGradient id={`${id}-area`} x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={active.color} stopOpacity=".2" /><stop offset="100%" stopColor={active.color} stopOpacity=".005" /></linearGradient><clipPath id={`${id}-reveal`}><rect className="insight-reveal" x={left - 8} y="0" width={plotW + 16} height={h} /></clipPath></defs>
          {scale.ticks.map(t => <g key={t}><line className="insight-grid" x1={left} x2={width - right} y1={y(t)} y2={y(t)} /><text className="insight-axis" x={left - 12} y={y(t) + 4} textAnchor="end">{compact(t)}</text></g>)}
          <g clipPath={`url(#${id}-reveal)`}>
            <path d={filledPath(points, y(0))} fill={`url(#${id}-area)`} />
            <path className="insight-line" d={linePath(points)} fill="none" stroke={active.color} strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
            {points.map((p, i) => p && (i === points.length - 1 || !points[i + 1]) && <g key={i}><circle cx={p.x} cy={p.y} r="6" fill="var(--surface)" /><circle cx={p.x} cy={p.y} r="3.5" fill={active.color} /></g>)}
          </g>
          {data.map((d, i) => (width > 440 || i % 2 === 0 || i === data.length - 1) && <text key={i} className={`insight-axis${hover === i ? ' is-active' : ''}`} x={x(i)} y={h - 7} textAnchor="middle">{d.label}</text>)}
          {selected && <line className="insight-crosshair" x1={x(hover)} x2={x(hover)} y1={top} y2={h - bottom} />}
          {selectedPoint && <g><circle cx={selectedPoint.x} cy={selectedPoint.y} r="8" fill={active.color} opacity=".13" /><circle cx={selectedPoint.x} cy={selectedPoint.y} r="4.5" fill={active.color} stroke="var(--surface)" strokeWidth="2" /></g>}
        </svg>
        <div className="insight-hit" tabIndex={0} role="group" aria-label={`${active.label} grafigi. Oylarni chap va o‘ng tugma bilan tanlang.`} aria-describedby={selected ? `${id}-tip` : undefined}
          onPointerMove={pinned ? undefined : pickAt} onClick={e => { pickAt(e); setPinned(v => !v) }}
          onFocus={() => setHover(Math.max(0, data.length - 1))} onBlur={() => { if (!pinned) setHover(null) }}
          onKeyDown={e => {
            if (e.key === 'Escape') { setPinned(false); setHover(null); return }
            if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(e.key)) return
            e.preventDefault()
            setHover(i => e.key === 'Home' ? 0 : e.key === 'End' ? data.length - 1 : Math.max(0, Math.min(data.length - 1, (i ?? data.length - 1) + (e.key === 'ArrowRight' ? 1 : -1))))
          }} />
        {selected && <div className="insight-tooltip" id={`${id}-tip`} role="tooltip" style={{ left: Math.max(8, Math.min(width - 205, x(hover) - 95)), top: 14 }}><strong>{selected.label}</strong>{series.map(s => <div key={s.key}><span><i style={{ background: s.color }} />{s.label}</span><b>{selected[s.key] == null ? '—' : number(selected[s.key])}</b></div>)}</div>}
      </> : <div className="insight-empty">Bu davr uchun ma’lumot yo‘q</div>}
    </div>
    {footnote && <footer className="insight-foot">{footnote}</footer>}
  </section>
}
