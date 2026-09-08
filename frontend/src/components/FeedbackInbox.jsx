import { PageIntro, Initials, ViewTabs } from './ui/Workspace'
import { useEffect, useState } from 'react'
import { toast } from 'react-hot-toast'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faCommentDots, faCheck, faPhoneSlash, faRotateLeft,
} from '@fortawesome/free-solid-svg-icons'
import { fetchFeedbacks, updateFeedbackStatus } from '../api'
import Badge from './ui/Badge'
import { EmptyState, CardSkeleton } from './ui/States'

const STATUS_META = {
  new:       { label: 'Yangi',                   variant: 'danger'  },
  resolved:  { label: 'Hal qilindi',             variant: 'success' },
  no_answer: { label: 'Ota-onasi javob bermadi', variant: 'warning' },
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
  const [selectedId, setSelectedId] = useState(null)

  useEffect(() => { load() }, [tab])

  async function load() {
    setLoading(true)
    try {
      const next = await fetchFeedbacks(null, tab || undefined)
      setItems(next)
      setSelectedId(id => next.some(item => item.id === id) ? id : null)
    }
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
    <div className="page feedback-studio">
      <PageIntro title="O‘quvchi izohlari" eyebrow="Muloqot va e’tibor" description="Har bir murojaatni ko‘rib chiqing va natijasini belgilang." />
      <ViewTabs items={TABS} value={tab} onChange={v => { setTab(v); setSelectedId(null) }} />
      {loading && <CardSkeleton count={3} height={132} />}
      {!loading && items.length === 0 && (
        <EmptyState
          icon={faCommentDots}
          title={tab === 'new' ? "Yangi izohlar yo'q" : 'Izohlar topilmadi'}
          description={tab === 'new'
            ? "Hammasi ko'rib chiqilgan — yangi murojaat kelganda shu yerda paydo bo'ladi."
            : 'Boshqa holatni tanlab ko\'ring.'}
        />
      )}

      {items.length > 0 && <div className="feedback-desk"><aside className="feedback-queue"><div className="studio-section-head"><h2>Murojaatlar</h2><span>{items.length}</span></div>{items.map(f => <button key={f.id} aria-pressed={(selectedId || items[0]?.id) === f.id} className={(selectedId || items[0]?.id) === f.id ? 'is-selected' : ''} onClick={() => setSelectedId(f.id)}><Initials name={f.student_name} /><span><strong>{f.student_name || 'Talaba'}</strong><p>{f.comment}</p><small>{f.group_name || 'Guruhsiz'} · {fmtDate(f.created_at)}</small></span></button>)}</aside><div className="fb-list">
        {items.filter(f => f.id === (selectedId || items[0]?.id)).map(f => {
          const meta = STATUS_META[f.status] || STATUS_META.new
          const busy = savingId === f.id
          return (
            <article key={f.id} className={`fb-card is-${f.status}`}>
              <header className="fb-head"><Initials name={f.student_name} />
                <strong>{f.student_name || 'Talaba'}</strong>
                {f.group_name && <span className="muted-sm">· {f.group_name}</span>}
                <Badge variant={meta.variant} size="sm" className="fb-status">{meta.label}</Badge>
              </header>

              <p className="fb-comment">{f.comment}</p>

              <div className="fb-meta">
                {f.teacher_name && <>O'qituvchi: {f.teacher_name} · </>}
                {fmtDate(f.created_at)}
                {f.status !== 'new' && f.status_updated_by_name && (
                  <> · Belgiladi: {f.status_updated_by_name} ({fmtDate(f.status_updated_at)})</>
                )}
              </div>

              <footer className="fb-actions">
                {f.status !== 'resolved' && (
                  <button className="button small" disabled={busy} onClick={() => setStatus(f, 'resolved')}>
                    <FontAwesomeIcon icon={faCheck} /> Hal qilindi
                  </button>
                )}
                {f.status !== 'no_answer' && (
                  <button className="button small secondary" disabled={busy} onClick={() => setStatus(f, 'no_answer')}>
                    <FontAwesomeIcon icon={faPhoneSlash} /> Javob bermadi
                  </button>
                )}
                {f.status !== 'new' && (
                  <button className="button small secondary" disabled={busy} onClick={() => setStatus(f, 'new')}>
                    <FontAwesomeIcon icon={faRotateLeft} /> Yangiga qaytarish
                  </button>
                )}
              </footer>
            </article>
          )
        })}
      </div></div>}
    </div>
  )
}
