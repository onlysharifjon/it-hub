import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { toast } from 'react-hot-toast'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faSitemap, faChevronLeft, faChevronRight, faExpand, faCompress,
  faMagnifyingGlassPlus, faMagnifyingGlassMinus, faArrowsRotate,
  faFileArrowDown, faUsers, faPercent, faClock, faMoneyBillWave,
  faXmark, faCircleExclamation,
} from '@fortawesome/free-solid-svg-icons'
import { fetchConversionTree, fetchLeadActivities, addLeadNote } from '../api'
import { PageIntro, SummaryRow, ViewTabs } from './ui/Workspace'
import { Drawer } from './ui/Modal'
import Overlay from './ui/Overlay'
import useFocusTrap from './ui/useFocusTrap'
import { EmptyState, ErrorState, CardSkeleton, Skeleton } from './ui/States'
import ConversionCanvas from './tree/ConversionCanvas'
import useCanvasLayout from './tree/useCanvasLayout'
import TreeMobile from './tree/TreeMobile'
import TreeDetailPanel from './tree/TreeDetailPanel'
import { ConversionInsights, SourceConversion, OperatorConversion } from './tree/ConversionPanels'
import { LINK_LABEL } from './tree/layout'
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
export default function Tree({ currentUser }) {
  const now = tashkentNow()
  const [month, setMonth] = useState(now.getMonth() + 1)
  const [year, setYear] = useState(now.getFullYear())
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState(null)
  const [selection, setSelection] = useState(null)
  const canvasLayout = useCanvasLayout('minar:conversion-layout:v1:' + (currentUser?.id ?? 'local'))
  const [mapView, setMapView] = useState(() => window.matchMedia('(max-width:760px)').matches ? 'list' : 'canvas')
  const [full, setFull] = useState(false)
  const fullRef = useRef(null)
  useFocusTrap(full, fullRef, () => setFull(false))
  const [openLead, setOpenLead] = useState(null)
  const [leadActivities, setLeadActivities] = useState([])
  const [showMinor, setShowMinor] = useState(false)
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
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = previousOverflow }
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

  const treeArea = (
    <section className="map-stage">
      <header className="map-stage-bar">
        <div className="map-stage-title"><span><FontAwesomeIcon icon={faSitemap} /></span><div><h2>Konversiya xaritasi</h2><p>{data?.stages.length || 0} bosqich · {shownTransitions.length} o‘tish</p></div></div>
        <div className="map-stage-views">
          {minorCount > 0 && <button className={'chip' + (showMinor ? ' is-on' : '')} onClick={() => setShowMinor(v => !v)} aria-pressed={showMinor}>Kichik oqimlar <span>{minorCount}</span></button>}
          <ViewTabs label="Xarita ko‘rinishi" value={mapView} onChange={setMapView} items={[{ key: 'canvas', label: 'Xarita' }, { key: 'list', label: 'Ro‘yxat' }]} />
        </div>
      </header>
      {loading ? <CardSkeleton count={3} /> : !data || data.total_leads === 0 ? <EmptyState icon={faSitemap} title="Bu oy uchun lidlar topilmadi" description={MONTHS[month - 1] + ' ' + year + ' oyida yaratilgan lid yo‘q. Boshqa oyni tanlang.'} /> : mapView === 'list' ? (
        <div className="map-list"><TreeMobile stages={data.stages} transitions={shownTransitions} total={data.total_leads} onSelectNode={selectNode} onSelectTransition={selectTransition} /></div>
      ) : <ConversionCanvas stages={data.stages} transitions={shownTransitions} total={data.total_leads} selection={selection} onSelectNode={selectNode} onSelectTransition={selectTransition} layout={canvasLayout} />}
      <footer className="map-stage-footer"><div className="map-legend"><span><i />Jarayon</span>{shownTransitions.some(t => t.kind === 'back') && <span><i className="back" />Qayta o‘tish</span>}<span><i className="won" />To‘landi</span><span><i className="lost" />Yo‘qotish</span></div><span>Ctrl + g‘ildirak: masshtab · Shift: katakka tekislash</span></footer>
    </section>
  )

  if (full) {
    return (
      <Overlay ref={fullRef} layer={1100} className="tree-fullscreen" role="dialog" aria-modal="true" aria-label="Tree — to'liq ekran">
        <div className="tree-full-bar">
          <h3><FontAwesomeIcon icon={faSitemap} /> Tree · {MONTHS[month - 1]} {year}</h3>
          <span style={{ flex: 1 }} />
          {controls}
        </div>
        <div className="tree-full-body">{treeArea}</div>
        <Drawer open={!!selection} title="Xarita tafsilotlari" onClose={() => setSelection(null)} width={500}><TreeDetailPanel selection={selection} onClear={() => setSelection(null)} onOpenLead={showLead} /></Drawer>
        {openLead && (
          <LeadDrawer
            lead={openLead} stages={[]} activities={leadActivities}
            canMove={false} canDelete={false} canConvert={false}
            currentUser={currentUser} allowNote
            onClose={() => setOpenLead(null)} onNote={addNote}
          />
        )}
      </Overlay>
    )
  }

  return (
    <div className="page tree-studio map-workspace">
      <PageIntro title="Tree" eyebrow="Konversiya tahlili" description="Aloqalardan natijagacha. Jarayonni o‘zingiz joylashtiring." actions={controls} />
      {err ? (
        <ErrorState
          title="Conversion ma'lumotlarini yuklashda xatolik yuz berdi"
          onRetry={load}
        />
      ) : (
        <>
          {loading ? <CardSkeleton count={4} /> : <SummaryRow items={[
            { label: 'Jami lidlar', value: money(data?.total_leads), sub: MONTHS[month - 1] + ' ' + year + ' da yaratilgan' },
            { label: 'Konversiya', value: (data?.conversion_rate ?? 0) + '%', sub: money(data?.won_leads) + ' to‘landi · ' + money(data?.lost_leads) + ' rad etildi', tone: 'success' },
            { label: 'O‘rtacha konversiya', value: data?.avg_conversion_days ?? '—', unit: 'kun', sub: data?.median_conversion_days != null ? 'Mediana ' + data.median_conversion_days + ' kun' : 'Hali konversiya yo‘q' },
            { label: 'To‘langan tushum', value: money(data?.revenue), unit: 'so‘m', sub: 'Ushbu lidlarga bog‘langan to‘lovlar' },
          ]} />}

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

          <div className="tree-flow-workspace">{treeArea}</div>
          <p className="flow-definition">Foizlar shu oyda kelgan lidlarga nisbatan. Joylashuvni ko‘chirish hisob-kitoblarga ta’sir qilmaydi.</p>
          <Drawer open={!!selection} title="Xarita tafsilotlari" onClose={() => setSelection(null)} width={500}><TreeDetailPanel selection={selection} onClear={() => setSelection(null)} onOpenLead={showLead} /></Drawer>

          {!loading && data && data.total_leads > 0 && (
            <details className="map-reports"><summary>Manbalar va operatorlar tahlili <span>Hisobotlarni ochish</span></summary><ConversionInsights insights={data.insights} onFocus={focusInsight} /><div className="tree-tables">
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
            </div></details>
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
