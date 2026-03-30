import { useState } from 'react'

const CATEGORY_LABELS = {
  foundation: 'Foundation',
  frontend: 'Frontend',
  backend: 'Backend',
}

function AddLessonModal({ category, onSave, onClose, existingNumbers }) {
  const [form, setForm] = useState({ lesson_number: '', title: '', section: '' })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  function handleChange(e) {
    const { name, value } = e.target
    setForm(prev => ({ ...prev, [name]: value }))
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    const num = Number(form.lesson_number)
    if (!num || num < 1) { setError("Dars raqami musbat son bo'lishi kerak"); return }
    if (existingNumbers.includes(num)) { setError(`${num}-dars raqami allaqachon mavjud`); return }
    if (!form.title.trim()) { setError('Dars nomi kiritilishi shart'); return }
    setSaving(true)
    try {
      await onSave({
        lesson_number: num,
        title: form.title.trim(),
        section: form.section.trim() || null,
      })
    } catch (err) {
      setError(err.message || 'Xatolik yuz berdi')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal">
        <div className="modal-header">
          <h3>{CATEGORY_LABELS[category]} — yangi dars</h3>
          <button className="modal-close" onClick={onClose}>✕</button>
        </div>
        <form onSubmit={handleSubmit}>
          <div className="modal-body">
            <label>Dars №</label>
            <input
              className="field"
              type="number"
              name="lesson_number"
              value={form.lesson_number}
              onChange={handleChange}
              placeholder="1"
              min="1"
              required
            />
            <label>Dars nomi *</label>
            <input
              className="field"
              type="text"
              name="title"
              value={form.title}
              onChange={handleChange}
              placeholder="Dars nomini kiriting"
              required
            />
            <label>Bo'lim</label>
            <input
              className="field"
              type="text"
              name="section"
              value={form.section}
              onChange={handleChange}
              placeholder="Bo'lim nomi (ixtiyoriy)"
            />
            {error && <div className="error">{error}</div>}
          </div>
          <div className="modal-footer">
            <button type="button" className="button secondary" onClick={onClose}>Bekor</button>
            <button type="submit" className="button primary" disabled={saving}>
              {saving ? 'Saqlanmoqda...' : "Qo'shish"}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default AddLessonModal
