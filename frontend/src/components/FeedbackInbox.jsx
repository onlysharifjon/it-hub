import { useEffect, useState } from 'react'
import { toast } from 'react-hot-toast'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faCommentDots, faCheck, faPhoneSlash, faRotateLeft,
} from '@fortawesome/free-solid-svg-icons'
import { fetchFeedbacks, updateFeedbackStatus } from '../api'

const STATUS_META = {
  new:       { label: 'Yangi',                 color: '#dc2626', bg: '#fee2e2' },
  resolved:  { label: 'Hal qilindi',           color: '#16a34a', bg: '#dcfce7' },
  no_answer: { label: 'Ota-onasi javob bermadi', color: '#d97706', bg: '#fef3c7' },
}

const TABS = [
  { key: 'new',       label: 'Yangi' },
  { key: 'no_answer', label: 'Javob bermadi' },
  { key: 'resolved',  label: 'Hal qilindi' },
  { key: '',          label: 'Hammasi' },
]

const fmtDate = (s) => s ? new Date(s).toLocaleString('uz-UZ', { dateStyle: 'short', timeStyle: 'short' }) : ''

export default function FeedbackInbox({ currentUser }) {
  const [items, setItems] = useState([])
  const [tab, setTab] = useState('new')
  const [loading, setLoading] = useState(false)
  const [savingId, setSavingId] = useState(null)

  useEffect(() => { load() }, [tab])

  async function load() {
    setLoading(true)
    try { setItems(await fetchFeedbacks(null, tab || undefined)) }
    catch (e) { toast.error(e.message || "Yuklab bo'lmadi") }
    finally { setLoading(false) }
  }

  async function setStatus(item, status) {
    setSavingId(item.id)
    try {
      await updateFeedbackStatus(item.id, status)
      toast.success(status === 'resolved' ? 'Hal qilindi ✓'
        : status === 'no_answer' ? 'Javob bermadi deb belgilandi'
        : 'Yangi holatiga qaytarildi')
      // Sidebar'dagi qizil badge yangilansin
      window.dispatchEvent(new Event('feedbacks-changed'))
      load()
    } catch (e) { toast.error(e.message || 'Xatolik') }
    finally { setSavingId(null) }
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1><FontAwesomeIcon icon={faCommentDots} className="page-icon" /> O'quvchi izohlari</h1>
      </div>

      <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
        {TABS.map(t => (
          <button
            key={t.key}
            className={`button ${tab === t.key ? 'primary' : 'secondary'}`}
            style={{ padding: '6px 14px', fontSize: 13 }}
            onClick={() => setTab(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {loading && <p className="muted">Yuklanmoqda...</p>}
      {!loading && items.length === 0 && (
        <p className="muted">
          {tab === 'new' ? "Yangi izohlar yo'q — hammasi ko'rib chiqilgan 🎉" : "Izohlar topilmadi"}
        </p>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {items.map(f => {
          const meta = STATUS_META[f.status] || STATUS_META.new
          const busy = savingId === f.id
          return (
            <div key={f.id} style={{
              padding: 16, background: 'var(--surface)',
              border: '1px solid var(--border)', borderRadius: 'var(--radius)',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
                <strong>{f.student_name || 'Talaba'}</strong>
                {f.group_name && <span className="muted" style={{ fontSize: 13 }}>· {f.group_name}</span>}
                <span style={{
                  fontSize: 11, fontWeight: 700, padding: '2px 10px', borderRadius: 20,
                  color: meta.color, background: meta.bg, marginLeft: 'auto',
                }}>
                  {meta.label}
                </span>
              </div>
              <p style={{ margin: '0 0 10px', whiteSpace: 'pre-wrap' }}>{f.comment}</p>
              <div className="muted" style={{ fontSize: 12, marginBottom: 10 }}>
                {f.teacher_name && <>O'qituvchi: {f.teacher_name} · </>}
                {fmtDate(f.created_at)}
                {f.status !== 'new' && f.status_updated_by_name && (
                  <> · Belgiladi: {f.status_updated_by_name} ({fmtDate(f.status_updated_at)})</>
                )}
              </div>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                {f.status !== 'resolved' && (
                  <button className="button primary" style={{ padding: '6px 12px', fontSize: 13 }}
                    disabled={busy} onClick={() => setStatus(f, 'resolved')}>
                    <FontAwesomeIcon icon={faCheck} /> Hal qilindi
                  </button>
                )}
                {f.status !== 'no_answer' && (
                  <button className="button secondary" style={{ padding: '6px 12px', fontSize: 13 }}
                    disabled={busy} onClick={() => setStatus(f, 'no_answer')}>
                    <FontAwesomeIcon icon={faPhoneSlash} /> Telefonga javob bermadi
                  </button>
                )}
                {f.status !== 'new' && (
                  <button className="button secondary" style={{ padding: '6px 12px', fontSize: 13 }}
                    disabled={busy} onClick={() => setStatus(f, 'new')}>
                    <FontAwesomeIcon icon={faRotateLeft} /> Yangiga qaytarish
                  </button>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
