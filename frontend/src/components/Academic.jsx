import { useEffect, useMemo, useRef, useState } from 'react'
import { toast } from 'react-hot-toast'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faGraduationCap, faPlus, faTrash, faPen, faCommentDots,
  faAward, faCalendarDays, faToggleOn, faToggleOff, faFilePdf, faCoins,
} from '@fortawesome/free-solid-svg-icons'
import {
  fetchAcademicOptions,
  fetchGrades, createGrade, updateGrade, deleteGrade,
  fetchFeedbacks, createFeedback, updateFeedback, deleteFeedback,
  fetchCertificates, createCertificate, updateCertificate, deleteCertificate, uploadCertificatePdf,
  fetchEvents, createEvent, updateEvent, deleteEvent,
  fetchCoinSummary, giveCoins, deductCoins, fetchCoinTransactions, fetchCoinTotals,
} from '../api'

const EXAM_TYPES = { exam: 'Imtihon', test: 'Test', quiz: 'Quiz', project: 'Loyiha' }

const EMPTY_GRADE = { group_id: '', student_id: '', subject: '', score: '', max_score: 100, exam_type: 'exam', exam_date: '', comment: '' }
const EMPTY_FEEDBACK = { group_id: '', student_id: '', comment: '' }
const EMPTY_CERT = { group_id: '', student_id: '', title: '', file_url: '', issued_at: '' }
const EMPTY_EVENT = { title: '', description: '', event_date: '', event_time: '10:00', location: '' }
const EMPTY_COIN = { group_id: '', student_id: '', amount: '', reason: '' }

function fmtDate(d) {
  if (!d) return '—'
  return new Date(d).toLocaleDateString('uz-UZ', { day: '2-digit', month: '2-digit', year: 'numeric' })
}

export default function Academic({ currentUser }) {
  const isTeacher = currentUser?.role === 'teacher'
  const isAdmin = currentUser?.role === 'admin'
  const canCertificates = ['admin', 'metodist', 'hunter'].includes(currentUser?.role)

  const [tab, setTab] = useState('grades')
  const [options, setOptions] = useState([])
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(false)
  const [filterStudent, setFilterStudent] = useState('')
  const [modal, setModal] = useState(false)
  const [editing, setEditing] = useState(null)   // tahrirlanayotgan yozuv id'si
  const [form, setForm] = useState(EMPTY_GRADE)
  const [saving, setSaving] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [coinSummary, setCoinSummary] = useState(null)
  const [coinTotals, setCoinTotals] = useState([])
  const [coinMode, setCoinMode] = useState('give')   // give | deduct (deduct — faqat admin)
  const pdfInputRef = useRef(null)

  const allStudents = useMemo(() => {
    const seen = new Map()
    options.forEach(o => o.students.forEach(s => seen.set(s.id, s)))
    return [...seen.values()].sort((a, b) => a.full_name.localeCompare(b.full_name))
  }, [options])

  const formStudents = useMemo(() => {
    if (!form.group_id) return allStudents
    return options.find(o => o.group_id === parseInt(form.group_id))?.students || []
  }, [options, form.group_id, allStudents])

  useEffect(() => { fetchAcademicOptions().then(setOptions).catch(() => {}) }, [])
  useEffect(() => { load() }, [tab, filterStudent])

  async function load() {
    setLoading(true)
    try {
      const sid = filterStudent || undefined
      if (tab === 'grades') setItems(await fetchGrades({ student_id: sid }))
      else if (tab === 'feedback') setItems(await fetchFeedbacks(sid))
      else if (tab === 'certificates') setItems(await fetchCertificates(sid))
      else if (tab === 'coins') {
        const [txs, summary, totals] = await Promise.all([
          fetchCoinTransactions(sid), fetchCoinSummary(), fetchCoinTotals(),
        ])
        setItems(txs); setCoinSummary(summary); setCoinTotals(totals)
      }
      else setItems(await fetchEvents())
    } catch { toast.error("Yuklab bo'lmadi") }
    finally { setLoading(false) }
  }

  function openCreate() {
    setEditing(null)
    setCoinMode('give')
    setForm(tab === 'grades' ? EMPTY_GRADE : tab === 'feedback' ? EMPTY_FEEDBACK
      : tab === 'certificates' ? EMPTY_CERT : tab === 'coins' ? EMPTY_COIN : EMPTY_EVENT)
    setModal(true)
  }

  function openDeduct() {
    setEditing(null)
    setCoinMode('deduct')
    setForm(EMPTY_COIN)
    setModal(true)
  }

  function openEdit(item) {
    setEditing(item.id)
    if (tab === 'grades') {
      setForm({
        group_id: item.group_id || '', student_id: item.student_id,
        subject: item.subject, score: item.score, max_score: item.max_score,
        exam_type: item.exam_type, exam_date: item.exam_date || '', comment: item.comment || '',
      })
    } else if (tab === 'feedback') {
      setForm({ group_id: item.group_id || '', student_id: item.student_id, comment: item.comment })
    } else if (tab === 'certificates') {
      setForm({ group_id: '', student_id: item.student_id, title: item.title, file_url: item.file_url, issued_at: item.issued_at || '' })
    } else {
      const dt = new Date(item.event_date)
      setForm({
        title: item.title, description: item.description || '',
        event_date: dt.toISOString().slice(0, 10),
        event_time: dt.toTimeString().slice(0, 5),
        location: item.location || '',
      })
    }
    setModal(true)
  }

  async function handleSave() {
    setSaving(true)
    try {
      if (tab === 'grades') {
        if (!form.student_id) throw new Error('Talabani tanlang')
        if (!form.subject.trim()) throw new Error('Fan/mavzuni kiriting')
        if (form.score === '' || parseInt(form.score) < 0) throw new Error('Ballni kiriting')
        const p = {
          subject: form.subject.trim(), score: parseInt(form.score),
          max_score: parseInt(form.max_score) || 100, exam_type: form.exam_type,
          exam_date: form.exam_date || null, comment: form.comment || null,
        }
        if (editing) await updateGrade(editing, p)
        else await createGrade({ ...p, student_id: parseInt(form.student_id), group_id: form.group_id ? parseInt(form.group_id) : null })
      } else if (tab === 'feedback') {
        if (!form.student_id) throw new Error('Talabani tanlang')
        if (form.comment.trim().length < 2) throw new Error('Izohni kiriting')
        if (editing) await updateFeedback(editing, { comment: form.comment.trim() })
        else await createFeedback({
          student_id: parseInt(form.student_id),
          group_id: form.group_id ? parseInt(form.group_id) : null,
          comment: form.comment.trim(),
        })
      } else if (tab === 'certificates') {
        if (!form.student_id) throw new Error('Talabani tanlang')
        if (form.title.trim().length < 2) throw new Error('Sertifikat nomini kiriting')
        if (form.file_url.trim().length < 5) throw new Error('PDF havolasini kiriting')
        const p = { title: form.title.trim(), file_url: form.file_url.trim(), issued_at: form.issued_at || null }
        if (editing) await updateCertificate(editing, p)
        else await createCertificate({ ...p, student_id: parseInt(form.student_id) })
      } else if (tab === 'coins') {
        if (!form.student_id) throw new Error('Talabani tanlang')
        const amount = parseInt(form.amount)
        if (!amount || amount < 1) throw new Error('Coin miqdorini kiriting')
        if (amount > 1000) throw new Error("Bir amalda maksimal 1000 coin berish/yechish mumkin")
        if (coinMode === 'deduct') {
          await deductCoins({
            student_id: parseInt(form.student_id),
            amount, reason: form.reason.trim() || null,
          })
        } else {
          await giveCoins({
            student_id: parseInt(form.student_id),
            group_id: form.group_id ? parseInt(form.group_id) : null,
            amount, reason: form.reason.trim() || null,
          })
        }
      } else {
        if (form.title.trim().length < 2) throw new Error('Tadbir nomini kiriting')
        if (!form.event_date) throw new Error('Sanani tanlang')
        const p = {
          title: form.title.trim(), description: form.description || null,
          event_date: `${form.event_date}T${form.event_time || '10:00'}:00`,
          location: form.location || null,
        }
        if (editing) await updateEvent(editing, p)
        else await createEvent(p)
      }
      toast.success(tab === 'coins' ? (coinMode === 'deduct' ? 'Coin yechildi' : 'Coin berildi 🪙') : editing ? 'Yangilandi' : "Qo'shildi")
      setModal(false)
      load()
    } catch (e) { toast.error(e.message) }
    finally { setSaving(false) }
  }

  async function handleDelete(item) {
    const label = tab === 'grades' ? 'Baho' : tab === 'feedback' ? 'Izoh' : tab === 'certificates' ? 'Sertifikat' : 'Tadbir'
    if (!confirm(`${label} o'chiriladi. Tasdiqlaysizmi?`)) return
    try {
      if (tab === 'grades') await deleteGrade(item.id)
      else if (tab === 'feedback') await deleteFeedback(item.id)
      else if (tab === 'certificates') await deleteCertificate(item.id)
      else await deleteEvent(item.id)
      toast.success("O'chirildi")
      load()
    } catch (e) { toast.error(e.message) }
  }

  async function handlePdfFile(e) {
    const file = e.target.files[0]
    if (!file) return
    if (file.type !== 'application/pdf') { toast.error('Faqat PDF fayl yuklash mumkin'); e.target.value = ''; return }
    if (file.size > 10 * 1024 * 1024) { toast.error('Fayl hajmi 10 MB dan oshmasin'); e.target.value = ''; return }
    setUploading(true)
    try {
      const { file_url } = await uploadCertificatePdf(file)
      setForm(p => ({ ...p, file_url }))
      toast.success('PDF yuklandi')
    } catch (err) { toast.error(err.message) }
    finally { setUploading(false); e.target.value = '' }
  }

  async function handleEventToggle(ev) {
    try {
      await updateEvent(ev.id, { is_active: !ev.is_active })
      toast.success(ev.is_active ? 'Tadbir yashirildi' : 'Tadbir faollashtirildi')
      load()
    } catch (e) { toast.error(e.message) }
  }

  const canWrite = tab === 'certificates' ? canCertificates : tab === 'events' ? isAdmin : true

  const TABS = [
    { key: 'grades', label: 'Baholar', icon: faGraduationCap },
    { key: 'coins', label: 'Coinlar', icon: faCoins },
    { key: 'feedback', label: 'Izohlar', icon: faCommentDots },
    ...(canCertificates ? [{ key: 'certificates', label: 'Sertifikatlar', icon: faAward }] : []),
    { key: 'events', label: 'Tadbirlar', icon: faCalendarDays },
  ]

  return (
    <div className="page">
      <div className="page-header">
        <h1><FontAwesomeIcon icon={faGraduationCap} className="page-icon" /> Akademik</h1>
        <div style={{ display: 'flex', gap: 8 }}>
          {tab === 'coins' && isAdmin && (
            <button className="button secondary" onClick={openDeduct} style={{ color: '#dc2626' }}>
              <FontAwesomeIcon icon={faCoins} /> Coin yechish
            </button>
          )}
          {canWrite && (
            <button className="button primary" onClick={openCreate}
              disabled={tab === 'coins' && coinSummary?.remaining === 0}>
              <FontAwesomeIcon icon={tab === 'coins' ? faCoins : faPlus} />
              {' '}{tab === 'grades' ? "Baho qo'shish" : tab === 'coins' ? 'Coin berish'
                : tab === 'feedback' ? "Izoh qo'shish" : tab === 'certificates' ? "Sertifikat qo'shish" : "Tadbir qo'shish"}
            </button>
          )}
        </div>
      </div>

      <p className="text-muted" style={{ fontSize: 13, marginTop: -8 }}>
        Bu yerdagi baholar, izohlar va sertifikatlar ota-onalar mobil ilovasida ko'rinadi.
      </p>

      <div className="tab-bar">
        {TABS.map(t => (
          <button key={t.key} className={`tab-btn ${tab === t.key ? 'active' : ''}`}
            onClick={() => { setTab(t.key); setItems([]) }}>
            <FontAwesomeIcon icon={t.icon} /> {t.label}
          </button>
        ))}
      </div>

      {tab === 'coins' && coinSummary && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 12, margin: '12px 0',
          padding: '10px 14px', borderRadius: 10, border: '1px solid var(--border)',
        }}>
          <FontAwesomeIcon icon={faCoins} style={{ color: '#ca8a04', fontSize: 22 }} />
          {coinSummary.budget === null ? (
            <span>Bu oy berilgani: <strong>{coinSummary.spent}</strong> coin (siz uchun limit yo'q)</span>
          ) : (
            <>
              <span>Hamyon: <strong>{coinSummary.remaining}</strong> / {coinSummary.budget} coin</span>
              <div style={{ flex: 1, maxWidth: 220, height: 8, borderRadius: 4, background: 'var(--border)', overflow: 'hidden' }}>
                <div style={{
                  width: `${coinSummary.budget ? Math.round((coinSummary.remaining / coinSummary.budget) * 100) : 0}%`,
                  height: '100%', background: '#ca8a04', transition: 'width .3s',
                }} />
              </div>
              <span className="text-muted" style={{ fontSize: 12 }}>
                Har oy 1-sanada to'ladi (har bir talabangizga 50 coin)
              </span>
            </>
          )}
        </div>
      )}

      {tab !== 'events' && (
        <div style={{ margin: '12px 0' }}>
          <select className="field" style={{ maxWidth: 320 }} value={filterStudent}
            onChange={e => setFilterStudent(e.target.value)}>
            <option value="">Barcha talabalar</option>
            {allStudents.map(s => <option key={s.id} value={s.id}>{s.full_name}</option>)}
          </select>
        </div>
      )}

      {loading ? (
        <div className="muted center py-8">Yuklanmoqda...</div>
      ) : (
        <div className="table-wrap">
          <table className="data-table">
            {tab === 'grades' && (
              <>
                <thead>
                  <tr><th>#</th><th>Talaba</th><th>Guruh</th><th>Fan/Mavzu</th><th>Turi</th><th>Ball</th><th>Sana</th><th>Kim qo'ydi</th><th></th></tr>
                </thead>
                <tbody>
                  {items.map((g, i) => (
                    <tr key={g.id}>
                      <td className="text-muted">{i + 1}</td>
                      <td><strong>{g.student_name}</strong></td>
                      <td>{g.group_name || '—'}</td>
                      <td>{g.subject}{g.comment && <div className="text-muted" style={{ fontSize: 12 }}>{g.comment}</div>}</td>
                      <td>{EXAM_TYPES[g.exam_type] || g.exam_type}</td>
                      <td>
                        <span className="badge" style={{
                          background: g.score / g.max_score >= 0.8 ? '#dcfce7' : g.score / g.max_score >= 0.6 ? '#fef9c3' : '#fee2e2',
                          color: g.score / g.max_score >= 0.8 ? '#16a34a' : g.score / g.max_score >= 0.6 ? '#ca8a04' : '#dc2626',
                        }}>{g.score}/{g.max_score}</span>
                      </td>
                      <td>{fmtDate(g.exam_date)}</td>
                      <td className="text-muted">{g.created_by_name || '—'}</td>
                      <td>
                        <button className="btn-icon" title="Tahrirlash" onClick={() => openEdit(g)}><FontAwesomeIcon icon={faPen} /></button>
                        <button className="btn-icon danger" title="O'chirish" onClick={() => handleDelete(g)}><FontAwesomeIcon icon={faTrash} /></button>
                      </td>
                    </tr>
                  ))}
                  {items.length === 0 && <tr><td colSpan={9} className="muted center py-4">Baholar yo'q</td></tr>}
                </tbody>
              </>
            )}

            {tab === 'coins' && (
              <>
                <thead>
                  <tr><th>#</th><th>Talaba</th><th>Guruh</th><th>Coin</th><th>Sabab</th><th>Kim berdi</th><th>Sana</th></tr>
                </thead>
                <tbody>
                  {items.map((t, i) => (
                    <tr key={t.id}>
                      <td className="text-muted">{i + 1}</td>
                      <td><strong>{t.student_name}</strong></td>
                      <td>{t.group_name || '—'}</td>
                      <td>
                        <span className="badge" style={t.amount < 0
                          ? { background: '#fee2e2', color: '#dc2626' }
                          : { background: '#fef9c3', color: '#ca8a04' }}>
                          <FontAwesomeIcon icon={faCoins} /> {t.amount < 0 ? t.amount : `+${t.amount}`}
                        </span>
                      </td>
                      <td>{t.reason || <span className="text-muted">—</span>}</td>
                      <td className="text-muted">{t.teacher_name || '—'}</td>
                      <td>{fmtDate(t.created_at)}</td>
                    </tr>
                  ))}
                  {items.length === 0 && <tr><td colSpan={7} className="muted center py-4">Hali coin berilmagan</td></tr>}
                </tbody>
              </>
            )}

            {tab === 'feedback' && (
              <>
                <thead>
                  <tr><th>#</th><th>Talaba</th><th>Guruh</th><th>Izoh</th><th>O'qituvchi</th><th>Sana</th><th></th></tr>
                </thead>
                <tbody>
                  {items.map((f, i) => (
                    <tr key={f.id}>
                      <td className="text-muted">{i + 1}</td>
                      <td><strong>{f.student_name}</strong></td>
                      <td>{f.group_name || '—'}</td>
                      <td style={{ maxWidth: 420 }}>{f.comment}</td>
                      <td className="text-muted">{f.teacher_name || '—'}</td>
                      <td>{fmtDate(f.created_at)}</td>
                      <td>
                        <button className="btn-icon" title="Tahrirlash" onClick={() => openEdit(f)}><FontAwesomeIcon icon={faPen} /></button>
                        <button className="btn-icon danger" title="O'chirish" onClick={() => handleDelete(f)}><FontAwesomeIcon icon={faTrash} /></button>
                      </td>
                    </tr>
                  ))}
                  {items.length === 0 && <tr><td colSpan={7} className="muted center py-4">Izohlar yo'q</td></tr>}
                </tbody>
              </>
            )}

            {tab === 'certificates' && (
              <>
                <thead>
                  <tr><th>#</th><th>Talaba</th><th>Sertifikat</th><th>PDF</th><th>Berilgan sana</th><th>Kim berdi</th><th></th></tr>
                </thead>
                <tbody>
                  {items.map((c, i) => (
                    <tr key={c.id}>
                      <td className="text-muted">{i + 1}</td>
                      <td><strong>{c.student_name}</strong></td>
                      <td>{c.title}</td>
                      <td>
                        <a href={c.file_url} target="_blank" rel="noreferrer" className="button secondary" style={{ padding: '4px 10px', fontSize: 12 }}>
                          <FontAwesomeIcon icon={faFilePdf} /> Ochish
                        </a>
                      </td>
                      <td>{fmtDate(c.issued_at)}</td>
                      <td className="text-muted">{c.created_by_name || '—'}</td>
                      <td>
                        <button className="btn-icon" title="Tahrirlash" onClick={() => openEdit(c)}><FontAwesomeIcon icon={faPen} /></button>
                        <button className="btn-icon danger" title="O'chirish" onClick={() => handleDelete(c)}><FontAwesomeIcon icon={faTrash} /></button>
                      </td>
                    </tr>
                  ))}
                  {items.length === 0 && <tr><td colSpan={7} className="muted center py-4">Sertifikatlar yo'q</td></tr>}
                </tbody>
              </>
            )}

            {tab === 'events' && (
              <>
                <thead>
                  <tr><th>#</th><th>Tadbir</th><th>Sana</th><th>Joy</th><th>Holat</th><th>Kim yaratdi</th>{isAdmin && <th></th>}</tr>
                </thead>
                <tbody>
                  {items.map((ev, i) => (
                    <tr key={ev.id} className={!ev.is_active ? 'row-inactive' : ''}>
                      <td className="text-muted">{i + 1}</td>
                      <td>
                        <strong>{ev.title}</strong>
                        {ev.description && <div className="text-muted" style={{ fontSize: 12 }}>{ev.description}</div>}
                      </td>
                      <td>{new Date(ev.event_date).toLocaleString('uz-UZ', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })}</td>
                      <td>{ev.location || '—'}</td>
                      <td>
                        <span className={`status-badge ${ev.is_active ? 'active' : 'inactive'}`}>
                          {ev.is_active ? 'Faol' : 'Yashirilgan'}
                        </span>
                      </td>
                      <td className="text-muted">{ev.created_by_name || '—'}</td>
                      {isAdmin && (
                        <td>
                          <button className="btn-icon" title={ev.is_active ? 'Yashirish' : 'Faollashtirish'} onClick={() => handleEventToggle(ev)}>
                            <FontAwesomeIcon icon={ev.is_active ? faToggleOn : faToggleOff} />
                          </button>
                          <button className="btn-icon" title="Tahrirlash" onClick={() => openEdit(ev)}><FontAwesomeIcon icon={faPen} /></button>
                          <button className="btn-icon danger" title="O'chirish" onClick={() => handleDelete(ev)}><FontAwesomeIcon icon={faTrash} /></button>
                        </td>
                      )}
                    </tr>
                  ))}
                  {items.length === 0 && <tr><td colSpan={isAdmin ? 7 : 6} className="muted center py-4">Tadbirlar yo'q</td></tr>}
                </tbody>
              </>
            )}
          </table>
        </div>
      )}

      {tab === 'coins' && !loading && coinTotals.length > 0 && (
        <>
          <h3 style={{ margin: '20px 0 8px' }}><FontAwesomeIcon icon={faAward} /> Coin reytingi</h3>
          <div className="table-wrap">
            <table className="data-table">
              <thead><tr><th>O'rin</th><th>Talaba</th><th>Jami coin</th></tr></thead>
              <tbody>
                {coinTotals.slice(0, 10).map((t, i) => (
                  <tr key={t.student_id}>
                    <td>{i === 0 ? '🥇' : i === 1 ? '🥈' : i === 2 ? '🥉' : <span className="text-muted">{i + 1}</span>}</td>
                    <td><strong>{t.student_name}</strong></td>
                    <td>
                      <span className="badge" style={{ background: '#fef9c3', color: '#ca8a04' }}>
                        <FontAwesomeIcon icon={faCoins} /> {t.total}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {modal && (
        <div className="modal-overlay" onClick={() => setModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>
                {tab === 'coins'
                  ? (coinMode === 'deduct' ? 'Coin yechish (admin)' : 'Coin berish')
                  : `${editing ? 'Tahrirlash' : "Qo'shish"} — ${TABS.find(t => t.key === tab)?.label}`}
              </h3>
              <button className="modal-close" onClick={() => setModal(false)}>✕</button>
            </div>
            <div className="modal-body">
              {tab !== 'events' && !editing && (
                <>
                  <label>Guruh {isTeacher ? '*' : ''}</label>
                  <select className="field" value={form.group_id}
                    onChange={e => setForm(p => ({ ...p, group_id: e.target.value, student_id: '' }))}>
                    {!isTeacher && <option value="">— Guruhsiz —</option>}
                    {isTeacher && <option value="">— Tanlang —</option>}
                    {options.map(o => <option key={o.group_id} value={o.group_id}>{o.group_name}</option>)}
                  </select>

                  <label>Talaba *</label>
                  <select className="field" value={form.student_id}
                    onChange={e => setForm(p => ({ ...p, student_id: e.target.value }))}>
                    <option value="">— Tanlang —</option>
                    {formStudents.map(s => <option key={s.id} value={s.id}>{s.full_name}</option>)}
                  </select>
                </>
              )}

              {tab === 'grades' && (
                <>
                  <label>Fan / mavzu *</label>
                  <input className="field" value={form.subject} placeholder="Masalan: JavaScript Basics"
                    onChange={e => setForm(p => ({ ...p, subject: e.target.value }))} />
                  <div className="row-2">
                    <div>
                      <label>Ball *</label>
                      <input className="field" type="number" min="0" value={form.score}
                        onChange={e => setForm(p => ({ ...p, score: e.target.value }))} placeholder="85" />
                    </div>
                    <div>
                      <label>Maksimal ball</label>
                      <input className="field" type="number" min="1" value={form.max_score}
                        onChange={e => setForm(p => ({ ...p, max_score: e.target.value }))} />
                    </div>
                  </div>
                  <div className="row-2">
                    <div>
                      <label>Turi</label>
                      <select className="field" value={form.exam_type}
                        onChange={e => setForm(p => ({ ...p, exam_type: e.target.value }))}>
                        {Object.entries(EXAM_TYPES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                      </select>
                    </div>
                    <div>
                      <label>Sana</label>
                      <input className="field" type="date" value={form.exam_date}
                        onChange={e => setForm(p => ({ ...p, exam_date: e.target.value }))} />
                    </div>
                  </div>
                  <label>Izoh</label>
                  <input className="field" value={form.comment} placeholder="Ixtiyoriy"
                    onChange={e => setForm(p => ({ ...p, comment: e.target.value }))} />
                </>
              )}

              {tab === 'coins' && (
                <>
                  <label>Coin miqdori *</label>
                  <input className="field" type="number" min="1" max="1000" value={form.amount}
                    onChange={e => setForm(p => ({ ...p, amount: e.target.value }))}
                    placeholder={coinMode === 'give' && coinSummary?.remaining != null ? `Maks. ${coinSummary.remaining}` : '50'} />
                  {coinMode === 'deduct' ? (
                    <p className="text-muted" style={{ fontSize: 12, margin: '4px 0 8px', color: '#dc2626' }}>
                      Talabaning balansidan yechiladi — balans manfiy bo'lolmaydi. Ota-onaga bildirishnoma boradi.
                    </p>
                  ) : coinSummary?.remaining != null && (
                    <p className="text-muted" style={{ fontSize: 12, margin: '4px 0 8px' }}>
                      Hamyoningizda {coinSummary.remaining} coin qoldi — har oy 1-sanada to'ladi.
                    </p>
                  )}
                  <label>Sabab</label>
                  <input className="field" value={form.reason}
                    placeholder={coinMode === 'deduct' ? "Masalan: intizom buzilishi" : "Masalan: darsda faol qatnashdi"}
                    onChange={e => setForm(p => ({ ...p, reason: e.target.value }))} />
                </>
              )}

              {tab === 'feedback' && (
                <>
                  <label>Izoh *</label>
                  <textarea className="field" rows={4} value={form.comment}
                    placeholder="Talaba haqida izoh — ota-onaga ko'rinadi"
                    onChange={e => setForm(p => ({ ...p, comment: e.target.value }))} />
                </>
              )}

              {tab === 'certificates' && (
                <>
                  <label>Sertifikat nomi *</label>
                  <input className="field" value={form.title} placeholder="Foundation kursi sertifikati"
                    onChange={e => setForm(p => ({ ...p, title: e.target.value }))} />

                  <label>PDF fayl *</label>
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 4 }}>
                    <button type="button" className="button secondary" disabled={uploading}
                      onClick={() => pdfInputRef.current?.click()}>
                      <FontAwesomeIcon icon={faFilePdf} /> {uploading ? 'Yuklanmoqda...' : 'PDF yuklash'}
                    </button>
                    {form.file_url && (
                      <a href={form.file_url} target="_blank" rel="noreferrer"
                        style={{ fontSize: 12, wordBreak: 'break-all' }}>
                        {form.file_url.split('/').pop()}
                      </a>
                    )}
                  </div>
                  <input ref={pdfInputRef} type="file" accept="application/pdf"
                    style={{ display: 'none' }} onChange={handlePdfFile} />
                  <p className="text-muted" style={{ fontSize: 12, margin: '0 0 8px' }}>
                    Yoki tashqi havolani qo'lda kiriting:
                  </p>
                  <input className="field" value={form.file_url} placeholder="https://..."
                    onChange={e => setForm(p => ({ ...p, file_url: e.target.value }))} />

                  <label>Berilgan sana</label>
                  <input className="field" type="date" value={form.issued_at}
                    onChange={e => setForm(p => ({ ...p, issued_at: e.target.value }))} />
                </>
              )}

              {tab === 'events' && (
                <>
                  <label>Tadbir nomi *</label>
                  <input className="field" value={form.title} placeholder="Ochiq eshiklar kuni"
                    onChange={e => setForm(p => ({ ...p, title: e.target.value }))} />
                  <label>Tavsif</label>
                  <textarea className="field" rows={3} value={form.description}
                    onChange={e => setForm(p => ({ ...p, description: e.target.value }))} />
                  <div className="row-2">
                    <div>
                      <label>Sana *</label>
                      <input className="field" type="date" value={form.event_date}
                        onChange={e => setForm(p => ({ ...p, event_date: e.target.value }))} />
                    </div>
                    <div>
                      <label>Vaqt</label>
                      <input className="field" type="time" value={form.event_time}
                        onChange={e => setForm(p => ({ ...p, event_time: e.target.value }))} />
                    </div>
                  </div>
                  <label>Joy</label>
                  <input className="field" value={form.location} placeholder="Minar Academy, asosiy bino"
                    onChange={e => setForm(p => ({ ...p, location: e.target.value }))} />
                </>
              )}
            </div>
            <div className="modal-footer">
              <button className="button secondary" onClick={() => setModal(false)}>Bekor</button>
              <button className="button primary" onClick={handleSave} disabled={saving || uploading}>
                {saving ? 'Saqlanmoqda...' : 'Saqlash'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
