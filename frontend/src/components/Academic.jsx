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
  fetchCoinSummary, giveCoins, deductCoins, fetchCoinTransactions, fetchCoinTotals, cancelCoinTransaction,
} from '../api'
import DataTable, { RowActions } from './ui/DataTable'
import Badge from './ui/Badge'
import useConfirm from './ui/useConfirm'
import { isoToInput, inputToIso, fmtDateTime } from '../utils/datetime'

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

const EMPTY_BY_TAB = {
  grades: "Baholar yo'q",
  coins: 'Hali coin berilmagan',
  feedback: "Izohlar yo'q",
  certificates: "Sertifikatlar yo'q",
  events: "Tadbirlar yo'q",
}

export default function Academic({ currentUser }) {
  const [confirmUI, ask] = useConfirm()
  const isTeacher = currentUser?.role === 'teacher'
  const isAdmin = currentUser?.role === 'admin'
  const canCertificates = ['admin', 'support_teacher', 'hunter'].includes(currentUser?.role)

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
      // Toshkent devor-soati: `toISOString()` UTC beradi va kechki tadbir
      // tahrirlashda BIR KUN OLDINGI sanaga tushib qolardi.
      const dtLocal = isoToInput(item.event_date)
      setForm({
        title: item.title, description: item.description || '',
        event_date: dtLocal.slice(0, 10),
        event_time: dtLocal.slice(11, 16),
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
          event_date: inputToIso(`${form.event_date}T${form.event_time || '10:00'}`),
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
    const ok = await ask({
      title: "O'chirish",
      message: `${label} o'chirilsinmi?`,
      confirmLabel: "Ha, o'chirish",
    })
    if (!ok) return
    try {
      if (tab === 'grades') await deleteGrade(item.id)
      else if (tab === 'feedback') await deleteFeedback(item.id)
      else if (tab === 'certificates') await deleteCertificate(item.id)
      else await deleteEvent(item.id)
      toast.success("O'chirildi")
      load()
    } catch (e) { toast.error(e.message) }
  }

  async function handleCancelCoin(t) {
    const ok = await ask({
      title: 'Coin yozuvini bekor qilish',
      message: `${Math.abs(t.amount)} coinlik yozuv bekor qilinsinmi?`,
      detail: "Talabaning coin balansi shu miqdorga qaytariladi.",
      confirmLabel: 'Ha, bekor qilish',
    })
    if (!ok) return
    try {
      await cancelCoinTransaction(t.id)
      toast.success('Bekor qilindi')
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

  // ── Har bir tab uchun ustunlar ────────────────────────────────────────
  const gradeTone = g => {
    const r = g.max_score ? g.score / g.max_score : 0
    return r >= 0.8 ? 'success' : r >= 0.6 ? 'warning' : 'danger'
  }
  const editDeleteCol = {
    key: 'actions', header: '', align: 'right', className: 'actions',
    render: r => (
      <RowActions>
        <button className="btn-icon" title="Tahrirlash" aria-label="Tahrirlash" onClick={() => openEdit(r)}>
          <FontAwesomeIcon icon={faPen} />
        </button>
        <button className="btn-icon danger" title="O'chirish" aria-label="O'chirish" onClick={() => handleDelete(r)}>
          <FontAwesomeIcon icon={faTrash} />
        </button>
      </RowActions>
    ),
  }

  const COLUMNS_BY_TAB = {
    grades: [
      { key: 'student_name', header: 'Talaba', sortable: true, render: g => <strong>{g.student_name}</strong> },
      { key: 'group_name', header: 'Guruh', sortable: true, render: g => g.group_name || '—' },
      {
        key: 'subject', header: 'Fan / Mavzu', sortable: true,
        render: g => (
          <>
            {g.subject}
            {g.comment && <div className="muted-sm">{g.comment}</div>}
          </>
        ),
      },
      { key: 'exam_type', header: 'Turi', sortable: true, render: g => EXAM_TYPES[g.exam_type] || g.exam_type },
      {
        key: 'score', header: 'Ball', align: 'right', sortable: true,
        sortValue: g => (g.max_score ? g.score / g.max_score : 0),
        render: g => <Badge variant={gradeTone(g)} size="sm">{g.score}/{g.max_score}</Badge>,
      },
      { key: 'exam_date', header: 'Sana', sortable: true, render: g => <span className="muted-sm">{fmtDate(g.exam_date)}</span> },
      { key: 'created_by_name', header: "Kim qo'ydi", sortable: true, render: g => <span className="text-muted">{g.created_by_name || '—'}</span> },
      editDeleteCol,
    ],
    coins: [
      { key: 'student_name', header: 'Talaba', sortable: true, render: t => <strong>{t.student_name}</strong> },
      { key: 'group_name', header: 'Guruh', sortable: true, render: t => t.group_name || '—' },
      {
        key: 'amount', header: 'Coin', align: 'right', sortable: true,
        sortValue: t => Number(t.amount),
        render: t => (
          <Badge variant={t.amount < 0 ? 'danger' : 'warning'} size="sm">
            <FontAwesomeIcon icon={faCoins} /> {t.amount < 0 ? t.amount : `+${t.amount}`}
          </Badge>
        ),
      },
      { key: 'reason', header: 'Sabab', render: t => t.reason || <span className="text-muted">—</span> },
      { key: 'teacher_name', header: 'Kim berdi', sortable: true, render: t => <span className="text-muted">{t.teacher_name || '—'}</span> },
      { key: 'created_at', header: 'Sana', sortable: true, render: t => <span className="muted-sm">{fmtDate(t.created_at)}</span> },
      {
        key: 'actions', header: '', align: 'right', className: 'actions',
        render: t => (isAdmin || t.teacher_id === currentUser?.id) ? (
          <RowActions>
            <button className="btn-icon danger" title="Bekor qilish" aria-label="Bekor qilish" onClick={() => handleCancelCoin(t)}>
              <FontAwesomeIcon icon={faTrash} />
            </button>
          </RowActions>
        ) : null,
      },
    ],
    feedback: [
      { key: 'student_name', header: 'Talaba', sortable: true, render: f => <strong>{f.student_name}</strong> },
      { key: 'group_name', header: 'Guruh', sortable: true, render: f => f.group_name || '—' },
      { key: 'comment', header: 'Izoh', render: f => <span className="cell-clamp">{f.comment}</span> },
      { key: 'teacher_name', header: "O'qituvchi", sortable: true, render: f => <span className="text-muted">{f.teacher_name || '—'}</span> },
      { key: 'created_at', header: 'Sana', sortable: true, render: f => <span className="muted-sm">{fmtDate(f.created_at)}</span> },
      editDeleteCol,
    ],
    certificates: [
      { key: 'student_name', header: 'Talaba', sortable: true, render: c => <strong>{c.student_name}</strong> },
      { key: 'title', header: 'Sertifikat', sortable: true },
      {
        key: 'file_url', header: 'PDF',
        render: c => (
          <a href={c.file_url} target="_blank" rel="noreferrer" className="btn-sm">
            <FontAwesomeIcon icon={faFilePdf} /> Ochish
          </a>
        ),
      },
      { key: 'issued_at', header: 'Berilgan sana', sortable: true, render: c => <span className="muted-sm">{fmtDate(c.issued_at)}</span> },
      { key: 'created_by_name', header: 'Kim berdi', sortable: true, render: c => <span className="text-muted">{c.created_by_name || '—'}</span> },
      editDeleteCol,
    ],
    events: [
      {
        key: 'title', header: 'Tadbir', sortable: true,
        render: ev => (
          <>
            <strong>{ev.title}</strong>
            {ev.description && <div className="muted-sm">{ev.description}</div>}
          </>
        ),
      },
      {
        key: 'event_date', header: 'Sana', sortable: true,
        render: ev => fmtDateTime(ev.event_date),
      },
      { key: 'location', header: 'Joy', sortable: true, render: ev => ev.location || '—' },
      {
        key: 'is_active', header: 'Holat', sortable: true,
        render: ev => (
          <span className={`status-badge ${ev.is_active ? 'active' : 'inactive'}`}>
            {ev.is_active ? 'Faol' : 'Yashirilgan'}
          </span>
        ),
      },
      { key: 'created_by_name', header: 'Kim yaratdi', sortable: true, render: ev => <span className="text-muted">{ev.created_by_name || '—'}</span> },
      ...(isAdmin ? [{
        key: 'actions', header: '', align: 'right', className: 'actions',
        render: ev => (
          <RowActions>
            <button className="btn-icon" title={ev.is_active ? 'Yashirish' : 'Faollashtirish'}
              aria-label={ev.is_active ? 'Yashirish' : 'Faollashtirish'} onClick={() => handleEventToggle(ev)}>
              <FontAwesomeIcon icon={ev.is_active ? faToggleOn : faToggleOff} />
            </button>
            <button className="btn-icon" title="Tahrirlash" aria-label="Tahrirlash" onClick={() => openEdit(ev)}>
              <FontAwesomeIcon icon={faPen} />
            </button>
            <button className="btn-icon danger" title="O'chirish" aria-label="O'chirish" onClick={() => handleDelete(ev)}>
              <FontAwesomeIcon icon={faTrash} />
            </button>
          </RowActions>
        ),
      }] : []),
    ],
  }

  return (
    <div className="page">
      {confirmUI}
      <div className="page-header">
        <div className="page-header-text">
          <h1><FontAwesomeIcon icon={faGraduationCap} className="page-icon" /> Baholar va izohlar</h1>
          <p className="page-subtitle">
            Bu yerdagi baholar, izohlar va sertifikatlar ota-onalar mobil ilovasida ko'rinadi.
          </p>
        </div>
        <div className="header-actions">
          {tab === 'coins' && isAdmin && (
            <button className="button secondary" onClick={openDeduct} style={{ color: 'var(--danger-text)' }}>
              <FontAwesomeIcon icon={faCoins} /> Coin yechish
            </button>
          )}
          {canWrite && (
            <button className="button" onClick={openCreate}
              disabled={tab === 'coins' && coinSummary?.remaining === 0}>
              <FontAwesomeIcon icon={tab === 'coins' ? faCoins : faPlus} />
              {' '}{tab === 'grades' ? "Baho qo'shish" : tab === 'coins' ? 'Coin berish'
                : tab === 'feedback' ? "Izoh qo'shish" : tab === 'certificates' ? "Sertifikat qo'shish" : "Tadbir qo'shish"}
            </button>
          )}
        </div>
      </div>

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
          <FontAwesomeIcon icon={faCoins} style={{ color: 'var(--warning-text)', fontSize: 22 }} />
          {coinSummary.budget === null ? (
            <span>Bu oy berilgani: <strong>{coinSummary.spent}</strong> coin (siz uchun limit yo'q)</span>
          ) : (
            <>
              <span>Hamyon: <strong>{coinSummary.remaining}</strong> / {coinSummary.budget} coin</span>
              <div style={{ flex: 1, maxWidth: 220, height: 8, borderRadius: 4, background: 'var(--border)', overflow: 'hidden' }}>
                <div style={{
                  width: `${coinSummary.budget ? Math.round((coinSummary.remaining / coinSummary.budget) * 100) : 0}%`,
                  height: '100%', background: 'var(--warning-text)', transition: 'width .3s',
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

      <DataTable
        columns={COLUMNS_BY_TAB[tab]}
        rows={items}
        loading={loading}
        clientPageSize={25}
        rowClassName={r => (tab === 'events' && !r.is_active ? 'row-inactive' : undefined)}
        densityToggle densityKey={`academic-${tab}`}
        toolbar={tab !== 'events' && (
          <select className="field-sm" value={filterStudent} aria-label="Talaba bo'yicha filtr"
            onChange={e => setFilterStudent(e.target.value)}>
            <option value="">Barcha talabalar</option>
            {allStudents.map(s => <option key={s.id} value={s.id}>{s.full_name}</option>)}
          </select>
        )}
        empty={{
          icon: TABS.find(t => t.key === tab)?.icon,
          title: EMPTY_BY_TAB[tab],
          description: filterStudent ? "Boshqa talabani tanlab ko'ring." : undefined,
        }}
      />

      {tab === 'coins' && !loading && coinTotals.length > 0 && (
        <section>
          <div className="ui-section-head">
            <div className="ui-section-head-text">
              <h2><FontAwesomeIcon icon={faAward} /> Coin reytingi</h2>
              <p>Eng ko'p coin to'plagan 10 ta talaba</p>
            </div>
          </div>
          <DataTable
            columns={[
              {
                key: 'rank', header: "O'rin", width: 70,
                render: (t, i) => i === 0 ? '🥇' : i === 1 ? '🥈' : i === 2 ? '🥉' : <span className="text-muted">{i + 1}</span>,
              },
              { key: 'student_name', header: 'Talaba', render: t => <strong>{t.student_name}</strong> },
              {
                key: 'total', header: 'Jami coin', align: 'right',
                render: t => <Badge variant="warning" size="sm"><FontAwesomeIcon icon={faCoins} /> {t.total}</Badge>,
              },
            ]}
            rows={coinTotals.slice(0, 10)}
            rowKey={t => t.student_id}
          />
        </section>
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
                    onChange={e => {
                      const sid = e.target.value
                      setForm(p => {
                        if (p.group_id || !sid) return { ...p, student_id: sid }
                        // Guruh tanlanmagan bo'lsa (masalan teacher to'g'ridan-to'g'ri talabani tanlasa),
                        // talaba tegishli guruhni avtomatik aniqlaymiz — aks holda backend teacher uchun guruh talab qiladi.
                        const owner = options.find(o => o.students.some(s => String(s.id) === sid))
                        return { ...p, student_id: sid, group_id: owner ? String(owner.group_id) : p.group_id }
                      })
                    }}>
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
                  <input className="field" type="number" min="1" value={form.amount}
                    onChange={e => setForm(p => ({ ...p, amount: e.target.value }))}
                    placeholder={coinMode === 'give' && coinSummary?.remaining != null ? `Maks. ${coinSummary.remaining}` : '50'} />
                  {coinMode === 'deduct' ? (
                    <p className="text-muted" style={{ fontSize: 12, margin: '4px 0 8px', color: 'var(--danger-text)' }}>
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
                      <input className="field" type="time" lang="uz-UZ" value={form.event_time}
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
              <button className="button" onClick={handleSave} disabled={saving || uploading}>
                {saving ? 'Saqlanmoqda...' : 'Saqlash'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
