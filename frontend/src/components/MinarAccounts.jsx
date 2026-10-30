
import {t as uiText, useI18n as useInterfaceLanguage, localeTag as uiLocaleTag} from '../space-design/i18n';
import SpaceControls from '../space-design/SpaceControls'
import { PageIntro, Initials, SummaryRow } from './ui/Workspace'
import Overlay from './ui/Overlay'
import PersonName from './ui/PersonName'
import { useEffect, useRef, useState } from 'react'
import { toast } from 'react-hot-toast'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faRocket, faPlus, faKey, faToggleOn, faToggleOff,
  faCopy, faLayerGroup, faLock, faQrcode,
} from '@fortawesome/free-solid-svg-icons'
import {
  fetchMinarAccounts, createMinarAccount, createMinarAccountsBulk,
  resetMinarPassword, patchMinarAccount, fetchStudents, fetchMinarAccountGroups,
} from '../api'
import useConfirm from './ui/useConfirm'
import DataTable, { RowActions } from './ui/DataTable'
import MinarQrCards from './MinarQrCards'

const COURSES = ['HTML', 'CSS', 'JavaScript']

export default function MinarAccounts({ currentUser }) {
  useInterfaceLanguage();
  const [confirmUI, ask] = useConfirm()
  const canManage = currentUser?.role === 'admin' || currentUser?.role === 'support_teacher'
  const isTeacher = currentUser?.role === 'teacher'
  const canCreate = canManage || isTeacher

  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(false)
  const [search, setSearch] = useState('')
  const [groupFilter,setGroupFilter]=useState('all'),[statusFilter,setStatusFilter]=useState('all')
  const accountsRequest=useRef(0)

  // Bitta hisob ochish modali
  const [modal, setModal] = useState(false)
  const [studentQuery, setStudentQuery] = useState('')
  const [studentResults, setStudentResults] = useState([])
  const [pickedStudent, setPickedStudent] = useState(null)
  const [course, setCourse] = useState('')
  const [customPassword, setCustomPassword] = useState('')
  const [saving, setSaving] = useState(false)

  // Guruh bo'yicha ommaviy ochish modali
  const [bulkModal, setBulkModal] = useState(false)
  const [qr, setQr] = useState(null)   // null | { studentIds } | { studentIds: null } (guruh tanlash)
  const [groups, setGroups] = useState([])
  const [groupsLoading, setGroupsLoading] = useState(false)
  const [groupsError, setGroupsError] = useState('')
  const groupsRequest = useRef(0)
  const [bulkGroupId, setBulkGroupId] = useState('')
  const [bulkCourse, setBulkCourse] = useState('')
  const [bulkSaving, setBulkSaving] = useState(false)

  // Yaratilgan/tiklangan login-parol — BIR MARTA ko'rsatiladi
  const [creds, setCreds] = useState(null)            // { full_name, login_id, password }
  const [bulkCreds, setBulkCreds] = useState(null)     // [{ full_name, login_id, password }]

  useEffect(() => { const timer=setTimeout(()=>load(search.trim()||undefined),250);return()=>{clearTimeout(timer);accountsRequest.current++} }, [search])

  async function load(q) {
    const request=++accountsRequest.current
    setLoading(true)
    try { const result=await fetchMinarAccounts({ q });if(request===accountsRequest.current)setItems(result) }
    catch { if(request===accountsRequest.current)toast.error(uiText("Yuklab bo'lmadi")) }
    finally { if(request===accountsRequest.current)setLoading(false) }
  }

  function handleSearch(e) {
    e.preventDefault()
    load(search.trim() || undefined)
  }

  useEffect(() => {
    if (!modal) return
    const t = setTimeout(() => {
      fetchStudents({ search: studentQuery.trim() || undefined, is_active: true, page_size: 20 })
        .then(r => setStudentResults(r.items || []))
        .catch(() => setStudentResults([]))
    }, 250)
    return () => clearTimeout(t)
  }, [studentQuery, modal])

  function openCreateModal() {
    setPickedStudent(null)
    setStudentQuery('')
    setStudentResults([])
    setCourse('')
    setCustomPassword('')
    setModal(true)
  }

  async function handleCreate() {
    if (!pickedStudent) return toast.error(uiText("Talabani tanlang"))
    if (customPassword && customPassword.length < 6) return toast.error(uiText("Parol kamida 6 belgi"))
    setSaving(true)
    try {
      const res = await createMinarAccount({
        student_id: pickedStudent.id,
        course: course || null,
        password: customPassword || null,
      })
      toast.success(uiText("Hisob yaratildi"))
      setModal(false)
      setCreds({ full_name: res.full_name, login_id: res.login_id, password: res.password })
      load(search.trim() || undefined)
    } catch (e) { toast.error(e.message) }
    finally { setSaving(false) }
  }

  async function loadGroups() {
    const request = ++groupsRequest.current
    setGroupsLoading(true)
    setGroupsError('')
    setGroups([])
    try {
      const result = await fetchMinarAccountGroups()
      if (request === groupsRequest.current) setGroups(result)
    } catch (e) {
      if (request === groupsRequest.current) setGroupsError(e.message || uiText("Guruhlarni yuklab bo'lmadi"))
    } finally {
      if (request === groupsRequest.current) setGroupsLoading(false)
    }
  }

  function openBulkModal() {
    setBulkGroupId('')
    setBulkCourse('')
    loadGroups()
    setBulkModal(true)
  }

  async function handleBulkCreate() {
    if (bulkSaving || groupsLoading || groupsError) return
    if (!groups.some(g => String(g.id) === bulkGroupId)) return toast.error(uiText("Guruhni tanlang"))
    setBulkSaving(true)
    try {
      const res = await createMinarAccountsBulk({ group_id: Number(bulkGroupId), course: bulkCourse || null })
      setBulkModal(false)
      if (res.count > 0) {
        toast.success(`${res.count} ta hisob yaratildi`)
        setBulkCreds(res.created)
        load(search.trim() || undefined)
      } else {
        toast(uiText("Bu guruhda hisobsiz faol talaba topilmadi"), { icon: 'ℹ️' })
      }
    } catch (e) { toast.error(e.message) }
    finally { setBulkSaving(false) }
  }

  async function handleReset(row) {
    const ok = await ask({
      title: uiText("Parolni yangilash"),
      message: `${row.full_name} (${row.login_id}) uchun yangi parol yaratilsinmi?`,
      detail: uiText("Eski parol darhol ishlamay qoladi — yangi parol bir marta ko'rsatiladi."),
      confirmLabel: 'Ha, yangilash',
    })
    if (!ok) return
    try {
      const res = await resetMinarPassword(row.student_id)
      setCreds({ full_name: row.full_name, login_id: res.login_id, password: res.password })
      toast.success(uiText("Yangi parol yaratildi"))
    } catch (e) { toast.error(e.message) }
  }

  async function handleToggle(row) {
    try {
      await patchMinarAccount(row.student_id, { is_active: !row.is_active })
      toast.success(row.is_active ? uiText("Hisob bloklandi") : uiText("Hisob faollashtirildi"))
      load(search.trim() || undefined)
    } catch (e) { toast.error(e.message) }
  }

  function copy(text) {
    navigator.clipboard.writeText(text).then(
      () => toast.success(uiText("Nusxalandi")),
      () => toast.error(uiText("Nusxalab bo'lmadi")),
    )
  }

  const columns = [
    { key: 'full_name', header: uiText("Talaba"), sortable: true, render: r => <PersonName name={r.full_name} /> },
    { key: 'group', header: uiText("Guruh"), sortable: true, render: r => r.group || <span className="text-muted">—</span> },
    {
      key: 'login_id', header: 'Login', sortable: true,
      render: r => (
        <span className="cell-copy">
          <code>{r.login_id}</code>
          <button className="btn-icon" title={uiText("Loginni nusxalash")} aria-label={uiText("Loginni nusxalash")} onClick={() => copy(r.login_id)}>
            <FontAwesomeIcon icon={faCopy} />
          </button>
        </span>
      ),
    },
    { key: 'course', header: uiText("Kurs"), sortable: true,render:r=>!canManage ? r.course : <select aria-label={r.full_name+uiText(" kursi")} value={r.course} onChange={async e=>{try{await patchMinarAccount(r.student_id,{course:e.target.value});toast.success(uiText("Kurs yangilandi"));load()}catch(e){toast.error(e.message)}}}>{COURSES.map(c=><option key={c}>{c}</option>)}</select> },
    {key:'age_band',header:uiText("Yosh toifasi"),render:r=>!canManage ? (r.age_band || '—') : <select aria-label={r.full_name+uiText(" yosh toifasi")} value={r.age_band||''} onChange={async e=>{try{await patchMinarAccount(r.student_id,{age_band:e.target.value||null});load()}catch(e){toast.error(e.message)}}}><option value="">{uiText("Kiritilmagan")}</option>{['7-9','10-12','13-16','17+'].map(a=><option key={a}>{a}</option>)}</select>},
    { key: 'xp', header: 'XP', sortable: true, align: 'right' },
    { key: 'streak', header: 'Streak', sortable: true, align: 'right' },
    {
      key: 'is_active', header: uiText("Holat"), sortable: true,
      render: r => (
        r.is_active && r.can_login === false
          ? <span className="status-badge inactive"
              title={uiText("Talaba CRM'da arxivda yoki nofaol — o'quvchi kirganda «Akkaunt faol emas» chiqadi. Talabani arxivdan chiqaring.")}>{uiText("Talaba arxivda")}</span>
          : <span className={`status-badge ${r.is_active ? 'active' : 'inactive'}`}>
              {r.locked ? <><FontAwesomeIcon icon={faLock} /> {uiText("Qulflangan")}</> : (r.is_active ? (r.is_test ? uiText("Faol (test)") : uiText("Faol")) : uiText("Bloklangan"))}
            </span>
      ),
    },
    ...(canManage ? [{
      key: 'actions', header: '', align: 'right', className: 'actions',
      render: r => (
        <RowActions>
          <button className="btn-icon" title={uiText("Parolni yangilash")} aria-label={uiText("Parolni yangilash")} onClick={() => handleReset(r)}>
            <FontAwesomeIcon icon={faKey} />
          </button>
          <button className="btn-icon" title={uiText("QR kirish kartasi")} aria-label={uiText("QR kirish kartasi")}
            disabled={r.can_login === false} onClick={() => setQr({ studentIds: [r.student_id] })}>
            <FontAwesomeIcon icon={faQrcode} />
          </button>
          <button className="btn-icon" title={r.is_active ? uiText("Bloklash") : uiText("Faollashtirish")}
            aria-label={r.is_active ? uiText("Bloklash") : uiText("Faollashtirish")} onClick={() => handleToggle(r)}>
            <FontAwesomeIcon icon={r.is_active ? faToggleOn : faToggleOff} />
          </button>
        </RowActions>
      ),
    }] : []),
  ]

  return (
    <div className="page space-enterprise"><SpaceControls/>
      {confirmUI}
      <PageIntro
        title={<>Minar Space</>}
        description={<><FontAwesomeIcon icon={faRocket} /> {isTeacher ? uiText("O'z guruhlaringizdagi o'quvchilar uchun SPACE hisoblari.") : uiText("space.minaracademy.uz o'quvchi kabineti hisoblari.")} {uiText("Parol faqat yaratilganda/tiklanganda bir marta ko'rsatiladi.")}</>}
        actions={canCreate && <div className="header-actions">
          <button className="button secondary" onClick={openBulkModal}>
            <FontAwesomeIcon icon={faLayerGroup} />{uiText("Guruh bo'yicha ochish")}</button>
          {canManage && <><button className="button secondary" onClick={() => {
            loadGroups()
            setQr({ studentIds: null })
          }}>
            <FontAwesomeIcon icon={faQrcode} />{uiText("QR kartalar")}</button>
          <button className="button" onClick={openCreateModal}>
            <FontAwesomeIcon icon={faPlus} />{uiText("Hisob ochish")}</button>
          </>}
        </div>}
      />

      <SummaryRow items={[
        { label: uiText("Jami hisoblar"), value: items.length },
        { label: uiText("Faol"), value: items.filter(r => r.is_active && r.can_login !== false).length },
        { label: uiText("Talaba arxivda"), value: items.filter(r => r.is_active && r.can_login === false).length },
        { label: uiText("Qulflangan"), value: items.filter(r => r.locked).length },
      ]} />

      <div className="directory-toolbar">
        <form onSubmit={handleSearch}>
          <input className="field" value={search} onChange={e => setSearch(e.target.value)}
            placeholder={uiText("Ism yoki login (MA0042) bo'yicha qidirish")} aria-label={uiText("Hisob qidirish")} />
        </form><select aria-label={uiText("Guruh")} value={groupFilter} onChange={e=>setGroupFilter(e.target.value)}><option value="all">{uiText("Barcha guruhlar")}</option>{[...new Set(items.map(r=>r.group))].filter(Boolean).map(g=><option key={g}>{g}</option>)}</select><select aria-label={uiText("Holat")} value={statusFilter} onChange={e=>setStatusFilter(e.target.value)}><option value="all">{uiText("Barcha holatlar")}</option><option value="active">{uiText("Faol")}</option><option value="inactive">{uiText("Nofaol")}</option></select>
      </div>

      <DataTable
        columns={columns}
        rows={items.filter(r=>(groupFilter==='all'||r.group===groupFilter)&&(statusFilter==='all'||(statusFilter==='active'?r.is_active&&r.can_login!==false:!r.is_active||r.can_login===false)))}
        loading={loading}
        rowClassName={r => (!r.is_active || r.can_login === false ? 'row-inactive' : undefined)}
        clientPageSize={25}
        densityToggle densityKey="minar_accounts"
        empty={{
          icon: faRocket,
          title: search ? uiText("Hech narsa topilmadi") : uiText("Minar Space hisoblari yo'q"),
          description: search
            ? uiText("Qidiruv so'zini o'zgartirib ko'ring.")
            : uiText("Hisob ochilgach, talaba space.minaracademy.uz ga kira oladi."),
        }}
      />

      {/* Bitta hisob ochish modali */}
      {modal && (
        <Overlay className="modal-overlay" onClick={() => setModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3><FontAwesomeIcon icon={faRocket} /> {uiText("Minar Space hisobi ochish")}</h3>
              <button className="modal-close" onClick={() => setModal(false)}>✕</button>
            </div>
            <div className="modal-body">
              <label>{uiText("Talaba *")}</label>
              {pickedStudent ? (
                <div className="cell-copy" style={{ marginBottom: 10 }}>
                  <strong>{pickedStudent.full_name}</strong>
                  <button className="btn-icon" title={uiText("Boshqasini tanlash")} aria-label={uiText("Boshqasini tanlash")}
                    onClick={() => setPickedStudent(null)}>
                    <FontAwesomeIcon icon={faPlus} style={{ transform: 'rotate(45deg)' }} />
                  </button>
                </div>
              ) : (
                <>
                  <input className="field" value={studentQuery} onChange={e => setStudentQuery(e.target.value)}
                    placeholder={uiText("Ism bo'yicha qidirish")} />
                  <div style={{ maxHeight: 180, overflowY: 'auto', border: '1px solid var(--border, var(--border))', borderRadius: 8, marginTop: 6 }}>
                    {studentResults.map(s => (
                      <button key={s.id} className="button secondary" type="button"
                        style={{ display: 'block', width: '100%', textAlign: 'left', border: 'none', borderRadius: 0 }}
                        onClick={() => setPickedStudent(s)}>
                        {s.full_name} <span className="text-muted" style={{ fontSize: 12 }}>({s.phone1})</span>
                      </button>
                    ))}
                    {studentResults.length === 0 && <div className="muted py-2" style={{ padding: 8 }}>{uiText("Talaba topilmadi")}</div>}
                  </div>
                </>
              )}

              <div className="row-2" style={{ marginTop: 10 }}>
                <div>
                  <label>{uiText("Kurs")}</label>
                  <select className="field" value={course} onChange={e => setCourse(e.target.value)}>
                    <option value="">{uiText("Avtomatik (guruh bosqichidan)")}</option>
                    {COURSES.map(c => <option key={c} value={c}>{c}</option>)}
                  </select>
                </div>
                <div>
                  <label>{uiText("Parol")}</label>
                  <input className="field" value={customPassword} onChange={e => setCustomPassword(e.target.value)}
                    placeholder={uiText("Bo'sh qolsa — avto")} />
                </div>
              </div>
            </div>
            <div className="modal-footer">
              <button className="button secondary" onClick={() => setModal(false)}>{uiText("Bekor")}</button>
              <button className="button" onClick={handleCreate} disabled={saving}>
                {saving ? uiText("Yaratilmoqda...") : 'Yaratish'}
              </button>
            </div>
          </div>
        </Overlay>
      )}

      {/* Guruh bo'yicha ommaviy ochish modali */}
      {qr && <MinarQrCards groups={groups} groupsLoading={groupsLoading} groupsError={groupsError} onRetryGroups={loadGroups} studentIds={qr.studentIds} onClose={() => setQr(null)} />}

      {bulkModal && (
        <Overlay className="modal-overlay" onClick={() => { if (!bulkSaving) setBulkModal(false) }}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3><FontAwesomeIcon icon={faLayerGroup} /> {uiText("Guruh bo'yicha ommaviy ochish")}</h3>
              <button className="modal-close" disabled={bulkSaving} onClick={() => setBulkModal(false)}>✕</button>
            </div>
            <div className="modal-body">
              <p className="text-muted" style={{ fontSize: 13, marginTop: 0 }}>{uiText("Guruhdagi hisobi hali yo'q barcha faol talabalarga hisob ochiladi.")}{' '}{uiText("Mavjud hisoblarning login va parollari o'zgarmaydi.")}{isTeacher && <> {uiText("Faqat sizga biriktirilgan faol guruhlar ko'rsatiladi.")}</>}
              </p>
              <label htmlFor="minar-bulk-group">{uiText("Guruh *")}</label>
              <select id="minar-bulk-group" className="field" value={bulkGroupId} disabled={groupsLoading || bulkSaving || !!groupsError} onChange={e => setBulkGroupId(e.target.value)}>
                <option value="">{groupsLoading ? uiText("Guruhlar yuklanmoqda...") : uiText("Guruhni tanlang...")}</option>
                {groups.map(g => <option key={g.id} value={g.id}>{g.name}</option>)}
              </select>
              {groupsLoading && <p className="text-muted" role="status">{uiText("Guruhlar yuklanmoqda...")}</p>}
              {groupsError && <div role="alert"><p>{groupsError}</p><button className="button secondary" onClick={loadGroups}>{uiText("Qayta urinish")}</button></div>}
              {!groupsLoading && !groupsError && groups.length === 0 && <p className="text-muted" role="status">{uiText("Faol guruh topilmadi.")}</p>}

              <label style={{ marginTop: 10 }}>{uiText("Kurs")}</label>
              <select className="field" value={bulkCourse} disabled={bulkSaving} onChange={e => setBulkCourse(e.target.value)}>
                <option value="">{uiText("Avtomatik (guruh bosqichidan)")}</option>
                {COURSES.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            <div className="modal-footer">
              <button className="button secondary" disabled={bulkSaving} onClick={() => setBulkModal(false)}>{uiText("Bekor")}</button>
              <button className="button" onClick={handleBulkCreate} disabled={bulkSaving || groupsLoading || !!groupsError || !groups.some(g => String(g.id) === bulkGroupId)}>
                {bulkSaving ? uiText("Yaratilmoqda...") : 'Yaratish'}
              </button>
            </div>
          </div>
        </Overlay>
      )}

      {/* Login/parol modali — bitta hisob, bir marta ko'rsatiladi */}
      {creds && (
        <Overlay className="modal-overlay" onClick={() => setCreds(null)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3><FontAwesomeIcon icon={faKey} /> {uiText("Kirish ma'lumotlari")}</h3>
              <button className="modal-close" onClick={() => setCreds(null)}>✕</button>
            </div>
            <div className="modal-body">
              <p style={{ margin: '0 0 10px' }}>
                <strong>{creds.full_name}</strong>{uiText("uchun space.minaracademy.uz kirish ma'lumotlari. Parol")}<strong>{uiText("faqat hozir")}</strong>{uiText("ko'rinadi — talabaga yozib bering yoki yuboring.")}</p>
              <label>Login</label>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <input className="field" readOnly value={creds.login_id} style={{ fontFamily: 'monospace' }} />
                <button className="button secondary" onClick={() => copy(creds.login_id)}>
                  <FontAwesomeIcon icon={faCopy} />
                </button>
              </div>
              <label>{uiText("Parol")}</label>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <input className="field" readOnly value={creds.password || ''} style={{ fontFamily: 'monospace' }} />
                <button className="button secondary" onClick={() => copy(creds.password || '')}>
                  <FontAwesomeIcon icon={faCopy} />
                </button>
              </div>
              <button
                className="button secondary" style={{ marginTop: 10 }}
                onClick={() => copy(`Minar Space (space.minaracademy.uz)\nLogin: ${creds.login_id}\nParol: ${creds.password}`)}
              >
                <FontAwesomeIcon icon={faCopy} />{uiText("Hammasini nusxalash")}</button>
            </div>
            <div className="modal-footer">
              <button className="button" onClick={() => setCreds(null)}>{uiText("Yopdim, saqlab oldim")}</button>
            </div>
          </div>
        </Overlay>
      )}

      {/* Login/parol ro'yxati — guruh bo'yicha ommaviy yaratilganda */}
      {bulkCreds && (
        <Overlay className="modal-overlay" onClick={() => setBulkCreds(null)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3><FontAwesomeIcon icon={faKey} /> {uiText("Yaratilgan hisoblar (")}{bulkCreds.length})</h3>
              <button className="modal-close" onClick={() => setBulkCreds(null)}>✕</button>
            </div>
            <div className="modal-body">
              <p style={{ margin: '0 0 10px' }}>{uiText("Parollar")}<strong>{uiText("faqat hozir")}</strong>{uiText("ko'rinadi — talabalarga yozib bering yoki yuboring.")}</p>
              <div style={{ maxHeight: 320, overflowY: 'auto' }}>
                {bulkCreds.map(c => (
                  <div key={c.login_id} className="cell-copy" style={{ display: 'flex', gap: 10, padding: '6px 0', borderBottom: '1px solid var(--border, var(--border))' }}>
                    <span style={{ flex: 1 }}>{c.full_name}</span>
                    <code>{c.login_id}</code>
                    <code>{c.password}</code>
                  </div>
                ))}
              </div>
              <button
                className="button secondary" style={{ marginTop: 10 }}
                onClick={() => copy(bulkCreds.map(c => `${c.full_name}: ${c.login_id} / ${c.password}`).join('\n'))}
              >
                <FontAwesomeIcon icon={faCopy} />{uiText("Hammasini nusxalash")}</button>
            </div>
            <div className="modal-footer">
              <button className="button" onClick={() => setBulkCreds(null)}>{uiText("Yopdim, saqlab oldim")}</button>
            </div>
          </div>
        </Overlay>
      )}
    </div>
  )
}
