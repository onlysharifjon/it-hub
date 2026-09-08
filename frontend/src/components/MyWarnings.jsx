import { useEffect, useState } from 'react'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faTriangleExclamation, faCircleCheck, faClock } from '@fortawesome/free-solid-svg-icons'
import { fetchMyWarnings } from '../api'
import { PageIntro, ViewTabs } from './ui/Workspace'
import { EmptyState, ErrorState, CardSkeleton } from './ui/States'
import Badge from './ui/Badge'
import { fmtDateTime } from '../utils/datetime'

const SEVERITY = { gray: { label: 'Kulrang', variant: 'neutral' }, yellow: { label: 'Sariq', variant: 'warning' }, red: { label: 'Qizil', variant: 'danger' } }

export default function MyWarnings() {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [view, setView] = useState('all')
  const [limit, setLimit] = useState(25)
  async function load() {
    setLoading(true); setError(null)
    try { setItems(await fetchMyWarnings()) } catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }
  useEffect(() => { load() }, [])
  const active = items.filter(w => !w.cancelled_at)
  const rows = items.filter(w => view === 'all' || (view === 'active' ? !w.cancelled_at : w.cancelled_at)).slice().sort((a,b) => new Date(b.created_at) - new Date(a.created_at))
  return <div className="page warning-inbox">
    <PageIntro title="Mening ogohlantirishlarim" description="Shaxsiy ogohlantirishlar va ularning holati." />
    {error ? <ErrorState title="Ogohlantirishlarni yuklab bo‘lmadi" onRetry={load} /> : loading ? <CardSkeleton count={2} /> : <>
      <section className={'warning-status-banner' + (active.length ? ' has-warnings' : '')}><span><FontAwesomeIcon icon={active.length ? faTriangleExclamation : faCircleCheck} /></span><div><h2>{active.length ? `${active.length} ta faol ogohlantirish` : 'Faol ogohlantirish yo‘q'}</h2><p>{active.length ? 'Tafsilotlar va sabablar quyida keltirilgan.' : 'Barcha yangi ogohlantirishlar shu yerda ko‘rinadi.'}</p></div><span className="warning-total">{items.length}<small>jami yozuv</small></span></section>
      <ViewTabs value={view} onChange={v => { setView(v); setLimit(25) }} items={[{ key: 'all', label: 'Barchasi', count: items.length }, { key: 'active', label: 'Faol', count: active.length }, { key: 'cancelled', label: 'Bekor qilingan', count: items.length - active.length }]} />
      {!rows.length ? <EmptyState icon={faCircleCheck} title="Ogohlantirish yo‘q" description={items.length ? 'Tanlangan holat bo‘yicha yozuv topilmadi.' : 'Sizga intizomiy ogohlantirish berilmagan.'} /> : <div className="warning-records">{rows.slice(0,limit).map(w => {
        const severity = SEVERITY[w.severity] || SEVERITY.gray
        return <article className={'warning-record severity-' + w.severity + (w.cancelled_at ? ' is-cancelled' : '')} key={w.id}><header><Badge variant={severity.variant} size="sm">{w.code ? `${w.code} · ` : ''}{severity.label}</Badge><time><FontAwesomeIcon icon={faClock} />{fmtDateTime(w.created_at)}</time></header><p>{w.reason || 'Sabab ko‘rsatilmagan'}</p><footer><span>Mas’ul: <strong>{w.issued_by_name || '—'}</strong></span><span className="warning-record-state">{w.cancelled_at ? 'Bekor qilingan' : 'Faol'}</span></footer></article>
      })}{limit < rows.length && <button className="button secondary" onClick={() => setLimit(n => n + 25)}>Ko‘proq ko‘rsatish</button>}</div>}
    </>}
  </div>
}
