import { useEffect, useState } from 'react'
import { toast } from 'react-hot-toast'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faPlus, faPen, faTrash, faBookOpen } from '@fortawesome/free-solid-svg-icons'
import { fetchCourses, createCourse, updateCourse, deleteCourse } from '../api'
import DataTable from './ui/DataTable'
import Modal from './ui/Modal'
import ConfirmDialog from './ui/ConfirmDialog'
import Badge from './ui/Badge'
import { Input } from './ui/Field'

const EMPTY = { name: '', description: '', total_lessons: '', duration_months: '' }

export default function Courses() {
  const [courses, setCourses] = useState([])
  const [loading, setLoading] = useState(false)
  const [modal, setModal] = useState(null)
  const [form, setForm] = useState(EMPTY)
  const [errors, setErrors] = useState({})
  const [saving, setSaving] = useState(false)
  const [confirmTarget, setConfirmTarget] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => { load() }, [])

  async function load() {
    setLoading(true)
    setError(null)
    try { setCourses(await fetchCourses()) }
    catch (e) { setError(e) }
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
    const errs = {}
    if (!form.name.trim()) errs.name = 'Kurs nomi majburiy'
    if (!form.total_lessons) errs.total_lessons = 'Darslar soni majburiy'
    else if (parseInt(form.total_lessons) <= 0) errs.total_lessons = "Musbat son bo'lishi kerak"
    if (form.duration_months && parseInt(form.duration_months) <= 0) errs.duration_months = "Musbat son bo'lishi kerak"
    setErrors(errs)
    if (Object.keys(errs).length) return
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

  async function handleDelete() {
    try {
      await deleteCourse(confirmTarget.id)
      setConfirmTarget(null)
      toast.success("O'chirildi")
      load()
    } catch (e) { toast.error(e.message) }
  }

  return (
    <div className="page">
      <div className="page-header">
        <div className="page-header-text">
          <h1><FontAwesomeIcon icon={faBookOpen} className="page-icon" /> Kurslar</h1>
          <p className="page-subtitle">Dastur, davomiyligi va darslar soni</p>
        </div>
        <div className="header-actions">
          <button className="button" onClick={openAdd}>
            <FontAwesomeIcon icon={faPlus} /> Kurs qo'shish
          </button>
        </div>
      </div>

      <DataTable
        columns={[
          { key: 'index', header: '#', width: 52, className: 'text-muted', render: (_c, i) => i + 1 },
          { key: 'name', header: 'Kurs nomi', sortable: true, render: c => (
            <>
              <strong>{c.name}</strong>
              {c.description && <div className="muted cell-sm">{c.description}</div>}
            </>
          ) },
          { key: 'duration_months', header: 'Davomiyligi', sortable: true,
            sortValue: c => c.duration_months || 0,
            render: c => c.duration_months ? `${c.duration_months} oy` : '—' },
          { key: 'total_lessons', header: 'Darslar soni', sortable: true,
            sortValue: c => c.total_lessons,
            render: c => `${c.total_lessons} ta dars` },
          { key: 'is_active', header: 'Holat', sortable: true, render: c => (
            <Badge variant={c.is_active ? 'success' : 'neutral'}>{c.is_active ? 'Faol' : 'Yopiq'}</Badge>
          ) },
          { key: 'actions', header: 'Amallar', className: 'actions', render: c => (
            <>
              <button className="btn-icon" onClick={() => openEdit(c)} title="Tahrirlash" aria-label="Tahrirlash">
                <FontAwesomeIcon icon={faPen} />
              </button>
              <button className="btn-sm" onClick={() => handleToggle(c)}>
                {c.is_active ? 'Yopish' : 'Ochish'}
              </button>
              <button className="btn-icon danger" onClick={() => setConfirmTarget(c)} title="O'chirish" aria-label="O'chirish">
                <FontAwesomeIcon icon={faTrash} />
              </button>
            </>
          ) },
        ]}
        rows={courses}
        loading={loading}
        error={error}
        onRetry={load}
        rowClassName={c => (!c.is_active ? 'row-inactive' : undefined)}
        empty={{
          icon: faBookOpen,
          title: "Kurslar yo'q",
          description: "Guruhlarga biriktirish uchun birinchi kursni qo'shing.",
          action: <button className="button" onClick={openAdd}><FontAwesomeIcon icon={faPlus} /> Kurs qo'shish</button>,
        }}
      />

      <Modal
        open={!!modal}
        title={modal === 'add' ? 'Yangi kurs' : 'Kursni tahrirlash'}
        onClose={() => { setModal(null); setErrors({}) }}
        footer={
          <>
            <button className="button secondary" onClick={() => { setModal(null); setErrors({}) }}>Bekor</button>
            <button className="button" onClick={handleSave} disabled={saving}>
              {saving ? 'Saqlanmoqda...' : 'Saqlash'}
            </button>
          </>
        }
      >
        <Input label="Kurs nomi" required value={form.name} error={errors.name}
          onChange={e => setForm(p => ({ ...p, name: e.target.value }))}
          placeholder="Masalan: Foundation, Python, Flutter..." />
        <Input label="Tavsif" value={form.description}
          onChange={e => setForm(p => ({ ...p, description: e.target.value }))}
          placeholder="Ixtiyoriy qisqa tavsif" />
        <Input label="Davomiyligi (oy)" type="number" min="1" value={form.duration_months}
          error={errors.duration_months}
          onChange={e => setForm(p => ({ ...p, duration_months: e.target.value }))}
          placeholder="Masalan: 2" />
        <Input label="Jami darslar soni" required type="number" min="1" value={form.total_lessons}
          error={errors.total_lessons}
          onChange={e => setForm(p => ({ ...p, total_lessons: e.target.value }))}
          placeholder="Masalan: 24" />
      </Modal>

      <ConfirmDialog
        open={!!confirmTarget}
        title="Kursni o'chirish"
        message={confirmTarget ? `"${confirmTarget.name}" kursi o'chirilsinmi?` : ''}
        confirmLabel="Ha, o'chirish"
        onConfirm={handleDelete}
        onClose={() => setConfirmTarget(null)}
      />

    </div>
  )
}
