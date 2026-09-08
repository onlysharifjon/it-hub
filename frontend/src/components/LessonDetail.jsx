import { useEffect, useState } from 'react'
import { ViewTabs } from './ui/Workspace'

function LessonDetail({ lesson, onSave, saving, canEdit }) {
  const [sectionView, setSectionView] = useState('guide')
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

  const sectionLabels = { guide: 'Dars qo‘llanmasi', homework: 'Uyga vazifa', extra_notes: 'Qo‘shimcha eslatmalar' }
  const changed = Object.keys(form).some(key => form[key] !== (lesson[key] || ''))
  if (!canEdit) return <article className="lesson-reader">
    <header><span className="studio-eyebrow">{lesson.lesson_number ? `${lesson.lesson_number}-dars` : 'Dars rejasi'}</span><h2>{lesson.title}</h2>{lesson.section && <span className="lesson-reader-section">{lesson.section}</span>}</header>
    <ViewTabs value={sectionView} onChange={setSectionView} label="Dars materiali" items={[{ key: 'guide', label: 'Qo‘llanma' }, { key: 'homework', label: 'Uyga vazifa' }, { key: 'extra_notes', label: 'Eslatmalar' }]} />
    <section className="lesson-reader-content"><h3>{sectionLabels[sectionView]}</h3><div>{lesson[sectionView] || 'Bu bo‘limga hali material kiritilmagan.'}</div></section>
    {updatedInfo && <footer className="updated-info">{updatedInfo}</footer>}
  </article>
  return (
    <form className="form lesson-document" onSubmit={handleSubmit}>
      <header className="lesson-document-head"><span className="studio-eyebrow">{lesson.lesson_number ? `${lesson.lesson_number}-dars` : 'Dars rejasi'}</span><h2 className="field-value-static">{lesson.title}</h2><span className="lesson-document-state">{changed ? 'Saqlanmagan o‘zgarishlar' : 'Dars materiallari'}</span></header>
      <div className="field lesson-section-field">
        <label htmlFor="lesson-section">Bo‘lim</label>
        <input
          id="lesson-section"
          type="text"
          name="section"
          value={form.section}
          onChange={handleChange}
          placeholder="Bo'lim nomi"
          disabled={!canEdit}
          className={!canEdit ? 'readonly' : ''}
        />
      </div>
      <ViewTabs value={sectionView} onChange={setSectionView} label="Dars materiali" items={[{ key: 'guide', label: 'Qo‘llanma' }, { key: 'homework', label: 'Uyga vazifa' }, { key: 'extra_notes', label: 'Eslatmalar' }]} />
      <div className="field">
        <label className="sr-only" htmlFor="lesson-material">{sectionLabels[sectionView]}</label>
        <textarea
          id="lesson-material"
          name={sectionView}
          value={form[sectionView]}
          onChange={handleChange}
          placeholder={canEdit ? sectionLabels[sectionView] + ' matnini kiriting...' : 'Kiritilmagan'}
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
          <button className="button" type="submit" disabled={saving}>
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
