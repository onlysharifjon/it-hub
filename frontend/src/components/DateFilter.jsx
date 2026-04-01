/**
 * DateFilter — preset tugmalari + bitta kalendarli oraliq tanlash
 * Props:
 *   value:    { preset, date_from, date_to }
 *   onChange: (newValue) => void
 */
import DateRangePicker from './DateRangePicker'

const presets = [
  { key: 'all',   label: 'Barchasi' },
  { key: 'today', label: 'Bugun' },
  { key: 'week',  label: '7 kun' },
  { key: 'month', label: 'Bu oy' },
]

function applyPreset(key) {
  const now = new Date()
  const pad = n => String(n).padStart(2, '0')
  const fmt = d => `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}`

  if (key === 'all')   return { preset: 'all',   date_from: '', date_to: '' }
  if (key === 'today') return { preset: 'today', date_from: fmt(now), date_to: fmt(now) }
  if (key === 'week') {
    const from = new Date(now); from.setDate(now.getDate() - 6)
    return { preset: 'week', date_from: fmt(from), date_to: fmt(now) }
  }
  if (key === 'month') {
    const from = new Date(now.getFullYear(), now.getMonth(), 1)
    return { preset: 'month', date_from: fmt(from), date_to: fmt(now) }
  }
  return { preset: key, date_from: '', date_to: '' }
}

function DateFilter({ value = { preset: 'all', date_from: '', date_to: '' }, onChange }) {
  const current = value || { preset: 'all', date_from: '', date_to: '' }

  function handlePreset(key) {
    onChange(applyPreset(key))
  }

  function handleRange({ date_from, date_to }) {
    onChange({ ...current, preset: 'custom', date_from, date_to })
  }

  return (
    <div className="df-wrap">
      <div className="df-presets">
        {presets.map(p => (
          <button
            key={p.key}
            className={`df-preset${current.preset === p.key ? ' active' : ''}`}
            onClick={() => handlePreset(p.key)}
            type="button"
          >
            {p.label}
          </button>
        ))}
      </div>

      <DateRangePicker
        dateFrom={current.date_from}
        dateTo={current.date_to}
        onChange={handleRange}
      />
    </div>
  )
}

export default DateFilter
