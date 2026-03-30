import { useEffect, useState } from 'react'
import { toast } from 'react-hot-toast'
import {
  fetchGroups, createGroup, updateGroup, deleteGroup,
  getGroup, addStudentToGroup, removeStudentFromGroup,
  fetchStudents, fetchUsers,
} from '../api'

const EMPTY_GROUP = { name: '', teacher_id: '', course_price: '', schedule: '', start_date: '' }

export default function Groups() {
  const [groups, setGroups] = useState([])
  const [teachers, setTeachers] = useState([])
  const [allStudents, setAllStudents] = useState([])
  const [loading, setLoading] = useState(false)
  const [modal, setModal] = useState(null)
  const [form, setForm] = useState(EMPTY_GROUP)
  const [saving, setSaving] = useState(false)
  const [detailGroup, setDetailGroup] = useState(null)
  const [addStudentId, setAddStudentId] = useState('')

  useEffect(() => {
    load()
    fetchUsers().then(users => setTeachers(users.filter(u => u.role === 'teacher' || u.role === 'metodist')))
    fetchStudents({ is_active: true }).then(setAllStudents)
  }, [])

  async function load() {
    setLoading(true)
    try { setGroups(await fetchGroups()) }
    catch { toast.error("Yuklab bo'lmadi") }
    finally { setLoading(false) }
  }

  async function loadDetail(id) {
    const g = await getGroup(id)
    setDetailGroup(g)
  }

  function openAdd() { setForm(EMPTY_GROUP); setModal('add') }
  function openEdit(g) {
    setForm({
      name: g.name, teacher_id: g.teacher_id || '',
      course_price: g.course_price, schedule: g.schedule || '',
      start_date: g.start_date ? g.start_date.slice(0, 10) : '',
    })
    setModal(g)
  }

  async function handleSave() {
    if (!form.name.trim()) return toast.error("Guruh nomi majburiy")
    setSaving(true)
    const payload = {
      name: form.name,
      teacher_id: form.teacher_id ? parseInt(form.teacher_id) : null,
      course_price: parseFloat(form.course_price) || 0,
      schedule: form.schedule || null,
      start_date: form.start_date ? new Date(form.start_date).toISOString() : null,
    }
    try {
      if (modal === 'add') {
        const g = await createGroup(payload)
        setGroups(prev => [g, ...prev])
        toast.success("Guruh qo'shildi")
      } else {
        const g = await updateGroup(modal.id, payload)
        setGroups(prev => prev.map(x => x.id === g.id ? g : x))
        toast.success('Saqlandi')
      }
      setModal(null)
    } catch (e) { toast.error(e.message) }
    finally { setSaving(false) }
  }

  async function handleDelete(id) {
    if (!confirm("Guruhni o'chirishni tasdiqlaysizmi?")) return
    try {
      await deleteGroup(id)
      setGroups(prev => prev.filter(g => g.id !== id))
      toast.success("O'chirildi")
    } catch (e) { toast.error(e.message) }
  }

  async function handleToggle(g) {
    try {
      const updated = await updateGroup(g.id, { is_active: !g.is_active })
      setGroups(prev => prev.map(x => x.id === updated.id ? updated : x))
    } catch { toast.error('Xatolik') }
  }

  async function handleAddStudent() {
    if (!addStudentId) return
    try {
      await addStudentToGroup(detailGroup.id, parseInt(addStudentId))
      await loadDetail(detailGroup.id)
      setAddStudentId('')
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
        <h1>Guruhlar</h1>
        <button className="button primary" onClick={openAdd}>+ Guruh yaratish</button>
      </div>

      {loading ? <div className="muted center">Yuklanmoqda...</div> : (
        <div className="groups-grid">
          {groups.map(g => (
            <div key={g.id} className={`group-card ${!g.is_active ? 'inactive' : ''}`}>
              <div className="group-card-header">
                <h3>{g.name}</h3>
                <span className={`status-badge ${g.is_active ? 'active' : 'inactive'}`}>
                  {g.is_active ? 'Faol' : 'Yopiq'}
                </span>
              </div>
              <div className="group-card-info">
                <div><span className="label">Ustoz:</span> {g.teacher_name || '—'}</div>
                <div><span className="label">Narx:</span> {Number(g.course_price).toLocaleString()} so'm/oy</div>
                <div><span className="label">Jadval:</span> {g.schedule || '—'}</div>
                <div><span className="label">O'quvchilar:</span> <span className="badge">{g.student_count}</span></div>
              </div>
              <div className="group-card-actions">
                <button className="btn-sm" onClick={() => { loadDetail(g.id).then(() => {}) ; setDetailGroup({ ...g, members: [] }) }}>
                  👥 Tarkib
                </button>
                <button className="btn-sm" onClick={() => openEdit(g)}>✏️ Tahrir</button>
                <button className="btn-sm" onClick={() => handleToggle(g)}>
                  {g.is_active ? '🔴 Yopish' : '🟢 Ochish'}
                </button>
                <button className="btn-sm danger" onClick={() => handleDelete(g.id)}>🗑️</button>
              </div>
            </div>
          ))}
          {groups.length === 0 && <div className="muted center">Guruhlar yo'q</div>}
        </div>
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
              <label>Ustoz</label>
              <select className="field" value={form.teacher_id} onChange={e => setForm(p => ({ ...p, teacher_id: e.target.value }))}>
                <option value="">— Tanlang —</option>
                {teachers.map(t => <option key={t.id} value={t.id}>{t.full_name || t.username}</option>)}
              </select>
              <label>Kurs narxi (so'm/oy)</label>
              <input className="field" type="number" value={form.course_price} onChange={e => setForm(p => ({ ...p, course_price: e.target.value }))} placeholder="500000" />
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
              <div className="add-student-row">
                <select className="field flex-1" value={addStudentId} onChange={e => setAddStudentId(e.target.value)}>
                  <option value="">— Talaba tanlang —</option>
                  {availableStudents.map(s => (
                    <option key={s.id} value={s.id}>{s.full_name} ({s.phone1})</option>
                  ))}
                </select>
                <button className="button primary" onClick={handleAddStudent}>+ Qo'shish</button>
              </div>
              <table className="data-table mt-1">
                <thead>
                  <tr><th>#</th><th>Ism</th><th>Telefon</th><th>Qo'shilgan</th><th></th></tr>
                </thead>
                <tbody>
                  {(detailGroup.members || []).map((m, i) => (
                    <tr key={m.id}>
                      <td>{i + 1}</td>
                      <td>{m.student_name}</td>
                      <td>{m.student_phone}</td>
                      <td>{new Date(m.joined_at).toLocaleDateString('uz')}</td>
                      <td><button className="btn-icon danger" onClick={() => handleRemoveStudent(m.student_id)}>✕</button></td>
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
