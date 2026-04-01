import { useEffect, useState } from 'react'
import { fetchAuditLogs } from '../api'
import DateFilter from './DateFilter'

const ACTION_LABELS = {
  create:    { label: 'Qo\'shildi',         color: '#4ade80' },
  update:    { label: 'Tahrirlandi',         color: '#60a5fa' },
  delete:    { label: 'O\'chirildi',         color: '#f87171' },
  reorder:   { label: 'Tartib o\'zgardi',    color: '#fbbf24' },
  block:     { label: 'Bloklandi',           color: '#f87171' },
  unblock:   { label: 'Blok olib tashlandi', color: '#4ade80' },
  archive:   { label: 'Arxivlandi',          color: '#94a3b8' },
  unarchive: { label: 'Arxivdan chiqarildi', color: '#60a5fa' },
}

function AuditLogPanel({ onClose }) {
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [dateFilter, setDateFilter] = useState({ preset: 'all', date_from: '', date_to: '' })

  useEffect(() => { load(dateFilter) }, [])

  function load(df = dateFilter) {
    setLoading(true)
    setError('')
    fetchAuditLogs({ page_size: 100, date_from: df.date_from || undefined, date_to: df.date_to || undefined })
      .then(r => setLogs(r.items || r))
      .catch(() => setError("Tarixni yuklashda xatolik"))
      .finally(() => setLoading(false))
  }

  function handleDateFilter(df) {
    setDateFilter(df)
    load(df)
  }

  function formatDate(dateStr) {
    return new Date(dateStr).toLocaleString('uz-UZ', {
      day: '2-digit', month: '2-digit', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    })
  }

  function formatValue(jsonStr) {
    if (!jsonStr) return null
    try {
      const obj = JSON.parse(jsonStr)
      return Object.entries(obj)
        .filter(([, v]) => v !== null && v !== '')
        .map(([k, v]) => `${k}: ${v}`)
        .join(' | ')
    } catch {
      return jsonStr
    }
  }

  return (
    <div className="audit-overlay" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="audit-panel">
        <div className="audit-header">
          <div>
            <h3>O'zgarishlar tarixi</h3>
            <p className="muted-sm">So'nggi {logs.length} ta amal</p>
          </div>
          <button className="modal-close" onClick={onClose}>✕</button>
        </div>

        <div style={{ padding: '10px 16px', borderBottom: '1px solid #2a2a2a' }}>
          <DateFilter value={dateFilter} onChange={handleDateFilter} />
        </div>

        <div className="audit-body">
          {loading && <div className="muted">Yuklanmoqda...</div>}
          {error && <div className="error">{error}</div>}
          {!loading && logs.length === 0 && <div className="muted">Hech qanday o'zgarish yo'q</div>}

          {logs.map((log) => {
            const action = ACTION_LABELS[log.action] || { label: log.action, color: '#fff' }
            const newVal = formatValue(log.new_value)
            const oldVal = formatValue(log.old_value)
            return (
              <div key={log.id} className="audit-entry">
                <div className="audit-entry-top">
                  <span className="audit-action" style={{ color: action.color }}>{action.label}</span>
                  <span className="audit-entity">
                    {log.entity_type === 'lesson'   ? `Dars #${log.entity_id}`
                    : log.entity_type === 'student' ? `Talaba #${log.entity_id}`
                    : log.entity_type === 'group'   ? `Guruh #${log.entity_id}`
                    : log.entity_type === 'payment' ? `To'lov #${log.entity_id}`
                    : log.entity_type === 'user'    ? `Foydalanuvchi #${log.entity_id}`
                    : `${log.entity_type} #${log.entity_id}`}
                  </span>
                  <span className="audit-time">{formatDate(log.changed_at)}</span>
                </div>
                <div className="audit-user">
                  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>
                  </svg>
                  {log.changed_by_username}
                </div>
                {newVal && (
                  <div className="audit-diff">
                    {oldVal && <div className="audit-old">← {oldVal}</div>}
                    <div className="audit-new">→ {newVal}</div>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

export default AuditLogPanel
