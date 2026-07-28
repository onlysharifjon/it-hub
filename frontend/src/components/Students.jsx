import { useEffect, useState } from 'react'
import { toast } from 'react-hot-toast'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faPen, faToggleOn, faToggleOff, faPlus,
  faMagnifyingGlass, faUserGraduate, faPhone,
  faBoxArchive, faArrowUpFromBracket, faCamera,
  faClockRotateLeft, faArrowRightToBracket, faArrowRightFromBracket,
} from '@fortawesome/free-solid-svg-icons'
import { faTelegram as faTelegramBrand } from '@fortawesome/free-brands-svg-icons'
import { fetchStudents, createStudent, updateStudent, archiveStudent, unarchiveStudent, uploadStudentPhoto, fetchStudentCameraAttendance, API_BASE } from '../api'
import Pagination from './Pagination'
import DateFilter from './DateFilter'

const EMPTY = {
  full_name: '', phone1: '',
  father_name: '', father_phone: '',
  mother_name: '', mother_phone: '',
  telegram_id: '', notes: '',
}

function StudentAvatar({ photoUrl, size = 60 }) {
  if (!photoUrl) return (
    <div style={{ width: size, height: size, borderRadius: '50%', background: '#e2e8f0', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
      <FontAwesomeIcon icon={faUserGraduate} style={{ color: '#94a3b8', fontSize: size * 0.4 }} />
    </div>
  )
  return (
    <img
      src={`${API_BASE}${photoUrl}`}
      alt=""
      style={{ width: size, height: size, borderRadius: '50%', objectFit: 'cover', flexShrink: 0 }}
    />
  )
}

export default function Students() {
  const [tab, setTab] = useState('active')          // 'active' | 'archived'
  const [data, setData] = useState({ items: [], meta: null })
  const [search, setSearch] = useState('')
  const [dateFilter, setDateFilter] = useState({ preset: 'all', date_from: '', date_to: '' })
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)
  const [modal, setModal] = useState(null)
  const [editStudent, setEditStudent] = useState(null)
  const [form, setForm] = useState(EMPTY)
  const [saving, setSaving] = useState(false)
  const [photoUploading, setPhotoUploading] = useState(false)
  const [attendanceModal, setAttendanceModal] = useState(null)  // student object
  const [attendanceData, setAttendanceData]   = useState([])
  const [attendanceDays, setAttendanceDays]   = useState(30)
  const [attendanceLoading, setAttendanceLoading] = useState(false)

  useEffect(() => { load(search, dateFilter, page, tab) }, [tab])

  async function load(s = search, df = dateFilter, p = page, t = tab) {
    setLoading(true)
    try {
      const res = await fetchStudents({
        search: s || undefined,
        is_archived: t === 'archived' ? true : false,
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

  function openAdd() { setForm(EMPTY); setEditStudent(null); setModal('add') }
  function openEdit(s) {
    setForm({
      full_name: s.full_name, phone1: s.phone1,
      father_name: s.father_name || '', father_phone: s.father_phone || '',
      mother_name: s.mother_name || '', mother_phone: s.mother_phone || '',
      telegram_id: s.telegram_id || '', notes: s.notes || '',
    })
    setEditStudent(s)
    setModal(s)
  }

  async function handlePhotoUpload(file) {
    if (!editStudent?.id) return
    setPhotoUploading(true)
    try {
      const res = await uploadStudentPhoto(editStudent.id, file)
      setEditStudent(prev => ({ ...prev, photo_url: res.photo_url }))
      toast.success('Rasm yuklandi')
      load()
    } catch (e) { toast.error(e.message) }
    finally { setPhotoUploading(false) }
  }

  async function handleSave() {
    if (!form.full_name.trim() || !form.phone1.trim()) return toast.error("Ism va telefon majburiy")
    setSaving(true)
    try {
      if (modal === 'add') {
        await createStudent(form)
        toast.success("Talaba qo'shildi")
      } else {
        await updateStudent(modal.id, form)
        toast.success('Saqlandi')
      }
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
        {tab === 'active' && (
          <button className="button primary" onClick={openAdd}>
            <FontAwesomeIcon icon={faPlus} /> Talaba qo'shish
          </button>
        )}
      </div>

      {/* Tabs */}
      <div className="tab-bar">
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
                      {s.telegram_id
                        ? <span className="tg-badge"><FontAwesomeIcon icon={faTelegramBrand} /> {s.telegram_id}</span>
                        : <span className="text-muted">—</span>}
                    </td>
                    <td>
                      {(s.group_names && s.group_names.length > 0)
                        ? <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, maxWidth: 180 }}>
                            {s.group_names.map((n, gi) => <span key={gi} className="badge">{n}</span>)}
                          </div>
                        : <span className="text-muted">—</span>}
                    </td>
                    <td><PayStatus s={s} /></td>
                    <td className="text-muted" style={{ fontSize: 12 }}>{fmtDate(s.created_at)}</td>
                    <td className="text-muted" style={{ fontSize: 12 }}>{fmtDate(s.updated_at)}</td>
                    <td>
                      <span className={`status-badge ${s.is_active ? 'active' : 'inactive'}`}>
                        {s.is_active ? 'Faol' : 'Nofaol'}
                      </span>
                    </td>
                    <td className="actions">
                      <button className="btn-icon" onClick={() => openAttendance(s)} title="Davomat tarixi" style={{ color: '#7c3aed' }}>
                        <FontAwesomeIcon icon={faClockRotateLeft} />
                      </button>
                      {tab === 'active' ? (
                        <>
                          <button className="btn-icon" onClick={() => openEdit(s)} title="Tahrirlash">
                            <FontAwesomeIcon icon={faPen} />
                          </button>
                          <button className="btn-icon" onClick={() => handleToggle(s)} title={s.is_active ? "Nofaollashtirish" : "Faollashtirish"}>
                            <FontAwesomeIcon icon={s.is_active ? faToggleOn : faToggleOff} style={{ color: s.is_active ? '#22c55e' : '#ef4444' }} />
                          </button>
                          <button className="btn-icon danger" onClick={() => handleArchive(s)} title="Arxivga o'tkazish">
                            <FontAwesomeIcon icon={faBoxArchive} />
                          </button>
                        </>
                      ) : (
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
                      {tab === 'archived' ? 'Arxivlangan talabalar yo\'q' : 'Talabalar topilmadi'}
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
              <h3>{modal === 'add' ? "Yangi talaba" : "Talabani tahrirlash"}</h3>
              <button className="modal-close" onClick={() => setModal(null)}>✕</button>
            </div>
            <div className="modal-body">
              {modal !== 'add' && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 16 }}>
                  <StudentAvatar photoUrl={editStudent?.photo_url} size={72} />
                  <div>
                    <div style={{ fontSize: 13, color: 'var(--muted)', marginBottom: 6 }}>
                      Kamera tizimi uchun yuz rasmi
                    </div>
                    <label className="button secondary" style={{ cursor: 'pointer', fontSize: 13 }}>
                      <FontAwesomeIcon icon={faCamera} style={{ marginRight: 6 }} />
                      {photoUploading ? 'Yuklanmoqda...' : 'Rasm yuklash'}
                      <input
                        type="file"
                        accept="image/jpeg,image/png,image/webp"
                        style={{ display: 'none' }}
                        disabled={photoUploading}
                        onChange={e => e.target.files[0] && handlePhotoUpload(e.target.files[0])}
                      />
                    </label>
                  </div>
                </div>
              )}
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
              <label>Telegram ID</label>
              <input className="field" value={form.telegram_id} onChange={e => setForm(p => ({ ...p, telegram_id: e.target.value }))} placeholder="username (@ siz)" />
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
    </div>
  )
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
