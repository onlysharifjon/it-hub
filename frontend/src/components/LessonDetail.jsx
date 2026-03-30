import { useEffect, useState } from 'react'

function LessonDetail({ lesson, onSave, saving, canEdit }) {
  const [form, setForm] = useState({
    section: '',
    guide: '',
    homework: '',
    extra_notes: '',
  })

  useEffect(() => {
    if (!lesson) return
    setForm({
      section: lesson.section || '',
      guide: lesson.guide || '',
      homework: lesson.homework || '',
      extra_notes: lesson.extra_notes || '',
    })
  }, [lesson])

  function handleChange(e) {
    const { name, value } = e.target
    setForm((prev) => ({ ...prev, [name]: value }))
  }

  function handleSubmit(e) {
    e.preventDefault()
    if (canEdit) onSave(form)
  }

  const updatedInfo = lesson.updated_at
    ? `${lesson.updated_by_username || 'Noma\u02bclum'} tomonidan ${new Date(lesson.updated_at).toLocaleString('uz-UZ')}`
    : null

  return (
    <form className="form" onSubmit={handleSubmit}>
      <div className="field">
        <label>Dars nomi</label>
        <div className="field-value-static">{lesson.title}</div>
      </div>

      <div className="field">
        <label>Bo'lim</label>
        <input
          type="text"
          name="section"
          value={form.section}
          onChange={handleChange}
          placeholder="Bo'lim nomi"
          disabled={!canEdit}
          className={!canEdit ? 'readonly' : ''}
        />
      </div>

      <div className="field">
        <label>Qo'llanma</label>
        <textarea
          name="guide"
          value={form.guide}
          onChange={handleChange}
          placeholder={canEdit ? "Bosqichma-bosqich ko'rsatmalar" : 'Kiritilmagan'}
          disabled={!canEdit}
          className={!canEdit ? 'readonly' : ''}
        />
      </div>

      <div className="field">
        <label>Uyga vazifa</label>
        <textarea
          name="homework"
          value={form.homework}
          onChange={handleChange}
          placeholder={canEdit ? 'Uyga vazifa matni' : 'Kiritilmagan'}
          disabled={!canEdit}
          className={!canEdit ? 'readonly' : ''}
        />
      </div>

      <div className="field">
        <label>Qo'shimcha fikr</label>
        <textarea
          name="extra_notes"
          value={form.extra_notes}
          onChange={handleChange}
          placeholder={canEdit ? 'Izohlar' : 'Kiritilmagan'}
          disabled={!canEdit}
          className={!canEdit ? 'readonly' : ''}
        />
      </div>

      {updatedInfo && (
        <div className="updated-info">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
          </svg>
          {updatedInfo}
        </div>
      )}

      {canEdit && (
        <div className="actions">
          <button className="button primary" type="submit" disabled={saving}>
            {saving ? 'Saqlanmoqda...' : 'Saqlash'}
          </button>
        </div>
      )}

      {!canEdit && (
        <div className="readonly-notice">
          Ko'rish rejimi — faqat metodist tahrirlashi mumkin
        </div>
      )}
    </form>
  )
}

export default LessonDetail
