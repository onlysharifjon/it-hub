import { PageIntro } from './ui/Workspace'
import { Initials, SummaryRow, ViewTabs } from './ui/Workspace'
import Overlay from './ui/Overlay'
import PersonName from './ui/PersonName'
import { useEffect, useMemo, useState } from 'react'
import './parents-form.css'
import { toast } from 'react-hot-toast'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faPeopleRoof, faPlus, faKey, faToggleOn, faToggleOff,
  faCopy, faSearch, faUserPlus, faXmark, faMobileScreen, faPaperPlane, faCheck,
  faUsers, faUser, faFileExcel, faFilePdf, faArrowLeft, faTrash,
} from '@fortawesome/free-solid-svg-icons'
import {
  fetchParents, createParent, updateParent, resetParentPassword,
  linkParentChild, unlinkParentChild, fetchStudents, broadcastToParents,
  bulkCreateParents, downloadParentCredentials, deleteParent,
} from '../api'
import useConfirm from './ui/useConfirm'
import DataTable, { RowActions } from './ui/DataTable'

const EMPTY = { full_name: '', phone: '', username: '', password: '', student_ids: [] }

export default function Parents({ currentUser }) {
  const [confirmUI, ask] = useConfirm()
  const canManage = currentUser?.role === 'hunter' || currentUser?.role === 'admin'
  const isAdmin = currentUser?.role === 'admin'

  const [items, setItems] = useState([])
  const [students, setStudents] = useState([])
  const [studentSearch, setStudentSearch] = useState('')
  const [picked, setPicked] = useState({})          // tanlangan talabalar: id -> talaba (qidiruv o'zgarsa ham saqlanadi)
  const [loading, setLoading] = useState(false)
  const [search, setSearch] = useState('')
  const [parentView, setParentView] = useState('families')

  const [modal, setModal] = useState(false)
  // Keng oyna: chapda talabalar, o'ngda bitta yoki ommaviy yaratish
  const [mode, setMode] = useState('single')        // 'single' | 'bulk'
  const [allStudents, setAllStudents] = useState([])
  const [studentsLoading, setStudentsLoading] = useState(false)
  const [linkedIds, setLinkedIds] = useState(new Set())   // akkaunti bor talabalar
  const [pickSearch, setPickSearch] = useState('')
  const [onlyNoAccount, setOnlyNoAccount] = useState(true)
  const [bulkChoice, setBulkChoice] = useState({})  // student_id -> 'mother' | 'father'
  const [bulkResult, setBulkResult] = useState(null)
  const [downloaded, setDownloaded] = useState(false)
  const [form, setForm] = useState(EMPTY)
  const [saving, setSaving] = useState(false)

  // Yaratilgandan keyin login/parol BIR MARTA ko'rsatiladi
  const [creds, setCreds] = useState(null)          // { full_name, username, password }
  const [linkFor, setLinkFor] = useState(null)      // farzand biriktirish modali (parent obj)

  // Telegram orqali barcha ota-onalarga xabar yuborish
  const [broadcastModal, setBroadcastModal] = useState(false)
  const [broadcastText, setBroadcastText] = useState('')
  const [broadcasting, setBroadcasting] = useState(false)

  async function handleBroadcast() {
    if (!broadcastText.trim()) { toast.error('Xabar matnini kiriting'); return }
    setBroadcasting(true)
    try {
      const r = await broadcastToParents(broadcastText.trim())
      if (r.sent > 0) {
        toast.success(`Yuborildi: ${r.sent}/${r.total} ota-onaga`)
        setBroadcastModal(false)
        setBroadcastText('')
      } else {
        toast.error(
          `Hech kimga yetmadi (0/${r.total}).` +
          (r.sample_errors?.length ? ` Sabab: ${r.sample_errors[0]}` : ''),
          { duration: 8000 }
        )
      }
    } catch (e) { toast.error(e.message) }
    finally { setBroadcasting(false) }
  }

  useEffect(() => { load() }, [])
  useEffect(() => {
    // Qidiruv serverda (/students?search=) — 100 tadan ko'p talaba bo'lsa ham hammasi topiladi
    const t = setTimeout(() => {
      fetchStudents({ page_size: 100, search: studentSearch.trim() || undefined })
        .then(r => setStudents(r.items || [])).catch(() => {})
    }, 250)
    return () => clearTimeout(t)
  }, [studentSearch])
  useEffect(() => { if (linkFor) setStudentSearch('') }, [linkFor])

  async function load(q) {
    setLoading(true)
    try { setItems(await fetchParents(q)) }
    catch { toast.error("Yuklab bo'lmadi") }
    finally { setLoading(false) }
  }

  function handleSearch(e) {
    e.preventDefault()
    load(search.trim() || undefined)
  }

  // Talaba kartasidagi ota-ona ma'lumoti (CRM: mother_name/phone, father_name/phone)
  function guardiansOf(s) {
    return [
      { role: 'Ona', name: (s.mother_name || '').trim(), phone: (s.mother_phone || '').trim() },
      { role: 'Ota', name: (s.father_name || '').trim(), phone: (s.father_phone || '').trim() },
    ].filter(g => g.name)
  }

  function pickGuardian(g) {
    setForm(p => ({ ...p, full_name: g.name, phone: g.phone || p.phone }))
  }

  function toggleStudent(s) {
    const adding = !form.student_ids.includes(s.id)
    setPicked(p => {
      const next = { ...p }
      if (adding) next[s.id] = s; else delete next[s.id]
      return next
    })
    setForm(p => {
      const next = {
        ...p,
        student_ids: adding ? [...p.student_ids, s.id] : p.student_ids.filter(x => x !== s.id),
      }
      // Farzand belgilanganda ism/telefon bo'sh bo'lsa — talaba kartasidagi ota-onadan avto to'ldiriladi
      if (adding && !p.full_name.trim()) {
        const g = guardiansOf(s).sort((a, b) => Number(!!b.phone) - Number(!!a.phone))[0]
        if (g) {
          next.full_name = g.name
          if (!p.phone.trim() && g.phone) next.phone = g.phone
        }
      }
      return next
    })
  }

  const pickedGuardians = form.student_ids
    .map(id => picked[id]).filter(Boolean)
    .flatMap(s => guardiansOf(s).map(g => ({ ...g, child: s.full_name, key: `${s.id}-${g.role}` })))

  async function loadAllStudents() {
    // Hamma faol (arxivlanmagan) talabalar — sahifalab (API page_size ≤ 100)
    setStudentsLoading(true)
    try {
      const out = []
      for (let page = 1; page <= 30; page++) {
        const r = await fetchStudents({ page, page_size: 100, is_archived: false })
        const chunk = r.items || []
        out.push(...chunk)
        if (chunk.length < 100 || (r.total && out.length >= r.total)) break
      }
      setAllStudents(out)
      const parents = await fetchParents()
      setLinkedIds(new Set(parents.flatMap(p => (p.children || []).map(c => c.student_id))))
    } catch (e) { toast.error(e.message || "Talabalarni yuklab bo'lmadi") }
    finally { setStudentsLoading(false) }
  }

  function openCreate() {
    setForm(EMPTY); setPicked({}); setStudentSearch(''); setPickSearch('')
    setMode('single'); setBulkChoice({}); setBulkResult(null); setDownloaded(false)
    setModal(true)
    loadAllStudents()
  }

  async function closeCreate() {
    const unsaved = bulkResult && bulkResult.created > 0 && !downloaded
    if (unsaved && !await ask({
      title: 'Parollar yuklab olinmadi',
      message: 'Yaratilgan parollar faqat hozir ko\'rinadi. Yopilsinmi?',
      detail: "Keyin faqat «Parolni yangilash» orqali yangi parol berish mumkin bo'ladi.",
      confirmLabel: 'Ha, yopish',
    })) return
    setModal(false)
    if (bulkResult) load(search.trim() || undefined)
  }

  const digits = v => (v || '').replace(/\D/g, '')
  const hasPhone = v => digits(v).length >= 9

  // Chap ustun: qidiruv + "akkaunti yo'qlar" filtri (brauzerda — hamma talaba yuklangan)
  const visibleStudents = useMemo(() => {
    const q = pickSearch.trim().toLowerCase()
    const qd = digits(q)
    return allStudents.filter(s => {
      if (onlyNoAccount && linkedIds.has(s.id) && !form.student_ids.includes(s.id)) return false
      if (!q) return true
      const hay = [s.full_name, s.mother_name, s.father_name].filter(Boolean).join(' ').toLowerCase()
      if (hay.includes(q)) return true
      return qd.length >= 3 && [s.phone1, s.mother_phone, s.father_phone].some(p => digits(p).includes(qd))
    })
  }, [allStudents, pickSearch, onlyNoAccount, linkedIds, form.student_ids])

  const studentById = useMemo(() => Object.fromEntries(allStudents.map(s => [s.id, s])), [allStudents])
  const allVisibleSelected = visibleStudents.length > 0 && visibleStudents.every(s => form.student_ids.includes(s.id))

  function toggleAllVisible() {
    if (allVisibleSelected) {
      const hide = new Set(visibleStudents.map(s => s.id))
      setForm(p => ({ ...p, student_ids: p.student_ids.filter(id => !hide.has(id)) }))
      setPicked(p => { const n = { ...p }; hide.forEach(id => delete n[id]); return n })
    } else {
      const add = visibleStudents.filter(s => !form.student_ids.includes(s.id))
      setForm(p => ({ ...p, student_ids: [...p.student_ids, ...add.map(s => s.id)] }))
      setPicked(p => ({ ...p, ...Object.fromEntries(add.map(s => [s.id, s])) }))
    }
  }

  function defaultGuardian(s) {
    if (s.mother_name?.trim() && hasPhone(s.mother_phone)) return 'mother'
    if (s.father_name?.trim() && hasPhone(s.father_phone)) return 'father'
    return s.mother_name?.trim() ? 'mother' : 'father'
  }

  // Ommaviy: tanlangan har bir talaba uchun oldindan ko'rish (server baribir qayta tekshiradi)
  const bulkPreview = useMemo(() => {
    const seenPhones = new Map()
    return form.student_ids.map(id => studentById[id] || picked[id]).filter(Boolean).map(s => {
      const g = bulkChoice[s.id] || defaultGuardian(s)
      const name = ((g === 'mother' ? s.mother_name : s.father_name) || '').trim()
      const phone = ((g === 'mother' ? s.mother_phone : s.father_phone) || '').trim()
      const key = digits(phone).slice(-9)
      let state = 'ok', note = 'Yangi akkaunt'
      if (!name) { state = 'bad'; note = (g === 'mother' ? 'Ona' : 'Ota') + ' ismi yo\'q' }
      else if (!hasPhone(phone)) { state = 'bad'; note = 'Telefon yo\'q' }
      else if (linkedIds.has(s.id)) { state = 'info'; note = 'Akkaunt bor — tekshiriladi' }
      else if (seenPhones.has(key)) { state = 'info'; note = `Aka-uka: ${seenPhones.get(key)} bilan bitta akkaunt` }
      if (state !== 'bad' && key && !seenPhones.has(key)) seenPhones.set(key, s.full_name)
      return { s, g, name, phone, state, note,
               canMother: !!s.mother_name?.trim(), canFather: !!s.father_name?.trim() }
    })
  }, [form.student_ids, studentById, picked, bulkChoice, linkedIds])

  const bulkReady = bulkPreview.filter(r => r.state !== 'bad').length

  async function handleBulkCreate() {
    if (bulkReady === 0) return toast.error("Yaratish uchun yaroqli talaba yo'q (ism va telefon kerak)")
    const ok = await ask({
      title: 'Ommaviy yaratish',
      message: `${bulkReady} ta talaba uchun ota-ona akkaunti yaratilsinmi?`,
      detail: "Login — telefon, parol — ism + oxirgi 4 raqam. Raqami allaqachon akkauntda bo'lsa, talaba o'sha akkauntga biriktiriladi (parol o'zgarmaydi).",
      confirmLabel: 'Ha, yaratish', danger: false,
    })
    if (!ok) return
    setSaving(true)
    try {
      const items = bulkPreview.filter(r => r.state !== 'bad').map(r => ({ student_id: r.s.id, guardian: r.g }))
      const res = await bulkCreateParents(items)
      setBulkResult(res); setDownloaded(false)
      toast.success(`Yaratildi: ${res.created}, biriktirildi: ${res.linked}, o'tkazildi: ${res.skipped}`)
      loadAllStudents()
    } catch (e) { toast.error(e.message) }
    finally { setSaving(false) }
  }

  // Faqat hozir yaratilganlar (parol faqat ularda bor); aka-ukalar bitta qatorda
  const credentialRows = useMemo(() => {
    if (!bulkResult) return []
    const byParent = new Map()
    for (const r of bulkResult.rows) {
      if (!r.parent_id || r.status === 'skipped') continue
      if (r.status === 'created') byParent.set(r.parent_id, { full_name: r.full_name, username: r.username, password: r.password, kids: [r.student_name] })
    }
    for (const r of bulkResult.rows) {
      if (r.status === 'linked' && byParent.has(r.parent_id)) byParent.get(r.parent_id).kids.push(r.student_name)
    }
    return [...byParent.values()].map(x => ({ full_name: x.full_name, username: x.username, password: x.password, children: x.kids.filter(Boolean).join(', ') }))
  }, [bulkResult])

  async function handleDownload(format) {
    if (credentialRows.length === 0) return toast.error("Yuklab olinadigan yangi akkaunt yo'q")
    try {
      await downloadParentCredentials(format, credentialRows)
      setDownloaded(true)
    } catch (e) { toast.error(e.message) }
  }

  async function handleCreate() {
    if (!form.full_name.trim()) return toast.error("Ism-familiyani kiriting")
    if (!form.phone.trim()) return toast.error("Telefon raqamini kiriting")
    if (form.student_ids.length === 0) return toast.error("Kamida bitta farzand (talaba) tanlang")
    if (form.password && form.password.length < 6) return toast.error("Parol kamida 6 belgi")
    setSaving(true)
    try {
      const res = await createParent({
        full_name: form.full_name.trim(),
        phone: form.phone.trim(),
        username: form.username.trim() || null,
        password: form.password || null,
        student_ids: form.student_ids,
      })
      toast.success("Akkaunt yaratildi")
      setModal(false)
      setForm(EMPTY)
      setPicked({})
      setCreds({ full_name: res.full_name, username: res.username, password: res.generated_password })
      load()
    } catch (e) { toast.error(e.message) }
    finally { setSaving(false) }
  }

  async function handleDelete(p) {
    const ok = await ask({
      title: "Akkauntni o'chirish",
      message: `${p.full_name} (${p.phone}) akkaunti o'chirilsinmi?`,
      detail: "Login va parol darhol ishlamay qoladi, ota-ona ilovadan chiqariladi, farzandlar bog'lanishi o'chadi. " +
        "To'lov tarixi buxgalteriya uchun saqlanadi. Qaytarib bo'lmaydi — kerak bo'lsa keyin yangi akkaunt ochiladi.",
      confirmLabel: "Ha, o'chirish",
      requireText: "O'CHIRISH",
    })
    if (!ok) return
    try {
      await deleteParent(p.id)
      toast.success("Akkaunt o'chirildi")
      load(search.trim() || undefined)
    } catch (e) { toast.error(e.message) }
  }

  async function handleToggle(p) {
    try {
      await updateParent(p.id, { is_active: !p.is_active })
      toast.success(p.is_active ? "Akkaunt bloklandi" : "Akkaunt faollashtirildi")
      load(search.trim() || undefined)
    } catch (e) { toast.error(e.message) }
  }

  async function handleReset(p) {
    const ok = await ask({
      title: 'Parolni yangilash',
      message: `${p.full_name} uchun yangi parol yaratilsinmi?`,
      detail: 'Eski parol darhol ishlamay qoladi — yangi parol bir marta ko\'rsatiladi.',
      confirmLabel: 'Ha, yangilash',
    })
    if (!ok) return
    try {
      const res = await resetParentPassword(p.id)
      setCreds({ full_name: p.full_name, username: p.username, password: res.generated_password })
      toast.success("Yangi parol yaratildi")
    } catch (e) { toast.error(e.message) }
  }

  async function handleLink(studentId) {
    try {
      await linkParentChild(linkFor.id, studentId)
      toast.success("Farzand biriktirildi")
      setLinkFor(null)
      load(search.trim() || undefined)
    } catch (e) { toast.error(e.message) }
  }

  async function handleUnlink(p, child) {
    const ok = await ask({
      title: 'Farzandni uzish',
      message: `${child.student_name} ushbu ota-onadan uzilsinmi?`,
      detail: "Ota-ona mobil ilovada bu farzandning ma'lumotlarini ko'ra olmaydi.",
      confirmLabel: 'Ha, uzish',
    })
    if (!ok) return
    try {
      await unlinkParentChild(p.id, child.student_id)
      toast.success("Uzildi")
      load(search.trim() || undefined)
    } catch (e) { toast.error(e.message) }
  }

  function copy(text) {
    navigator.clipboard.writeText(text).then(
      () => toast.success("Nusxalandi"),
      () => toast.error("Nusxalab bo'lmadi"),
    )
  }

  const columns = [
    { key: 'full_name', header: 'Ota-ona', sortable: true, render: p => <PersonName name={p.full_name} /> },
    { key: 'phone', header: 'Telefon', sortable: true },
    {
      key: 'username', header: 'Login', sortable: true,
      render: p => (
        <span className="cell-copy">
          <code>{p.username}</code>
          <button className="btn-icon" title="Loginni nusxalash" aria-label="Loginni nusxalash" onClick={() => copy(p.username)}>
            <FontAwesomeIcon icon={faCopy} />
          </button>
        </span>
      ),
    },
    {
      key: 'children', header: 'Farzandlari', sortable: true,
      sortValue: p => p.children.length,
      render: p => p.children.length === 0
        ? <span className="text-muted">—</span>
        : (
          <div className="chip-row">
            {p.children.map(c => (
              <span key={c.student_id} className="ui-badge ui-badge-sm ui-badge-primary">
                {c.student_name}
                {canManage && (
                  <button className="chip-x" title="Uzish" aria-label="Uzish" onClick={() => handleUnlink(p, c)}>
                    <FontAwesomeIcon icon={faXmark} />
                  </button>
                )}
              </span>
            ))}
          </div>
        ),
    },
    {
      key: 'is_active', header: 'Holat', sortable: true,
      render: p => (
        <span className={`status-badge ${p.is_active ? 'active' : 'inactive'}`}>
          {p.is_active ? 'Faol' : 'Bloklangan'}
        </span>
      ),
    },
    ...(canManage ? [{
      key: 'actions', header: '', align: 'right', className: 'actions',
      render: p => (
        <RowActions>
          <button className="btn-icon" title="Farzand biriktirish" aria-label="Farzand biriktirish" onClick={() => setLinkFor(p)}>
            <FontAwesomeIcon icon={faUserPlus} />
          </button>
          <button className="btn-icon" title="Parolni yangilash" aria-label="Parolni yangilash" onClick={() => handleReset(p)}>
            <FontAwesomeIcon icon={faKey} />
          </button>
          <button className="btn-icon" title={p.is_active ? 'Bloklash' : 'Faollashtirish'}
            aria-label={p.is_active ? 'Bloklash' : 'Faollashtirish'} onClick={() => handleToggle(p)}>
            <FontAwesomeIcon icon={p.is_active ? faToggleOn : faToggleOff} />
          </button>
          <button className="btn-icon danger" title="Akkauntni o'chirish" aria-label="Akkauntni o'chirish" onClick={() => handleDelete(p)}>
            <FontAwesomeIcon icon={faTrash} />
          </button>
        </RowActions>
      ),
    }] : []),
  ]

  return (
    <div className="page parents-studio">
      {confirmUI}
      <PageIntro title={<>Ota-onalar</>} description={<><FontAwesomeIcon icon={faMobileScreen} /> Mobil ilova akkauntlari — davomat, baho va to'lovlar.
            Parol faqat yaratilganda bir marta ko'rsatiladi.</>} actions={<><div className="header-actions">
          {isAdmin && (
            <button className="button secondary" onClick={() => { setBroadcastText(''); setBroadcastModal(true) }}>
              <FontAwesomeIcon icon={faPaperPlane} /> Telegram orqali xabar
            </button>
          )}
          {canManage && (
            <button className="button" onClick={openCreate}>
              <FontAwesomeIcon icon={faPlus} /> Akkaunt ochish
            </button>
          )}
        </div></>} />

      <SummaryRow items={[{ label: 'Ro‘yxatdagi ota-onalar', value: items.length }, { label: 'Faol akkauntlar', value: items.filter(p => p.is_active).length }, { label: 'Biriktirilgan farzandlar', value: items.reduce((n,p) => n + (p.children || []).length, 0) }]} />
      <div className="directory-toolbar"><ViewTabs value={parentView} onChange={setParentView} items={[{ key: 'families', label: 'Oilalar' }, { key: 'table', label: 'Jadval' }]} /><form onSubmit={handleSearch}><input className="field" value={search} onChange={e => setSearch(e.target.value)} placeholder="Ism yoki telefon bo‘yicha qidirish" aria-label="Ota-onani qidirish" /></form></div>
      {parentView === 'families' && !loading && items.length > 0 ? <div className="family-grid">{items.map(p => <article key={p.id} className="family-card"><header><Initials name={p.full_name} /><div><h2>{p.full_name}</h2><a href={'tel:' + p.phone}>{p.phone || 'Telefon kiritilmagan'}</a></div><span className={'family-status' + (p.is_active ? ' is-active' : '')}>{p.is_active ? 'Faol' : 'Bloklangan'}</span></header><div className="family-children"><span className="studio-eyebrow">Farzandlar</span>{p.children?.length ? p.children.map(c => <div key={c.student_id ?? c.id}><Initials name={c.full_name || c.student_name} /><span>{c.full_name || c.student_name}</span>{canManage && <button className="btn-icon danger" title="Farzandni ajratish" aria-label="Farzandni ajratish" onClick={() => handleUnlink(p, c)}><FontAwesomeIcon icon={faXmark} /></button>}</div>) : <p>Hali farzand biriktirilmagan</p>}</div>{canManage && <footer><button className="button secondary small" onClick={() => setLinkFor(p)}><FontAwesomeIcon icon={faUserPlus} /> Biriktirish</button><button className="btn-icon" title="Parolni yangilash" aria-label="Parolni yangilash" onClick={() => handleReset(p)}><FontAwesomeIcon icon={faKey} /></button><button className="btn-icon" title={p.is_active ? 'Bloklash' : 'Faollashtirish'} aria-label={p.is_active ? 'Bloklash' : 'Faollashtirish'} onClick={() => handleToggle(p)}><FontAwesomeIcon icon={p.is_active ? faToggleOn : faToggleOff} /></button><button className="btn-icon danger" title="Akkauntni o'chirish" aria-label="Akkauntni o'chirish" onClick={() => handleDelete(p)}><FontAwesomeIcon icon={faTrash} /></button></footer>}</article>)}</div> : <DataTable
        columns={columns}
        rows={items}
        loading={loading}
        rowClassName={p => (!p.is_active ? 'row-inactive' : undefined)}
        clientPageSize={25}
        densityToggle densityKey="parents"
        empty={{
          icon: faPeopleRoof,
          title: search ? 'Hech narsa topilmadi' : "Ota-ona akkauntlari yo'q",
          description: search
            ? "Qidiruv so'zini o'zgartirib ko'ring."
            : 'Akkaunt ochilgach, ota-ona mobil ilovaga kira oladi.',
        }}
      />}

      {/* Yangi akkaunt modali */}
      {modal && (
        <Overlay className="modal-overlay" onClick={closeCreate}>
          <div className="modal pf-modal pf-wide" onClick={e => e.stopPropagation()}>
            <div className="modal-header pf-header">
              <h3><FontAwesomeIcon icon={faPeopleRoof} /> Ota-ona akkaunti ochish</h3>
              <div className="pf-tabs" role="tablist" aria-label="Yaratish turi">
                <button type="button" role="tab" aria-selected={mode === 'single'}
                  className={'pf-tab' + (mode === 'single' ? ' is-on' : '')} onClick={() => setMode('single')}>
                  <FontAwesomeIcon icon={faUser} /> Bitta ota-ona
                </button>
                <button type="button" role="tab" aria-selected={mode === 'bulk'}
                  className={'pf-tab' + (mode === 'bulk' ? ' is-on' : '')} onClick={() => setMode('bulk')}>
                  <FontAwesomeIcon icon={faUsers} /> Ommaviy yaratish
                </button>
              </div>
              <button className="modal-close" onClick={closeCreate}>✕</button>
            </div>

            <div className="pf-layout">
              {/* ── Chap: talabalar ───────────────────────────────────── */}
              <aside className="pf-left">
                <div className="pf-section-head">
                  <span className="pf-step">1</span>
                  <h4>{mode === 'bulk' ? 'Talabalarni belgilang' : 'Farzandini tanlang'} <span className="pf-req">*</span></h4>
                  {form.student_ids.length > 0 && <span className="pf-count">{form.student_ids.length} ta</span>}
                </div>
                <div className="pf-search">
                  <FontAwesomeIcon icon={faSearch} />
                  <input value={pickSearch} onChange={e => setPickSearch(e.target.value)}
                    placeholder="Talaba, ota-ona ismi yoki telefon" aria-label="Talabani qidirish" />
                  {pickSearch && (
                    <button type="button" className="pf-search-clear" aria-label="Qidiruvni tozalash"
                      onClick={() => setPickSearch('')}><FontAwesomeIcon icon={faXmark} /></button>
                  )}
                </div>
                <div className="pf-toolbar">
                  <label className="pf-selectall">
                    <input type="checkbox" checked={allVisibleSelected} onChange={toggleAllVisible}
                      disabled={visibleStudents.length === 0} />
                    Barchasini belgilash ({visibleStudents.length})
                  </label>
                  <div className="pf-filter" role="group" aria-label="Filtr">
                    <button type="button" className={onlyNoAccount ? 'is-on' : ''} onClick={() => setOnlyNoAccount(true)}>Akkaunti yo'q</button>
                    <button type="button" className={!onlyNoAccount ? 'is-on' : ''} onClick={() => setOnlyNoAccount(false)}>Hammasi</button>
                  </div>
                </div>
                <div className="pf-list" role="listbox" aria-multiselectable="true" aria-label="Talabalar">
                  {studentsLoading && allStudents.length === 0 && <div className="pf-empty">Yuklanmoqda…</div>}
                  {visibleStudents.map(s => {
                    const on = form.student_ids.includes(s.id)
                    const gs = guardiansOf(s)
                    return (
                      <label key={s.id} className={'pf-row' + (on ? ' is-on' : '')} role="option" aria-selected={on}>
                        <input type="checkbox" className="pf-check-input" checked={on} onChange={() => toggleStudent(s)} />
                        <span className="pf-check" aria-hidden="true">{on && <FontAwesomeIcon icon={faCheck} />}</span>
                        <span className="pf-row-main">
                          <span className="pf-row-name">
                            {s.full_name}
                            {linkedIds.has(s.id) && <span className="pf-badge">Akkaunt bor</span>}
                          </span>
                          <span className="pf-row-meta">
                            {gs.length > 0 ? gs.map(g => `${g.role}: ${g.name}`).join(' · ') : 'Ota-ona kiritilmagan'}
                          </span>
                        </span>
                      </label>
                    )
                  })}
                  {!studentsLoading && visibleStudents.length === 0 && (
                    <div className="pf-empty">{onlyNoAccount && !pickSearch ? "Hamma talabada akkaunt bor" : 'Talabalar topilmadi'}</div>
                  )}
                </div>
              </aside>

              {/* ── O'ng: bitta ota-ona ─────────────────────────────────── */}
              {mode === 'single' && (
                <div className="pf-main pf-main-single">
                  <section className="pf-card">
                    <div className="pf-section-head">
                      <span className="pf-step">2</span>
                      <h4>Ota-ona</h4>
                    </div>
                    {pickedGuardians.length > 0 ? (
                      <div className="pf-guardians">
                        {pickedGuardians.map(g => {
                          const active = form.full_name === g.name && (!g.phone || form.phone === g.phone)
                          return (
                            <button key={g.key} type="button" className={'pf-guardian' + (active ? ' is-on' : '')}
                              title={`${g.child} — ${g.role.toLowerCase()}si`} onClick={() => pickGuardian(g)}>
                              <strong>{g.role}: {g.name}</strong>
                              {g.phone && <span>{g.phone}</span>}
                            </button>
                          )
                        })}
                      </div>
                    ) : (
                      <p className="pf-hint">Chapdan farzandni belgilang — ota-ona ismi va telefoni avto yoziladi.</p>
                    )}
                    <div className="pf-field">
                      <label>Ism-familiya *</label>
                      <input className="field" value={form.full_name}
                        onChange={e => setForm(p => ({ ...p, full_name: e.target.value }))}
                        placeholder="Farzand tanlansa — avto" />
                    </div>
                    <div className="pf-field">
                      <label>Telefon *</label>
                      <input className="field" value={form.phone} inputMode="tel"
                        onChange={e => setForm(p => ({ ...p, phone: e.target.value }))}
                        placeholder="+998901234567" />
                    </div>
                  </section>

                  <section className="pf-card">
                    <div className="pf-section-head">
                      <span className="pf-step">3</span>
                      <h4>Ilovaga kirish</h4>
                    </div>
                    <div className="pf-field">
                      <label>Login</label>
                      <input className="field" value={form.username}
                        onChange={e => setForm(p => ({ ...p, username: e.target.value }))}
                        placeholder="Bo'sh — telefon" />
                    </div>
                    <div className="pf-field">
                      <label>Parol</label>
                      <input className="field" value={form.password}
                        onChange={e => setForm(p => ({ ...p, password: e.target.value }))}
                        placeholder="Bo'sh — Ism + 4 raqam" autoComplete="new-password" />
                    </div>
                    <p className="pf-hint">Bo'sh qoldirilsa: login — telefon, parol — ism va telefonning oxirgi 4 raqami.</p>
                    <div className="pf-kids">
                      <span className="pf-kids-label">Farzandlari:</span>
                      {form.student_ids.length === 0 && <span className="pf-hint">tanlanmagan</span>}
                      {form.student_ids.map(id => studentById[id] || picked[id]).filter(Boolean).map(s => (
                        <span key={s.id} className="pf-chip">
                          {s.full_name}
                          <button type="button" aria-label={`${s.full_name} ni olib tashlash`} onClick={() => toggleStudent(s)}>
                            <FontAwesomeIcon icon={faXmark} />
                          </button>
                        </span>
                      ))}
                    </div>
                  </section>
                </div>
              )}

              {/* ── O'ng: ommaviy yaratish ──────────────────────────────── */}
              {mode === 'bulk' && !bulkResult && (
                <div className="pf-main">
                  <div className="pf-section-head">
                    <span className="pf-step">2</span>
                    <h4>Har bir talabaga ota-ona akkaunti</h4>
                    {bulkPreview.length > 0 && <span className="pf-count">{bulkReady} ta tayyor</span>}
                  </div>
                  <p className="pf-hint">Login — telefon, parol — ism + oxirgi 4 raqam. Aka-ukalarning ota-onasi bitta raqamda bo'lsa, bitta akkaunt ochiladi.</p>
                  {bulkPreview.length === 0 ? (
                    <div className="pf-empty pf-empty-big">Chapdan talabalarni belgilang yoki «Barchasini belgilash»ni bosing.</div>
                  ) : (
                    <div className="pf-table-wrap">
                      <table className="pf-table">
                        <thead><tr><th>Talaba</th><th>Kimga</th><th>Ota-ona</th><th>Telefon</th><th>Holat</th></tr></thead>
                        <tbody>
                          {bulkPreview.map(r => (
                            <tr key={r.s.id} className={'is-' + r.state}>
                              <td className="pf-td-strong">{r.s.full_name}</td>
                              <td>
                                <div className="pf-seg">
                                  <button type="button" className={r.g === 'mother' ? 'is-on' : ''} disabled={!r.canMother}
                                    onClick={() => setBulkChoice(p => ({ ...p, [r.s.id]: 'mother' }))}>Ona</button>
                                  <button type="button" className={r.g === 'father' ? 'is-on' : ''} disabled={!r.canFather}
                                    onClick={() => setBulkChoice(p => ({ ...p, [r.s.id]: 'father' }))}>Ota</button>
                                </div>
                              </td>
                              <td>{r.name || '—'}</td>
                              <td className="pf-mono">{r.phone || '—'}</td>
                              <td><span className={'pf-status is-' + r.state}>{r.note}</span></td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )}

              {mode === 'bulk' && bulkResult && (
                <div className="pf-main">
                  <div className="pf-result-head">
                    <div className="pf-stat is-ok"><b>{bulkResult.created}</b><span>yaratildi</span></div>
                    <div className="pf-stat is-info"><b>{bulkResult.linked}</b><span>mavjudga biriktirildi</span></div>
                    <div className="pf-stat is-bad"><b>{bulkResult.skipped}</b><span>o'tkazib yuborildi</span></div>
                    <div className="pf-download">
                      <button type="button" className="button" onClick={() => handleDownload('xlsx')} disabled={credentialRows.length === 0}>
                        <FontAwesomeIcon icon={faFileExcel} /> Excel
                      </button>
                      <button type="button" className="button" onClick={() => handleDownload('pdf')} disabled={credentialRows.length === 0}>
                        <FontAwesomeIcon icon={faFilePdf} /> PDF
                      </button>
                    </div>
                  </div>
                  {credentialRows.length > 0 && (
                    <p className={'pf-warn' + (downloaded ? ' is-done' : '')}>
                      {downloaded
                        ? "Fayl yuklab olindi. Uni faqat ota-onalarga shaxsan bering."
                        : "Parollar faqat hozir ko'rinadi — oynani yopishdan oldin Excel yoki PDF yuklab oling."}
                    </p>
                  )}
                  <div className="pf-table-wrap">
                    <table className="pf-table">
                      <thead><tr><th>Talaba</th><th>Ota-ona</th><th>Login</th><th>Parol</th><th>Natija</th></tr></thead>
                      <tbody>
                        {bulkResult.rows.map(r => (
                          <tr key={`${r.student_id}-${r.guardian}`} className={'is-' + (r.status === 'created' ? 'ok' : r.status === 'linked' ? 'info' : 'bad')}>
                            <td className="pf-td-strong">{r.student_name || `#${r.student_id}`}</td>
                            <td>{r.full_name || '—'}</td>
                            <td className="pf-mono">{r.username || '—'}</td>
                            <td className="pf-mono">{r.password || (r.status === 'linked' ? 'o\'zgarmadi' : '—')}</td>
                            <td><span className={'pf-status is-' + (r.status === 'created' ? 'ok' : r.status === 'linked' ? 'info' : 'bad')}>
                              {r.status === 'created' ? 'Yaratildi' : r.reason}
                            </span></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>

            <div className="modal-footer">
              <button className="button secondary" onClick={closeCreate}>{bulkResult ? 'Yopish' : 'Bekor'}</button>
              {mode === 'single' && (
                <button className="button" onClick={handleCreate} disabled={saving}>
                  {saving ? 'Yaratilmoqda...' : 'Yaratish'}
                </button>
              )}
              {mode === 'bulk' && !bulkResult && (
                <button className="button" onClick={handleBulkCreate} disabled={saving || bulkReady === 0}>
                  {saving ? 'Yaratilmoqda...' : `${bulkReady} ta akkaunt yaratish`}
                </button>
              )}
              {mode === 'bulk' && bulkResult && (
                <button className="button secondary" onClick={async () => {
                  if (bulkResult.created > 0 && !downloaded && !await ask({
                    title: 'Parollar yuklab olinmadi', message: "Yaratilgan parollar faqat hozir ko'rinadi. Davom etilsinmi?",
                    confirmLabel: 'Ha, davom etish',
                  })) return
                  setBulkResult(null); setForm(EMPTY); setPicked({}); setBulkChoice({}); setDownloaded(false)
                }}><FontAwesomeIcon icon={faArrowLeft} /> Yana yaratish</button>
              )}
            </div>
          </div>
        </Overlay>
      )}

      {/* Login/parol modali — bir marta ko'rsatiladi */}
      {creds && (
        <Overlay className="modal-overlay" onClick={() => setCreds(null)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3><FontAwesomeIcon icon={faKey} /> Kirish ma'lumotlari</h3>
              <button className="modal-close" onClick={() => setCreds(null)}>✕</button>
            </div>
            <div className="modal-body">
              <p style={{ margin: '0 0 10px' }}>
                <strong>{creds.full_name}</strong> uchun mobil ilova kirish ma'lumotlari.
                Parol <strong>faqat hozir</strong> ko'rinadi — ota-onaga yozib bering yoki yuboring.
              </p>
              <label>Login</label>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <input className="field" readOnly value={creds.username} style={{ fontFamily: 'monospace' }} />
                <button className="button secondary" onClick={() => copy(creds.username)}>
                  <FontAwesomeIcon icon={faCopy} />
                </button>
              </div>
              <label>Parol</label>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <input className="field" readOnly value={creds.password || ''} style={{ fontFamily: 'monospace' }} />
                <button className="button secondary" onClick={() => copy(creds.password || '')}>
                  <FontAwesomeIcon icon={faCopy} />
                </button>
              </div>
              <button
                className="button secondary" style={{ marginTop: 10 }}
                onClick={() => copy(`Minar Academy ota-onalar ilovasi\nLogin: ${creds.username}\nParol: ${creds.password}`)}
              >
                <FontAwesomeIcon icon={faCopy} /> Hammasini nusxalash
              </button>
            </div>
            <div className="modal-footer">
              <button className="button" onClick={() => setCreds(null)}>Yopdim, saqlab oldim</button>
            </div>
          </div>
        </Overlay>
      )}

      {/* Farzand biriktirish modali */}
      {linkFor && (
        <Overlay className="modal-overlay" onClick={() => setLinkFor(null)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3><FontAwesomeIcon icon={faUserPlus} /> Farzand biriktirish</h3>
              <button className="modal-close" onClick={() => setLinkFor(null)}>✕</button>
            </div>
            <div className="modal-body">
              <p style={{ margin: '0 0 10px' }}><strong>{linkFor.full_name}</strong> ga talaba biriktirish:</p>
              <input className="field" value={studentSearch}
                onChange={e => setStudentSearch(e.target.value)}
                placeholder="Talabani qidirish: ism yoki telefon" style={{ marginBottom: 8 }} />
              <div style={{ maxHeight: 260, overflowY: 'auto' }}>
                {students
                  .filter(s => !linkFor.children.some(c => c.student_id === s.id))
                  .map(s => (
                    <button
                      key={s.id} className="button secondary"
                      style={{ display: 'block', width: '100%', textAlign: 'left', marginBottom: 6 }}
                      onClick={() => handleLink(s.id)}
                    >
                      {s.full_name} <span className="text-muted" style={{ fontSize: 12 }}>({s.phone1})</span>
                    </button>
                  ))}
              </div>
            </div>
            <div className="modal-footer">
              <button className="button secondary" onClick={() => setLinkFor(null)}>Yopish</button>
            </div>
          </div>
        </Overlay>
      )}

      {broadcastModal && (
        <Overlay className="modal-overlay" onClick={() => setBroadcastModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3><FontAwesomeIcon icon={faPaperPlane} /> Barcha ota-onalarga xabar</h3>
              <button className="modal-close" onClick={() => setBroadcastModal(false)}>✕</button>
            </div>
            <div className="modal-body">
              <p className="text-muted" style={{ fontSize: 13, marginTop: 0 }}>
                Xabar Telegram orqali — talabaga bog'langan Telegram ID'si bor barcha ota-onalarga yuboriladi
                (mobil ilova akkountiga emas).
              </p>
              <label className="form-label">Xabar matni *</label>
              <textarea className="field" rows={5} value={broadcastText}
                onChange={e => setBroadcastText(e.target.value)}
                placeholder="Xabar matnini shu yerga yozing..." />
            </div>
            <div className="modal-footer">
              <button className="button secondary" onClick={() => setBroadcastModal(false)}>Bekor</button>
              <button className="button" onClick={handleBroadcast} disabled={broadcasting}>
                {broadcasting ? 'Yuborilmoqda...' : 'Yuborish'}
              </button>
            </div>
          </div>
        </Overlay>
      )}
    </div>
  )
}
