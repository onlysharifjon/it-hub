import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'

export function PageIntro({ title, description, eyebrow, actions }) {
  return <header className="page-header studio-intro">
    <div>{eyebrow && <span className="studio-eyebrow">{eyebrow}</span>}<h1>{title}</h1>{description && <p className="page-subtitle">{description}</p>}</div>
    {actions && <div className="header-actions">{actions}</div>}
  </header>
}

export function SummaryRow({ items, label = 'Asosiy ko‘rsatkichlar' }) {
  return <div className="summary-row" role="group" aria-label={label}>
    {items.map((item, index) => {
      const Tag = item.onClick ? 'button' : 'div'
      return <Tag key={item.label} className={`summary-item${item.tone ? ` tone-${item.tone}` : ''}`} onClick={item.onClick} style={{ '--item-index': index }}>
        <span className="summary-label">{item.icon && <FontAwesomeIcon icon={item.icon} />}{item.label}</span>
        <strong>{item.value ?? '—'}{item.unit && <small>{item.unit}</small>}</strong>
        {item.sub && <span className="summary-sub">{item.sub}</span>}
      </Tag>
    })}
  </div>
}

export function ViewTabs({ items, value, onChange, label = 'Ko‘rinish' }) {
  return <div className="studio-tabs" role="tablist" aria-label={label} onKeyDown={e => {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(e.key)) return
    e.preventDefault()
    const current = items.findIndex(item => item.key === value)
    const index = e.key === 'Home' ? 0 : e.key === 'End' ? items.length - 1 : (current + (e.key === 'ArrowRight' ? 1 : items.length - 1)) % items.length
    onChange(items[index].key)
    e.currentTarget.children[index]?.focus()
  }}>
    {items.map(item => <button key={item.key} type="button" role="tab" aria-selected={item.key === value} tabIndex={item.key === value ? 0 : -1} className={item.key === value ? 'is-active' : ''} onClick={() => onChange(item.key)}>
      {item.icon && <FontAwesomeIcon icon={item.icon} />}{item.label}{item.count != null && <span>{item.count}</span>}
    </button>)}
  </div>
}

export function Initials({ name = '', className = '' }) {
  return <span className={`studio-avatar ${className}`} aria-hidden="true">{String(name).trim().split(/\s+/).filter(Boolean).slice(0, 2).map(n => n[0]).join('').toUpperCase() || '—'}</span>
}

export function ProgressRing({ value = 0, label, size = 88 }) {
  const pct = Math.min(100, Math.max(0, Number(value) || 0))
  return <div className="studio-ring" style={{ width: size, height: size }} role="img" aria-label={`${label || 'Bajarildi'}: ${Math.round(pct)}%`}>
    <svg viewBox="0 0 100 100" aria-hidden="true"><circle cx="50" cy="50" r="43" /><circle className="studio-ring-value" cx="50" cy="50" r="43" pathLength="100" strokeDasharray={`${pct} 100`} /></svg>
    <strong>{Math.round(pct)}<small>%</small></strong>
  </div>
}
