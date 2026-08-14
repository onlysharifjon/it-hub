import { useEffect, useRef, useState } from 'react'
import { toast } from 'react-hot-toast'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faBell, faRightToBracket, faRightFromBracket,
  faCamera, faMagnifyingGlass,
} from '@fortawesome/free-solid-svg-icons'
import { fetchStudents, fetchVisits, createVisit, uploadStudentPhoto, API_BASE, tashkentToday } from '../api'

const TODAY_STR = tashkentToday()

export default function Notifications() {
  const [students, setStudents] = useState([])
  const [visits, setVisits] = useState([])
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(false)
  const [sendingId, setSendingId] = useState(null)   // "studentId-kind"
  const [uploadingId, setUploadingId] = useState(null)
  const fileInputRef = useRef(null)
  const uploadTargetRef = useRef(null)

  useEffect(() => {
    loadStudents()
    loadVisits()
  }, [])

  async function loadStudents() {
    try {
      const r = await fetchStudents({ is_active: true, page_size: 100 })
      setStudents(r.items || [])
    } catch { toast.error("Talabalarni yuklab bo'lmadi") }
  }

  async function loadVisits() {
    setLoading(true)
    try { setVisits(await fetchVisits({ visit_date: TODAY_STR })) }
    catch { toast.error("Yuklab bo'lmadi") }
    finally { setLoading(false) }
  }

  async function handleVisit(student, kind) {
    setSendingId(`${student.id}-${kind}`)
    try {
      const v = await createVisit({ student_id: student.id, kind })
      if (v.telegram_sent) {
        toast.success(kind === 'arrived' ? "Keldi ✓ — Telegram xabar yuborildi" : "Ketdi ✓ — Telegram xabar yuborildi")
      } else {
        toast(`Saqlandi. Telegram: ${v.telegram_error || 'yuborilmadi'}`, { icon: '⚠️' })
      }
      loadVisits()
    } catch (e) { toast.error(e.message) }
    finally { setSendingId(null) }
  }

  function pickPhoto(student) {
    uploadTargetRef.current = student
    fileInputRef.current?.click()
  }

  async function handlePhotoFile(e) {
    const file = e.target.files[0]
    const student = uploadTargetRef.current
    e.target.value = ''
    if (!file || !student) return
    setUploadingId(student.id)
    try {
      await uploadStudentPhoto(student.id, file)
      toast.success('Rasm yuklandi — endi xabarlar rasm bilan ketadi')
      loadStudents()
    } catch (err) { toast.error(err.message) }
    finally { setUploadingId(null) }
  }

  const filtered = students.filter(s => {
    if (!search.trim()) return true
    const q = search.toLowerCase()
    return s.full_name.toLowerCase().includes(q) || (s.phone1 || '').includes(q)
  })

  const lastVisitByStudent = {}
  for (const v of visits) {
    if (!lastVisitByStudent[v.student_id]) lastVisitByStudent[v.student_id] = v
  }

  function photoUrl(photo) {
    return photo ? `${API_BASE}/uploads/${photo}` : null
  }

  function timeLabel(iso) {
    return new Date(iso).toLocaleTimeString('uz', { hour: '2-digit', minute: '2-digit' })
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1><FontAwesomeIcon icon={faBell} className="page-icon" /> Notifications</h1>
      </div>

      <input
        ref={fileInputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp,image/gif"
        style={{ display: 'none' }}
        onChange={handlePhotoFile}
      />

      <div className="toolbar">
        <FontAwesomeIcon icon={faMagnifyingGlass} className="text-muted" />
        <input
          className="field-sm"
          style={{ minWidth: 220 }}
          placeholder="Talaba ismi yoki telefon..."
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
        <span className="muted" style={{ marginLeft: 'auto', fontSize: 13 }}>
          Bugun: {visits.length} ta belgi
        </span>
      </div>

      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>Rasm</th>
              <th>Talaba</th>
              <th>Telegram</th>
              <th>Oxirgi holat (bugun)</th>
              <th>Amallar</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map(s => {
              const last = lastVisitByStudent[s.id]
              return (
                <tr key={s.id}>
                  <td>
                    <div style={{ position: 'relative', width: 42 }}>
                      {s.photo
                        ? <img src={photoUrl(s.photo)} alt="" style={{ width: 40, height: 40, borderRadius: '50%', objectFit: 'cover' }} />
                        : <div style={{ width: 40, height: 40, borderRadius: '50%', background: 'var(--bg-secondary, #e5e5e5)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700 }}>
                            {s.full_name[0]}
                          </div>}
                      <button
                        className="btn-icon"
                        title="Rasm yuklash"
                        style={{ position: 'absolute', right: -8, bottom: -6, fontSize: 10 }}
                        disabled={uploadingId === s.id}
                        onClick={() => pickPhoto(s)}
                      >
                        <FontAwesomeIcon icon={faCamera} />
                      </button>
                    </div>
                  </td>
                  <td>
                    <strong>{s.full_name}</strong>
                    <div className="text-muted" style={{ fontSize: 12 }}>{s.phone1}</div>
                  </td>
                  <td>
                    {s.telegram_user_id
                      ? <span className="badge" style={{ background: '#dbeafe', color: '#1d4ed8' }}>ID: {s.telegram_user_id}</span>
                      : <span className="text-muted" style={{ fontSize: 12 }}>Biriktirilmagan</span>}
                  </td>
                  <td>
                    {last ? (
                      <span className="badge" style={{
                        background: last.kind === 'arrived' ? '#dcfce7' : '#fef3c7',
                        color: last.kind === 'arrived' ? '#16a34a' : '#d97706',
                      }}>
                        {last.kind === 'arrived' ? 'Keldi' : 'Ketdi'} · {timeLabel(last.created_at)}
                        {last.telegram_sent ? ' ✅' : ' ⚠️'}
                      </span>
                    ) : <span className="text-muted">—</span>}
                  </td>
                  <td>
                    <div style={{ display: 'flex', gap: 6 }}>
                      <button
                        className="button primary small"
                        disabled={sendingId === `${s.id}-arrived`}
                        onClick={() => handleVisit(s, 'arrived')}
                      >
                        <FontAwesomeIcon icon={faRightToBracket} /> Keldi
                      </button>
                      <button
                        className="button secondary small"
                        disabled={sendingId === `${s.id}-left`}
                        onClick={() => handleVisit(s, 'left')}
                      >
                        <FontAwesomeIcon icon={faRightFromBracket} /> Ketdi
                      </button>
                    </div>
                  </td>
                </tr>
              )
            })}
            {filtered.length === 0 && (
              <tr><td colSpan={5} className="muted center py-4">Talaba topilmadi</td></tr>
            )}
          </tbody>
        </table>
      </div>

      <h3 style={{ marginTop: 24 }}>Bugungi tarix</h3>
      {loading ? (
        <div className="muted center py-4">Yuklanmoqda...</div>
      ) : (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Vaqt</th>
                <th>Talaba</th>
                <th>Holat</th>
                <th>Kim belgiladi</th>
                <th>Telegram</th>
              </tr>
            </thead>
            <tbody>
              {visits.map(v => (
                <tr key={v.id}>
                  <td>{timeLabel(v.created_at)}</td>
                  <td>{v.student_name}</td>
                  <td>
                    <span className="badge" style={{
                      background: v.kind === 'arrived' ? '#dcfce7' : '#fef3c7',
                      color: v.kind === 'arrived' ? '#16a34a' : '#d97706',
                    }}>
                      {v.kind === 'arrived' ? 'Keldi' : 'Ketdi'}
                    </span>
                  </td>
                  <td className="text-muted">{v.noted_by_name || '—'}</td>
                  <td>
                    {v.telegram_sent
                      ? <span style={{ color: '#16a34a' }}>Yuborildi ✅</span>
                      : <span className="text-muted" title={v.telegram_error || ''}>⚠️ {v.telegram_error || 'Yuborilmadi'}</span>}
                  </td>
                </tr>
              ))}
              {visits.length === 0 && (
                <tr><td colSpan={5} className="muted center py-4">Bugun hali belgi yo'q</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
