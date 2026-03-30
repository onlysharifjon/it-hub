import { useState } from 'react'

function AddLessonModal({ onSave, onClose, existingNumbers }) {
  const [form, setForm] = useState({
    month: 1,
    week: 1,
    lesson_number: '',
    title: '',
    section: '',
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  function handleChange(e) {
    const { name, value } = e.target
    setForm((prev) => ({ ...prev, [name]: value }))
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
        month: Number(form.month),
        week: Number(form.week),
        lesson_number: num,
        title: form.title.trim(),
        section: form.section.trim() || null,
      })
    } catch (err) {
      setError(err.message || "Xatolik yuz berdi")
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal-card">
        <div className="modal-header">
          <h3>Yangi dars qo'shish</h3>
          <button className="modal-close" onClick={onClose}>✕</button>
        </div>
        <form className="form" onSubmit={handleSubmit}>
          <div className="form-row">
            <div className="field">
              <label>Oy</label>
              <select name="month" value={form.month} onChange={handleChange}>
                <option value={1}>1-oy</option>
                <option value={2}>2-oy</option>
                <option value={3}>3-oy</option>
              </select>
            </div>
            <div className="field">
              <label>Hafta</label>
              <select name="week" value={form.week} onChange={handleChange}>
                {[1,2,3,4,5,6,7,8,9,10,11,12].map((w) => (
                  <option key={w} value={w}>{w}-hafta</option>
                ))}
              </select>
            </div>
            <div className="field">
              <label>Dars №</label>
              <input
                type="number"
                name="lesson_number"
                value={form.lesson_number}
                onChange={handleChange}
                placeholder="37"
                min="1"
                required
              />
            </div>
          </div>
          <div className="field">
            <label>Dars nomi *</label>
            <input
              type="text"
              name="title"
              value={form.title}
              onChange={handleChange}
              placeholder="Dars nomini kiriting"
              required
            />
          </div>
          <div className="field">
            <label>Bo'lim</label>
            <input
              type="text"
              name="section"
              value={form.section}
              onChange={handleChange}
              placeholder="Bo'lim nomi (ixtiyoriy)"
            />
          </div>
          {error && <div className="error">{error}</div>}
          <div className="actions">
            <button type="button" className="button secondary" onClick={onClose}>
              Bekor qilish
            </button>
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
