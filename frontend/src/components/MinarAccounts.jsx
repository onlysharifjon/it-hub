import { PageIntro, Initials, SummaryRow } from './ui/Workspace'
import Overlay from './ui/Overlay'
import PersonName from './ui/PersonName'
import { useEffect, useState } from 'react'
import { toast } from 'react-hot-toast'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faRocket, faPlus, faKey, faToggleOn, faToggleOff,
  faCopy, faLayerGroup, faLock,
} from '@fortawesome/free-solid-svg-icons'
import {
  fetchMinarAccounts, createMinarAccount, createMinarAccountsBulk,
  resetMinarPassword, patchMinarAccount, fetchStudents, fetchGroups,
} from '../api'
import useConfirm from './ui/useConfirm'
import DataTable, { RowActions } from './ui/DataTable'

const COURSES = ['HTML', 'CSS', 'JavaScript']

export default function MinarAccounts({ currentUser }) {
  const [confirmUI, ask] = useConfirm()
  const canManage = currentUser?.role === 'admin' || currentUser?.role === 'support_teacher'

  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(false)
  const [search, setSearch] = useState('')

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
  const [groups, setGroups] = useState([])
  const [bulkGroupId, setBulkGroupId] = useState('')
  const [bulkCourse, setBulkCourse] = useState('')
  const [bulkSaving, setBulkSaving] = useState(false)

  // Yaratilgan/tiklangan login-parol — BIR MARTA ko'rsatiladi
  const [creds, setCreds] = useState(null)            // { full_name, login_id, password }
  const [bulkCreds, setBulkCreds] = useState(null)     // [{ full_name, login_id, password }]

  useEffect(() => { load() }, [])

  async function load(q) {
    setLoading(true)
    try { setItems(await fetchMinarAccounts({ q })) }
    catch { toast.error("Yuklab bo'lmadi") }
    finally { setLoading(false) }
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
    if (!pickedStudent) return toast.error("Talabani tanlang")
    if (customPassword && customPassword.length < 6) return toast.error("Parol kamida 6 belgi")
    setSaving(true)
    try {
      const res = await createMinarAccount({
        student_id: pickedStudent.id,
        course: course || null,
        password: customPassword || null,
      })
      toast.success("Hisob yaratildi")
      setModal(false)
      setCreds({ full_name: res.full_name, login_id: res.login_id, password: res.password })
      load(search.trim() || undefined)
    } catch (e) { toast.error(e.message) }
    finally { setSaving(false) }
  }

  function openBulkModal() {
    setBulkGroupId('')
    setBulkCourse('')
    if (groups.length === 0) {
      fetchGroups({ is_active: true, page_size: 200 }).then(r => setGroups(r.items || [])).catch(() => {})
    }
    setBulkModal(true)
  }

  async function handleBulkCreate() {
    if (!bulkGroupId) return toast.error("Guruhni tanlang")
    setBulkSaving(true)
    try {
      const res = await createMinarAccountsBulk({ group_id: Number(bulkGroupId), course: bulkCourse || null })
      setBulkModal(false)
      if (res.count > 0) {
        toast.success(`${res.count} ta hisob yaratildi`)
        setBulkCreds(res.created)
        load(search.trim() || undefined)
      } else {
        toast("Bu guruhda hisobsiz faol talaba topilmadi", { icon: 'ℹ️' })
      }
    } catch (e) { toast.error(e.message) }
    finally { setBulkSaving(false) }
  }

  async function handleReset(row) {
    const ok = await ask({
      title: 'Parolni yangilash',
      message: `${row.full_name} (${row.login_id}) uchun yangi parol yaratilsinmi?`,
      detail: "Eski parol darhol ishlamay qoladi — yangi parol bir marta ko'rsatiladi.",
      confirmLabel: 'Ha, yangilash',
    })
    if (!ok) return
    try {
      const res = await resetMinarPassword(row.student_id)
      setCreds({ full_name: row.full_name, login_id: res.login_id, password: res.password })
      toast.success("Yangi parol yaratildi")
    } catch (e) { toast.error(e.message) }
  }

  async function handleToggle(row) {
    try {
      await patchMinarAccount(row.student_id, { is_active: !row.is_active })
      toast.success(row.is_active ? "Hisob bloklandi" : "Hisob faollashtirildi")
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
    { key: 'full_name', header: 'Talaba', sortable: true, render: r => <PersonName name={r.full_name} /> },
    { key: 'group', header: 'Guruh', sortable: true, render: r => r.group || <span className="text-muted">—</span> },
    {
      key: 'login_id', header: 'Login', sortable: true,
      render: r => (
        <span className="cell-copy">
          <code>{r.login_id}</code>
          <button className="btn-icon" title="Loginni nusxalash" aria-label="Loginni nusxalash" onClick={() => copy(r.login_id)}>
            <FontAwesomeIcon icon={faCopy} />
          </button>
        </span>
      ),
    },
    { key: 'course', header: 'Kurs', sortable: true },
    { key: 'xp', header: 'XP', sortable: true, align: 'right' },
    { key: 'streak', header: 'Streak', sortable: true, align: 'right' },
    {
      key: 'is_active', header: 'Holat', sortable: true,
      render: r => (
        <span className={`status-badge ${r.is_active ? 'active' : 'inactive'}`}>
          {r.locked ? <><FontAwesomeIcon icon={faLock} /> Qulflangan</> : (r.is_active ? 'Faol' : 'Bloklangan')}
        </span>
      ),
    },
    ...(canManage ? [{
      key: 'actions', header: '', align: 'right', className: 'actions',
      render: r => (
        <RowActions>
          <button className="btn-icon" title="Parolni yangilash" aria-label="Parolni yangilash" onClick={() => handleReset(r)}>
            <FontAwesomeIcon icon={faKey} />
          </button>
          <button className="btn-icon" title={r.is_active ? 'Bloklash' : 'Faollashtirish'}
            aria-label={r.is_active ? 'Bloklash' : 'Faollashtirish'} onClick={() => handleToggle(r)}>
            <FontAwesomeIcon icon={r.is_active ? faToggleOn : faToggleOff} />
          </button>
        </RowActions>
      ),
    }] : []),
  ]

  return (
    <div className="page">
      {confirmUI}
      <PageIntro
        title={<>Minar Space</>}
        description={<><FontAwesomeIcon icon={faRocket} /> space.minaracademy.uz o'quvchi kabineti hisoblari. Parol faqat yaratilganda/tiklanganda bir marta ko'rsatiladi.</>}
        actions={canManage && <div className="header-actions">
          <button className="button secondary" onClick={openBulkModal}>
            <FontAwesomeIcon icon={faLayerGroup} /> Guruh bo'yicha ochish
          </button>
          <button className="button" onClick={openCreateModal}>
            <FontAwesomeIcon icon={faPlus} /> Hisob ochish
          </button>
        </div>}
      />

      <SummaryRow items={[
        { label: 'Jami hisoblar', value: items.length },
        { label: 'Faol', value: items.filter(r => r.is_active).length },
        { label: 'Qulflangan', value: items.filter(r => r.locked).length },
      ]} />

      <div className="directory-toolbar">
        <form onSubmit={handleSearch}>
          <input className="field" value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Ism yoki login (MA0042) bo'yicha qidirish" aria-label="Hisob qidirish" />
        </form>
      </div>

      <DataTable
        columns={columns}
        rows={items}
        loading={loading}
        rowClassName={r => (!r.is_active ? 'row-inactive' : undefined)}
        clientPageSize={25}
        densityToggle densityKey="minar_accounts"
        empty={{
          icon: faRocket,
          title: search ? 'Hech narsa topilmadi' : "Minar Space hisoblari yo'q",
          description: search
            ? "Qidiruv so'zini o'zgartirib ko'ring."
            : "Hisob ochilgach, talaba space.minaracademy.uz ga kira oladi.",
        }}
      />

      {/* Bitta hisob ochish modali */}
      {modal && (
        <Overlay className="modal-overlay" onClick={() => setModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3><FontAwesomeIcon icon={faRocket} /> Minar Space hisobi ochish</h3>
              <button className="modal-close" onClick={() => setModal(false)}>✕</button>
            </div>
            <div className="modal-body">
              <label>Talaba *</label>
              {pickedStudent ? (
                <div className="cell-copy" style={{ marginBottom: 10 }}>
                  <strong>{pickedStudent.full_name}</strong>
                  <button className="btn-icon" title="Boshqasini tanlash" aria-label="Boshqasini tanlash"
                    onClick={() => setPickedStudent(null)}>
                    <FontAwesomeIcon icon={faPlus} style={{ transform: 'rotate(45deg)' }} />
                  </button>
                </div>
              ) : (
                <>
                  <input className="field" value={studentQuery} onChange={e => setStudentQuery(e.target.value)}
                    placeholder="Ism bo'yicha qidirish" />
                  <div style={{ maxHeight: 180, overflowY: 'auto', border: '1px solid var(--border, var(--border))', borderRadius: 8, marginTop: 6 }}>
                    {studentResults.map(s => (
                      <button key={s.id} className="button secondary" type="button"
                        style={{ display: 'block', width: '100%', textAlign: 'left', border: 'none', borderRadius: 0 }}
                        onClick={() => setPickedStudent(s)}>
                        {s.full_name} <span className="text-muted" style={{ fontSize: 12 }}>({s.phone1})</span>
                      </button>
                    ))}
                    {studentResults.length === 0 && <div className="muted py-2" style={{ padding: 8 }}>Talaba topilmadi</div>}
                  </div>
                </>
              )}

              <div className="row-2" style={{ marginTop: 10 }}>
                <div>
                  <label>Kurs</label>
                  <select className="field" value={course} onChange={e => setCourse(e.target.value)}>
                    <option value="">Avtomatik (guruh bosqichidan)</option>
                    {COURSES.map(c => <option key={c} value={c}>{c}</option>)}
                  </select>
                </div>
                <div>
                  <label>Parol</label>
                  <input className="field" value={customPassword} onChange={e => setCustomPassword(e.target.value)}
                    placeholder="Bo'sh qolsa — avto" />
                </div>
              </div>
            </div>
            <div className="modal-footer">
              <button className="button secondary" onClick={() => setModal(false)}>Bekor</button>
              <button className="button" onClick={handleCreate} disabled={saving}>
                {saving ? 'Yaratilmoqda...' : 'Yaratish'}
              </button>
            </div>
          </div>
        </Overlay>
      )}

      {/* Guruh bo'yicha ommaviy ochish modali */}
      {bulkModal && (
        <Overlay className="modal-overlay" onClick={() => setBulkModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3><FontAwesomeIcon icon={faLayerGroup} /> Guruh bo'yicha ommaviy ochish</h3>
              <button className="modal-close" onClick={() => setBulkModal(false)}>✕</button>
            </div>
            <div className="modal-body">
              <p className="text-muted" style={{ fontSize: 13, marginTop: 0 }}>
                Guruhdagi hisobi hali yo'q barcha faol talabalarga hisob ochiladi.
              </p>
              <label>Guruh *</label>
              <select className="field" value={bulkGroupId} onChange={e => setBulkGroupId(e.target.value)}>
                <option value="">Tanlang...</option>
                {groups.map(g => <option key={g.id} value={g.id}>{g.name}</option>)}
              </select>

              <label style={{ marginTop: 10 }}>Kurs</label>
              <select className="field" value={bulkCourse} onChange={e => setBulkCourse(e.target.value)}>
                <option value="">Avtomatik (guruh bosqichidan)</option>
                {COURSES.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            <div className="modal-footer">
              <button className="button secondary" onClick={() => setBulkModal(false)}>Bekor</button>
              <button className="button" onClick={handleBulkCreate} disabled={bulkSaving}>
                {bulkSaving ? 'Yaratilmoqda...' : 'Yaratish'}
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
              <h3><FontAwesomeIcon icon={faKey} /> Kirish ma'lumotlari</h3>
              <button className="modal-close" onClick={() => setCreds(null)}>✕</button>
            </div>
            <div className="modal-body">
              <p style={{ margin: '0 0 10px' }}>
                <strong>{creds.full_name}</strong> uchun space.minaracademy.uz kirish ma'lumotlari.
                Parol <strong>faqat hozir</strong> ko'rinadi — talabaga yozib bering yoki yuboring.
              </p>
              <label>Login</label>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <input className="field" readOnly value={creds.login_id} style={{ fontFamily: 'monospace' }} />
                <button className="button secondary" onClick={() => copy(creds.login_id)}>
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
                onClick={() => copy(`Minar Space (space.minaracademy.uz)\nLogin: ${creds.login_id}\nParol: ${creds.password}`)}
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

      {/* Login/parol ro'yxati — guruh bo'yicha ommaviy yaratilganda */}
      {bulkCreds && (
        <Overlay className="modal-overlay" onClick={() => setBulkCreds(null)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3><FontAwesomeIcon icon={faKey} /> Yaratilgan hisoblar ({bulkCreds.length})</h3>
              <button className="modal-close" onClick={() => setBulkCreds(null)}>✕</button>
            </div>
            <div className="modal-body">
              <p style={{ margin: '0 0 10px' }}>
                Parollar <strong>faqat hozir</strong> ko'rinadi — talabalarga yozib bering yoki yuboring.
              </p>
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
                <FontAwesomeIcon icon={faCopy} /> Hammasini nusxalash
              </button>
            </div>
            <div className="modal-footer">
              <button className="button" onClick={() => setBulkCreds(null)}>Yopdim, saqlab oldim</button>
            </div>
          </div>
        </Overlay>
      )}
    </div>
  )
}
