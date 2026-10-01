import { useEffect, useState } from 'react'
import { toast } from 'react-hot-toast'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faInbox, faCheck, faLink, faCoins } from '@fortawesome/free-solid-svg-icons'
import Overlay from './ui/Overlay'
import { fetchHomeworkSubmissions, gradeHomeworkSubmission } from '../api'

const STATUS = {
  submitted: { label: 'Tekshirish kerak', cls: 'pending' },
  pending: { label: 'Topshirmagan', cls: '' },
  graded: { label: 'Baholangan', cls: 'active' },
}

// Bitta talaba qatori: javob + baho/izoh/coin formasi
function SubmissionRow({ homeworkId, row, onSaved }) {
  const [grade, setGrade] = useState(row.grade ?? '')
  const [comment, setComment] = useState(row.teacher_comment || '')
  const [coins, setCoins] = useState(row.coins || 0)
  const [saving, setSaving] = useState(false)
  const st = STATUS[row.status] || STATUS.pending

  async function save() {
    const g = Number(grade)
    if (grade === '' || !Number.isInteger(g) || g < 0 || g > 100) {
      toast.error('Baho 0 dan 100 gacha butun son bo\'lsin')
      return
    }
    setSaving(true)
    try {
      onSaved(await gradeHomeworkSubmission(homeworkId, row.student_id, {
        grade: g, comment: comment.trim() || null, coins: row.coins ? 0 : Number(coins) || 0,
      }))
      toast.success(`${row.full_name}: baholandi`)
    } catch (e) {
      toast.error(e.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="hw-sub-row">
      <div className="hw-sub-head">
        <strong>{row.full_name}</strong>
        <span className={`status-badge ${st.cls}`}>{st.label}</span>
        {!row.has_space_account && <span className="text-muted" style={{ fontSize: 11 }}>Space akkaunti yo'q</span>}
      </div>
      {row.answer
        ? <pre className="hw-sub-answer">{row.answer}</pre>
        : <div className="text-muted" style={{ fontSize: 12 }}>Space orqali javob yuborilmagan (qog'ozda topshirgan bo'lsa ham baholash mumkin)</div>}
      {row.link && (
        <a href={row.link} target="_blank" rel="noopener noreferrer" className="hw-sub-link">
          <FontAwesomeIcon icon={faLink} /> {row.link}
        </a>
      )}
      <div className="hw-sub-form">
        <label>Baho
          <input className="field" type="number" min={0} max={100} value={grade}
            onChange={e => setGrade(e.target.value)} placeholder="0–100" />
        </label>
        <label className="hw-sub-comment">Izoh
          <input className="field" value={comment} maxLength={1000}
            onChange={e => setComment(e.target.value)} placeholder="Masalan: Zo'r, lekin alt yetishmayapti" />
        </label>
        <label title={row.coins ? 'Coin berilgan' : 'Oylik budjetingizdan'}>
          <FontAwesomeIcon icon={faCoins} /> Coin
          <input className="field" type="number" min={0} max={20} value={coins} disabled={!!row.coins}
            onChange={e => setCoins(e.target.value)} />
        </label>
        <button className="button small" onClick={save} disabled={saving}>
          <FontAwesomeIcon icon={faCheck} /> {saving ? '...' : row.status === 'graded' ? 'Yangilash' : 'Baholash'}
        </button>
      </div>
    </div>
  )
}

export default function HomeworkSubmissions({ homework, onClose, onChanged }) {
  const [rows, setRows] = useState(null)

  useEffect(() => {
    fetchHomeworkSubmissions(homework.id).then(setRows).catch(e => {
      toast.error(e.message)
      setRows([])
    })
  }, [homework.id])

  function saved(updated) {
    setRows(rs => rs.map(r => (r.student_id === updated.student_id ? updated : r)))
    onChanged?.()
  }

  const waiting = (rows || []).filter(r => r.status === 'submitted').length
  return (
    <Overlay className="modal-overlay" onClick={onClose}>
      <div className="modal modal-lg" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h3>
            <FontAwesomeIcon icon={faInbox} /> Javoblar — {homework.lesson_title || new Date(homework.lesson_date + 'T00:00:00').toLocaleDateString('uz')}
          </h3>
          <button className="modal-close" onClick={onClose}>✕</button>
        </div>
        <div className="modal-body">
          <div className="text-muted" style={{ fontSize: 13, whiteSpace: 'pre-wrap', marginBottom: 12 }}>{homework.text}</div>
          {rows === null
            ? <div className="text-muted">Yuklanmoqda...</div>
            : <>
                <div style={{ fontSize: 13, marginBottom: 10 }}>
                  {waiting ? <strong>{waiting} ta javob tekshirilishi kerak</strong> : 'Yangi javob yo\'q'}
                </div>
                {rows.map(r => <SubmissionRow key={r.student_id} homeworkId={homework.id} row={r} onSaved={saved} />)}
              </>}
        </div>
      </div>
    </Overlay>
  )
}
