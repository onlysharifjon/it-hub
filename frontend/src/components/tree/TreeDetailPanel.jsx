import { useEffect, useMemo, useRef, useState } from 'react'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faMagnifyingGlass, faArrowRight, faLayerGroup, faInbox } from '@fortawesome/free-solid-svg-icons'
import { fetchLeadsByIds } from '../../api'
import { EmptyState, ErrorState, Skeleton } from '../ui/States'
import { Initials, ViewTabs } from '../ui/Workspace'
import { fmtDateTime } from '../../utils/datetime'
import { LINK_LABEL } from './layout'

const PAGE = 100
const fmt = n => Number(n || 0).toLocaleString('uz-UZ')
const tally = (rows, field) => {
  const counts = new Map()
  for (const row of rows) { const name = field(row); counts.set(name, (counts.get(name) || 0) + 1) }
  return [...counts].sort((a, b) => b[1] - a[1])
}

export default function TreeDetailPanel({ selection, onOpenLead }) {
  const [tab, setTab] = useState('leads')
  const [rows, setRows] = useState([])
  const [loaded, setLoaded] = useState(0)
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState(null)
  const [q, setQ] = useState('')
  const reqId = useRef(0)
  const ids = selection?.lead_ids || []

  useEffect(() => {
    ++reqId.current
    setRows([]); setLoaded(0); setErr(null); setQ(''); setTab('leads'); setLoading(false)
    if (ids.length) load(0, true)
    return () => { ++reqId.current }
    // Each selection has its own paginated request; ignore responses after it closes or changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selection?.id, selection?.key])

  async function load(from, reset = false) {
    const mine = ++reqId.current
    setLoading(true); setErr(null)
    try {
      const slice = ids.slice(from, from + PAGE)
      const data = await fetchLeadsByIds(slice)
      if (reqId.current !== mine) return
      setRows(prev => reset ? data : [...prev, ...data])
      setLoaded(from + slice.length)
    } catch (e) { if (reqId.current === mine) setErr(e.message) }
    finally { if (reqId.current === mine) setLoading(false) }
  }

  const filtered = useMemo(() => {
    const query = q.trim().toLowerCase()
    return rows.filter(l => !query || [l.full_name, l.phone, l.phone_display].some(v => String(v || '').toLowerCase().includes(query)))
  }, [rows, q])
  if (!selection) return null
  const transition = selection.type === 'transition'
  const title = transition ? `${selection.from_name} → ${selection.to_name}` : selection.name

  return <div className={'tree-panel map-detail kind-' + selection.kind}>
    <header className="map-detail-hero">
      <span className="map-detail-icon"><FontAwesomeIcon icon={transition ? faArrowRight : faLayerGroup} /></span>
      <div className="map-detail-heading"><span>{transition ? 'Bosqichlararo o‘tish' : 'Bosqich tafsilotlari'}</span><h2>{title}</h2>{transition && <p>{LINK_LABEL[selection.tone || selection.kind]}</p>}</div>
      <div className="map-detail-count"><strong>{fmt(selection.count)}</strong><span>ta lid</span><b>{selection.percent}%</b></div>
      <p className="map-detail-explanation">{transition ? `${selection.from_name} bosqichiga yetgan lidlardan` : 'Tanlangan oyda kelgan barcha lidlardan'}</p>
    </header>
    <ViewTabs label="Bosqich tafsilotlari" value={tab} onChange={setTab} items={[{ key: 'leads', label: 'Lidlar', count: ids.length }, { key: 'stats', label: 'Statistika' }]} />
    {err && <ErrorState compact title="Lidlarni yuklab bo‘lmadi" onRetry={() => load(loaded, loaded === 0)} />}
    {tab === 'leads' ? <>
      <label className="map-detail-search"><FontAwesomeIcon icon={faMagnifyingGlass} /><input value={q} onChange={e => setQ(e.target.value)} placeholder="Ism yoki telefon orqali qidirish" aria-label="Lidlar ichida qidirish" /></label>
      {loading && !rows.length ? <div className="map-lead-list">{[0,1,2,3].map(i => <Skeleton key={i} height={88} />)}</div> : !filtered.length ? <EmptyState compact brand={false} icon={faInbox} title={q ? 'Lid topilmadi' : 'Bu bosqichda lid yo‘q'} description={q ? 'Boshqa ism yoki telefonni kiriting.' : 'Lidlar shu bosqichga yetganda bu yerda ko‘rinadi.'} /> : <div className="map-lead-list">
        {filtered.map(l => <button type="button" className="map-lead-card" key={l.id} onClick={() => onOpenLead(l)} aria-label={`${l.full_name} — lid kartasini ochish`}>
          <Initials name={l.full_name} /><span className="map-lead-info"><strong>{l.full_name}</strong><span>{l.phone_display || l.phone}</span><small>{l.source_name || 'Manba belgilanmagan'} · {fmtDateTime(l.created_at)}</small></span>
          <span className="map-lead-side">{l.stage_name && <span className={'map-stage-pill kind-' + l.stage_kind}>{l.stage_name}</span>}<FontAwesomeIcon icon={faArrowRight} /></span>
        </button>)}
      </div>}
    </> : <div className="map-breakdown">
      <div className="map-overdue"><span>Muddati o‘tgan aloqa</span><strong>{fmt(rows.filter(l => l.is_overdue).length)}</strong></div>
      {loaded < ids.length && <p className="map-partial-note">Kesimlar yuklangan {fmt(loaded)} ta liddan hisoblangan. Jami {fmt(ids.length)} ta lid.</p>}
      <Breakdown title="Manbalar" rows={tally(rows, l => l.source_name || 'Ko‘rsatilmagan')} total={rows.length} />
      <Breakdown title="Mas’ullar" rows={tally(rows, l => l.claimed_by_name || l.created_by_name || 'Biriktirilmagan')} total={rows.length} />
    </div>}
    <footer className="map-detail-foot"><span>{fmt(loaded)} / {fmt(ids.length)} ko‘rsatildi</span>{loaded < ids.length && <button className="button secondary sm" disabled={loading} onClick={() => load(loaded)}>{loading ? 'Yuklanmoqda…' : 'Ko‘proq yuklash'}</button>}</footer>
  </div>
}

function Breakdown({ title, rows, total }) {
  return <section className="map-breakdown-section"><h3>{title}</h3>{!rows.length ? <p className="muted">Ma’lumot yo‘q</p> : rows.slice(0, 8).map(([name, count]) => <div className="map-breakdown-row" key={name}><div><span>{name}</span><strong>{fmt(count)} <small>{total ? Math.round(count / total * 100) : 0}%</small></strong></div><div className="map-breakdown-track"><i style={{ width: (total ? count / total * 100 : 0) + '%' }} /></div></div>)}</section>
}
