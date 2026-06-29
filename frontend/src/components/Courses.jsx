import { useEffect, useState } from 'react'
import { toast } from 'react-hot-toast'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faPlus, faPen, faTrash, faBookOpen } from '@fortawesome/free-solid-svg-icons'
import { fetchCourses, createCourse, updateCourse, deleteCourse } from '../api'

const EMPTY = { name: '', description: '', total_lessons: '', duration_months: '' }

export default function Courses() {
  const [courses, setCourses] = useState([])
  const [loading, setLoading] = useState(false)
  const [modal, setModal] = useState(null)
  const [form, setForm] = useState(EMPTY)
  const [saving, setSaving] = useState(false)

  useEffect(() => { load() }, [])

  async function load() {
    setLoading(true)
    try { setCourses(await fetchCourses()) }
    catch { toast.error("Yuklab bo'lmadi") }
    finally { setLoading(false) }
  }

  function openAdd() { setForm(EMPTY); setModal('add') }
  function openEdit(c) {
    setForm({
      name: c.name,
      description: c.description || '',
      total_lessons: c.total_lessons,
      duration_months: c.duration_months || '',
    })
    setModal(c)
  }

  async function handleSave() {
    if (!form.name.trim()) return toast.error("Kurs nomi majburiy")
    if (!form.total_lessons) return toast.error("Darslar soni majburiy")
    setSaving(true)
    const payload = {
      name: form.name.trim(),
      description: form.description.trim() || null,
      total_lessons: parseInt(form.total_lessons),
      duration_months: form.duration_months ? parseInt(form.duration_months) : null,
    }
    try {
      if (modal === 'add') {
        await createCourse(payload)
        toast.success("Kurs qo'shildi")
      } else {
        await updateCourse(modal.id, payload)
        toast.success('Saqlandi')
      }
      setModal(null)
      load()
    } catch (e) { toast.error(e.message) }
    finally { setSaving(false) }
  }

  async function handleToggle(c) {
    try {
      await updateCourse(c.id, { is_active: !c.is_active })
      load()
    } catch { toast.error('Xatolik') }
  }

  async function handleDelete(c) {
    if (!window.confirm(`"${c.name}" kursini o'chirasizmi?`)) return
    try {
      await deleteCourse(c.id)
      toast.success("O'chirildi")
      load()
    } catch (e) { toast.error(e.message) }
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1><FontAwesomeIcon icon={faBookOpen} className="page-icon" /> Kurslar</h1>
        <button className="button primary" onClick={openAdd}>
          <FontAwesomeIcon icon={faPlus} /> Kurs qo'shish
        </button>
      </div>

      {loading ? <div className="muted center">Yuklanmoqda...</div> : (
        <table className="data-table">
          <thead>
            <tr>
              <th>#</th>
              <th>Kurs nomi</th>
              <th>Davomiyligi</th>
              <th>Darslar soni</th>
              <th>Holat</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {courses.map((c, i) => (
              <tr key={c.id} style={{ opacity: c.is_active ? 1 : 0.55 }}>
                <td>{i + 1}</td>
                <td>
                  <strong>{c.name}</strong>
                  {c.description && <div className="muted" style={{ fontSize: 12 }}>{c.description}</div>}
                </td>
                <td>{c.duration_months ? `${c.duration_months} oy` : '—'}</td>
                <td>{c.total_lessons} ta dars</td>
                <td>
                  <span className={`status-badge ${c.is_active ? 'active' : 'inactive'}`}>
                    {c.is_active ? 'Faol' : 'Yopiq'}
                  </span>
                </td>
                <td style={{ display: 'flex', gap: 6 }}>
                  <button className="btn-sm" onClick={() => openEdit(c)}>
                    <FontAwesomeIcon icon={faPen} />
                  </button>
                  <button className="btn-sm" onClick={() => handleToggle(c)}>
                    {c.is_active ? 'Yopish' : 'Ochish'}
                  </button>
                  <button className="btn-icon danger" onClick={() => handleDelete(c)}>
                    <FontAwesomeIcon icon={faTrash} />
                  </button>
                </td>
              </tr>
            ))}
            {courses.length === 0 && (
              <tr><td colSpan={6} className="muted center">Kurslar yo'q</td></tr>
            )}
          </tbody>
        </table>
      )}

      {modal && (
        <div className="modal-overlay" onClick={() => setModal(null)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>{modal === 'add' ? 'Yangi kurs' : 'Kursni tahrirlash'}</h3>
              <button className="modal-close" onClick={() => setModal(null)}>✕</button>
            </div>
            <div className="modal-body">
              <label>Kurs nomi *</label>
              <input
                className="field"
                value={form.name}
                onChange={e => setForm(p => ({ ...p, name: e.target.value }))}
                placeholder="Masalan: Foundation, Python, Flutter..."
              />
              <label>Tavsif</label>
              <input
                className="field"
                value={form.description}
                onChange={e => setForm(p => ({ ...p, description: e.target.value }))}
                placeholder="Ixtiyoriy qisqa tavsif"
              />
              <label>Davomiyligi (oy)</label>
              <input
                className="field"
                type="number"
                min="1"
                value={form.duration_months}
                onChange={e => setForm(p => ({ ...p, duration_months: e.target.value }))}
                placeholder="Masalan: 2"
              />
              <label>Jami darslar soni *</label>
              <input
                className="field"
                type="number"
                min="1"
                value={form.total_lessons}
                onChange={e => setForm(p => ({ ...p, total_lessons: e.target.value }))}
                placeholder="Masalan: 24"
              />
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
