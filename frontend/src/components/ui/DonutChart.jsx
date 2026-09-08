const COLORS = { success: 'var(--viz-1)', danger: 'var(--danger)', primary: 'var(--viz-3)', warning: 'var(--viz-4)' }

export default function DonutChart({ segments = [], value, label, format = String }) {
  const total = segments.reduce((n, s) => n + Math.max(0, Number(s.value) || 0), 0)
  let offset = 0
  return <div className="workspace-donut">
    <div className="workspace-donut-figure">
      <svg viewBox="0 0 200 200" role="img" aria-label={segments.map(s => `${s.label}: ${format(s.value)}`).join(', ')}>
        <circle cx="100" cy="100" r="80" fill="none" stroke="var(--viz-track)" strokeWidth="17" />
        {segments.map((s, i) => {
          const part = total ? Math.max(0, Number(s.value) || 0) / total * 100 : 0
          const start = offset
          offset += part
          return part > 0 && <circle key={i} cx="100" cy="100" r="80" pathLength="100" fill="none" stroke={COLORS[s.tone] || COLORS.primary} strokeWidth="17" strokeDasharray={`${part} ${100 - part}`} strokeDashoffset={-start} transform="rotate(-90 100 100)" />
        })}
      </svg>
      <div className="workspace-donut-center" aria-hidden="true"><strong>{value}</strong><span>{label}</span></div>
    </div>
    <div className="workspace-donut-legend">
      {segments.map((s, i) => <div key={i}><span><i style={{ background: COLORS[s.tone] || COLORS.primary }} />{s.label}</span><strong>{format(s.value)}</strong></div>)}
    </div>
  </div>
}
