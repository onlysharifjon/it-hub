import { useEffect, useState } from 'react'
import { toast } from 'react-hot-toast'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faPlus, faPen, faUsers, faUserPlus, faUserMinus,
  faLock, faLockOpen,
} from '@fortawesome/free-solid-svg-icons'
import {
  fetchGroups, createGroup, updateGroup,
  getGroup, addStudentToGroup, removeStudentFromGroup,
  fetchStudents, fetchUsers, fetchTariffs,
} from '../api'
import DateFilter from './DateFilter'
import Pagination from './Pagination'

const EMPTY_GROUP = { name: '', stage: 'foundation', teacher_id: '', course_price: '', teacher_pay_per_student: '', schedule: '', start_date: '' }

const STAGE_COLORS = {
  foundation: { bg: '#eff6ff', color: '#1d4ed8', bar: '#3b82f6' },
  frontend:   { bg: '#f0fdf4', color: '#15803d', bar: '#22c55e' },
  backend:    { bg: '#faf5ff', color: '#7e22ce', bar: '#a855f7' },
}
const STAGE_LABELS = { foundation: 'Foundation', frontend: 'Frontend', backend: 'Backend' }

export default function Groups({ onOpenGroup }) {
  const [data, setData] = useState({ items: [], meta: null })
  const [dateFilter, setDateFilter] = useState({ preset: 'all', date_from: '', date_to: '' })
  const [page, setPage] = useState(1)
  const [teachers, setTeachers] = useState([])
  const [allStudents, setAllStudents] = useState([])
  const [loading, setLoading] = useState(false)
  const [modal, setModal] = useState(null)
  const [form, setForm] = useState(EMPTY_GROUP)
  const [saving, setSaving] = useState(false)
  const [detailGroup, setDetailGroup] = useState(null)
  const [addStudentId, setAddStudentId] = useState('')
  const [addTariffId, setAddTariffId] = useState('')
  const [tariffs, setTariffs] = useState([])

  useEffect(() => {
    load(dateFilter, page)
    fetchUsers().then(r => setTeachers((r.items || r).filter(u => u.role === 'teacher' || u.role === 'metodist')))
    fetchStudents({ is_active: true, page_size: 100 }).then(r => setAllStudents(r.items || []))
    fetchTariffs().then(r => setTariffs(r || []))
  }, [])

  async function load(df = dateFilter, p = page) {
    setLoading(true)
    try {
      const res = await fetchGroups({
        date_from: df.date_from || undefined,
        date_to: df.date_to || undefined,
        page: p, page_size: 20,
      })
      setData(res)
    }
    catch { toast.error("Yuklab bo'lmadi") }
    finally { setLoading(false) }
  }

  function handleDateFilter(df) {
    setDateFilter(df)
    setPage(1)
    load(df, 1)
  }

  function handlePageChange(p) {
    setPage(p)
    load(dateFilter, p)
  }

  async function loadDetail(id) {
    const g = await getGroup(id)
    setDetailGroup(g)
  }

  function openAdd() { setForm(EMPTY_GROUP); setModal('add') }
  function openEdit(g) {
    setForm({
      name: g.name, stage: g.stage || 'foundation', teacher_id: g.teacher_id || '',
      course_price: g.course_price, teacher_pay_per_student: g.teacher_pay_per_student || '',
      schedule: g.schedule || '',
      start_date: g.start_date ? g.start_date.slice(0, 10) : '',
    })
    setModal(g)
  }

  async function handleSave() {
    if (!form.name.trim()) return toast.error("Guruh nomi majburiy")
    setSaving(true)
    const payload = {
      name: form.name,
      stage: form.stage || 'foundation',
      teacher_id: form.teacher_id ? parseInt(form.teacher_id) : null,
      course_price: parseFloat(form.course_price) || 0,
      teacher_pay_per_student: parseFloat(form.teacher_pay_per_student) || 0,
      schedule: form.schedule || null,
      start_date: form.start_date ? new Date(form.start_date).toISOString() : null,
    }
    try {
      if (modal === 'add') {
        await createGroup(payload)
        toast.success("Guruh qo'shildi")
      } else {
        await updateGroup(modal.id, payload)
        toast.success('Saqlandi')
      }
      setModal(null)
      load(dateFilter, page)
    } catch (e) { toast.error(e.message) }
    finally { setSaving(false) }
  }

  async function handleToggle(g) {
    try {
      await updateGroup(g.id, { is_active: !g.is_active })
      load(dateFilter, page)
    } catch { toast.error('Xatolik') }
  }

  async function handleAddStudent() {
    if (!addStudentId) return
    if (!addTariffId) return toast.error("Iltimos tarif tanlang")
    try {
      await addStudentToGroup(detailGroup.id, parseInt(addStudentId), parseInt(addTariffId))
      await loadDetail(detailGroup.id)
      setAddStudentId('')
      setAddTariffId('')
      toast.success("Talaba qo'shildi")
    } catch (e) { toast.error(e.message) }
  }

  async function handleRemoveStudent(studentId) {
    try {
      await removeStudentFromGroup(detailGroup.id, studentId)
      await loadDetail(detailGroup.id)
      toast.success("Talaba chiqarildi")
    } catch (e) { toast.error(e.message) }
  }

  const membersInDetail = detailGroup?.members?.map(m => m.student_id) || []
  const availableStudents = allStudents.filter(s => !membersInDetail.includes(s.id))

  return (
    <div className="page">
      <div className="page-header">
        <h1><FontAwesomeIcon icon={faUsers} className="page-icon" /> Guruhlar</h1>
        <button className="button primary" onClick={openAdd}>
          <FontAwesomeIcon icon={faPlus} /> Guruh yaratish
        </button>
      </div>

      <div className="toolbar">
        <DateFilter value={dateFilter} onChange={handleDateFilter} />
        {data.meta && <span className="muted">Jami: {data.meta.total} ta guruh</span>}
      </div>

      {loading ? <div className="muted center">Yuklanmoqda...</div> : (
        <>
          <div className="groups-grid">
            {(data.items || []).map(g => (
              <div
                key={g.id}
                className={`group-card group-card-clickable ${!g.is_active ? 'inactive' : ''}`}
                onClick={() => onOpenGroup(g)}
              >
                <div className="group-card-header">
                  <h3>{g.name}</h3>
                  <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                    <span
                      className="stage-badge"
                      style={{
                        background: STAGE_COLORS[g.stage || 'foundation'].bg,
                        color: STAGE_COLORS[g.stage || 'foundation'].color,
                      }}
                    >
                      {STAGE_LABELS[g.stage || 'foundation']}
                    </span>
                    <span className={`status-badge ${g.is_active ? 'active' : 'inactive'}`}>
                      {g.is_active ? 'Faol' : 'Yopiq'}
                    </span>
                  </div>
                </div>
                <div className="group-card-info">
                  <div><span className="label">Ustoz:</span> {g.teacher_name || '—'}</div>
                  <div><span className="label">Narx:</span> {Number(g.course_price).toLocaleString()} so'm/oy</div>
                  <div><span className="label">Jadval:</span> {g.schedule || '—'}</div>
                  <div><span className="label">O'quvchilar:</span> <span className="badge">{g.student_count}</span></div>
                </div>

                {/* Progress bar */}
                <div className="group-progress-wrap">
                  <div className="group-progress-header">
                    <span className="group-progress-label">
                      {g.completed_lessons}/{g.total_lessons} dars
                    </span>
                    <span
                      className="group-progress-pct"
                      style={{ color: g.progress_pct >= 80 ? '#ef4444' : g.progress_pct >= 60 ? '#f59e0b' : STAGE_COLORS[g.stage || 'foundation'].color }}
                    >
                      {g.progress_pct}%
                    </span>
                  </div>
                  <div className="group-progress-bar">
                    <div
                      className="group-progress-fill"
                      style={{
                        width: `${g.progress_pct}%`,
                        background: STAGE_COLORS[g.stage || 'foundation'].bar,
                      }}
                    />
                  </div>
                  <div className="group-progress-remaining">
                    {g.remaining_lessons > 0
                      ? <span style={{ color: g.remaining_lessons <= 5 ? '#ef4444' : '#737373' }}>
                          {g.remaining_lessons} dars qoldi
                          {g.remaining_lessons <= 5 && ' ⚠'}
                        </span>
                      : <span style={{ color: '#16a34a', fontWeight: 600 }}>Tugadi ✓</span>
                    }
                  </div>
                </div>

                <div className="group-card-actions" onClick={e => e.stopPropagation()}>
                  <button className="btn-sm" onClick={() => loadDetail(g.id)}>
                    <FontAwesomeIcon icon={faUsers} /> Talabalar
                  </button>
                  <button className="btn-sm" onClick={() => openEdit(g)}>
                    <FontAwesomeIcon icon={faPen} /> Tahrir
                  </button>
                  <button className="btn-sm" onClick={() => handleToggle(g)}>
                    <FontAwesomeIcon icon={g.is_active ? faLock : faLockOpen} />
                    {g.is_active ? ' Yopish' : ' Ochish'}
                  </button>
                </div>
              </div>
            ))}
            {(data.items || []).length === 0 && <div className="muted center">Guruhlar yo'q</div>}
          </div>
          <Pagination meta={data.meta} onPageChange={handlePageChange} />
        </>
      )}

      {/* Group form modal */}
      {modal && (
        <div className="modal-overlay" onClick={() => setModal(null)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>{modal === 'add' ? 'Yangi guruh' : 'Guruhni tahrirlash'}</h3>
              <button className="modal-close" onClick={() => setModal(null)}>✕</button>
            </div>
            <div className="modal-body">
              <label>Guruh nomi *</label>
              <input className="field" value={form.name} onChange={e => setForm(p => ({ ...p, name: e.target.value }))} placeholder="Masalan: Python 1-guruh" />
              <label>Bosqich (Stage)</label>
              <select className="field" value={form.stage} onChange={e => setForm(p => ({ ...p, stage: e.target.value }))}>
                <option value="foundation">Foundation (2 oy — 24 dars)</option>
                <option value="frontend">Frontend (6 oy — 72 dars)</option>
                <option value="backend">Backend (9 oy — 108 dars)</option>
              </select>
              <label>Ustoz</label>
              <select className="field" value={form.teacher_id} onChange={e => setForm(p => ({ ...p, teacher_id: e.target.value }))}>
                <option value="">— Tanlang —</option>
                {teachers.map(t => <option key={t.id} value={t.id}>{t.full_name || t.username}</option>)}
              </select>
              <label>Kurs narxi (so'm/oy)</label>
              <input className="field" type="number" value={form.course_price} onChange={e => setForm(p => ({ ...p, course_price: e.target.value }))} placeholder="500000" />
              <label>O'qituvchi haqi (har bir talabadan, so'm/oy)</label>
              <input className="field" type="number" value={form.teacher_pay_per_student} onChange={e => setForm(p => ({ ...p, teacher_pay_per_student: e.target.value }))} placeholder="50000" />
              <label>Dars jadvali</label>
              <input className="field" value={form.schedule} onChange={e => setForm(p => ({ ...p, schedule: e.target.value }))} placeholder="Du,Cho,Ju 14:00" />
              <label>Boshlanish sanasi</label>
              <input className="field" type="date" value={form.start_date} onChange={e => setForm(p => ({ ...p, start_date: e.target.value }))} />
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

      {/* Detail modal */}
      {detailGroup && (
        <div className="modal-overlay" onClick={() => setDetailGroup(null)}>
          <div className="modal modal-lg" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>👥 {detailGroup.name} — O'quvchilar</h3>
              <button className="modal-close" onClick={() => setDetailGroup(null)}>✕</button>
            </div>
            <div className="modal-body">
              <div className="add-student-row" style={{ flexWrap: 'wrap', gap: 8 }}>
                <select className="field flex-1" value={addStudentId} onChange={e => setAddStudentId(e.target.value)} style={{ minWidth: 180 }}>
                  <option value="">— Talaba tanlang —</option>
                  {availableStudents.map(s => (
                    <option key={s.id} value={s.id}>{s.full_name} ({s.phone1})</option>
                  ))}
                </select>
                <select className="field" value={addTariffId} onChange={e => setAddTariffId(e.target.value)} style={{ minWidth: 160 }}>
                  <option value="">— Tarif tanlang —</option>
                  {tariffs.filter(t => t.is_active).map(t => (
                    <option key={t.id} value={t.id}>{t.name} — {Number(t.price).toLocaleString()} so'm</option>
                  ))}
                </select>
                <button className="button primary" onClick={handleAddStudent}>
                  <FontAwesomeIcon icon={faUserPlus} /> Qo'shish
                </button>
              </div>
              <table className="data-table mt-1">
                <thead>
                  <tr><th>#</th><th>Ism</th><th>Telefon</th><th>Tarif</th><th>Qo'shilgan</th><th></th></tr>
                </thead>
                <tbody>
                  {(detailGroup.members || []).map((m, i) => (
                    <tr key={m.id}>
                      <td>{i + 1}</td>
                      <td>{m.student_name}</td>
                      <td>{m.student_phone}</td>
                      <td>
                        {m.tariff_name
                          ? <span>{m.tariff_name} <span className="text-muted" style={{ fontSize: 11 }}>({Number(m.tariff_price).toLocaleString()} so'm)</span></span>
                          : <span className="text-muted">—</span>}
                      </td>
                      <td>{new Date(m.joined_at).toLocaleDateString('uz')}</td>
                      <td><button className="btn-icon danger" onClick={() => handleRemoveStudent(m.student_id)} title="Chiqarish"><FontAwesomeIcon icon={faUserMinus} /></button></td>
                    </tr>
                  ))}
                  {(detailGroup.members || []).length === 0 && (
                    <tr><td colSpan={5} className="muted center">Hali o'quvchi yo'q</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
