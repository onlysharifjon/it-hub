import LeadBoard from './LeadBoard'
import { PageIntro, SummaryRow, Initials, ViewTabs } from './ui/Workspace'
import Overlay from './ui/Overlay'
import { useEffect, useState, useRef, useMemo, Fragment } from 'react'
import { toast } from 'react-hot-toast'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faBullseye, faPlus, faMagnifyingGlass, faPhone, faCircle,
  faPen, faTrash, faTableColumns, faList, faSliders, faXmark,
  faArrowUp, faArrowDown, faClockRotateLeft, faChartPie,
  faBell, faCheck, faClock, faTriangleExclamation,
  faInbox, faHandHolding, faShareNodes, faLink, faCopy, faClipboardList,
  faCommentDots, faSpinner, faArrowRotateRight, faUserPlus, faBellSlash,
  faHourglassHalf, faPaperPlane, faArrowDownWideShort, faArrowUpWideShort,
} from '@fortawesome/free-solid-svg-icons'
import {
  fetchLeads, createLead, updateLead, checkLeadPhone, addLeadNote, convertLead, moveLeadStage, deleteLead,
  fetchLeadStages, createLeadStage, updateLeadStage, reorderLeadStages, deleteLeadStage,
  fetchLeadSources, fetchLeadActivities, fetchLeadAnalytics, fetchCommentStats,
  fetchReminders, createReminder, updateReminder, deleteReminder,
  claimLead, releaseLead, shareLead, fetchGroups, fetchTariffs,
  fetchIntakeForms, createIntakeForm, updateIntakeForm, deleteIntakeForm,
} from '../api'
import { parseTs, fmtDateTime, fmtTime, fmtRelative, fmtDayLabel, dayKey, inputToIso, isoToInput } from '../utils/datetime'
import useConfirm from './ui/useConfirm'
import { STAGE_OPTIONS, STAGE_LABELS } from '../constants/domain'
import useFocusTrap from './ui/useFocusTrap'
import DataTable from './ui/DataTable'
import Modal from './ui/Modal'
import Badge from './ui/Badge'
import { Input, Textarea, Select } from './ui/Field'
import { BarChart } from './ui/Chart'
import { EmptyState } from './ui/States'

// Bosqich rangi kaliti → hex
// Bosqich rangi kaliti → CSS o'zgaruvchisi.
//
// Ilgari bu yerda qat'iy hex turardi va qorong'i rejimda to'q ko'k/binafsha
// bosqich ranglari fon bilan qo'shilib ketardi. Endi qiymat `styles.css`
// dagi `--stage-*` tokenidan keladi: yorug'da to'yingan, qorong'ida esa
// yorug'roq variant — ikkalasi ham bitta joyda ta'riflangan.
const COLOR_KEYS = [
  'sky', 'indigo', 'amber', 'violet', 'emerald', 'red', 'slate',
  'purple', 'teal', 'rose', 'blue', 'green', 'orange', 'cyan',
]
/** Kalit → CSS o'zgaruvchisi (mavzuga qarab qiymati almashadi). */
const COLORS = Object.fromEntries(COLOR_KEYS.map(k => [k, `var(--stage-${k})`]))
const hex = (c) => COLORS[c] || COLORS.slate
/** Rangning joriy yuza ustidagi yumshoq tinti — alfa qo'shish o'rniga. */
const soft = (c) => `color-mix(in srgb, ${c} 16%, var(--surface))`

const KIND_LABEL = { lead: 'Jarayon', won: 'Yutuq', lost: 'Yo‘qotish' }

// Kurs ro'yxati guruh bosqichlari bilan bir manbadan olinadi (constants/domain).
// Ilgari bu yerda 'frontend'/'backend' qattiq yozilgan edi — bazadagi guruhlarda
// esa bunday bosqich yo'q (foundation/fullstack), ya'ni tanlov real emas edi.
// Eski lidlarda saqlanib qolgan qiymatlar ro'yxatga qo'shib qo'yiladi.
const LEGACY_COURSES = ['frontend', 'backend']
const COURSES = [
  { key: '', label: 'Kurs tanlang' },
  ...STAGE_OPTIONS.map(o => ({ key: o.value, label: o.label })),
]
const courseOptionsFor = (current) => (
  current && LEGACY_COURSES.includes(current)
    ? [...COURSES, { key: current, label: `${STAGE_LABELS[current] || current} (eski)` }]
    : COURSES
)

const EMPTY_FORM = {
  full_name: '', phone: '', course_interest: '', source_id: '', notes: '',
  date_of_birth: '', parent_phone: '', parent2_phone: '', interested_group_id: '',
}
// Vaqt o'girish yagona joyda — `utils/datetime`.
const fmtDate = fmtDateTime

/** Ism bosh harflari — izoh muallifining belgisi ('Ali Valiyev' → 'AV'). */
const initials = (name) => (name || '?').trim().split(/\s+/).slice(0, 2)
  .map(w => w[0]).join('').toUpperCase()

// Kanban ustunida bir marta chiziladigan karta soni
const COL_PAGE = 40

export default function Leads({ currentUser }) {
  const [confirmUI, ask] = useConfirm()
  const role = currentUser?.role
  const isAdmin = role === 'admin'
  const isHunter = role === 'hunter'
  const isCallCenter = role === 'call_center'
  // Sales — faqat o'z lidlari doirasida ishlaydi (backend ham shunday filtrlaydi)
  const isSales = role === 'sales'
  const canAddLead = isHunter || isSales || role === 'call_center' || isAdmin
  const canMove    = isHunter || isSales || role === 'call_center' || isAdmin
  const canDelete  = isHunter || isSales || isAdmin
  const canSeeOwner = isHunter || role === 'call_center' || isAdmin
  // Talabaga aylantirish — backend'da require_call_center (call_center/hunter/admin)
  const canConvert = isHunter || isCallCenter || isAdmin

  const [view, setView]     = useState('kanban')     // 'kanban' | 'list'
  const [leads, setLeads]   = useState([])
  const [stages, setStages] = useState([])
  const [sources, setSources] = useState([])
  const [loading, setLoading] = useState(false)
  const [search, setSearch]   = useState('')
  const [filterSource, setFilterSource] = useState('')

  const [addModal, setAddModal] = useState(false)
  const [form, setForm]   = useState(EMPTY_FORM)
  const [formErrors, setFormErrors] = useState({})
  const [saving, setSaving] = useState(false)

  const [drawer, setDrawer]         = useState(null)   // lead object
  const [metricModal, setMetricModal] = useState(null) // sarlavhadagi raqam bosilgani — tafsilot oynasi
  const [activities, setActivities] = useState([])
  const [stageModal, setStageModal] = useState(false)
  const [formModal, setFormModal]   = useState(false)
  const [poolMode, setPoolMode]     = useState(false)
  const [todayMode, setTodayMode]   = useState(false)
  const [overdueMode, setOverdueMode] = useState(false)
  const [groups, setGroups]         = useState([])
  const [tariffs, setTariffs]       = useState([])
  const [editLead, setEditLead]     = useState(null)   // tahrirlanayotgan lid
  const [phoneDup, setPhoneDup]     = useState(null)   // shu raqam bilan bazada turgan lid
  const [convertFor, setConvertFor] = useState(null)   // talabaga aylantirilayotgan lid

  const [dragId, setDragId]       = useState(null)
  const [dragOver, setDragOver]   = useState(null)
  // Bir ustunda bir vaqtda nechta karta chiziladi. 274 ta kartani birdan
  // render qilish sahifani sekinlashtirardi — qolganini tugma bilan ochamiz.
  const [colLimit, setColLimit]   = useState({})

  const [loadError, setLoadError] = useState(false)
  const [claimingId, setClaimingId] = useState(null)
  const searchRef = useRef(null)
  const searchSkipFirst = useRef(true)

  useEffect(() => { boot() }, [])

  // Bir raqam — bitta lid. Raqam yozilayotgan paytda bazadagi mavjud yozuvni
  // ko'rsatamiz: xodim butun formani to'ldirib bo'lib 409 xatoga urilmasin va
  // ayni odam ikkinchi marta "Yangi lidlar"ga tushib qolmasin.
  const dupPhone   = addModal ? form.phone : (editLead ? editLead.phone : '')
  const dupExclude = addModal ? null : (editLead ? editLead.id : null)
  useEffect(() => {
    const digits = (dupPhone || '').replace(/\D/g, '')
    if (digits.length < 7) { setPhoneDup(null); return }
    let alive = true
    const t = setTimeout(() => {
      checkLeadPhone(dupPhone.trim(), dupExclude)
        .then(r => { if (alive) setPhoneDup(r.duplicate ? r.lead : null) })
        .catch(() => { if (alive) setPhoneDup(null) })
    }, 400)
    return () => { alive = false; clearTimeout(t) }
  }, [dupPhone, dupExclude])

  const dupMessage = phoneDup
    ? `Bu raqam bazada bor: ${phoneDup.full_name} (#${phoneDup.id}` +
      `${phoneDup.stage_name ? ', ' + phoneDup.stage_name : ''}` +
      `${phoneDup.claimed_by_name ? ', mas’ul: ' + phoneDup.claimed_by_name : ''}) — takroriy lid ochilmaydi`
    : null

  // Debounced live search (Enter still triggers immediately via onKeyDown)
  useEffect(() => {
    if (searchSkipFirst.current) { searchSkipFirst.current = false; return }
    const t = setTimeout(() => { reload() }, 300)
    return () => clearTimeout(t)
  }, [search])

  // "/" focuses search, unless already typing somewhere
  useEffect(() => {
    function onKey(e) {
      if (e.key !== '/' || e.metaKey || e.ctrlKey || e.altKey) return
      const tag = document.activeElement?.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return
      e.preventDefault()
      searchRef.current?.focus()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [])

  async function boot() {
    setLoading(true)
    setLoadError(false)
    try {
      const [st, src] = await Promise.all([fetchLeadStages(), fetchLeadSources()])
      setStages(st)
      setSources(src)
      fetchGroups({ is_active: true }).then(g => setGroups(g.items || g || [])).catch(() => {})
      fetchTariffs().then(t => setTariffs(t.items || t || [])).catch(() => {})
      await load(false)
    } catch { toast.error("Yuklab bo'lmadi"); setLoadError(true) }
    finally { setLoading(false) }
  }

  async function load(pool = poolMode, today = todayMode, over = overdueMode) {
    const data = await fetchLeads({
      search: search || undefined,
      source_id: filterSource || undefined,
      pool: pool || undefined,
      today: today || undefined,
      overdue: over || undefined,
    })
    setLeads(data)
  }
  // Uch preset bir-birini istisno qiladi — bir vaqtda faqat bittasi yoqiladi.
  function applyPreset(next) {
    setPoolMode(next.pool); setTodayMode(next.today); setOverdueMode(next.overdue)
    setLoading(true)
    load(next.pool, next.today, next.overdue)
      .catch(() => toast.error("Yuklab bo'lmadi")).finally(() => setLoading(false))
  }
  function togglePool()    { const on = !poolMode;    applyPreset({ pool: on, today: false, overdue: false }) }
  function toggleToday()   { const on = !todayMode;   applyPreset({ pool: false, today: on, overdue: false }) }
  function toggleOverdue() { const on = !overdueMode; applyPreset({ pool: false, today: false, overdue: on }) }
  async function reload() {
    setLoading(true)
    try { await load(); setLoadError(false) }
    catch { toast.error("Yuklab bo'lmadi"); setLoadError(true) }
    finally { setLoading(false) }
  }
  async function refreshStages() { try { setStages(await fetchLeadStages()) } catch {} }

  // ── Add lead ──
  async function handleAdd() {
    const errs = {}
    if (!form.full_name.trim()) errs.full_name = 'Ism majburiy'
    if (!form.phone.trim()) errs.phone = 'Telefon majburiy'
    setFormErrors(errs)
    if (Object.keys(errs).length) return
    if (dupMessage) return toast.error(dupMessage)
    setSaving(true)
    try {
      await createLead({
        full_name: form.full_name.trim(),
        phone: form.phone.trim(),
        course_interest: form.course_interest || null,
        source_id: form.source_id ? Number(form.source_id) : null,
        notes: form.notes || null,
        date_of_birth: form.date_of_birth || null,
        parent_phone: form.parent_phone || null,
        parent2_phone: form.parent2_phone || null,
        interested_group_id: form.interested_group_id ? Number(form.interested_group_id) : null,
      })
      toast.success("Lid qo'shildi")
      setAddModal(false); setForm(EMPTY_FORM); setFormErrors({}); reload()
    } catch (e) { toast.error(e.message) } finally { setSaving(false) }
  }

  // ── Claim / release ──
  async function handleClaim(lead) {
    if (claimingId) return
    setClaimingId(lead.id)
    try {
      const updated = await claimLead(lead.id)
      toast.success('Lid band qilindi')
      if (poolMode) setLeads(ls => ls.filter(l => l.id !== lead.id))
      else setLeads(ls => ls.map(l => l.id === updated.id ? updated : l))
      if (drawer?.id === lead.id) setDrawer(updated)
    } catch (e) { toast.error(e.message) } finally { setClaimingId(null) }
  }
  async function handleRelease(lead) {
    try {
      const updated = await releaseLead(lead.id)
      toast.success('Havzaga qaytarildi')
      setLeads(ls => ls.map(l => l.id === updated.id ? updated : l))
      if (drawer?.id === lead.id) setDrawer(updated)
    } catch (e) { toast.error(e.message) }
  }

  // ── Tahrirlash ──
  function openEdit(lead) {
    setEditLead({
      id: lead.id,
      full_name: lead.full_name || '',
      phone: lead.phone || '',
      course_interest: lead.course_interest || '',
      source_id: lead.source_id ? String(lead.source_id) : '',
      notes: lead.notes || '',
      date_of_birth: lead.date_of_birth || '',
      parent_phone: lead.parent_phone || '',
      parent2_phone: lead.parent2_phone || '',
      interested_group_id: lead.interested_group_id ? String(lead.interested_group_id) : '',
    })
  }
  async function handleEditSave() {
    if (!editLead) return
    if (!editLead.full_name.trim()) return toast.error('Ism majburiy')
    if (!editLead.phone.trim()) return toast.error('Telefon majburiy')
    if (dupMessage) return toast.error(dupMessage)
    setSaving(true)
    try {
      const updated = await updateLead(editLead.id, {
        full_name: editLead.full_name.trim(),
        phone: editLead.phone.trim(),
        course_interest: editLead.course_interest || null,
        source_id: editLead.source_id ? Number(editLead.source_id) : null,
        notes: editLead.notes || null,
        date_of_birth: editLead.date_of_birth || null,
        parent_phone: editLead.parent_phone || null,
        parent2_phone: editLead.parent2_phone || null,
        interested_group_id: editLead.interested_group_id ? Number(editLead.interested_group_id) : null,
      })
      setLeads(ls => ls.map(l => l.id === updated.id ? updated : l))
      if (drawer?.id === updated.id) { setDrawer(updated); openActivities(updated.id) }
      setEditLead(null)
      toast.success('Saqlandi')
    } catch (e) { toast.error(e.message) } finally { setSaving(false) }
  }

  // ── Izoh (sanasiz) ──
  async function handleAddNote(leadId, body) {
    await addLeadNote(leadId, body)
    openActivities(leadId)
    toast.success("Izoh qo'shildi")
  }

  // ── Talabaga aylantirish ──
  async function handleConvert(payload) {
    if (!convertFor) return
    setSaving(true)
    try {
      const student = await convertLead(convertFor.id, payload)
      toast.success(`${student.full_name} talabalarga qo'shildi`)
      setConvertFor(null); setDrawer(null); reload()
    } catch (e) { toast.error(e.message) } finally { setSaving(false) }
  }

  async function handleDelete(lead) {
    const ok = await ask({
      title: 'Lidni o\'chirish',
      message: `"${lead.full_name}" lidi o'chirilsinmi?`,
      detail: "Lid tarixi, eslatmalari va izohlari ham o'chadi. Qaytarib bo'lmaydi.",
      confirmLabel: "Ha, o'chirish",
    })
    if (!ok) return
    try { await deleteLead(lead.id); toast.success("O'chirildi"); setDrawer(null); reload() }
    catch (e) { toast.error(e.message) }
  }

  // ── Move stage (drag or button) ──
  async function moveTo(lead, stageId, extra = {}) {
    if (lead.stage_id === stageId && !Object.keys(extra).length) return
    const prev = leads
    setLeads(ls => ls.map(l => l.id === lead.id ? { ...l, stage_id: stageId } : l))
    try {
      const updated = await moveLeadStage(lead.id, { stage_id: stageId, ...extra })
      setLeads(ls => ls.map(l => l.id === updated.id ? updated : l))
      if (drawer?.id === lead.id) { setDrawer(updated); openActivities(updated.id) }
    } catch (e) { setLeads(prev); toast.error(e.message) }
  }

  function onDrop(stageId) {
    setDragOver(null)
    const lead = leads.find(l => l.id === dragId)
    setDragId(null)
    if (lead) moveTo(lead, stageId)
  }

  // ── Drawer / timeline ──
  async function openDrawer(lead) {
    setDrawer(lead)
    openActivities(lead.id)
  }
  async function openActivities(id) {
    setActivities([])
    try { setActivities(await fetchLeadActivities(id)) } catch {}
  }

  const visibleStages = stages.filter(s => !s.is_archived)
  const byStage = (sid) => leads.filter(l => l.stage_id === sid)

  // ── Sarlavhadagi ko'rsatkichlar ────────────────────────────────────────
  // Har bir raqam bosiladi va ORTIDAGI LIDLARNI ko'rsatadi: raqamning o'zi
  // "9 ta jarayonda" deydi, lekin menejerga kerak bo'ladigan savol —
  // "aynan qaysi 9 tasi?". Ro'yxat joriy filtrlardan (qidiruv, manba,
  // havza) keyingi `leads` to'plamidan olinadi, ya'ni ekrandagi raqam
  // bilan oyna ichidagi ro'yxat har doim bir xil to'plam.
  const kindOf = (lead) => stages.find(s => s.id === lead.stage_id)?.kind
  const metrics = useMemo(() => {
    const active = leads.filter(l => !['won', 'lost'].includes(kindOf(l)))
    const won = leads.filter(l => kindOf(l) === 'won')
    const overdue = leads.filter(l => l.is_overdue)
    return {
      total: {
        key: 'total', label: 'Tanlangan ro‘yxatda', unit: ' ta lid', rows: leads,
        hint: 'Joriy qidiruv va filtrlarga mos keluvchi barcha lidlar.',
      },
      active: {
        key: 'active', label: 'Jarayonda', rows: active,
        hint: 'Hali yopilmagan lidlar — bosqichi "To‘landi" ham, "Rad etildi" ham emas.',
      },
      won: {
        key: 'won', label: 'To‘lovga yetgan', tone: 'success', rows: won,
        hint: 'Bosqichi yutuq (won) deb belgilangan lidlar — to‘lov qilib talabaga o‘tganlar.',
      },
      overdue: {
        key: 'overdue', label: 'Kechikkan aloqa', tone: 'danger', rows: overdue,
        hint: 'Kelish yoki qayta qo‘ng‘iroq vaqti o‘tib ketgan, hali yopilmagan lidlar.',
      },
    }
  }, [leads, stages])
  const activeMetric = metricModal ? metrics[metricModal] : null

  const activeSourceName = sources.find(s => String(s.id) === String(filterSource))?.name
  const hasActiveFilters = !!filterSource || poolMode || todayMode || overdueMode
  function clearAllFilters() {
    setFilterSource(''); setPoolMode(false); setTodayMode(false); setOverdueMode(false)
    setLoading(true)
    load(false, false, false).catch(() => toast.error("Yuklab bo'lmadi")).finally(() => setLoading(false))
  }


  return (
    <div className="page leads-studio">
      {confirmUI}
      <div className="page-header studio-intro"><div><span className="studio-eyebrow">Aloqalar markazi</span><h1>Lidlar</h1><p className="page-subtitle">Har bir qiziqishdan yangi imkoniyatga.</p></div>
        <div className="header-actions">
          {isAdmin && (
            <button className="button secondary" onClick={() => setFormModal(true)}>
              <FontAwesomeIcon icon={faClipboardList} /> Formalar
            </button>
          )}
          {isAdmin && (
            <button className="button secondary" onClick={() => setStageModal(true)}>
              <FontAwesomeIcon icon={faSliders} /> Bosqichlar
            </button>
          )}
          {canAddLead && (
            <button className="button" onClick={() => setAddModal(true)}>
              <FontAwesomeIcon icon={faPlus} /> Lid qo'shish
            </button>
          )}
        </div>
      </div>

      {/* Toolbar */}
      {/* Raqamlar bosiladi — ortidagi lidlar ro'yxati ochiladi. */}
      <div className="lead-pipeline-summary">
        {['total', 'active', 'won', 'overdue'].map(key => {
          const m = metrics[key]
          const tone = m.tone && m.rows.length ? ` tone-${m.tone}` : ''
          return (
            <button key={key} type="button" className="lead-metric" onClick={() => setMetricModal(key)}
              title={`${m.label}: ro'yxatni ko'rish`} aria-haspopup="dialog">
              <span>{m.label}</span>
              <strong className={tone.trim()}>{m.rows.length}{m.unit && <small>{m.unit}</small>}</strong>
            </button>
          )
        })}
      </div>
      <div className="toolbar">
        <div className="search-wrap">
          <FontAwesomeIcon icon={faMagnifyingGlass} className="search-icon" />
          <input ref={searchRef} className={`search-input${search ? ' has-clear' : ''}`}
            placeholder="Ism yoki telefon... ( / )"
            value={search} onChange={e => setSearch(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && reload()} />
          {search && (
            <button className="search-clear" aria-label="Qidiruvni tozalash"
              onClick={() => { setSearch(''); setTimeout(reload, 0) }}>
              <FontAwesomeIcon icon={faXmark} />
            </button>
          )}
        </div>
        <select className="field-sm" value={filterSource} aria-label="Manba bo'yicha filtr"
          onChange={e => { setFilterSource(e.target.value); setTimeout(reload, 0) }}>
          <option value="">Barcha manbalar</option>
          {sources.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
        </select>
        <button className={`df-preset${poolMode ? ' active' : ''}`} onClick={togglePool} title="Band qilinmagan umumiy lidlar">
          <FontAwesomeIcon icon={faInbox} /> Umumiy havza
        </button>
        {(isHunter || isCallCenter || isAdmin) && (
          <button className={`df-preset${todayMode ? ' active' : ''}`} onClick={toggleToday} title="Faqat bugun kelishi kerak bo'lgan lidlar">
            <FontAwesomeIcon icon={faClock} /> Bugun
          </button>
        )}
        {(isHunter || isCallCenter || isAdmin) && (
          <button className={`df-preset${overdueMode ? ' active' : ''}`} onClick={toggleOverdue}
            title="Kelish/qo'ng'iroq vaqti o'tib ketgan, hali yopilmagan lidlar">
            <FontAwesomeIcon icon={faHourglassHalf} /> Kechikkanlar
          </button>
        )}
        <span style={{ flex: 1 }} />
        <div className="view-toggle" role="tablist" aria-label="Ko'rinish"
          onKeyDown={e => {
            if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return
            const order = ['kanban', 'list', 'analytics']
            const i = order.indexOf(view)
            const next = order[(i + (e.key === 'ArrowRight' ? 1 : order.length - 1)) % order.length]
            setView(next)
            e.currentTarget.querySelector(`[data-tab="${next}"]`)?.focus()
          }}>
          <button role="tab" data-tab="kanban" aria-selected={view === 'kanban'} tabIndex={view === 'kanban' ? 0 : -1}
            className={view === 'kanban' ? 'active' : ''} onClick={() => setView('kanban')}>
            <FontAwesomeIcon icon={faTableColumns} /> Ish maydoni
          </button>
          <button role="tab" data-tab="list" aria-selected={view === 'list'} tabIndex={view === 'list' ? 0 : -1}
            className={view === 'list' ? 'active' : ''} onClick={() => setView('list')}>
            <FontAwesomeIcon icon={faList} /> Ro'yxat
          </button>
          <button role="tab" data-tab="analytics" aria-selected={view === 'analytics'} tabIndex={view === 'analytics' ? 0 : -1}
            className={view === 'analytics' ? 'active' : ''} onClick={() => setView('analytics')}>
            <FontAwesomeIcon icon={faChartPie} /> Analitika
          </button>
        </div>
        <span className="toolbar-count">Jami: <strong>{leads.length}</strong></span>
      </div>

      {hasActiveFilters && (
        <div className="filter-chip-row">
          {filterSource && (
            <span className="filter-chip">
              {activeSourceName || 'Manba'}
              <button aria-label="Manba filterini olib tashlash"
                onClick={() => { setFilterSource(''); setTimeout(reload, 0) }}>
                <FontAwesomeIcon icon={faXmark} />
              </button>
            </span>
          )}
          {poolMode && (
            <span className="filter-chip">
              Umumiy havza
              <button aria-label="Umumiy havza filterini olib tashlash" onClick={togglePool}>
                <FontAwesomeIcon icon={faXmark} />
              </button>
            </span>
          )}
          {todayMode && (
            <span className="filter-chip">
              Bugun
              <button aria-label="Bugun filterini olib tashlash" onClick={toggleToday}>
                <FontAwesomeIcon icon={faXmark} />
              </button>
            </span>
          )}
          {overdueMode && (
            <span className="filter-chip">
              Kechikkanlar
              <button aria-label="Kechikkanlar filterini olib tashlash" onClick={toggleOverdue}>
                <FontAwesomeIcon icon={faXmark} />
              </button>
            </span>
          )}
          <button className="filter-clear-all" onClick={clearAllFilters}>Tozalash</button>
        </div>
      )}

      {view === 'analytics' ? (
        <Analytics />
      ) : loadError ? (
        <div className="board-error-state">
          <FontAwesomeIcon icon={faTriangleExclamation} />
          <div className="be-title">Ma'lumotlarni yuklashda xatolik yuz berdi.</div>
          <button className="button secondary" onClick={boot}>
            <FontAwesomeIcon icon={faArrowRotateRight} /> Qayta urinish
          </button>
        </div>
      ) : loading ? (
        <KanbanSkeleton count={visibleStages.length || 4} />
      ) : view === 'kanban' ? (
        <LeadBoard leads={leads} stages={visibleStages} canMove={canMove} canSeeOwner={canSeeOwner} currentUser={currentUser}
          onOpen={openDrawer} onDragStart={setDragId} onDrop={onDrop} onClaim={handleClaim} claimingId={claimingId} onAdd={canAddLead ? () => setAddModal(true) : undefined} />
      ) : (
        <ListView leads={leads} stages={stages} canSeeOwner={canSeeOwner}
          canDelete={canDelete} canEdit={canMove} onOpen={openDrawer}
          onEdit={openEdit} onDelete={handleDelete} />
      )}

      {/* Add Lead Modal */}
      <Modal
        open={addModal}
        title="Yangi lid"
        onClose={() => setAddModal(false)}
        footer={
          <>
            <button className="button secondary" onClick={() => setAddModal(false)}>Bekor</button>
            <button className="button" onClick={handleAdd} disabled={saving}>
              {saving ? 'Saqlanmoqda...' : "Qo'shish"}
            </button>
          </>
        }
      >
        <Input
          label="Ism Familiya" required
          value={form.full_name} error={formErrors.full_name}
          onChange={e => setForm(p => ({ ...p, full_name: e.target.value }))}
          placeholder="To'liq ism"
        />
        <Input
          label="Telefon" required
          value={form.phone} error={formErrors.phone || dupMessage}
          onChange={e => setForm(p => ({ ...p, phone: e.target.value }))}
          placeholder="+998901234567"
        />
        <Select
          label="Qiziqayotgan kurs" value={form.course_interest}
          onChange={e => setForm(p => ({ ...p, course_interest: e.target.value }))}
        >
          {COURSES.map(c => <option key={c.key} value={c.key}>{c.label}</option>)}
        </Select>
        <Select
          label="Manba" value={form.source_id}
          onChange={e => setForm(p => ({ ...p, source_id: e.target.value }))}
        >
          <option value="">Manba tanlang</option>
          {sources.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
        </Select>
        <div className="field-row">
          <Input
            label="Tug'ilgan sana" type="date" value={form.date_of_birth}
            onChange={e => setForm(p => ({ ...p, date_of_birth: e.target.value }))}
          />
          <Select
            label="Qiziqqan guruh" value={form.interested_group_id}
            onChange={e => setForm(p => ({ ...p, interested_group_id: e.target.value }))}
          >
            <option value="">—</option>
            {groups.map(g => <option key={g.id} value={g.id}>{g.name}</option>)}
          </Select>
        </div>
        <div className="field-row">
          <Input
            label="Ota-ona telefoni" value={form.parent_phone}
            onChange={e => setForm(p => ({ ...p, parent_phone: e.target.value }))}
            placeholder="+998..."
          />
          <Input
            label="2-telefon" value={form.parent2_phone}
            onChange={e => setForm(p => ({ ...p, parent2_phone: e.target.value }))}
            placeholder="+998..."
          />
        </div>
        <Textarea
          label="Izoh" rows={2} value={form.notes}
          onChange={e => setForm(p => ({ ...p, notes: e.target.value }))}
          placeholder="Qo'shimcha ma'lumot..."
        />
      </Modal>

      {/* Ko'rsatkich tafsiloti — sarlavhadagi raqam bosilganda */}
      <Modal
        open={!!activeMetric}
        title={activeMetric ? `${activeMetric.label} — ${activeMetric.rows.length} ta lid` : ''}
        onClose={() => setMetricModal(null)}
        size="xl"
        footer={<button className="button secondary" onClick={() => setMetricModal(null)}>Yopish</button>}
      >
        {activeMetric && (
          <div className="lead-metric-detail">
            <p className="lead-metric-hint">{activeMetric.hint}</p>
            {/* Bosqichlar kesimi: "9 ta jarayonda" degan raqam qaysi
                bosqichlardan yig'ilganini bir qarashda ko'rsatadi. */}
            <div className="lead-metric-chips">
              {visibleStages
                .map(st => ({ st, n: activeMetric.rows.filter(l => l.stage_id === st.id).length }))
                .filter(x => x.n > 0)
                .map(({ st, n }) => (
                  <span key={st.id} className="lead-metric-chip" style={{ '--chip': hex(st.color) }}>
                    {st.name}<strong>{n}</strong>
                  </span>
                ))}
              {activeMetric.rows.some(l => !visibleStages.find(st => st.id === l.stage_id)) && (
                <span className="lead-metric-chip">
                  Bosqichsiz
                  <strong>{activeMetric.rows.filter(l => !visibleStages.find(st => st.id === l.stage_id)).length}</strong>
                </span>
              )}
            </div>
            <DataTable
              columns={metricColumns(stages, canSeeOwner)}
              rows={activeMetric.rows}
              clientPageSize={12}
              onRowClick={l => { setMetricModal(null); openDrawer(l) }}
              empty={{
                icon: faBullseye,
                title: 'Bu ko‘rsatkichda lid yo‘q',
                description: 'Filtrlarni o‘zgartirib qayta urinib ko‘ring.',
              }}
            />
          </div>
        )}
      </Modal>

      {/* Lead drawer */}
      {drawer && (
        <LeadDrawer
          lead={drawer} stages={visibleStages} activities={activities}
          canMove={canMove} canDelete={canDelete} canConvert={canConvert}
          currentUser={currentUser}
          onClose={() => setDrawer(null)}
          onMove={(sid, extra) => moveTo(drawer, sid, extra)}
          onClaim={() => handleClaim(drawer)}
          onRelease={() => handleRelease(drawer)}
          onEdit={openEdit}
          onNote={handleAddNote}
          onConvert={setConvertFor}
          onDelete={() => handleDelete(drawer)} />
      )}

      {/* Lidni tahrirlash */}
      <Modal
        open={!!editLead}
        title="Lidni tahrirlash"
        onClose={() => setEditLead(null)}
        footer={
          <>
            <button className="button secondary" onClick={() => setEditLead(null)}>Bekor</button>
            <button className="button" onClick={handleEditSave} disabled={saving}>
              {saving ? 'Saqlanmoqda...' : 'Saqlash'}
            </button>
          </>
        }
      >
        {editLead && (
          <>
            <Input label="Ism Familiya" required value={editLead.full_name}
              onChange={e => setEditLead(p => ({ ...p, full_name: e.target.value }))} />
            <Input label="Telefon" required value={editLead.phone} error={dupMessage}
              placeholder="+998901234567"
              onChange={e => setEditLead(p => ({ ...p, phone: e.target.value }))} />
            <Select label="Qiziqayotgan kurs" value={editLead.course_interest}
              onChange={e => setEditLead(p => ({ ...p, course_interest: e.target.value }))}>
              {courseOptionsFor(editLead.course_interest).map(c => (
                <option key={c.key} value={c.key}>{c.label}</option>
              ))}
            </Select>
            <Select label="Manba" value={editLead.source_id}
              onChange={e => setEditLead(p => ({ ...p, source_id: e.target.value }))}>
              <option value="">Manba tanlang</option>
              {sources.map(o => <option key={o.id} value={o.id}>{o.name}</option>)}
            </Select>
            <div className="field-row">
              <Input label="Tug'ilgan sana" type="date" value={editLead.date_of_birth}
                onChange={e => setEditLead(p => ({ ...p, date_of_birth: e.target.value }))} />
              <Select label="Qiziqqan guruh" value={editLead.interested_group_id}
                onChange={e => setEditLead(p => ({ ...p, interested_group_id: e.target.value }))}>
                <option value="">Guruh tanlang</option>
                {groups.map(g => <option key={g.id} value={g.id}>{g.name}</option>)}
              </Select>
            </div>
            <div className="field-row">
              <Input label="Ota-ona telefoni" value={editLead.parent_phone}
                onChange={e => setEditLead(p => ({ ...p, parent_phone: e.target.value }))} />
              <Input label="Qo'shimcha telefon" value={editLead.parent2_phone}
                onChange={e => setEditLead(p => ({ ...p, parent2_phone: e.target.value }))} />
            </div>
            <Textarea label="Izoh" rows={3} value={editLead.notes}
              onChange={e => setEditLead(p => ({ ...p, notes: e.target.value }))} />
          </>
        )}
      </Modal>

      {/* Talabaga aylantirish */}
      {convertFor && (
        <ConvertModal lead={convertFor} groups={groups} tariffs={tariffs} saving={saving}
          onClose={() => setConvertFor(null)} onSubmit={handleConvert} />
      )}

      {/* Stage management */}
      {stageModal && (
        <StageManager stages={stages} onClose={() => setStageModal(false)}
          onChanged={refreshStages} />
      )}

      {/* Intake form management */}
      {formModal && (
        <IntakeFormManager sources={sources} onClose={() => setFormModal(false)} />
      )}
    </div>
  )
}

// ── Skeleton loading state (mirrors the kanban structure) ─────────────────
function SkeletonCard() {
  return (
    <div className="skel-card">
      <div className="skel-line" style={{ width: '62%' }} />
      <div className="skel-line" style={{ width: '40%' }} />
      <div className="skel-line" style={{ width: '80%' }} />
    </div>
  )
}
function SkeletonColumn() {
  return (
    <div className="kanban-col">
      <div className="kanban-col-head">
        <span className="dot" style={{ background: 'var(--border-2)' }} />
        <span className="skel-line" style={{ width: 90, height: 11 }} />
      </div>
      <div className="skel-col">
        <SkeletonCard /><SkeletonCard /><SkeletonCard />
      </div>
    </div>
  )
}
function KanbanSkeleton({ count = 4 }) {
  return (
    <div className="kanban">
      {Array.from({ length: count }).map((_, i) => <SkeletonColumn key={i} />)}
    </div>
  )
}

// ── List (table) view ──────────────────────────────────────────────────────
/**
 * Ko'rsatkich oynasidagi jadval ustunlari.
 *
 * `ListView` dagi ustunlarning qisqartirilgan varianti: bu yerda amal
 * tugmalari yo'q (o'chirish/tahrirlash asosiy ro'yxatda qoladi) — oyna
 * faqat "qaysi lidlar shu raqam ortida?" degan savolga javob beradi, qatorni
 * bosish esa lid kartasini ochadi.
 */
function metricColumns(stages, canSeeOwner) {
  const stageOf = (id) => stages.find(s => s.id === id)
  return [
    { key: 'index', header: '#', width: 46, className: 'text-muted', render: (_l, i) => i + 1 },
    { key: 'full_name', header: 'Ism Familiya', sortable: true, render: l => <strong>{l.full_name}</strong> },
    {
      key: 'phone', header: <><FontAwesomeIcon icon={faPhone} /> Telefon</>, sortable: true,
      render: l => <a href={`tel:${l.phone}`} onClick={e => e.stopPropagation()}>{l.phone_display || l.phone}</a>,
    },
    {
      key: 'stage_id', header: 'Bosqich', sortable: true,
      sortValue: l => stageOf(l.stage_id)?.order ?? 999,
      render: l => {
        const st = stageOf(l.stage_id)
        return <Badge size="sm" color={hex(st?.color)}>{st?.name || l.status}</Badge>
      },
    },
    {
      key: 'source_name', header: 'Manba', sortable: true,
      render: l => l.source_name
        ? <Badge variant="neutral" size="sm">{l.source_name}</Badge>
        : <span className="text-muted">—</span>,
    },
    {
      key: 'time', header: 'Vaqt / Izoh', sortable: true,
      sortValue: l => l.callback_at || l.created_at,
      render: l => (
        <div className="lead-cell-meta">
          {l.callback_at
            ? <div className={l.is_overdue ? 'tone-danger' : 'tone-warning'}>
                {l.is_overdue && <><FontAwesomeIcon icon={faTriangleExclamation} />{' '}</>}
                {fmtDate(l.callback_at)}
              </div>
            : <div className="text-muted">{fmtDate(l.created_at)}</div>}
          {l.notes && <div className="text-muted kc-clamp2">{l.notes}</div>}
        </div>
      ),
    },
    ...(canSeeOwner ? [{
      key: 'created_by_name', header: 'Hunter', sortable: true,
      render: l => <span className="text-muted">{l.created_by_name || '—'}</span>,
    }] : []),
  ]
}


function ListView({ leads, stages, canSeeOwner, canDelete, canEdit, onOpen, onEdit, onDelete }) {
  const stageOf = (id) => stages.find(s => s.id === id)

  const columns = [
    { key: 'index', header: '#', width: 52, className: 'text-muted', render: (_l, i) => i + 1 },
    {
      key: 'full_name', header: 'Ism Familiya', sortable: true,
      render: l => <strong>{l.full_name}</strong>,
    },
    {
      key: 'phone', header: <><FontAwesomeIcon icon={faPhone} /> Telefon</>, sortable: true,
      sortValue: l => l.phone,
      render: l => <a href={`tel:${l.phone}`} onClick={e => e.stopPropagation()}>{l.phone_display || l.phone}</a>,
    },
    {
      key: 'source_name', header: 'Manba', sortable: true,
      render: l => l.source_name
        ? <Badge variant="neutral" size="sm">{l.source_name}</Badge>
        : <span className="text-muted">—</span>,
    },
    {
      key: 'stage_id', header: 'Bosqich', sortable: true,
      sortValue: l => stageOf(l.stage_id)?.order ?? 999,
      render: l => {
        const st = stageOf(l.stage_id)
        return <Badge size="sm" color={hex(st?.color)}>{st?.name || l.status}</Badge>
      },
    },
    {
      key: 'time', header: 'Vaqt / Izoh',
      sortValue: l => l.callback_at || l.created_at,
      sortable: true,
      render: l => (
        <div className="lead-cell-meta">
          {l.callback_at
            ? <div className={l.is_overdue ? 'tone-danger' : 'tone-warning'}>
                {l.is_overdue && <><FontAwesomeIcon icon={faTriangleExclamation} />{' '}</>}
                {fmtDate(l.callback_at)}
              </div>
            : <div className="text-muted">{fmtDate(l.created_at)}</div>}
          {l.notes && <div className="text-muted kc-clamp2">{l.notes}</div>}
          {l.next_reminder_body && (
            <div className="text-muted kc-clamp2">
              <FontAwesomeIcon icon={faClock} /> {l.next_reminder_body}
              {l.next_reminder_due_at && <> ({fmtDate(l.next_reminder_due_at)})</>}
            </div>
          )}
        </div>
      ),
    },
    ...(canSeeOwner ? [{
      key: 'created_by_name', header: 'Hunter', sortable: true,
      render: l => <span className="text-muted">{l.created_by_name || '—'}</span>,
    }] : []),
    {
      key: 'actions', header: 'Amallar', className: 'actions', align: 'right',
      render: l => (
        <span onClick={e => e.stopPropagation()}>
          <button className="btn-icon" title="Ochish" aria-label="Ochish" onClick={() => onOpen(l)}>
            <FontAwesomeIcon icon={faClipboardList} />
          </button>
          {canEdit && (
            <button className="btn-icon" title="Tahrirlash" aria-label="Tahrirlash" onClick={() => onEdit(l)}>
              <FontAwesomeIcon icon={faPen} />
            </button>
          )}
          {canDelete && (
            <button className="btn-icon danger" title="O'chirish" aria-label="O'chirish" onClick={() => onDelete(l)}>
              <FontAwesomeIcon icon={faTrash} />
            </button>
          )}
        </span>
      ),
    },
  ]

  return (
    <DataTable
      columns={columns}
      rows={leads}
      onRowClick={onOpen}
      clientPageSize={25}
      empty={{ icon: faInbox, title: 'Lidlar topilmadi', description: "Filtrlarni o'zgartiring yoki yangi lid qo'shing." }}
    />
  )
}

// ── Lead detail drawer with timeline ───────────────────────────────────────
export function LeadDrawer({ lead, stages, activities, canMove, canDelete, canConvert,
  currentUser, onClose, onMove, onClaim, onRelease, onDelete, onEdit, onNote, onConvert,
  allowNote }) {
  // Tree kabi tahlil ekranlarida bosqichni o'zgartirish o'chirilgan (ko'rsatkichlar
  // ko'z oldida o'zgarib ketmasin), lekin izoh qoldirish baribir kerak.
  const canNote = allowNote ?? canMove
  const [detailTab, setDetailTab] = useState('details')
  const [confirmUI, ask] = useConfirm()
  const [cb, setCb] = useState(isoToInput(lead.callback_at))
  const [reminders, setReminders] = useState([])
  const [remDue, setRemDue] = useState('')
  const [remBody, setRemBody] = useState('')
  const [remBusy, setRemBusy] = useState(false)
  const [note, setNote] = useState('')
  const [noteBusy, setNoteBusy] = useState(false)
  // Izohlar sukut bo'yicha eng yangisi tepada — xodim oxirgi gapni birinchi ko'radi.
  const [noteAsc, setNoteAsc] = useState(false)

  /* Tarix ikki xil narsani aralashtirib yuborardi: xodim yozgan izohlar va
     tizim hodisalari ("bosqich o'zgardi", "yaratildi"). Lidda 20 ta izoh
     bo'lsa, ular o'nlab avtomatik yozuvlar orasida ko'rinmay ketardi.
     Endi izohlar alohida oqim, tarix esa faqat hodisalar. */
  const notes  = useMemo(() => activities.filter(a => a.action === 'note'), [activities])
  const events = useMemo(() => activities.filter(a => a.action !== 'note'), [activities])

  /* Vaqt bo'yicha tartiblab, kunlarga bo'lamiz — sana har qatorda
     takrorlanmasin, o'qish oson bo'lsin. */
  const noteDays = useMemo(() => {
    const ts = (a) => parseTs(a.created_at)?.getTime() ?? 0
    const sorted = [...notes].sort((a, b) => noteAsc ? ts(a) - ts(b) : ts(b) - ts(a))
    const days = []
    for (const n of sorted) {
      const key = dayKey(n.created_at)
      if (!days.length || days[days.length - 1].key !== key) days.push({ key, items: [n] })
      else days[days.length - 1].items.push(n)
    }
    return days
  }, [notes, noteAsc])
  const drawerRef = useRef(null)
  useFocusTrap(true, drawerRef, onClose)

  useEffect(() => { loadReminders() }, [lead.id])
  useEffect(() => { setCb(isoToInput(lead.callback_at)) }, [lead.id, lead.callback_at])
  async function loadReminders() {
    try { setReminders(await fetchReminders({ lead_id: lead.id })) } catch {}
  }
  async function addReminder() {
    if (!remDue) return toast.error('Vaqtni tanlang')
    setRemBusy(true)
    try {
      await createReminder({ lead_id: lead.id, due_at: inputToIso(remDue), body: remBody || null, kind: 'call' })
      setRemDue(''); setRemBody(''); loadReminders(); toast.success("Eslatma qo'shildi")
    } catch (e) { toast.error(e.message) } finally { setRemBusy(false) }
  }
  async function doneReminder(r) {
    try { await updateReminder(r.id, { status: 'done' }); loadReminders() } catch (e) { toast.error(e.message) }
  }
  async function snoozeReminder(r, hours) {
    const until = new Date(Date.now() + hours * 3600 * 1000).toISOString()
    try { await updateReminder(r.id, { snoozed_until: until }); loadReminders(); toast.success(`${hours} soatga surildi`) }
    catch (e) { toast.error(e.message) }
  }
  async function removeReminder(r) {
    const ok = await ask({ title: 'Eslatmani o\'chirish', message: "Bu eslatma o'chirilsinmi?", confirmLabel: "Ha, o'chirish" })
    if (!ok) return
    try { await deleteReminder(r.id); loadReminders() } catch (e) { toast.error(e.message) }
  }
  async function submitNote() {
    const body = note.trim()
    if (!body) return
    setNoteBusy(true)
    try { await onNote(lead.id, body); setNote('') }
    catch (e) { toast.error(e.message) } finally { setNoteBusy(false) }
  }
  // Bosqichsiz lidda callback saqlash 404 berardi — avval bosqich tanlansin.
  function saveCallback() {
    if (!cb) return
    if (!lead.stage_id) return toast.error('Avval bosqichni tanlang')
    onMove(lead.stage_id, { callback_at: inputToIso(cb) })
  }

  return (
    <Overlay className="drawer-overlay" onClick={onClose}>
      {confirmUI}
      <div className="drawer lead-dossier" ref={drawerRef} role="dialog" aria-modal="true" aria-label={`${lead.full_name} — lid ma'lumotlari`} onClick={e => e.stopPropagation()}>
        <div className="drawer-head">
          <h3>Lid kartasi</h3>
          <span style={{ flex: 1 }} />
          {canMove && <button className="btn-icon" title="Tahrirlash" aria-label="Lidni tahrirlash" onClick={() => onEdit(lead)}><FontAwesomeIcon icon={faPen} /></button>}
          {canDelete && <button className="btn-icon danger" title="O'chirish" aria-label="Lidni o'chirish" onClick={onDelete}><FontAwesomeIcon icon={faTrash} /></button>}
          <button className="modal-close" aria-label="Yopish" onClick={onClose}><FontAwesomeIcon icon={faXmark} /></button>
        </div>
        <div className="drawer-body">
          <header className="lead-dossier-profile"><Initials name={lead.full_name} /><div><span className={'map-stage-pill kind-' + lead.stage_kind}>{lead.stage_name || 'Bosqich belgilanmagan'}</span><h2>{lead.full_name}</h2><p>{lead.course_interest || 'Kurs tanlanmagan'}</p></div></header>
          <a className="lead-dossier-phone" href={'tel:' + lead.phone}><span><FontAwesomeIcon icon={faPhone} /></span><span><small>Telefon raqami</small><strong>{lead.phone_display || lead.phone}</strong></span><span>Qo‘ng‘iroq qilish</span></a>
          {lead.is_overdue && <div className="lead-overdue"><FontAwesomeIcon icon={faTriangleExclamation} /><span>Kelish vaqti o‘tgan <strong>{fmtDate(lead.callback_at)}</strong></span></div>}
          <ViewTabs label="Lid kartasi bo‘limlari" value={detailTab} onChange={setDetailTab} items={[{ key: 'details', label: 'Ma’lumot' }, { key: 'notes', label: 'Izohlar', count: notes.length }, { key: 'reminders', label: 'Eslatmalar', count: reminders.length }, { key: 'history', label: 'Tarix' }]} />
          <section className="lead-dossier-section" hidden={detailTab !== 'details'}>
          <dl className="lead-facts">{[
            ['Manba', lead.source_name], ['Qiziqqan guruh', lead.interested_group_name], ['Mas’ul', lead.claimed_by_name], ['Yaratgan', lead.created_by_name], ['Taklif qilgan', lead.referred_by_name], ['Yaratilgan', fmtDate(lead.created_at)], ['Tug‘ilgan sana', lead.date_of_birth], ['Ota-ona telefoni', lead.parent_phone], ['Qo‘shimcha telefon', lead.parent2_phone], ['Keyingi aloqa', lead.callback_at ? fmtDate(lead.callback_at) : null],
          ].filter(([, value]) => value).map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
          {/* Claim / release */}
          {canMove && (
            <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
              {lead.is_shared && !lead.claimed_by_id && (
                <button className="button" style={{ flex: 1, justifyContent: 'center' }} onClick={onClaim}>
                  <FontAwesomeIcon icon={faHandHolding} /> Band qilish
                </button>
              )}
              {lead.claimed_by_id && (lead.claimed_by_id === currentUser?.id || currentUser?.role === 'admin' || currentUser?.role === 'hunter') && (
                <button className="button secondary" style={{ flex: 1, justifyContent: 'center' }} onClick={onRelease}>
                  <FontAwesomeIcon icon={faShareNodes} /> Havzaga qaytarish
                </button>
              )}
            </div>
          )}

          {canMove && (
            <>
              <label>Bosqich</label>
              <div className="leads-status-grid" style={{ marginBottom: 14 }}>
                {stages.map(s => {
                  const on = s.id === lead.stage_id
                  const c = hex(s.color)
                  return (
                    <button key={s.id}
                      className={`leads-status-opt${on ? ' selected' : ''}`}
                      style={on ? { background: soft(c), borderColor: c, color: c } : {}}
                      onClick={() => onMove(s.id, cb ? { callback_at: inputToIso(cb) } : {})}>
                      <FontAwesomeIcon icon={faCircle} style={{ color: c, fontSize: 8 }} />
                      {s.name}
                    </button>
                  )
                })}
              </div>
              <label>Kelish / qayta ring vaqti</label>
              <input className="field" type="datetime-local" value={cb}
                onChange={e => setCb(e.target.value)}
                onBlur={saveCallback} />
            </>
          )}

          {lead.notes && (
            <div style={{ marginTop: 14 }}>
              <label>Izoh (lid kartasi)</label>
              <div className="text-muted" style={{ fontSize: 13, whiteSpace: 'pre-wrap' }}>{lead.notes}</div>
            </div>
          )}

          {canConvert && (
            <button className="button" style={{ width: '100%', justifyContent: 'center', marginTop: 16 }}
              onClick={() => onConvert(lead)}>
              <FontAwesomeIcon icon={faUserPlus} /> Talabaga aylantirish
            </button>
          )}

          </section>
          <section className="lead-dossier-section" hidden={detailTab !== 'notes'}>
          {/* Izohlar — bitta lidga cheklovsiz izoh qoldirish mumkin,
              vaqt bo'yicha tartiblangan holda ko'rsatiladi. */}
          <div className="lc-head">
            <h4><FontAwesomeIcon icon={faCommentDots} /> Izohlar
              {notes.length > 0 && <span className="lc-count">{notes.length}</span>}</h4>
            {notes.length > 1 && (
              <button className="btn-icon" onClick={() => setNoteAsc(v => !v)}
                title={noteAsc ? 'Eng eskisi tepada — almashtirish' : 'Eng yangisi tepada — almashtirish'}
                aria-label="Izohlar tartibini almashtirish">
                <FontAwesomeIcon icon={noteAsc ? faArrowUpWideShort : faArrowDownWideShort} />
              </button>
            )}
          </div>

          {canNote && (
            <div className="lc-compose">
              <Textarea rows={2} placeholder="Mijoz bilan nima gaplashildi?"
                value={note} onChange={e => setNote(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) submitNote() }} />
              <div className="lc-compose-foot">
                <span className="muted">Ctrl+Enter — saqlash</span>
                <button className="button" onClick={submitNote} disabled={noteBusy || !note.trim()}>
                  <FontAwesomeIcon icon={noteBusy ? faSpinner : faPaperPlane} className={noteBusy ? 'kc-spin' : ''} />
                  {' '}Saqlash
                </button>
              </div>
            </div>
          )}

          {notes.length === 0 ? (
            <div className="muted" style={{ fontSize: 13 }}>Hozircha izoh yo'q</div>
          ) : (
            <ul className="lead-comments">
              {noteDays.map(day => (
                <Fragment key={day.key}>
                  <li className="lc-day"><span>{fmtDayLabel(day.items[0].created_at)}</span></li>
                  {day.items.map(n => (
                    <li key={n.id} className="lc-item">
                      <span className="lc-avatar" aria-hidden="true">{initials(n.author_name)}</span>
                      <div className="lc-main">
                        <div className="lc-meta">
                          <strong>{n.author_name || 'Tizim'}</strong>
                          <time dateTime={n.created_at} title={fmtDateTime(n.created_at)}>
                            {fmtTime(n.created_at)}
                          </time>
                          <span className="lc-rel">{fmtRelative(n.created_at)}</span>
                        </div>
                        <div className="lc-text">{n.description}</div>
                      </div>
                    </li>
                  ))}
                </Fragment>
              ))}
            </ul>
          )}

          </section>
          <section className="lead-dossier-section" hidden={detailTab !== 'reminders'}>
          {/* Reminders */}
          <h4 style={{ margin: '22px 0 10px' }}><FontAwesomeIcon icon={faClock} /> Eslatmalar</h4>
          {reminders.map(r => (
            <div key={r.id} className={`rem-item${r.is_overdue ? ' overdue' : ''}${r.status !== 'pending' ? ' done' : ''}`}>
              <FontAwesomeIcon icon={r.is_overdue ? faTriangleExclamation : faClock} style={{ marginTop: 3 }} />
              <div style={{ flex: 1 }}>
                <div className="rem-when">{fmtDate(r.snoozed_until || r.due_at)}</div>
                {r.body && <div className="text-muted" style={{ fontSize: 12 }}>{r.body}</div>}
              </div>
              {r.status === 'pending' && (
                <>
                  <button className="btn-icon" title="Bajarildi" aria-label="Eslatma bajarildi" onClick={() => doneReminder(r)}>
                    <FontAwesomeIcon icon={faCheck} />
                  </button>
                  <button className="btn-icon" title="1 soatga surish" aria-label="1 soatga surish" onClick={() => snoozeReminder(r, 1)}>
                    <FontAwesomeIcon icon={faBellSlash} />
                  </button>
                </>
              )}
              <button className="btn-icon danger" title="O'chirish" aria-label="Eslatmani o'chirish" onClick={() => removeReminder(r)}>
                <FontAwesomeIcon icon={faTrash} />
              </button>
            </div>
          ))}
          {reminders.length === 0 && <div className="muted" style={{ fontSize: 13 }}>Eslatma yo'q</div>}
          {canMove && (
            <div style={{ display: 'flex', gap: 6, marginTop: 10, flexWrap: 'wrap' }}>
              <input className="field" type="datetime-local" style={{ flex: 1, minWidth: 150 }}
                value={remDue} onChange={e => setRemDue(e.target.value)} />
              <input className="field" style={{ flex: 1, minWidth: 120 }} placeholder="Izoh"
                value={remBody} onChange={e => setRemBody(e.target.value)} />
              <button className="button" onClick={addReminder} disabled={remBusy}>
                <FontAwesomeIcon icon={faPlus} />
              </button>
            </div>
          )}

          </section>
          <section className="lead-dossier-section" hidden={detailTab !== 'history'}>
          <h4 style={{ margin: '22px 0 12px' }}><FontAwesomeIcon icon={faClockRotateLeft} /> Tarix</h4>
          {events.length === 0 ? (
            <div className="muted" style={{ fontSize: 13 }}>Hozircha yozuv yo'q</div>
          ) : (
            <ul className="timeline">
              {events.map(a => (
                <li key={a.id}>
                  <div className="tl-desc">{a.description}</div>
                  <div className="tl-meta">{a.author_name || 'Tizim'} · {fmtDate(a.created_at)}</div>
                </li>
              ))}
            </ul>
          )}
          </section>
        </div>
      </div>
    </Overlay>
  )
}

// ── Lidni talabaga aylantirish ─────────────────────────────────────────────
function ConvertModal({ lead, groups, tariffs, saving, onClose, onSubmit }) {
  const [groupId, setGroupId] = useState(lead.interested_group_id ? String(lead.interested_group_id) : '')
  const [tariffId, setTariffId] = useState('')
  const [fatherName, setFatherName] = useState('')
  const [motherName, setMotherName] = useState('')
  const [isDemo, setIsDemo] = useState(false)

  return (
    <Modal
      open
      title={`${lead.full_name} — talabaga aylantirish`}
      onClose={onClose}
      footer={
        <>
          <button className="button secondary" onClick={onClose}>Bekor</button>
          <button className="button" disabled={saving}
            onClick={() => onSubmit({
              group_id: groupId ? Number(groupId) : null,
              tariff_id: tariffId ? Number(tariffId) : null,
              father_name: fatherName || null,
              mother_name: motherName || null,
              is_demo: isDemo,
            })}>
            {saving ? 'Yaratilmoqda...' : 'Talaba yaratish'}
          </button>
        </>
      }
    >
      <div className="text-muted" style={{ fontSize: 13, marginBottom: 12 }}>
        Lid ma'lumotlari talaba kartasiga ko'chiriladi: <strong>{lead.phone_display || lead.phone}</strong>
        {lead.parent_phone && <> · ota-ona: {lead.parent_phone}</>}
        . Lid "To'landi" bosqichiga o'tadi va tarixi saqlanadi.
      </div>
      <Select label="Guruhga qo'shish (ixtiyoriy)" value={groupId}
        onChange={e => setGroupId(e.target.value)}>
        <option value="">Guruhsiz qoldirish</option>
        {groups.map(g => <option key={g.id} value={g.id}>{g.name}</option>)}
      </Select>
      {groupId && (
        <Select label="Tarif" value={tariffId} onChange={e => setTariffId(e.target.value)}>
          <option value="">Tarifsiz</option>
          {tariffs.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
        </Select>
      )}
      <div className="field-row">
        <Input label="Otasining ismi" value={fatherName} onChange={e => setFatherName(e.target.value)} />
        <Input label="Onasining ismi" value={motherName} onChange={e => setMotherName(e.target.value)} />
      </div>
      <label className="check-row" style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 8 }}>
        <input type="checkbox" checked={isDemo} onChange={e => setIsDemo(e.target.checked)} />
        <span>Demo talaba (hali darsga kelmagan)</span>
      </label>
    </Modal>
  )
}


// ── Stage management (admin) ───────────────────────────────────────────────
function StageManager({ stages, onClose, onChanged }) {
  const [confirmUI, ask] = useConfirm()
  const [list, setList] = useState(stages)
  const [name, setName] = useState('')
  const [color, setColor] = useState('sky')
  const [kind, setKind] = useState('lead')
  const [busy, setBusy] = useState(false)
  const modalRef = useRef(null)
  useFocusTrap(true, modalRef, onClose)

  async function refresh() { const s = await fetchLeadStages(); setList(s); onChanged?.() }

  async function add() {
    if (!name.trim()) return toast.error('Nom kiriting')
    setBusy(true)
    try { await createLeadStage({ name: name.trim(), color, kind, icon: 'circle' }); setName(''); await refresh(); toast.success("Qo'shildi") }
    catch (e) { toast.error(e.message) } finally { setBusy(false) }
  }
  async function patch(s, data) {
    try { await updateLeadStage(s.id, data); await refresh() } catch (e) { toast.error(e.message) }
  }
  async function remove(s) {
    const ok = await ask({
      title: 'Bosqichni o\'chirish',
      message: `"${s.name}" bosqichi o'chirilsinmi?`,
      detail: 'Bu bosqichdagi lidlar birinchi bosqichga ko\'chiriladi.',
      confirmLabel: "Ha, o'chirish",
    })
    if (!ok) return
    try { await deleteLeadStage(s.id); await refresh() } catch (e) { toast.error(e.message) }
  }
  async function move(idx, dir) {
    const arr = [...list]
    const j = idx + dir
    if (j < 0 || j >= arr.length) return
    ;[arr[idx], arr[j]] = [arr[j], arr[idx]]
    setList(arr)
    try { await reorderLeadStages(arr.map(s => s.id)); onChanged?.() } catch (e) { toast.error(e.message); refresh() }
  }

  return (
    <Overlay className="modal-overlay" onClick={onClose}>
      {confirmUI}
      <div className="modal" ref={modalRef} onClick={e => e.stopPropagation()} style={{ maxWidth: 560 }}>
        <div className="modal-header">
          <h3>Pipeline bosqichlari</h3>
          <button className="modal-close" aria-label="Yopish" onClick={onClose}>✕</button>
        </div>
        <div className="modal-body">
          {list.map((s, i) => (
            <div key={s.id} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
              <span className="dot" style={{ width: 12, height: 12, borderRadius: '50%', background: hex(s.color), flex: 'none' }} />
              <strong style={{ flex: 1 }}>{s.name}</strong>
              <span className="kc-tag">{KIND_LABEL[s.kind]}</span>
              <span className="text-muted" style={{ fontSize: 12 }}>{s.lead_count} lid</span>
              <button className="btn-icon" disabled={i === 0} onClick={() => move(i, -1)}><FontAwesomeIcon icon={faArrowUp} /></button>
              <button className="btn-icon" disabled={i === list.length - 1} onClick={() => move(i, 1)}><FontAwesomeIcon icon={faArrowDown} /></button>
              <button className="btn-icon danger" onClick={() => remove(s)}><FontAwesomeIcon icon={faTrash} /></button>
            </div>
          ))}

          <div style={{ marginTop: 16 }}>
            <label>Yangi bosqich</label>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
              <input className="field" style={{ flex: 1, minWidth: 140 }} value={name}
                onChange={e => setName(e.target.value)} placeholder="Bosqich nomi" />
              <select className="field" style={{ width: 130 }} value={kind} onChange={e => setKind(e.target.value)}>
                <option value="lead">Jarayon</option>
                <option value="won">Yutuq</option>
                <option value="lost">Yo'qotish</option>
              </select>
            </div>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', margin: '10px 0' }}>
              {COLOR_KEYS.map(c => (
                <button key={c} onClick={() => setColor(c)}
                  title={c}
                  style={{
                    width: 24, height: 24, borderRadius: '50%', background: hex(c),
                    border: color === c ? '3px solid var(--text)' : '2px solid var(--border)',
                    cursor: 'pointer',
                  }} />
              ))}
            </div>
            <button className="button" onClick={add} disabled={busy}>
              <FontAwesomeIcon icon={faPlus} /> Bosqich qo'shish
            </button>
          </div>
        </div>
        <div className="modal-footer">
          <button className="button secondary" onClick={onClose}>Yopish</button>
        </div>
      </div>
    </Overlay>
  )
}

// ── Referral funnel board — draggable nodes, full-page ──────────────────────
const FF_NODE_W = 190
const FF_NODE_H = 96
const FF_DEFAULT_POS = {
  target:   { x: 60,  y: 260 },
  canceled: { x: 400, y: 60  },
  waiting:  { x: 400, y: 260 },
  comming:  { x: 740, y: 460 },
  payed:    { x: 1040, y: 460 },
}
const FF_STORAGE_KEY = 'ithub_referral_funnel_positions_v1'

const FF_NODE_DEFS = [
  { key: 'target',   label: 'Kelgan',        color: COLORS.sky },
  { key: 'canceled', label: 'Bekor qilindi', color: COLORS.red },
  { key: 'waiting',  label: 'Kutilmoqda',    color: COLORS.amber },
  { key: 'comming',  label: 'Kelmoqchi',     color: COLORS.violet },
  { key: 'payed',    label: "To'landi",      color: COLORS.emerald },
]

const FF_VIEW_DEFAULT = { x: 0, y: 0, scale: 1 }
const FF_MIN_SCALE = 0.3
const FF_MAX_SCALE = 2.5

function FunnelBoard({ referrer, onClose }) {
  const boardRef = useRef(null)
  const dragRef = useRef(null)   // node drag
  const panRef = useRef(null)    // whole-board pan
  const [pos, setPos] = useState(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(FF_STORAGE_KEY))
      return saved?.positions ? { ...FF_DEFAULT_POS, ...saved.positions } : { ...FF_DEFAULT_POS }
    } catch { return { ...FF_DEFAULT_POS } }
  })
  const [view, setView] = useState(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(FF_STORAGE_KEY))
      return saved?.view || { ...FF_VIEW_DEFAULT }
    } catch { return { ...FF_VIEW_DEFAULT } }
  })
  const [panel, setPanel] = useState(null)     // { key, label, color } | null
  const [panelLeads, setPanelLeads] = useState(null)
  const [panelLoading, setPanelLoading] = useState(false)

  useEffect(() => {
    localStorage.setItem(FF_STORAGE_KEY, JSON.stringify({ positions: pos, view }))
  }, [pos, view])

  useEffect(() => {
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = '' }
  }, [])

  const nodes = FF_NODE_DEFS.map(n => ({ ...n, count: referrer.funnel[n.key] }))
  const edges = [
    ['target', 'canceled'], ['target', 'waiting'], ['target', 'comming'],
    ['waiting', 'comming'], ['comming', 'payed'],
  ]
  const center = (k) => ({ x: pos[k].x + FF_NODE_W / 2, y: pos[k].y + FF_NODE_H / 2 })

  function onNodePointerDown(e, key) {
    e.stopPropagation()
    dragRef.current = {
      key, moved: false,
      startX: e.clientX, startY: e.clientY,
      startPosX: pos[key].x, startPosY: pos[key].y,
    }
    e.currentTarget.setPointerCapture(e.pointerId)
  }
  function onBoardPointerDown(e) {
    if (e.target.closest('.ff-node')) return
    panRef.current = {
      startX: e.clientX, startY: e.clientY,
      startViewX: view.x, startViewY: view.y,
    }
    e.currentTarget.setPointerCapture(e.pointerId)
  }
  function onPointerMove(e) {
    if (dragRef.current) {
      const d = dragRef.current
      if (Math.abs(e.clientX - d.startX) > 4 || Math.abs(e.clientY - d.startY) > 4) d.moved = true
      const dx = (e.clientX - d.startX) / view.scale
      const dy = (e.clientY - d.startY) / view.scale
      setPos(p => ({ ...p, [d.key]: { x: d.startPosX + dx, y: d.startPosY + dy } }))
      return
    }
    if (panRef.current) {
      const { startX, startY, startViewX, startViewY } = panRef.current
      setView(v => ({ ...v, x: startViewX + (e.clientX - startX), y: startViewY + (e.clientY - startY) }))
    }
  }
  function onPointerUp() {
    const d = dragRef.current
    dragRef.current = null
    panRef.current = null
    if (d && !d.moved) openPanel(d.key)
  }

  function onWheel(e) {
    e.preventDefault()
    const rect = boardRef.current.getBoundingClientRect()
    const cx = e.clientX - rect.left
    const cy = e.clientY - rect.top
    if (e.ctrlKey) {
      // Trackpadda ikki barmoq bilan pinch (yoki ctrl+scroll) — kursor tagini markaz qilib zoom
      setView(v => {
        const factor = Math.exp(-e.deltaY * 0.012)
        const scale = Math.min(FF_MAX_SCALE, Math.max(FF_MIN_SCALE, v.scale * factor))
        const k = scale / v.scale
        return { scale, x: cx - (cx - v.x) * k, y: cy - (cy - v.y) * k }
      })
    } else {
      // Trackpadda ikki barmoq bilan surish (pan)
      setView(v => ({ ...v, x: v.x - e.deltaX, y: v.y - e.deltaY }))
    }
  }

  function zoomBy(factor) {
    const rect = boardRef.current.getBoundingClientRect()
    const cx = rect.width / 2, cy = rect.height / 2
    setView(v => {
      const scale = Math.min(FF_MAX_SCALE, Math.max(FF_MIN_SCALE, v.scale * factor))
      const k = scale / v.scale
      return { scale, x: cx - (cx - v.x) * k, y: cy - (cy - v.y) * k }
    })
  }

  async function openPanel(key) {
    const node = FF_NODE_DEFS.find(n => n.key === key)
    setPanel(node)
    setPanelLeads(null)
    setPanelLoading(true)
    try {
      const params = { referred_by_id: referrer.referrer_id }
      if (key !== 'target') params.bucket = key
      const leads = await fetchLeads(params)
      setPanelLeads(leads)
    } catch {
      toast.error("Lidlarni yuklab bo'lmadi")
      setPanelLeads([])
    } finally {
      setPanelLoading(false)
    }
  }

  return (
    <Overlay className="ff-overlay">
      <div className="ff-header">
        <div>
          <h2>{referrer.referrer_name} — taklif qilingan bolalar</h2>
          <div className="text-muted" style={{ fontSize: 13 }}>
            {referrer.total_leads} ta lid · {referrer.total_paid} ta to'landi · bo'sh joyni sudrab butun boardni suring, trackpadda ikki barmoq bilan suring/pinch qiling
          </div>
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          <button className="button secondary" onClick={() => { setPos({ ...FF_DEFAULT_POS }); setView({ ...FF_VIEW_DEFAULT }) }}>Joylashuvni tiklash</button>
          <button className="button" onClick={onClose}><FontAwesomeIcon icon={faXmark} /> Yopish</button>
        </div>
      </div>
      <div className="ff-body">
        <div
          className="ff-board"
          ref={boardRef}
          onWheel={onWheel}
          onPointerDown={onBoardPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerLeave={onPointerUp}
        >
          <div className="ff-canvas" style={{ transform: `translate(${view.x}px, ${view.y}px) scale(${view.scale})` }}>
            <svg className="ff-edges">
              <defs>
                <marker id="ff-arrowhead" markerWidth="10" markerHeight="10" refX="8" refY="4" orient="auto">
                  <path d="M0,0 L8,4 L0,8 Z" fill="var(--muted-2)" />
                </marker>
              </defs>
              {edges.map(([a, b]) => {
                const p1 = center(a), p2 = center(b)
                const mx = (p1.x + p2.x) / 2
                return (
                  <path key={a + b}
                    d={`M${p1.x},${p1.y} C ${mx},${p1.y} ${mx},${p2.y} ${p2.x},${p2.y}`}
                    stroke="var(--muted-2)" strokeWidth="2.5" fill="none" markerEnd="url(#ff-arrowhead)" />
                )
              })}
            </svg>
            {nodes.map(n => (
              <div key={n.key} className={`ff-node${panel?.key === n.key ? ' active' : ''}`}
                style={{ left: pos[n.key].x, top: pos[n.key].y, width: FF_NODE_W, height: FF_NODE_H, '--ff-accent': n.color }}
                onPointerDown={e => onNodePointerDown(e, n.key)}>
                <div className="ff-node-label">{n.label}</div>
                <div className="ff-node-count">{n.count}</div>
                <div className="ff-node-hint">bosing →</div>
              </div>
            ))}
          </div>

          <div className="ff-zoom">
            <button className="btn-icon" onClick={() => zoomBy(1 / 1.2)}>−</button>
            <span>{Math.round(view.scale * 100)}%</span>
            <button className="btn-icon" onClick={() => zoomBy(1.2)}>+</button>
          </div>
        </div>

        {panel && (
          <div className="ff-panel">
            <div className="ff-panel-head" style={{ '--ff-accent': panel.color }}>
              <div>
                <div className="ff-panel-title">{panel.label}</div>
                <div className="text-muted" style={{ fontSize: 12 }}>
                  {panelLeads ? `${panelLeads.length} ta lid` : 'Yuklanmoqda...'}
                </div>
              </div>
              <button className="btn-icon" onClick={() => setPanel(null)}><FontAwesomeIcon icon={faXmark} /></button>
            </div>
            <div className="ff-panel-list">
              {panelLoading && <div className="muted center py-8">Yuklanmoqda...</div>}
              {!panelLoading && panelLeads && panelLeads.length === 0 && (
                <div className="muted center py-8">Bu guruhda lid yo'q</div>
              )}
              {!panelLoading && panelLeads && panelLeads.map(l => (
                <div key={l.id} className="ff-panel-row">
                  <div className="ff-panel-row-name">{l.full_name}</div>
                  <div className="ff-panel-row-meta">
                    <span><FontAwesomeIcon icon={faPhone} /> {l.phone}</span>
                    {l.stage_name && <span className="kc-tag">{l.stage_name}</span>}
                  </div>
                  <div className="text-muted" style={{ fontSize: 11.5 }}>{fmtDate(l.created_at)}</div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </Overlay>
  )
}

// ── Analytics view ──────────────────────────────────────────────────────────
function Analytics() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [boardOpen, setBoardOpen] = useState(null)

  useEffect(() => { (async () => {
    try { setData(await fetchLeadAnalytics()) } catch { toast.error("Yuklab bo'lmadi") } finally { setLoading(false) }
  })() }, [])

  if (loading) return <div className="muted center py-8">Yuklanmoqda...</div>
  if (!data) return null
  const maxCount = Math.max(1, ...data.distribution.map(d => d.count))

  return (
    <div>
      <div className="analytics-tiles">
        <div className="a-tile"><div className="a-label">Jami lidlar</div><div className="a-value">{data.total}</div></div>
        <div className="a-tile"><div className="a-label">Ro'yxatdan o'tgan</div><div className="a-value" style={{ color: COLORS.emerald }}>{data.won}</div></div>
        <div className="a-tile"><div className="a-label">Yo'qotilgan</div><div className="a-value" style={{ color: COLORS.red }}>{data.lost}</div></div>
        <div className="a-tile"><div className="a-label">Konversiya</div><div className="a-value" style={{ color: COLORS.indigo }}>{data.conversion}%</div></div>
      </div>

      <div className="analytics-grid">
        <div className="panel-card">
          <h4>Bosqichlar bo'yicha taqsimot</h4>
          {data.distribution.map(d => (
            <div key={d.slug} className="funnel-row">
              <div className="fr-top">
                <span>{d.name}</span>
                <span className="text-muted">{d.count} · {d.percentage}%</span>
              </div>
              <div className="funnel-bar">
                <span style={{ width: `${(d.count / maxCount) * 100}%`, background: hex(d.color) }} />
              </div>
            </div>
          ))}
        </div>

        <div className="panel-card">
          <h4>Manba bo'yicha konversiya</h4>
          {data.sources.length === 0 ? (
            <div className="muted" style={{ fontSize: 13 }}>Ma'lumot yo'q</div>
          ) : (
            <table className="src-table">
              <thead><tr><th>Manba</th><th className="num">Lidlar</th><th className="num">Ro'yxat</th><th className="num">Konv.</th></tr></thead>
              <tbody>
                {data.sources.map(s => {
                  const good = s.conversion_rate >= 30
                  return (
                    <tr key={s.source}>
                      <td>{s.source}</td>
                      <td className="num">{s.total}</td>
                      <td className="num">{s.enrolled}</td>
                      <td className="num">
                        <span className="conv-pill" style={{
                          background: soft(good ? COLORS.emerald : COLORS.amber),
                          color: good ? COLORS.emerald : COLORS.amber,
                        }}>{s.conversion_rate}%</span>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>

      <CommentStats />

      {data.referrals && data.referrals.length > 0 && (
        <div className="panel-card" style={{ marginTop: 22 }}>
          <h4>Taklif qilingan bolalar (oylik)</h4>
          <div className="text-muted" style={{ fontSize: 12, marginBottom: 14 }}>
            Facebook/Instagram orqali kelgan va shu xodimga bog'langan lidlar — kulrang: kelgan lidlar, yashil: to'lov qilib ro'yxatdan o'tganlar
          </div>
          {data.referrals.map(r => {
            return (
              <div key={r.referrer_id} style={{ marginBottom: 30 }}>
                <div className="fr-top" style={{ marginBottom: 10 }}>
                  <span>{r.referrer_name}</span>
                  <span className="text-muted">{r.total_leads} ta lid · {r.total_paid} ta to'landi</span>
                </div>
                <div className="ff-preview">
                  {[
                    { label: 'Kelgan', count: r.funnel.target, color: COLORS.sky },
                    { label: 'Bekor qilindi', count: r.funnel.canceled, color: COLORS.red },
                    { label: 'Kutilmoqda', count: r.funnel.waiting, color: COLORS.amber },
                    { label: 'Kelmoqchi', count: r.funnel.comming, color: COLORS.violet },
                    { label: "To'landi", count: r.funnel.payed, color: COLORS.emerald },
                  ].map(chip => (
                    <div key={chip.label} className="ff-chip" style={{ '--ff-accent': chip.color }}>
                      <span className="ff-chip-count">{chip.count}</span>
                      <span className="ff-chip-label">{chip.label}</span>
                    </div>
                  ))}
                  <button className="button secondary" onClick={() => setBoardOpen(r)}>
                    <FontAwesomeIcon icon={faChartPie} /> To'liq sxema
                  </button>
                </div>
                <div className="text-muted" style={{ fontSize: 11.5, margin: '14px 0 6px' }}>Oylik tarix</div>
                <BarChart
                  height={150}
                  seriesLabel="Lidlar"
                  compareLabel="To'landi"
                  valueFormat={v => String(Math.round(v))}
                  tooltipFormat={v => String(Math.round(v))}
                  data={r.months.map(m => {
                    const [y, mo] = m.period.split('-')
                    return { label: `${mo}/${y.slice(2)}`, value: m.leads_count, compare: m.paid_count }
                  })}
                />
              </div>
            )
          })}
        </div>
      )}

      {boardOpen && <FunnelBoard referrer={boardOpen} onClose={() => setBoardOpen(null)} />}
    </div>
  )
}

// ── Izohlar (eslatma matnlari) statistikasi ────────────────────────────────
const MONTH_NAMES = ['Yan', 'Fev', 'Mar', 'Apr', 'May', 'Iyun', 'Iyul', 'Avg', 'Sen', 'Okt', 'Noy', 'Dek']
const fmtMonth = (period) => {
  const [y, mo] = period.split('-')
  return `${MONTH_NAMES[Number(mo) - 1] || mo} ${y}`
}
const fmtDay = (s) => s ? new Date(s).toLocaleDateString('uz-UZ', { dateStyle: 'medium' }) : '—'

function CommentStats() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => { (async () => {
    try { setData(await fetchCommentStats()) } catch { toast.error("Izohlar statistikasini yuklab bo'lmadi") }
    finally { setLoading(false) }
  })() }, [])

  if (loading) return <div className="panel-card" style={{ marginTop: 22 }}><div className="muted center py-4">Yuklanmoqda...</div></div>
  if (!data) return null


  return (
    <div className="panel-card" style={{ marginTop: 22 }}>
      <h4>Izohlar statistikasi</h4>
      <div className="text-muted" style={{ fontSize: 12, marginBottom: 14 }}>
        Lidlarga qo'shilgan eslatma/izohlar (matn kiritilganlar) bo'yicha
      </div>

      <div className="analytics-tiles" style={{ marginBottom: 18 }}>
        <div className="a-tile"><div className="a-label">Jami izohlar</div><div className="a-value">{data.total}</div></div>
        <div className="a-tile"><div className="a-label">Birinchi izoh</div><div className="a-value" style={{ fontSize: 15 }}>{fmtDay(data.first_at)}</div></div>
        <div className="a-tile"><div className="a-label">Oxirgi izoh</div><div className="a-value" style={{ fontSize: 15 }}>{fmtDay(data.last_at)}</div></div>
        <div className="a-tile">
          <div className="a-label">Eng ko'p oy</div>
          <div className="a-value" style={{ color: COLORS.indigo, fontSize: 15 }}>
            {data.busiest_month ? `${fmtMonth(data.busiest_month.period)} · ${data.busiest_month.count}` : '—'}
          </div>
        </div>
      </div>

      {data.months.length === 0 ? (
        <div className="muted" style={{ fontSize: 13 }}>Hozircha izoh yo'q</div>
      ) : (
        <>
          <div className="text-muted" style={{ fontSize: 11.5, margin: '4px 0 6px' }}>Oylik tarix</div>
          <BarChart
            height={150}
            valueFormat={v => String(Math.round(v))}
            tooltipFormat={v => String(Math.round(v))}
            highlightIndex={data.months.findIndex(m => m.period === data.busiest_month?.period)}
            data={data.months.map(m => ({ label: fmtMonth(m.period), value: m.count }))}
          />
        </>
      )}

      {data.by_author.length > 0 && (
        <>
          <div className="text-muted" style={{ fontSize: 11.5, margin: '18px 0 6px' }}>Kim ko'proq izoh yozgan</div>
          <table className="src-table">
            <thead><tr><th>Xodim</th><th className="num">Izohlar</th></tr></thead>
            <tbody>
              {data.by_author.map(a => (
                <tr key={a.author_name}><td>{a.author_name}</td><td className="num">{a.count}</td></tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  )
}

// ── Intake form manager (admin) ─────────────────────────────────────────────
function IntakeFormManager({ sources, onClose }) {
  const [confirmUI, ask] = useConfirm()
  const [list, setList] = useState([])
  const [name, setName] = useState('')
  const [title, setTitle] = useState('')
  const [desc, setDesc] = useState('')
  const [sourceId, setSourceId] = useState('')
  const [busy, setBusy] = useState(false)
  const modalRef = useRef(null)
  useFocusTrap(true, modalRef, onClose)

  useEffect(() => { refresh() }, [])
  async function refresh() { try { setList(await fetchIntakeForms()) } catch {} }

  const linkFor = (slug) => `${window.location.origin}/#intake/${slug}`

  async function add() {
    if (!name.trim()) return toast.error('Nom kiriting')
    setBusy(true)
    try {
      await createIntakeForm({
        name: name.trim(), title: title.trim() || null,
        description: desc.trim() || null, source_id: sourceId ? Number(sourceId) : null,
      })
      setName(''); setTitle(''); setDesc(''); setSourceId(''); await refresh(); toast.success("Forma yaratildi")
    } catch (e) { toast.error(e.message) } finally { setBusy(false) }
  }
  async function toggle(f) {
    try { await updateIntakeForm(f.id, { is_active: !f.is_active }); refresh() } catch (e) { toast.error(e.message) }
  }
  async function remove(f) {
    const ok = await ask({
      title: 'Formani o\'chirish',
      message: `"${f.name}" formasi o'chirilsinmi?`,
      detail: 'Uning ommaviy havolasi ishlamay qoladi.',
      confirmLabel: "Ha, o'chirish",
    })
    if (!ok) return
    try { await deleteIntakeForm(f.id); refresh() } catch (e) { toast.error(e.message) }
  }
  async function copy(slug) {
    try { await navigator.clipboard.writeText(linkFor(slug)); toast.success('Havola nusxalandi') }
    catch { toast.error('Nusxalab bo\'lmadi') }
  }

  return (
    <Overlay className="modal-overlay" onClick={onClose}>
      {confirmUI}
      <div className="modal" ref={modalRef} onClick={e => e.stopPropagation()} style={{ maxWidth: 600 }}>
        <div className="modal-header">
          <h3>Ommaviy qabul formalari</h3>
          <button className="modal-close" aria-label="Yopish" onClick={onClose}>✕</button>
        </div>
        <div className="modal-body">
          {list.length === 0 && <div className="muted" style={{ fontSize: 13 }}>Hozircha forma yo'q</div>}
          {list.map(f => (
            <div key={f.id} className={`intake-row${f.is_active ? '' : ' ir-off'}`}>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div className="ir-name">{f.name} {!f.is_active && <span className="text-muted">(o'chiq)</span>}</div>
                <div className="ir-link"><FontAwesomeIcon icon={faLink} /> {linkFor(f.slug)}</div>
                <div className="text-muted" style={{ fontSize: 11.5 }}>{f.submissions} ta ariza · manba: {f.source_name || '—'}</div>
              </div>
              <button className="btn-icon" title="Havolani nusxalash" onClick={() => copy(f.slug)}><FontAwesomeIcon icon={faCopy} /></button>
              <button className="df-preset" onClick={() => toggle(f)}>{f.is_active ? "O'chirish" : 'Yoqish'}</button>
              <button className="btn-icon danger" onClick={() => remove(f)}><FontAwesomeIcon icon={faTrash} /></button>
            </div>
          ))}

          <div style={{ marginTop: 18 }}>
            <label>Yangi forma</label>
            <input className="field" value={name} onChange={e => setName(e.target.value)} placeholder="Forma nomi (ichki)" />
            <label>Sarlavha (formada ko'rinadi)</label>
            <input className="field" value={title} onChange={e => setTitle(e.target.value)} placeholder="Masalan: Minar Academy — Qabul" />
            <label>Tavsif</label>
            <textarea className="field" rows={2} value={desc} onChange={e => setDesc(e.target.value)} placeholder="Ariza qoldiring, biz bog'lanamiz" />
            <label>Manba</label>
            <select className="field" value={sourceId} onChange={e => setSourceId(e.target.value)}>
              <option value="">Manba tanlang</option>
              {sources.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
            <button className="button" style={{ marginTop: 12 }} onClick={add} disabled={busy}>
              <FontAwesomeIcon icon={faPlus} /> Forma yaratish
            </button>
          </div>
        </div>
        <div className="modal-footer">
          <button className="button secondary" onClick={onClose}>Yopish</button>
        </div>
      </div>
    </Overlay>
  )
}
