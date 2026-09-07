import { useEffect, useMemo, useRef, useState } from 'react'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faMagnifyingGlass, faPhone, faXmark, faArrowRight, faChartPie,
  faList, faSpinner, faInbox,
} from '@fortawesome/free-solid-svg-icons'
import { fetchLeadsByIds } from '../../api'
import { EmptyState, Skeleton } from '../ui/States'
import { fmtDateTime } from '../../utils/datetime'
import { stageColor, LINK_LABEL } from './layout'

const PAGE = 100

/**
 * Tanlangan tugun yoki o'tishning lidlari.
 *
 * Daraxt javobi faqat ID'larni olib keladi (bir tugunda mingta lid bo'lishi
 * mumkin — hammasini oldindan yuklash brauzerni bo'g'ib qo'yardi). To'liq
 * kartalar foydalanuvchi bosgandan keyin, 100 talik bo'laklarda olinadi.
 */
export default function TreeDetailPanel({ selection, onClear, onOpenLead }) {
  const [tab, setTab] = useState('leads')
  const [rows, setRows] = useState([])
  const [loaded, setLoaded] = useState(0)
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState(null)
  const [q, setQ] = useState('')
  const [debouncedQ, setDebouncedQ] = useState('')
  const reqId = useRef(0)

  const ids = selection?.lead_ids || []

  useEffect(() => {
    const t = setTimeout(() => setDebouncedQ(q.trim().toLowerCase()), 250)
    return () => clearTimeout(t)
  }, [q])

  useEffect(() => {
    setRows([]); setLoaded(0); setErr(null); setQ(''); setTab('leads')
    if (ids.length) load(0, true)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selection?.id, selection?.key])

  async function load(from, reset = false) {
    const mine = ++reqId.current
    setLoading(true); setErr(null)
    try {
      const slice = ids.slice(from, from + PAGE)
      const data = await fetchLeadsByIds(slice)
      if (reqId.current !== mine) return          // eskirgan javob — tashlab yuboramiz
      setRows(prev => reset ? data : [...prev, ...data])
      setLoaded(from + slice.length)
    } catch (e) {
      if (reqId.current === mine) setErr(e.message)
    } finally {
      if (reqId.current === mine) setLoading(false)
    }
  }

  const filtered = useMemo(() => {
    if (!debouncedQ) return rows
    return rows.filter(l =>
      (l.full_name || '').toLowerCase().includes(debouncedQ) ||
      (l.phone || '').includes(debouncedQ) ||
      (l.phone_display || '').includes(debouncedQ))
  }, [rows, debouncedQ])

  if (!selection) {
    return (
      <div className="tree-panel is-empty">
        <EmptyState
          compact icon={faList}
          title="Tugun yoki chiziqni tanlang"
          description="Daraxtdagi bosqichni bosing — o'sha bosqichga yetib kelgan lidlar shu yerda ochiladi. Chiziqni bossangiz — aynan o'sha o'tishni bajargan lidlar."
        />
      </div>
    )
  }

  const isTransition = selection.type === 'transition'
  const title = isTransition ? `${selection.from_name} → ${selection.to_name}` : selection.name
  const tone = isTransition
    ? undefined
    : stageColor(selection.color, selection.kind)

  return (
    <div className="tree-panel">
      <div className="tp-head">
        <div className="tp-title">
          {isTransition ? (
            <span className={`tp-flow tone-${selection.kind}`}>
              {selection.from_name} <FontAwesomeIcon icon={faArrowRight} /> {selection.to_name}
            </span>
          ) : (
            <span className="tp-stage">
              <span className="tp-dot" style={{ background: tone }} aria-hidden="true" />
              {title}
            </span>
          )}
          {/* Foiz DOIM izohlanadi — "46.2%" o'zi hech narsani anglatmaydi. */}
          <div className="tp-sub">
            {selection.count.toLocaleString('uz-UZ')} ta lid
            {isTransition ? (
              <> · <strong>{selection.percent}%</strong> — {selection.from_name} bosqichiga
                yetgan lidlardan</>
            ) : (
              <> · <strong>{selection.percent}%</strong> — bu oy kelgan barcha lidlardan</>
            )}
          </div>
          {isTransition && (
            <div className="tp-kind">{LINK_LABEL[selection.tone || selection.kind]}</div>
          )}
        </div>
        <button className="btn-icon" onClick={onClear} aria-label="Filterni tozalash" title="Filterni tozalash">
          <FontAwesomeIcon icon={faXmark} />
        </button>
      </div>

      <div className="tp-tabs" role="tablist">
        <button role="tab" aria-selected={tab === 'leads'}
          className={tab === 'leads' ? 'is-active' : ''} onClick={() => setTab('leads')}>
          <FontAwesomeIcon icon={faList} /> Lidlar
        </button>
        <button role="tab" aria-selected={tab === 'stats'}
          className={tab === 'stats' ? 'is-active' : ''} onClick={() => setTab('stats')}>
          <FontAwesomeIcon icon={faChartPie} /> Statistika
        </button>
      </div>

      {tab === 'stats' ? (
        <TransitionStats selection={selection} rows={rows} loaded={loaded} total={ids.length} />
      ) : (
        <>
          <div className="tp-search">
            <FontAwesomeIcon icon={faMagnifyingGlass} />
            <input
              className="field" value={q} onChange={e => setQ(e.target.value)}
              placeholder="Ism yoki telefon bo'yicha qidirish"
              aria-label="Lidlar ichida qidirish"
            />
          </div>

          {err && <div className="tp-error">Lidlarni yuklab bo'lmadi. <button className="link-btn" onClick={() => load(0, true)}>Qayta urinish</button></div>}

          {loading && !rows.length ? (
            <div className="tp-list">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="tp-lead"><Skeleton height={38} /></div>
              ))}
            </div>
          ) : filtered.length === 0 ? (
            <EmptyState compact brand={false} icon={faInbox}
              title={debouncedQ ? 'Topilmadi' : 'Lid yo\'q'}
              description={debouncedQ ? 'Qidiruv shartiga mos lid yo\'q' : undefined} />
          ) : (
            <ul className="tp-list">
              {filtered.map(l => (
                <li key={l.id}>
                  <button className="tp-lead" onClick={() => onOpenLead(l)}
                    aria-label={`${l.full_name} — lid kartasini ochish`}>
                    <span className="tp-lead-main">
                      <span className="tp-lead-name">{l.full_name}</span>
                      <span className="tp-lead-meta">
                        {l.phone_display || l.phone}
                        {l.source_name && <> · {l.source_name}</>}
                      </span>
                    </span>
                    <span className="tp-lead-side">
                      {l.stage_name && (
                        <span className="tp-lead-stage"
                          style={{ '--s': stageColor(l.stage_color, l.stage_kind) }}>
                          {l.stage_name}
                        </span>
                      )}
                      <span className="tp-lead-date">{fmtDateTime(l.created_at)}</span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}

          <div className="tp-foot">
            <span className="muted">
              {loaded.toLocaleString('uz-UZ')} / {ids.length.toLocaleString('uz-UZ')} ko'rsatildi
            </span>
            {loaded < ids.length && (
              <button className="button secondary" onClick={() => load(loaded)} disabled={loading}>
                {loading ? <><FontAwesomeIcon icon={faSpinner} className="kc-spin" /> Yuklanmoqda</> : 'Ko\'proq yuklash'}
              </button>
            )}
          </div>
        </>
      )}
    </div>
  )
}

/** Tanlangan to'plamning kichik kesimi — yuklangan lidlar asosida. */
function TransitionStats({ selection, rows, loaded, total }) {
  const bySource = useMemo(() => {
    const m = new Map()
    for (const l of rows) {
      const k = l.source_name || "Ko'rsatilmagan"
      m.set(k, (m.get(k) || 0) + 1)
    }
    return [...m.entries()].sort((a, b) => b[1] - a[1])
  }, [rows])

  const byOwner = useMemo(() => {
    const m = new Map()
    for (const l of rows) {
      const k = l.claimed_by_name || l.created_by_name || "Biriktirilmagan"
      m.set(k, (m.get(k) || 0) + 1)
    }
    return [...m.entries()].sort((a, b) => b[1] - a[1])
  }, [rows])

  const overdue = rows.filter(l => l.is_overdue).length

  return (
    <div className="tp-stats">
      <div className="tp-stat-row">
        <span>Jami</span><strong>{selection.count.toLocaleString('uz-UZ')}</strong>
      </div>
      <div className="tp-stat-row">
        <span>{selection.type === 'transition'
          ? `${selection.from_name} bosqichidan ulush`
          : 'Kogortadan ulush'}</span>
        <strong>{selection.percent}%</strong>
      </div>
      <div className="tp-stat-row">
        <span>Muddati o'tgan aloqa</span><strong>{overdue}</strong>
      </div>
      {loaded < total && (
        <p className="muted tp-stat-note">
          Kesimlar yuklangan {loaded} ta liddan hisoblangan (jami {total}).
          To'liq ko'rish uchun "Ko'proq yuklash"ni bosing.
        </p>
      )}
      <h5>Manba bo'yicha</h5>
      {bySource.length === 0 ? <p className="muted">Ma'lumot yo'q</p> : (
        <ul className="tp-mini">
          {bySource.slice(0, 8).map(([name, n]) => (
            <li key={name}><span>{name}</span><strong>{n}</strong></li>
          ))}
        </ul>
      )}
      <h5>Mas'ul bo'yicha</h5>
      {byOwner.length === 0 ? <p className="muted">Ma'lumot yo'q</p> : (
        <ul className="tp-mini">
          {byOwner.slice(0, 8).map(([name, n]) => (
            <li key={name}><span>{name}</span><strong>{n}</strong></li>
          ))}
        </ul>
      )}
    </div>
  )
}
