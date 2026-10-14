import { useEffect, useState } from 'react'
import { toast } from 'react-hot-toast'
import { PageIntro, ViewTabs } from './ui/Workspace'
import {
  fetchParentAbsences, reviewParentAbsence, fetchParentQuestions, replyParentQuestion,
  fetchParentEngagementStudents, fetchStudentWeeklySummary, saveStudentWeeklyRecommendation,
} from '../api'
import './parent-engagement.css'

const REASONS = { sick: 'Kasallik', travel: 'Safar', family: 'Oilaviy sabab', other: 'Boshqa sabab' }
const STATUS = { pending: 'Kutilmoqda', approved: 'Tasdiqlandi', rejected: 'Rad etildi', open: 'Javob kutilmoqda', answered: 'Javob berildi', closed: 'Yopildi' }

function currentMonday() {
  const today = new Date()
  const diff = (today.getDay() + 6) % 7
  today.setDate(today.getDate() - diff)
  const y = today.getFullYear()
  return `${y}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`
}

function mondayOf(value) {
  if (!value) return ''
  const [year, month, day] = value.split('-').map(Number)
  const selected = new Date(year, month - 1, day)
  selected.setDate(selected.getDate() - (selected.getDay() + 6) % 7)
  return `${selected.getFullYear()}-${String(selected.getMonth() + 1).padStart(2, '0')}-${String(selected.getDate()).padStart(2, '0')}`
}

export default function ParentEngagement() {
  const [tab, setTab] = useState('absences')
  const [absences, setAbsences] = useState([])
  const [questions, setQuestions] = useState([])
  const [students, setStudents] = useState([])
  const [studentId, setStudentId] = useState('')
  const [weekStart, setWeekStart] = useState(currentMonday)
  const [weekly, setWeekly] = useState(null)
  const [weeklyError, setWeeklyError] = useState('')
  const [recommendation, setRecommendation] = useState('')
  const [replyDrafts, setReplyDrafts] = useState({})
  const [reviewId, setReviewId] = useState(null)
  const [reviewNote, setReviewNote] = useState('')
  const [busy, setBusy] = useState(false)

  async function loadAbsences() {
    try { setAbsences(await fetchParentAbsences()) }
    catch (e) { toast.error(e.message) }
  }
  async function loadQuestions() {
    try { setQuestions(await fetchParentQuestions()) }
    catch (e) { toast.error(e.message) }
  }
  useEffect(() => {
    loadAbsences()
    loadQuestions()
    fetchParentEngagementStudents().then(rows => {
      setStudents(rows)
      if (rows.length) setStudentId(String(rows[0].id))
    }).catch(e => toast.error(e.message))
  }, [])
  useEffect(() => {
    if (!studentId || tab !== 'weekly') return
    let cancelled = false
    setWeekly(null)
    setWeeklyError('')
    fetchStudentWeeklySummary(studentId, weekStart).then(data => {
      if (cancelled) return
      setWeekly(data)
      setRecommendation(data.teacher_recommendation || '')
    }).catch(e => { if (!cancelled) setWeeklyError(e.message) })
    return () => { cancelled = true }
  }, [studentId, weekStart, tab])

  async function review(id, status) {
    setBusy(true)
    try {
      await reviewParentAbsence(id, { status, staff_note: reviewNote.trim() || null })
      toast.success(status === 'approved' ? 'Izoh tasdiqlandi' : 'Izoh rad etildi')
      setReviewId(null)
      setReviewNote('')
      await loadAbsences()
    } catch (e) { toast.error(e.message) }
    finally { setBusy(false) }
  }

  async function reply(id) {
    const body = (replyDrafts[id] || '').trim()
    if (body.length < 2) return toast.error('Javobni kiriting')
    setBusy(true)
    try {
      await replyParentQuestion(id, body)
      toast.success('Javob ota-onaga yuborildi')
      setReplyDrafts(current => ({ ...current, [id]: '' }))
      await loadQuestions()
    } catch (e) { toast.error(e.message) }
    finally { setBusy(false) }
  }

  async function saveRecommendation() {
    if (recommendation.trim().length < 4) return toast.error('Aniq tavsiyani kiriting')
    setBusy(true)
    try {
      await saveStudentWeeklyRecommendation(studentId, weekStart, recommendation.trim())
      toast.success('Haftalik tavsiya saqlandi')
      setWeekly(await fetchStudentWeeklySummary(studentId, weekStart))
    } catch (e) { toast.error(e.message) }
    finally { setBusy(false) }
  }

  return <div className="page parent-engagement-page">
    <PageIntro eyebrow="MINAR PARENTS" title="Ota-ona murojaatlari"
      description="Qoldirilgan dars izohlarini ko‘rib chiqing, savollarga javob bering va haftalik tavsiya yozing." />
    <ViewTabs value={tab} onChange={setTab} items={[
      { key: 'absences', label: 'Davomat izohlari', count: absences.filter(x => x.status === 'pending').length },
      { key: 'questions', label: 'Ota-ona savollari', count: questions.filter(x => x.status === 'open').length },
      { key: 'weekly', label: 'Haftalik hisobot' },
    ]} />

    {tab === 'absences' && <div className="pe-list">
      {!absences.length && <div className="pe-empty">Hozircha davomat izohlari yo‘q.</div>}
      {absences.map(item => <article className="pe-card" key={item.id}>
        <div className="pe-card-head"><div><span className="pe-eyebrow">{item.lesson_date} · {item.group_name}</span>
          <h2>{item.student_name}</h2></div><span className={`pe-status pe-${item.status}`}>{STATUS[item.status] || item.status}</span></div>
        <p><strong>{REASONS[item.reason] || item.reason}</strong>{item.note ? ` — ${item.note}` : ''}</p>
        {item.staff_note && <p className="pe-note">Xodim izohi: {item.staff_note}</p>}
        {item.status === 'pending' && <div className="pe-actions">
          {reviewId === item.id && <textarea className="field" rows={2} maxLength={500} value={reviewNote}
            onChange={e => setReviewNote(e.target.value)} placeholder="Ota-onaga qisqa izoh (ixtiyoriy)" />}
          <button className="button secondary" onClick={() => { setReviewId(item.id); setReviewNote('') }}>Izoh yozish</button>
          <button className="button" disabled={busy} onClick={() => review(item.id, 'approved')}>Tasdiqlash</button>
          <button className="button secondary" disabled={busy} onClick={() => review(item.id, 'rejected')}>Rad etish</button>
        </div>}
      </article>)}
    </div>}

    {tab === 'questions' && <div className="pe-list">
      {!questions.length && <div className="pe-empty">Hozircha ota-onalardan savol kelmagan.</div>}
      {questions.map(item => <article className="pe-card" key={item.id}>
        <div className="pe-card-head"><div><span className="pe-eyebrow">{item.student_name} · {new Date(item.created_at).toLocaleDateString('uz-UZ')}</span>
          <h2>{item.subject}</h2></div><span className={`pe-status pe-${item.status}`}>{STATUS[item.status] || item.status}</span></div>
        <p>{item.body}</p>
        {item.replies.map(reply => <div className="pe-reply" key={reply.id}><strong>{reply.author_name}</strong><p>{reply.body}</p></div>)}
        {item.status !== 'closed' && <div className="pe-actions">
          <textarea className="field" rows={3} maxLength={2000} value={replyDrafts[item.id] || ''}
            onChange={e => setReplyDrafts(current => ({ ...current, [item.id]: e.target.value }))}
            placeholder="Ota-onaga tushunarli javob yozing…" />
          <button className="button" disabled={busy} onClick={() => reply(item.id)}>Javob yuborish</button>
        </div>}
      </article>)}
    </div>}

    {tab === 'weekly' && <div className="pe-weekly">
      <div className="pe-filters"><label>Talaba<select className="field" value={studentId} onChange={e => setStudentId(e.target.value)}>
        {students.map(s => <option value={s.id} key={s.id}>{s.full_name}</option>)}
      </select></label><label>Hafta boshi (dushanba)<input className="field" type="date" value={weekStart}
        onChange={e => setWeekStart(mondayOf(e.target.value))} /></label></div>
      {weekly ? <>
        <div className="pe-metrics">
          <div><span>Davomat</span><strong>{weekly.attended_lessons}/{weekly.scheduled_lessons}</strong></div>
          <div><span>Uy vazifasi</span><strong>{weekly.homework_completed}/{weekly.homework_total}</strong></div>
          <div><span>O‘rtacha baho</span><strong>{weekly.average_grade == null ? '—' : `${weekly.average_grade}%`}</strong></div>
        </div>
        <div className="pe-card"><h2>Hafta xulosasi</h2>
          {weekly.highlights.map((text, i) => <p key={i}>✓ {text}</p>)}
          {weekly.needs_attention.map((text, i) => <p className="pe-attention" key={i}>• {text}</p>)}
          <label className="pe-label">O‘qituvchi tavsiyasi</label>
          <textarea className="field" rows={4} maxLength={500} value={recommendation}
            onChange={e => setRecommendation(e.target.value)}
            placeholder="Masalan: kasrlar mavzusini uyda 15 daqiqa takrorlang." />
          <button className="button" disabled={busy} onClick={saveRecommendation}>Tavsiyani saqlash</button>
        </div>
      </> : <div className="pe-empty">{weeklyError || (studentId ? 'Hisobot yuklanmoqda…' : 'Talabani tanlang.')}</div>}
    </div>}
  </div>
}
