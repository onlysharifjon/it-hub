import { useEffect, useState } from 'react'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faCircleCheck, faPaperPlane } from '@fortawesome/free-solid-svg-icons'
import MinaretLogo from './MinaretLogo'
import { fetchPublicIntake, submitPublicIntake } from '../api'

const COURSES = [
  { key: '',           label: 'Kursni tanlang' },
  { key: 'foundation', label: 'Foundation' },
  { key: 'frontend',   label: 'Frontend' },
  { key: 'backend',    label: 'Backend' },
]

export default function PublicIntake({ slug }) {
  const [cfg, setCfg]     = useState(null)
  const [state, setState] = useState('loading')   // loading | ready | notfound | done
  const [form, setForm]   = useState({ full_name: '', phone: '', course_interest: '', parent_phone: '', notes: '' })
  const [saving, setSaving] = useState(false)
  const [error, setError]   = useState('')

  useEffect(() => {
    fetchPublicIntake(slug)
      .then(c => { setCfg(c); setState('ready') })
      .catch(() => setState('notfound'))
  }, [slug])

  async function submit(e) {
    e.preventDefault()
    setError('')
    if (form.full_name.trim().length < 2) return setError('Ismingizni kiriting')
    if (form.phone.trim().length < 7)     return setError("To'g'ri telefon raqam kiriting")
    setSaving(true)
    try {
      await submitPublicIntake(slug, {
        full_name: form.full_name.trim(),
        phone: form.phone.trim(),
        course_interest: form.course_interest || null,
        parent_phone: form.parent_phone || null,
        notes: form.notes || null,
      })
      setState('done')
    } catch (err) { setError(err.message || 'Xatolik yuz berdi') }
    finally { setSaving(false) }
  }

  return (
    <div className="intake-page">
      <div className="intake-card">
        <div className="intake-brand">
          <MinaretLogo size={44} />
          <span>Minar Academy</span>
        </div>

        {state === 'loading' && <div className="muted center py-8">Yuklanmoqda...</div>}

        {state === 'notfound' && (
          <div className="center py-8">
            <h2>Forma topilmadi</h2>
            <p className="muted">Bu forma mavjud emas yoki faol emas.</p>
          </div>
        )}

        {state === 'done' && (
          <div className="center py-8 intake-done">
            <FontAwesomeIcon icon={faCircleCheck} className="intake-done-icon" />
            <h2>Rahmat!</h2>
            <p className="muted">Arizangiz qabul qilindi. Tez orada siz bilan bog'lanamiz.</p>
          </div>
        )}

        {state === 'ready' && cfg && (
          <>
            <h1 className="intake-title">{cfg.title || cfg.name}</h1>
            {cfg.description && <p className="intake-desc">{cfg.description}</p>}
            <form onSubmit={submit} className="intake-form">
              <label>Ism Familiya *</label>
              <input className="field" value={form.full_name} autoFocus
                onChange={e => setForm(p => ({ ...p, full_name: e.target.value }))} placeholder="To'liq ism" />
              <label>Telefon raqam *</label>
              <input className="field" value={form.phone} inputMode="tel"
                onChange={e => setForm(p => ({ ...p, phone: e.target.value }))} placeholder="+998 90 123 45 67" />
              <label>Qiziqayotgan kurs</label>
              <select className="field" value={form.course_interest}
                onChange={e => setForm(p => ({ ...p, course_interest: e.target.value }))}>
                {COURSES.map(c => <option key={c.key} value={c.key}>{c.label}</option>)}
              </select>
              <label>Ota-ona telefoni</label>
              <input className="field" value={form.parent_phone} inputMode="tel"
                onChange={e => setForm(p => ({ ...p, parent_phone: e.target.value }))} placeholder="Ixtiyoriy" />
              <label>Izoh</label>
              <textarea className="field" rows={2} value={form.notes}
                onChange={e => setForm(p => ({ ...p, notes: e.target.value }))} placeholder="Qo'shimcha (ixtiyoriy)" />

              {error && <div className="intake-error">{error}</div>}
              <button className="button primary intake-submit" disabled={saving}>
                <FontAwesomeIcon icon={faPaperPlane} /> {saving ? 'Yuborilmoqda...' : 'Ariza yuborish'}
              </button>
            </form>
          </>
        )}
      </div>
      <div className="intake-footer">© {new Date().getFullYear()} Minar Academy</div>
    </div>
  )
}
