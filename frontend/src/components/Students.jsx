import { useEffect, useState } from 'react'
import { toast } from 'react-hot-toast'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faEye, faToggleOn, faToggleOff, faPlus, faTrash,
  faMagnifyingGlass, faUserGraduate, faPhone,
  faBoxArchive, faArrowUpFromBracket,
  faClockRotateLeft, faArrowRightToBracket, faArrowRightFromBracket,
  faUmbrellaBeach, faXmark, faHourglassHalf, faLayerGroup, faRotateLeft,
  faPaperPlane, faSpinner,
} from '@fortawesome/free-solid-svg-icons'
import {
  fetchStudents, createStudent, updateStudent, archiveStudent, unarchiveStudent, fetchStudentCameraAttendance,
  fetchStudentVacations, createStudentVacation, deleteStudentVacation,
  fetchGroups, addStudentToGroup, checkStudentTelegram,
} from '../api'
import Pagination from './Pagination'
import DateFilter from './DateFilter'

const EMPTY = {
  full_name: '', phone1: '',
  father_name: '', father_phone: '',
  mother_name: '', mother_phone: '',
  telegram_user_id: '', notes: '',
}

export default function Students({ currentUser, onOpenStudent } = {}) {
  const isHunter = currentUser?.role === 'hunter' || currentUser?.role === 'admin'
  const [tab, setTab] = useState('active')          // 'active' | 'demo' | 'archived'
  const [data, setData] = useState({ items: [], meta: null })
  const [search, setSearch] = useState('')
  const [dateFilter, setDateFilter] = useState({ preset: 'all', date_from: '', date_to: '' })
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)
  const [modal, setModal] = useState(null)
  const [form, setForm] = useState(EMPTY)
  const [saving, setSaving] = useState(false)
  const [attendanceModal, setAttendanceModal] = useState(null)  // student object
  const [attendanceData, setAttendanceData]   = useState([])
  const [attendanceDays, setAttendanceDays]   = useState(30)
  const [attendanceLoading, setAttendanceLoading] = useState(false)
  const [vacationModal, setVacationModal] = useState(null)      // student object
  const [attachModal, setAttachModal] = useState(null)          // student object (demo -> guruhga biriktirish)
  const [tgCheck, setTgCheck] = useState({})   // { [studentId]: 'checking' | 'ok' | 'fail' }

  useEffect(() => { load(search, dateFilter, page, tab) }, [tab])

  async function load(s = search, df = dateFilter, p = page, t = tab) {
    setLoading(true)
    try {
      const res = await fetchStudents({
        search: s || undefined,
        is_archived: t === 'archived' ? true : false,
        is_demo: t === 'demo' ? true : false,
        date_from: df.date_from || undefined,
        date_to: df.date_to || undefined,
        page: p, page_size: 20,
      })
      setData(res)
    } catch { toast.error("Yuklab bo'lmadi") }
    finally { setLoading(false) }
  }

  function handleSearch(e) {
    const val = e.target.value
    setSearch(val)
    setPage(1)
    if (val.length === 0 || val.length >= 2) load(val, dateFilter, 1, tab)
  }

  function handleDateFilter(df) {
    setDateFilter(df)
    setPage(1)
    load(search, df, 1, tab)
  }

  function handlePageChange(p) {
    setPage(p)
    load(search, dateFilter, p, tab)
  }

  function switchTab(t) {
    setTab(t)
    setPage(1)
    setSearch('')
  }

  function openAdd() { setForm(EMPTY); setModal('add') }

  async function handleSave() {
    if (!form.full_name.trim() || !form.phone1.trim()) return toast.error("Ism va telefon majburiy")
    setSaving(true)
    try {
      await createStudent(tab === 'demo' ? { ...form, is_demo: true } : form)
      toast.success(tab === 'demo' ? "Demo talaba qo'shildi" : "Talaba qo'shildi")
      setModal(null)
      load()
    } catch (e) { toast.error(e.message) }
    finally { setSaving(false) }
  }

  async function handleArchive(s) {
    if (!confirm(`"${s.full_name}" ni arxivga o'tkazishni tasdiqlaysizmi?`)) return
    try {
      await archiveStudent(s.id)
      toast.success("Arxivga o'tkazildi")
      load()
    } catch (e) { toast.error(e.message) }
  }

  async function handleUnarchive(s) {
    try {
      await unarchiveStudent(s.id)
      toast.success("Arxivdan chiqarildi")
      load()
    } catch (e) { toast.error(e.message) }
  }

  async function handleMarkDemo(s) {
    if (!confirm(`"${s.full_name}" demo bo'limiga o'tkazilsinmi? U guruhga biriktirilmaguncha hali demo darsga kelmagan hisoblanadi.`)) return
    try {
      await updateStudent(s.id, { is_demo: true })
      toast.success("Demo bo'limiga o'tkazildi")
      load()
    } catch (e) { toast.error(e.message) }
  }

  async function handleUnmarkDemo(s) {
    try {
      await updateStudent(s.id, { is_demo: false })
      toast.success("Demo holatidan chiqarildi")
      load()
    } catch (e) { toast.error(e.message) }
  }

  async function handleTelegramCheck(s) {
    setTgCheck(p => ({ ...p, [s.id]: 'checking' }))
    try {
      const res = await checkStudentTelegram(s.id)
      setTgCheck(p => ({ ...p, [s.id]: res.ok ? 'ok' : 'fail' }))
      if (res.ok) toast.success("Sinov xabari yuborildi — yetkazish mumkin")
      else toast.error(res.detail || 'Xabar yuborib bo\'lmadi')
    } catch (e) {
      setTgCheck(p => ({ ...p, [s.id]: 'fail' }))
      toast.error(e.message)
    }
  }

  async function handleToggle(s) {
    try {
      await updateStudent(s.id, { is_active: !s.is_active })
      load()
    } catch { toast.error('Xatolik') }
  }

  async function openAttendance(s, days = 30) {
    setAttendanceModal(s)
    setAttendanceDays(days)
    setAttendanceLoading(true)
    setAttendanceData([])
    try {
      const rows = await fetchStudentCameraAttendance(s.id, days)
      setAttendanceData(rows)
    } catch { toast.error("Davomat yuklanmadi") }
    finally { setAttendanceLoading(false) }
  }

  async function changeAttendanceDays(s, days) {
    setAttendanceDays(days)
    setAttendanceLoading(true)
    try {
      const rows = await fetchStudentCameraAttendance(s.id, days)
      setAttendanceData(rows)
    } catch {}
    finally { setAttendanceLoading(false) }
  }

  const students = data.items || []
  const meta = data.meta

  return (
    <div className="page">
      <div className="page-header">
        <h1>
          <FontAwesomeIcon icon={faUserGraduate} className="page-icon" />
          Talabalar
        </h1>
        {(tab === 'active' || tab === 'demo') && (
          <button className="button primary" onClick={openAdd}>
            <FontAwesomeIcon icon={faPlus} /> Talaba qo'shish
          </button>
        )}
      </div>

      {/* Tabs */}
      <div className="tab-bar">
        <button
          className={`tab-btn ${tab === 'demo' ? 'active' : ''}`}
          onClick={() => switchTab('demo')}
        >
          <FontAwesomeIcon icon={faHourglassHalf} /> Demo
        </button>
        <button
          className={`tab-btn ${tab === 'active' ? 'active' : ''}`}
          onClick={() => switchTab('active')}
        >
          <FontAwesomeIcon icon={faUserGraduate} /> Faol talabalar
        </button>
        <button
          className={`tab-btn ${tab === 'archived' ? 'active' : ''}`}
          onClick={() => switchTab('archived')}
        >
          <FontAwesomeIcon icon={faBoxArchive} /> Arxiv
        </button>
      </div>

      <div className="toolbar">
        <div className="search-wrap">
          <FontAwesomeIcon icon={faMagnifyingGlass} className="search-icon" />
          <input
            className="search-input"
            placeholder="Ism yoki telefon..."
            value={search}
            onChange={handleSearch}
          />
        </div>
        <span style={{ flex: 1 }} />
        <DateFilter value={dateFilter} onChange={handleDateFilter} />
        {meta && <span className="toolbar-count">Jami: <strong>{meta.total}</strong> ta talaba</span>}
      </div>

      {loading ? (
        <div className="muted center py-8">Yuklanmoqda...</div>
      ) : (
        <>
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Ism Familiya</th>
                  <th><FontAwesomeIcon icon={faPhone} /> Telefon</th>
                  <th>Ota-ona</th>
                  <th>Telegram</th>
                  <th>Guruhlar</th>
                  <th>To'lov</th>
                  <th>Qo'shilgan</th>
                  <th>Yangilangan</th>
                  <th>Holat</th>
                  <th>Amallar</th>
                </tr>
              </thead>
              <tbody>
                {students.map((s, i) => (
                  <tr key={s.id} className={!s.is_active ? 'row-inactive' : ''}>
                    <td className="text-muted">{(page - 1) * 20 + i + 1}</td>
                    <td><strong>{s.full_name}</strong></td>
                    <td>
                      <div>{s.phone1}</div>
                    </td>
                    <td>
                      {(s.father_name || s.mother_name) ? (
                        <div style={{ fontSize: 12 }}>
                          {s.father_name && <div>{s.father_name}{s.father_phone ? ` — ${s.father_phone}` : ''}</div>}
                          {s.mother_name && <div>{s.mother_name}{s.mother_phone ? ` — ${s.mother_phone}` : ''}</div>}
                        </div>
                      ) : <span className="text-muted">—</span>}
                    </td>
                    <td>
                      {s.telegram_user_id ? (
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                          <span className="badge" style={tgBadgeStyle(tgCheck[s.id])}>ID: {s.telegram_user_id}</span>
                          <button
                            className="btn-icon"
                            title="Yetkazishni sinab ko'rish (sinov xabari yuboradi)"
                            style={{ padding: 4 }}
                            disabled={tgCheck[s.id] === 'checking'}
                            onClick={() => handleTelegramCheck(s)}
                          >
                            <FontAwesomeIcon icon={tgCheck[s.id] === 'checking' ? faSpinner : faPaperPlane} spin={tgCheck[s.id] === 'checking'} style={{ fontSize: 11 }} />
                          </button>
                        </div>
                      ) : <span className="text-muted">—</span>}
                    </td>
                    <td>
                      {(s.group_names && s.group_names.length > 0)
                        ? <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, maxWidth: 180 }}>
                            {s.group_names.map((n, gi) => <span key={gi} className="badge">{n}</span>)}
                          </div>
                        : <span className="text-muted">—</span>}
                    </td>
                    <td>
                      {isHunter ? (
                        <div
                          onClick={() => setVacationModal(s)}
                          style={{ cursor: 'pointer' }}
                          title="Ta'til belgilash uchun bosing"
                        >
                          <PayStatus s={s} />
                        </div>
                      ) : <PayStatus s={s} />}
                    </td>
                    <td className="text-muted" style={{ fontSize: 12 }}>{fmtDate(s.created_at)}</td>
                    <td className="text-muted" style={{ fontSize: 12 }}>{fmtDate(s.updated_at)}</td>
                    <td>
                      {tab === 'demo' ? (
                        <span className="status-badge inactive" style={{ background: '#fef3c7', color: '#b45309' }}>
                          Demo darsga kelmagan
                        </span>
                      ) : (
                        <span className={`status-badge ${s.is_active ? 'active' : 'inactive'}`}>
                          {s.is_active ? 'Faol' : 'Nofaol'}
                        </span>
                      )}
                    </td>
                    <td className="actions">
                      <button className="btn-icon" onClick={() => onOpenStudent?.(s)} title="To'liq ma'lumot / tahrirlash" style={{ color: '#2563eb' }}>
                        <FontAwesomeIcon icon={faEye} />
                      </button>
                      <button className="btn-icon" onClick={() => openAttendance(s)} title="Davomat tarixi" style={{ color: '#7c3aed' }}>
                        <FontAwesomeIcon icon={faClockRotateLeft} />
                      </button>
                      {tab === 'active' && (
                        <>
                          <button className="btn-icon" onClick={() => handleMarkDemo(s)} title="Demo bo'limiga o'tkazish" style={{ color: '#b45309' }}>
                            <FontAwesomeIcon icon={faHourglassHalf} />
                          </button>
                          <button className="btn-icon" onClick={() => handleToggle(s)} title={s.is_active ? "Nofaollashtirish" : "Faollashtirish"}>
                            <FontAwesomeIcon icon={s.is_active ? faToggleOn : faToggleOff} style={{ color: s.is_active ? '#22c55e' : '#ef4444' }} />
                          </button>
                          <button className="btn-icon danger" onClick={() => handleArchive(s)} title="Arxivga o'tkazish">
                            <FontAwesomeIcon icon={faBoxArchive} />
                          </button>
                        </>
                      )}
                      {tab === 'demo' && (
                        <>
                          <button className="btn-icon" onClick={() => setAttachModal(s)} title="Guruhga biriktirish (haqiqiy talabaga o'tkazish)" style={{ color: '#2563eb' }}>
                            <FontAwesomeIcon icon={faLayerGroup} />
                          </button>
                          <button className="btn-icon" onClick={() => handleUnmarkDemo(s)} title="Demo holatidan chiqarish">
                            <FontAwesomeIcon icon={faRotateLeft} />
                          </button>
                        </>
                      )}
                      {tab === 'archived' && (
                        <button className="btn-icon" onClick={() => handleUnarchive(s)} title="Arxivdan chiqarish" style={{ color: '#2563eb' }}>
                          <FontAwesomeIcon icon={faArrowUpFromBracket} />
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
                {students.length === 0 && (
                  <tr>
                    <td colSpan={11} className="muted center py-4">
                      {tab === 'archived' ? 'Arxivlangan talabalar yo\'q'
                        : tab === 'demo' ? 'Demo bo\'limida talaba yo\'q'
                        : 'Talabalar topilmadi'}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          <Pagination meta={meta} onPageChange={handlePageChange} />
        </>
      )}

      {/* ── Davomat modali ── */}
      {attendanceModal && (
        <div className="modal-overlay" onClick={() => setAttendanceModal(null)}>
          <div className="modal" style={{ maxWidth: 560 }} onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>
                <FontAwesomeIcon icon={faClockRotateLeft} style={{ marginRight: 8, color: '#7c3aed' }} />
                {attendanceModal.full_name} — Kamera davomati
              </h3>
              <button className="modal-close" onClick={() => setAttendanceModal(null)}>✕</button>
            </div>
            <div className="modal-body" style={{ padding: '12px 20px' }}>
              {/* Davr tanlash */}
              <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
                {[7, 14, 30, 90].map(d => (
                  <button
                    key={d}
                    className={`button ${attendanceDays === d ? 'primary' : 'secondary'}`}
                    style={{ fontSize: 12, padding: '4px 12px' }}
                    onClick={() => changeAttendanceDays(attendanceModal, d)}
                  >
                    {d} kun
                  </button>
                ))}
              </div>

              {attendanceLoading ? (
                <div className="muted center py-4">Yuklanmoqda...</div>
              ) : attendanceData.length === 0 ? (
                <div className="muted center py-4">
                  Bu davrda kamera yozuvi topilmadi
                </div>
              ) : (
                <div style={{ maxHeight: 420, overflowY: 'auto' }}>
                  <table className="data-table" style={{ fontSize: 13 }}>
                    <thead>
                      <tr>
                        <th>Sana</th>
                        <th>Kun</th>
                        <th>Soat</th>
                        <th>Holat</th>
                      </tr>
                    </thead>
                    <tbody>
                      {attendanceData.map(r => {
                        const dt   = new Date(r.detected_at)
                        const date = dt.toLocaleDateString('uz-UZ', { year: 'numeric', month: '2-digit', day: '2-digit' })
                        const day  = dt.toLocaleDateString('uz-UZ', { weekday: 'long' })
                        const time = dt.toLocaleTimeString('uz-UZ', { hour: '2-digit', minute: '2-digit' })
                        const isKeldi = r.event_type === 'keldi'
                        return (
                          <tr key={r.id}>
                            <td>{date}</td>
                            <td style={{ color: 'var(--muted)', fontSize: 12 }}>{day}</td>
                            <td><strong>{time}</strong></td>
                            <td>
                              <span style={{
                                display: 'inline-flex', alignItems: 'center', gap: 5,
                                padding: '2px 10px', borderRadius: 999, fontSize: 12, fontWeight: 600,
                                background: isKeldi ? '#dcfce7' : '#fee2e2',
                                color:      isKeldi ? '#16a34a' : '#dc2626',
                              }}>
                                <FontAwesomeIcon icon={isKeldi ? faArrowRightToBracket : faArrowRightFromBracket} />
                                {isKeldi ? 'Keldi' : 'Ketdi'}
                              </span>
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {modal && (
        <div className="modal-overlay" onClick={() => setModal(null)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>{tab === 'demo' ? "Yangi demo talaba" : "Yangi talaba"}</h3>
              <button className="modal-close" onClick={() => setModal(null)}>✕</button>
            </div>
            <div className="modal-body">
              <label>Ism Familiya *</label>
              <input className="field" value={form.full_name} onChange={e => setForm(p => ({ ...p, full_name: e.target.value }))} placeholder="To'liq ism" />
              <label><FontAwesomeIcon icon={faPhone} /> Telefon *</label>
              <input className="field" value={form.phone1} onChange={e => setForm(p => ({ ...p, phone1: e.target.value }))} placeholder="+998901234567" />
              <div className="row-2">
                <div>
                  <label>Otasining ismi</label>
                  <input className="field" value={form.father_name} onChange={e => setForm(p => ({ ...p, father_name: e.target.value }))} placeholder="Ixtiyoriy" />
                </div>
                <div>
                  <label>Otasining telefoni</label>
                  <input className="field" value={form.father_phone} onChange={e => setForm(p => ({ ...p, father_phone: e.target.value }))} placeholder="+998..." />
                </div>
              </div>
              <div className="row-2">
                <div>
                  <label>Onasining ismi</label>
                  <input className="field" value={form.mother_name} onChange={e => setForm(p => ({ ...p, mother_name: e.target.value }))} placeholder="Ixtiyoriy" />
                </div>
                <div>
                  <label>Onasining telefoni</label>
                  <input className="field" value={form.mother_phone} onChange={e => setForm(p => ({ ...p, mother_phone: e.target.value }))} placeholder="+998..." />
                </div>
              </div>
              <label>Telegram ID (bot xabar yuborishi uchun) *muhim*</label>
              <input className="field" type="text" value={form.telegram_user_id}
                onChange={e => setForm(p => ({ ...p, telegram_user_id: e.target.value }))}
                placeholder="123456789" />
              <p className="text-muted" style={{ fontSize: 12, margin: '4px 0 0' }}>
                Davomat/uy vazifasi/ota-onalarga xabar shu raqamli ID'ga yuboriladi — @userinfobot orqali olinadi.
              </p>
              <label>Izoh</label>
              <textarea className="field" rows={2} value={form.notes} onChange={e => setForm(p => ({ ...p, notes: e.target.value }))} placeholder="Qo'shimcha ma'lumot..." />
            </div>
            <div className="modal-footer">
              <button className="button secondary" onClick={() => setModal(null)}>Bekor</button>
              <button className="button primary" onClick={handleSave} disabled={saving}>
                {saving ? 'Saqlanmoqda...' : 'Saqlash'}
              </button>
            </div>
          </div>
        </div>
      )}

      {vacationModal && (
        <VacationModal student={vacationModal} onClose={() => setVacationModal(null)} />
      )}

      {attachModal && (
        <AttachGroupModal
          student={attachModal}
          onClose={() => setAttachModal(null)}
          onAttached={() => { setAttachModal(null); load() }}
        />
      )}
    </div>
  )
}

// ── Telegram ID badge rangi (yuborish tekshiruvi natijasiga qarab) ─────────
function tgBadgeStyle(status) {
  if (status === 'fail') return { background: '#fef3c7', color: '#b45309' }
  return { background: '#dbeafe', color: '#1d4ed8' }   // default / 'ok' — ko'k
}

// ── To'lov holati belgisi ───────────────────────────────────────────────────
const fmtSum = n => Number(n || 0).toLocaleString('uz-UZ')

function fmtDate(isoStr) {
  if (!isoStr) return '—'
  return new Date(isoStr).toLocaleDateString('uz-UZ', { day: '2-digit', month: '2-digit', year: 'numeric' })
}

function PayStatus({ s }) {
  const st = s.payment_status
  if (!st || st === 'none') return <span className="text-muted">—</span>
  const meta = {
    paid:    { label: "To'langan", bg: '#dcfce7', color: '#15803d' },
    partial: { label: 'Qisman',    bg: '#fef3c7', color: '#b45309' },
    debtor:  { label: 'Qarzdor',   bg: '#fee2e2', color: '#b91c1c' },
  }[st]
  if (!meta) return <span className="text-muted">—</span>
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <span className="lead-status-badge" style={{ background: meta.bg, color: meta.color, alignSelf: 'flex-start' }}>
        {meta.label}
      </span>
      {Number(s.debt) > 0 && (
        <span style={{ fontSize: 11.5, color: 'var(--danger)', fontWeight: 600 }}>
          −{fmtSum(s.debt)} so'm
        </span>
      )}
      {Number(s.advance_applied) > 0 && (
        <span style={{ fontSize: 11, color: 'var(--success)' }}>avans −{fmtSum(s.advance_applied)}</span>
      )}
    </div>
  )
}

// ── To'lov qabul qilish oynasi (hunter/admin) ───────────────────────────────
function RecordPaymentModal({ student, onClose, onSaved }) {
  const [sum, setSum] = useState(null)
  const [loading, setLoading] = useState(true)
  const [groupId, setGroupId] = useState('')
  const [amount, setAmount] = useState('')
  const [notes, setNotes] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => { loadSummary() }, [student.id])
  async function loadSummary() {
    setLoading(true)
    try {
      const s = await fetchStudentPaymentSummary(student.id)
      setSum(s)
      const firstDebt = s.groups.find(g => Number(g.remaining) > 0) || s.groups[0]
      if (firstDebt) {
        setGroupId(String(firstDebt.group_id))
        if (Number(firstDebt.remaining) > 0) setAmount(String(Math.round(firstDebt.remaining)))
      }
    } catch { toast.error("Yuklab bo'lmadi") } finally { setLoading(false) }
  }

  async function handleSave() {
    if (!groupId) return toast.error('Guruhni tanlang')
    const amt = Number(amount)
    if (!amt || amt <= 0) return toast.error("To'g'ri summa kiriting")
    setSaving(true)
    try {
      await createPayment({
        student_id: student.id,
        group_id: Number(groupId),
        amount: amt,
        month: sum.month, year: sum.year,
        notes: notes.trim() || null,
      })
      toast.success("To'lov qabul qilindi")
      onSaved()
    } catch (e) { toast.error(e.message) } finally { setSaving(false) }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: 520 }}>
        <div className="modal-header">
          <h3><FontAwesomeIcon icon={faWallet} /> To'lov — {student.full_name}</h3>
          <button className="modal-close" onClick={onClose}><FontAwesomeIcon icon={faXmark} /></button>
        </div>
        <div className="modal-body">
          {loading ? <div className="muted center py-4">Yuklanmoqda...</div> : sum && (
            <>
              <div className="rp-summary">
                <div><span className="muted">Oy</span><strong>{sum.month}/{sum.year}</strong></div>
                <div><span className="muted">Oylik summa</span><strong>{fmtSum(sum.total_owed)}</strong></div>
                <div><span className="muted">To'langan</span><strong>{fmtSum(sum.total_paid)}</strong></div>
                {Number(sum.advance_balance) > 0 && <div><span className="muted">Avans</span><strong style={{ color: 'var(--success)' }}>{fmtSum(sum.advance_balance)}</strong></div>}
                <div><span className="muted">Qarz</span><strong style={{ color: Number(sum.debt) > 0 ? 'var(--danger)' : 'var(--success)' }}>{fmtSum(sum.debt)}</strong></div>
              </div>

              {sum.groups.length === 0 ? (
                <div className="muted center py-4" style={{ fontSize: 13 }}>Talaba narxli faol guruhda emas — avval guruhga biriktiring.</div>
              ) : (
                <>
                  <label>Guruh</label>
                  <select className="field" value={groupId} onChange={e => setGroupId(e.target.value)}>
                    {sum.groups.map(g => (
                      <option key={g.group_id} value={g.group_id}>
                        {g.group_name} — qoldi: {fmtSum(g.remaining)}
                      </option>
                    ))}
                  </select>
                  <label>Summa (so'm)</label>
                  <input className="field" type="number" inputMode="numeric" value={amount}
                    onChange={e => setAmount(e.target.value)} placeholder="0" />
                  <label>Izoh</label>
                  <textarea className="field" rows={2} value={notes}
                    onChange={e => setNotes(e.target.value)} placeholder="Masalan: naqd, qolgani keyingi hafta..." />
                </>
              )}

              {sum.recent_payments.length > 0 && (
                <div className="rp-history">
                  <div className="rp-history-title">So'nggi to'lovlar</div>
                  {sum.recent_payments.slice(0, 5).map(p => (
                    <div key={p.id} className="rp-history-item">
                      <div>
                        <strong>{fmtSum(p.amount)} so'm</strong>
                        <span className="muted"> · {p.month}/{p.year} · {p.group_name}</span>
                        {p.notes && <div className="muted" style={{ fontSize: 12 }}>“{p.notes}”</div>}
                      </div>
                      {p.recorded_by_name && <span className="rp-by">{p.recorded_by_name}</span>}
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
        <div className="modal-footer">
          <button className="button secondary" onClick={onClose}>Bekor</button>
          <button className="button primary" onClick={handleSave} disabled={saving || loading || !sum?.groups.length}>
            <FontAwesomeIcon icon={faCircleCheck} /> {saving ? 'Saqlanmoqda...' : 'Qabul qilish'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Ta'til belgilash oynasi (hunter/admin) ──────────────────────────────────
const VAC_TODAY = new Date().toISOString().slice(0, 10)

function VacationModal({ student, onClose }) {
  const [vacations, setVacations] = useState([])
  const [loading, setLoading] = useState(true)
  const [form, setForm] = useState({ start_date: VAC_TODAY, end_date: VAC_TODAY, reason: '' })
  const [saving, setSaving] = useState(false)

  useEffect(() => { load() }, [student.id])
  async function load() {
    setLoading(true)
    try { setVacations(await fetchStudentVacations(student.id)) }
    catch { toast.error("Yuklab bo'lmadi") } finally { setLoading(false) }
  }

  async function handleSave() {
    if (!form.start_date || !form.end_date) return toast.error('Sanalarni kiriting')
    if (form.end_date < form.start_date) return toast.error("Tugash sanasi boshlanishdan oldin bo'lmasin")
    setSaving(true)
    try {
      await createStudentVacation(student.id, {
        start_date: form.start_date, end_date: form.end_date,
        reason: form.reason.trim() || null,
      })
      toast.success("Ta'til belgilandi")
      setForm({ start_date: VAC_TODAY, end_date: VAC_TODAY, reason: '' })
      await load()
    } catch (e) { toast.error(e.message) } finally { setSaving(false) }
  }

  async function handleDelete(id) {
    if (!confirm("Bu ta'til yozuvini o'chirishni tasdiqlaysizmi?")) return
    try {
      await deleteStudentVacation(student.id, id)
      toast.success("O'chirildi")
      await load()
    } catch (e) { toast.error(e.message) }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: 480 }}>
        <div className="modal-header">
          <h3><FontAwesomeIcon icon={faUmbrellaBeach} /> Ta'til — {student.full_name}</h3>
          <button className="modal-close" onClick={onClose}><FontAwesomeIcon icon={faXmark} /></button>
        </div>
        <div className="modal-body">
          <p className="text-muted" style={{ fontSize: 12.5, marginTop: 0 }}>
            Ta'til oralig'iga tushgan darslar oylik to'lovdan avtomatik chiqarib tashlanadi.
          </p>
          <div className="row-2">
            <div>
              <label>Boshlanish sanasi *</label>
              <input className="field" type="date" value={form.start_date}
                onChange={e => setForm(p => ({ ...p, start_date: e.target.value, end_date: p.end_date < e.target.value ? e.target.value : p.end_date }))} />
            </div>
            <div>
              <label>Tugash sanasi *</label>
              <input className="field" type="date" value={form.end_date} min={form.start_date}
                onChange={e => setForm(p => ({ ...p, end_date: e.target.value }))} />
            </div>
          </div>
          <label>Sababi (ixtiyoriy)</label>
          <input className="field" value={form.reason} placeholder="Masalan: shifokor tavsiyasi"
            onChange={e => setForm(p => ({ ...p, reason: e.target.value }))} />
          <button className="button primary" style={{ marginTop: 10 }} onClick={handleSave} disabled={saving}>
            <FontAwesomeIcon icon={faPlus} /> {saving ? 'Saqlanmoqda...' : "Qo'shish"}
          </button>

          {loading ? (
            <div className="muted center py-4">Yuklanmoqda...</div>
          ) : vacations.length > 0 && (
            <div style={{ marginTop: 16 }}>
              <label>Belgilangan ta'til kunlari</label>
              {vacations.map(v => (
                <div key={v.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 10px', borderRadius: 8, background: 'var(--bg-secondary, #f5f5f5)', marginBottom: 6 }}>
                  <div>
                    <div style={{ fontWeight: 600, fontSize: 13 }}>
                      {new Date(v.start_date + 'T00:00:00').toLocaleDateString('uz-UZ')} — {new Date(v.end_date + 'T00:00:00').toLocaleDateString('uz-UZ')}
                    </div>
                    {v.reason && <div className="text-muted" style={{ fontSize: 12 }}>{v.reason}</div>}
                    {v.created_by_name && <div className="text-muted" style={{ fontSize: 11 }}>{v.created_by_name}</div>}
                  </div>
                  <button className="btn-icon danger" onClick={() => handleDelete(v.id)}>
                    <FontAwesomeIcon icon={faTrash} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Demo talabani guruhga biriktirish (haqiqiy talabaga o'tkazish) ─────────
function AttachGroupModal({ student, onClose, onAttached }) {
  const [groups, setGroups] = useState([])
  const [groupId, setGroupId] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  useEffect(() => { load() }, [])
  async function load() {
    setLoading(true)
    try {
      const res = await fetchGroups({ is_active: true, page_size: 100 })
      setGroups(res.items || res || [])
    } catch { toast.error("Guruhlarni yuklab bo'lmadi") } finally { setLoading(false) }
  }

  async function handleSave() {
    if (!groupId) return toast.error('Guruhni tanlang')
    setSaving(true)
    try {
      await addStudentToGroup(parseInt(groupId), student.id)
      toast.success("Talaba guruhga biriktirildi — endi haqiqiy talaba")
      onAttached()
    } catch (e) { toast.error(e.message) } finally { setSaving(false) }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: 480 }}>
        <div className="modal-header">
          <h3><FontAwesomeIcon icon={faLayerGroup} /> Guruhga biriktirish — {student.full_name}</h3>
          <button className="modal-close" onClick={onClose}><FontAwesomeIcon icon={faXmark} /></button>
        </div>
        <div className="modal-body">
          <p className="text-muted" style={{ fontSize: 12.5, marginTop: 0 }}>
            Guruh tanlab biriktirilgach, talaba avtomatik "Faol talabalar" ro'yxatiga o'tadi.
          </p>
          {loading ? (
            <div className="muted center py-4">Yuklanmoqda...</div>
          ) : (
            <>
              <label>Guruh *</label>
              <select className="field" value={groupId} onChange={e => setGroupId(e.target.value)}>
                <option value="">— tanlang —</option>
                {groups.map(g => (
                  <option key={g.id} value={g.id}>{g.name}</option>
                ))}
              </select>
            </>
          )}
        </div>
        <div className="modal-footer">
          <button className="button secondary" onClick={onClose}>Bekor</button>
          <button className="button primary" onClick={handleSave} disabled={saving || loading}>
            {saving ? 'Saqlanmoqda...' : 'Biriktirish'}
          </button>
        </div>
      </div>
    </div>
  )
}
