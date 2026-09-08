import { useId, useState } from 'react'
import { chartScale, linePath } from './chartGeometry'

const fmtNum = n => Number(n || 0).toLocaleString('uz-UZ')
const compact = n => new Intl.NumberFormat('en', { notation: 'compact', maximumFractionDigits: 1 }).format(n)

export default function WorkspaceChart({
  data = [], height = 220, seriesLabel = '', compareLabel = '', lineLabel = '',
  highlightIndex = -1, valueFormat = compact, tooltipFormat = fmtNum, onBarClick,
  emptyText = "Ma'lumot yo'q",
}) {
  const id = useId()
  const [active, setActive] = useState(null)
  const [focused, setFocused] = useState(false)
  const hasCompare = data.some(d => d.compare != null)
  const hasLine = data.some(d => d.line != null)
  const scale = chartScale(data)
  const points = data.map((d, i) => d.line == null ? null : ({ x: (i + .5) / data.length * 1000, y: scale.y(d.line) * 2 }))
  const selected = active == null ? null : data[active]
  const barStyle = value => {
    const n = Number(value) || 0
    return { top: `${Math.min(scale.y(n), scale.zero)}%`, height: `${Math.abs(scale.y(n) - scale.zero)}%`, transformOrigin: n >= 0 ? 'center bottom' : 'center top' }
  }
  if (!data.length) return <div className="workspace-chart-empty">{emptyText}</div>

  return (
    <div className="workspace-chart" role="group" aria-label={[seriesLabel, compareLabel, lineLabel].filter(Boolean).join(', ') || 'Diagramma'}>
      <div className="workspace-chart-legend">
        <span><i className="series-income" />{seriesLabel || 'Miqdor'}</span>
        {hasCompare && <span><i className="series-compare" />{compareLabel || 'Taqqoslash'}</span>}
        {hasLine && <span><i className="series-line" />{lineLabel || 'Natija'}</span>}
      </div>
      <div className="workspace-chart-frame" style={{ '--chart-height': `${height}px` }}>
        <div className="workspace-chart-axis" aria-hidden="true">
          {scale.ticks.map(t => <span key={t} style={{ top: `${scale.y(t)}%` }}>{valueFormat(t)}</span>)}
        </div>
        <div className="workspace-chart-plot" onMouseLeave={() => { if (!focused) setActive(null) }}>
          <div className="workspace-chart-grid" aria-hidden="true">
            {scale.ticks.map(t => <span key={t} className={t === 0 ? 'is-zero' : ''} style={{ top: `${scale.y(t)}%` }} />)}
          </div>
          <div className="workspace-chart-columns">
            {data.map((d, i) => (
              <button type="button" key={i}
                className={`workspace-chart-column${active === i ? ' is-active' : ''}${i === highlightIndex ? ' is-current' : ''}${onBarClick ? ' is-clickable' : ''}`}
                style={{ '--bar-delay': `${Math.min(i * 35, 350)}ms` }}
                onMouseEnter={() => setActive(i)} onFocus={() => { setFocused(true); setActive(i) }}
                onBlur={() => { setFocused(false); setActive(null) }}
                onClick={onBarClick ? () => onBarClick(d, i) : undefined}
                onKeyDown={e => {
                  if (e.key === 'Escape') { setActive(null); return }
                  const delta = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0
                  if (delta) { e.preventDefault(); e.currentTarget.parentElement.children[(i + delta + data.length) % data.length]?.focus() }
                }}
                aria-label={`${d.label}: ${seriesLabel || 'Miqdor'} ${tooltipFormat(d.value)}${hasCompare ? `, ${compareLabel} ${tooltipFormat(d.compare)}` : ''}${d.line != null ? `, ${lineLabel} ${tooltipFormat(d.line)}` : ''}`}
                aria-describedby={active === i ? id : undefined}>
                <span className="workspace-chart-bar-pair" aria-hidden="true">
                  <span className="workspace-chart-bar series-income" style={barStyle(d.value)} />
                  {hasCompare && <span className="workspace-chart-bar series-compare" style={barStyle(d.compare)} />}
                </span>
                <span className="workspace-chart-x" aria-hidden="true">{d.label}</span>
              </button>
            ))}
          </div>
          {hasLine && <svg className="workspace-chart-line" viewBox="0 0 1000 200" preserveAspectRatio="none" aria-hidden="true">
            <path d={linePath(points)} fill="none" vectorEffect="non-scaling-stroke" pathLength="1" />
            {points.map((p, i) => p && <circle key={i} cx={p.x} cy={p.y} r={active === i ? 4 : 2.5} vectorEffect="non-scaling-stroke" />)}
          </svg>}
          {selected && <div id={id} role="tooltip" className={`workspace-chart-tooltip${active < data.length / 3 ? ' is-start' : active > data.length * 2 / 3 ? ' is-end' : ''}`}
            style={{ left: `${(active + .5) / data.length * 100}%` }}>
            <strong>{selected.label}</strong>
            <span><i className="series-income" />{seriesLabel || 'Miqdor'}<b>{tooltipFormat(selected.value)}</b></span>
            {hasCompare && <span><i className="series-compare" />{compareLabel || 'Taqqoslash'}<b>{tooltipFormat(selected.compare)}</b></span>}
            {selected.line != null && <span><i className="series-line" />{lineLabel || 'Natija'}<b>{tooltipFormat(selected.line)}</b></span>}
          </div>}
        </div>
      </div>
    </div>
  )
}
