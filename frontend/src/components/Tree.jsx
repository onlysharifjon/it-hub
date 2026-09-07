import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { toast } from 'react-hot-toast'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faSitemap, faChevronLeft, faChevronRight, faExpand, faCompress,
  faMagnifyingGlassPlus, faMagnifyingGlassMinus, faArrowsRotate,
  faFileArrowDown, faUsers, faPercent, faClock, faMoneyBillWave,
  faXmark, faCircleExclamation,
} from '@fortawesome/free-solid-svg-icons'
import { fetchConversionTree, fetchLeadActivities, addLeadNote } from '../api'
import KpiCard from './ui/KpiCard'
import { EmptyState, ErrorState, CardSkeleton, Skeleton } from './ui/States'
import ConversionTree from './tree/ConversionTree'
import TreeMobile from './tree/TreeMobile'
import TreeLegend from './tree/TreeLegend'
import TreeDetailPanel from './tree/TreeDetailPanel'
import { ConversionInsights, SourceConversion, OperatorConversion } from './tree/ConversionPanels'
import { LINK_LABEL, findMainPath } from './tree/layout'
import { LeadDrawer } from './Leads'
import { tashkentNow } from '../utils/datetime'

const MONTHS = [
  'Yanvar', 'Fevral', 'Mart', 'Aprel', 'May', 'Iyun',
  'Iyul', 'Avgust', 'Sentabr', 'Oktabr', 'Noyabr', 'Dekabr',
]
const money = (n) => Number(n || 0).toLocaleString('uz-UZ')

/**
 * Tree — konversiya oqimi tahlili.
 *
 * Leads > Analitika tez ko'rinish beradi ("hozir qayerda nechta lid bor").
 * Tree esa boshqa savolga javob beradi: "lidlar QAYERDA yo'qoladi va
 * QAYSI yo'l bilan to'lovga yetadi". Shuning uchun u alohida ish maydoni,
 * mavjud analitikaning o'rnini bosmaydi.
 *
 * Ma'lumot semantikasi (backend'da ham shu tarzda hisoblanadi):
 *   kogorta  — tanlangan OYDA yaratilgan lidlar;
 *   tugun    — shu bosqichga YETIB KELGAN kogorta lidlari soni;
 *   o'tish   — kogorta lidlarining bosqich o'zgarishlari (vaqtdan qat'i nazar);
 *   tushum   — konversiya bo'lgan lidlarga bog'langan talabalarning to'lovlari.
 */
/** Mobil ekran — grafik o'rniga soddalashtirilgan tik oqim ko'rsatiladi. */
function useIsNarrow(px = 760) {
  const [narrow, setNarrow] = useState(
    () => typeof window !== 'undefined' && window.matchMedia(`(max-width:${px}px)`).matches)
  useEffect(() => {
    const mq = window.matchMedia(`(max-width:${px}px)`)
    const on = e => setNarrow(e.matches)
    mq.addEventListener('change', on)
    setNarrow(mq.matches)
    return () => mq.removeEventListener('change', on)
  }, [px])
  return narrow
}

export default function Tree({ currentUser }) {
  const now = tashkentNow()
  const [month, setMonth] = useState(now.getMonth() + 1)
  const [year, setYear] = useState(now.getFullYear())
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState(null)
  const [selection, setSelection] = useState(null)
  const [zoom, setZoom] = useState(1)
  const [full, setFull] = useState(false)
  const [openLead, setOpenLead] = useState(null)
  const [leadActivities, setLeadActivities] = useState([])
  const isNarrow = useIsNarrow()
  const [showMinor, setShowMinor] = useState(false)
  const scrollRef = useRef(null)
  const [availWidth, setAvailWidth] = useState(0)

  // Konteyner kengligini kuzatamiz — grafik unga moslanadi.
  useEffect(() => {
    const el = scrollRef.current
    if (!el || typeof ResizeObserver === 'undefined') return
    const ro = new ResizeObserver(([e]) => setAvailWidth(e.contentRect.width - 32))
    ro.observe(el)
    return () => ro.disconnect()
  }, [full, isNarrow, loading])

  const load = useCallback(async () => {
    setLoading(true); setErr(null)
    try {
      const d = await fetchConversionTree(month, year)
      setData(d)
      setSelection(null)
    } catch (e) {
      setErr(e.message)
      setData(null)
    } finally {
      setLoading(false)
    }
  }, [month, year])

  useEffect(() => { load() }, [load])

  // Fullscreen — Escape bilan chiqish (§48).
  useEffect(() => {
    if (!full) return
    const onKey = (e) => { if (e.key === 'Escape') setFull(false) }
    window.addEventListener('keydown', onKey)
    document.body.style.overflow = 'hidden'
    return () => { window.removeEventListener('keydown', onKey); document.body.style.overflow = '' }
  }, [full])

  function shiftMonth(delta) {
    let m = month + delta, y = year
    if (m < 1) { m = 12; y -= 1 }
    if (m > 12) { m = 1; y += 1 }
    setMonth(m); setYear(y)
  }

  const selectNode = useCallback((node) => {
    setSelection(prev =>
      prev?.type === 'node' && prev.key === node.key ? null : { type: 'node', ...node })
  }, [])

  const selectTransition = useCallback((link) => {
    setSelection(prev =>
      prev?.type === 'transition' && prev.id === link.id ? null : { type: 'transition', ...link })
  }, [])

  /** Xulosa kartasi bosilganda — tegishli o'tish/tugunni daraxtda tanlaymiz. */
  function focusInsight(ins) {
    if (!data) return
    if (ins.from_key && ins.to_key) {
      const t = data.transitions.find(t => t.from_key === ins.from_key && t.to_key === ins.to_key)
      if (t) setSelection({ type: 'transition', id: `${t.from_key}->${t.to_key}`, ...t })
    } else if (ins.stage_key) {
      const n = data.stages.find(s => s.key === ins.stage_key)
      if (n) setSelection({ type: 'node', ...n })
    }
  }

  async function showLead(lead) {
    setOpenLead(lead)
    setLeadActivities([])
    try { setLeadActivities(await fetchLeadActivities(lead.id)) } catch {}
  }
  async function addNote(leadId, body) {
    await addLeadNote(leadId, body)
    setLeadActivities(await fetchLeadActivities(leadId))
    toast.success("Izoh qo'shildi")
  }

  function exportCsv() {
    if (!data) return
    const rows = [
      ['TREE — konversiya hisoboti'],
      ['Davr', `${MONTHS[month - 1]} ${year}`],
      ['Jami lidlar', data.total_leads],
      ['Konversiya', `${data.conversion_rate}%`],
      ["To'langan", data.won_leads],
      ['Yo\'qotilgan', data.lost_leads],
      ['Ochiq', data.open_leads],
      ["O'rtacha konversiya (kun)", data.avg_conversion_days ?? '—'],
      ['Mediana (kun)', data.median_conversion_days ?? '—'],
      ['Tushum', data.revenue],
      [],
      ['BOSQICHLAR'],
      ['Bosqich', 'Turi', 'Lidlar', 'Foiz'],
      ...data.stages.map(s => [s.name, s.kind, s.count, `${s.percent}%`]),
      [],
      ["O'TISHLAR"],
      ['Qayerdan', 'Qayerga', 'Turi', 'Lidlar', 'Foiz'],
      ...data.transitions.map(t => [t.from_name, t.to_name, LINK_LABEL[t.kind], t.count, `${t.percent}%`]),
      [],
      ['MANBALAR'],
      ['Manba', 'Lidlar', "To'landi", 'Konversiya', 'Tushum'],
      ...data.sources.map(s => [s.name, s.leads, s.won, `${s.conversion}%`, s.revenue]),
    ]
    if (data.can_see_operators && data.operators.length) {
      rows.push([], ['OPERATORLAR'], ['Operator', 'Lidlar', "To'landi", 'Konversiya', 'Tushum'],
        ...data.operators.map(o => [o.name, o.leads, o.won, `${o.conversion}%`, o.revenue]))
    }
    const csv = rows.map(r => r.map(c => {
      const v = String(c ?? '')
      return /[",;\n]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v
    }).join(';')).join('\n')
    // BOM — Excel kirill/lotin harflarini to'g'ri o'qishi uchun.
    const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8;' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `tree-${year}-${String(month).padStart(2, '0')}.csv`
    a.click()
    URL.revokeObjectURL(a.href)
  }

  const years = useMemo(() => {
    const y = now.getFullYear()
    return [y - 2, y - 1, y, y + 1]
  }, [])                                     // eslint-disable-line react-hooks/exhaustive-deps

  const controls = (
    <div className="tree-controls">
      <div className="tree-month" role="group" aria-label="Davrni tanlash">
        <button className="btn-icon" onClick={() => shiftMonth(-1)} aria-label="Oldingi oy">
          <FontAwesomeIcon icon={faChevronLeft} />
        </button>
        <select className="field" value={month} onChange={e => setMonth(Number(e.target.value))}
          aria-label="Oy">
          {MONTHS.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}
        </select>
        <select className="field" value={year} onChange={e => setYear(Number(e.target.value))}
          aria-label="Yil">
          {years.map(y => <option key={y} value={y}>{y}</option>)}
        </select>
        <button className="btn-icon" onClick={() => shiftMonth(1)} aria-label="Keyingi oy">
          <FontAwesomeIcon icon={faChevronRight} />
        </button>
      </div>
      <div className="tree-zoom" role="group" aria-label="Masshtab">
        <button className="btn-icon" onClick={() => setZoom(z => Math.max(0.5, +(z - 0.1).toFixed(2)))}
          aria-label="Kichraytirish"><FontAwesomeIcon icon={faMagnifyingGlassMinus} /></button>
        <span className="tree-zoom-val">{Math.round(zoom * 100)}%</span>
        <button className="btn-icon" onClick={() => setZoom(z => Math.min(1.6, +(z + 0.1).toFixed(2)))}
          aria-label="Kattalashtirish"><FontAwesomeIcon icon={faMagnifyingGlassPlus} /></button>
        <button className="btn-icon" onClick={() => setZoom(1)} aria-label="Masshtabni tiklash"
          title="Tiklash"><FontAwesomeIcon icon={faArrowsRotate} /></button>
      </div>
      <button className="button secondary" onClick={exportCsv} disabled={!data}>
        <FontAwesomeIcon icon={faFileArrowDown} /> Export
      </button>
      <button className="button secondary" onClick={() => setFull(f => !f)}>
        <FontAwesomeIcon icon={full ? faCompress : faExpand} />
        {full ? ' Chiqish' : " To'liq ekran"}
      </button>
    </div>
  )

  // Afsonada faqat HAQIQATAN mavjud bo'lgan ohanglar ko'rsatiladi.
  /* Kichik oqimlar.
     Avgustda 19 ta o'tishning 8 tasi 1–2 ta liddan iborat edi. Ular
     grafikni "elektron plata"ga aylantirardi, lekin hech qanday ma'no
     bermasdi. Shuning uchun ular yig'ib qo'yiladi — YO'Q QILINMAYDI:
     bitta bosish bilan qaytariladi, eksportda esa doim bor.
     Konversiya (`won`) o'tishlari HECH QACHON yashirilmaydi — voronkaning
     butun maqsadi shular. */
  const { shownTransitions, minorCount } = useMemo(() => {
    if (!data) return { shownTransitions: [], minorCount: 0 }
    const all = data.transitions
    if (all.length <= 10) return { shownTransitions: all, minorCount: 0 }
    const threshold = Math.max(2, Math.round(data.total_leads * 0.01))
    const minor = all.filter(t => t.count < threshold && t.kind !== 'won')
    if (showMinor || minor.length === 0) return { shownTransitions: all, minorCount: minor.length }
    const hide = new Set(minor.map(t => `${t.from_key}->${t.to_key}`))
    return {
      shownTransitions: all.filter(t => !hide.has(`${t.from_key}->${t.to_key}`)),
      minorCount: minor.length,
    }
  }, [data, showMinor])

  const tones = useMemo(() => {
    if (!data) return new Set()
    const mainPath = findMainPath(data.stages, shownTransitions)
    const mainSet = new Set(mainPath)
    const idx = new Map(data.stages.map((x, i) => [x.key, i]))
    const set = new Set()
    for (const t of shownTransitions) {
      const adj = mainSet.has(t.from_key) && mainSet.has(t.to_key) &&
        mainPath.indexOf(t.to_key) === mainPath.indexOf(t.from_key) + 1
      set.add(adj && t.kind === 'normal' ? 'main' : t.kind)
    }
    return set
  }, [data, shownTransitions])                 // eslint-disable-line react-hooks/exhaustive-deps

  const treeArea = (
    <div className="tree-stage">
      <div className="tree-stage-head">
        <TreeLegend tones={tones} />
        {minorCount > 0 && (
          <button className={`chip${showMinor ? ' is-on' : ''}`}
            onClick={() => setShowMinor(v => !v)}
            title="1–2 lidli mayda o'tishlar">
            Kichik oqimlar <span>{minorCount}</span>
          </button>
        )}
        {selection && (
          <button className="button secondary sm" onClick={() => setSelection(null)}>
            <FontAwesomeIcon icon={faXmark} /> Filtrni tozalash
          </button>
        )}
      </div>
      <div className={`tree-scroll${isNarrow ? ' is-mobile' : ''}`} ref={scrollRef}>
        {loading ? (
          <div className="tree-skeleton">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} height={92} radius="var(--radius-lg)" />
            ))}
          </div>
        ) : !data || data.total_leads === 0 ? (
          <EmptyState
            icon={faSitemap}
            title="Bu oy uchun lidlar topilmadi"
            description={`${MONTHS[month - 1]} ${year} oyida yaratilgan lid yo'q. Boshqa oyni tanlab ko'ring.`}
          />
        ) : isNarrow ? (
          <TreeMobile
            stages={data.stages} transitions={shownTransitions}
            total={data.total_leads}
            onSelectNode={selectNode} onSelectTransition={selectTransition}
          />
        ) : (
          <ConversionTree
            stages={data.stages}
            transitions={shownTransitions}
            total={data.total_leads}
            availableWidth={availWidth}
            selection={selection}
            onSelectNode={selectNode}
            onSelectTransition={selectTransition}
            zoom={zoom}
          />
        )}
      </div>
    </div>
  )

  if (full) {
    return createPortal(
      <div className="tree-fullscreen" role="dialog" aria-modal="true" aria-label="Tree — to'liq ekran">
        <div className="tree-full-bar">
          <h3><FontAwesomeIcon icon={faSitemap} /> Tree · {MONTHS[month - 1]} {year}</h3>
          <span style={{ flex: 1 }} />
          {controls}
        </div>
        <div className="tree-full-body">
          {treeArea}
          <TreeDetailPanel selection={selection} onClear={() => setSelection(null)} onOpenLead={showLead} />
        </div>
        {openLead && (
          <LeadDrawer
            lead={openLead} stages={[]} activities={leadActivities}
            canMove={false} canDelete={false} canConvert={false}
            currentUser={currentUser} allowNote
            onClose={() => setOpenLead(null)} onNote={addNote}
          />
        )}
      </div>,
      document.body,
    )
  }

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h2><FontAwesomeIcon icon={faSitemap} /> Tree</h2>
          <p className="page-sub">Lid oqimini vizual ko'ring va konversiya jarayonini tahlil qiling</p>
        </div>
      </div>

      {controls}

      {err ? (
        <ErrorState
          title="Conversion ma'lumotlarini yuklashda xatolik yuz berdi"
          onRetry={load}
        />
      ) : (
        <>
          <div className="kpi-grid" style={{ marginTop: 16 }}>
            {loading ? <CardSkeleton count={4} /> : (
              <>
                <KpiCard label="Jami lidlar" icon={faUsers} tone="primary"
                  value={money(data?.total_leads)}
                  sub={`${MONTHS[month - 1]} ${year} · yaratilgan`} />
                <KpiCard label="Konversiya" icon={faPercent} tone="success"
                  value={`${data?.conversion_rate ?? 0}%`}
                  sub={`${money(data?.won_leads)} ta to'landi · ${money(data?.lost_leads)} rad etildi`} />
                <KpiCard label="O'rtacha konversiya" icon={faClock} tone="info"
                  value={data?.avg_conversion_days != null ? `${data.avg_conversion_days} kun` : '—'}
                  sub={data?.median_conversion_days != null ? `mediana ${data.median_conversion_days} kun` : 'hali konversiya yo\'q'} />
                <KpiCard label="To'langan tushum" icon={faMoneyBillWave} tone="accent"
                  value={money(data?.revenue)} unit="so'm"
                  sub={data?.avg_revenue_per_won ? `o'rtacha ${money(data.avg_revenue_per_won)} / lid` : undefined} />
              </>
            )}
          </div>

          {!loading && data && data.won_without_student > 0 && (
            <div className="tree-warn">
              <FontAwesomeIcon icon={faCircleExclamation} />
              <div>
                <strong>{data.won_without_student} ta lid studentga o'tkazilmagan.</strong>
                <span> "To'landi" bosqichiga yetgan, lekin talaba kartasi yaratilmagan —
                  shuning uchun ularning to'lovlari tushumda ko'rinmaydi.</span>
              </div>
            </div>
          )}

          {!loading && data && (
            <ConversionInsights insights={data.insights} onFocus={focusInsight} />
          )}

          <div className="tree-layout">
            {treeArea}
            <TreeDetailPanel selection={selection} onClear={() => setSelection(null)} onOpenLead={showLead} />
          </div>

          {!loading && data && data.total_leads > 0 && (
            <div className="tree-tables">
              <section>
                <h4>Manba bo'yicha konversiya</h4>
                <SourceConversion sources={data.sources} />
              </section>
              {data.can_see_operators && (
                <section>
                  <h4>Operatorlar</h4>
                  <OperatorConversion operators={data.operators} />
                </section>
              )}
            </div>
          )}
        </>
      )}

      {openLead && (
        <LeadDrawer
          lead={openLead} stages={[]} activities={leadActivities}
          canMove={false} canDelete={false} canConvert={false}
          currentUser={currentUser} allowNote
          onClose={() => setOpenLead(null)} onNote={addNote}
        />
      )}
    </div>
  )
}
