import { useEffect, useState } from 'react'
import { toast } from 'react-hot-toast'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faArrowLeft, faChalkboardTeacher, faCalendarDay,
  faPlus, faTrash, faCheck, faXmark, faMinus,
  faUserGraduate, faChartBar,
} from '@fortawesome/free-solid-svg-icons'
import { fetchAttendance, saveAttendance, deleteAttendanceDate } from '../api'

const MONTHS = ['Yanvar','Fevral','Mart','Aprel','May','Iyun','Iyul','Avgust','Sentyabr','Oktyabr','Noyabr','Dekabr']
const NOW = new Date()

export default function GroupDetail({ group, onBack }) {
  const [month, setMonth] = useState(NOW.getMonth() + 1)
  const [year, setYear] = useState(NOW.getFullYear())
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [newDate, setNewDate] = useState('')
  const [addingDate, setAddingDate] = useState(false)
  const [saving, setSaving] = useState(false)

  useEffect(() => { load() }, [month, year, group.id])

  async function load() {
    setLoading(true)
    try {
      const res = await fetchAttendance(group.id, month, year)
      setData(res)
    } catch { toast.error("Yuklab bo'lmadi") }
    finally { setLoading(false) }
  }

  async function handleAddDate() {
    if (!newDate) return
    const existing = data?.dates || []
    if (existing.includes(newDate)) return toast.error("Bu sana allaqachon mavjud")

    setSaving(true)
    try {
      const records = (data?.students || []).map(s => ({
        student_id: s.student_id,
        is_present: true,
      }))
      await saveAttendance(group.id, newDate, records)
      setNewDate('')
      setAddingDate(false)
      toast.success("Dars sanasi qo'shildi")
      await load()
    } catch (e) { toast.error(e.message) }
    finally { setSaving(false) }
  }

  async function handleToggle(studentId, lessonDate, currentVal) {
    const newVal = currentVal === true ? false : currentVal === false ? null : true
    try {
      if (newVal === null) {
        // remove this single record by re-saving without it
        const allStudents = data.students
        const others = allStudents
          .filter(s => s.student_id !== studentId)
          .map(s => ({ student_id: s.student_id, is_present: s.dates[lessonDate] ?? true }))
        await saveAttendance(group.id, lessonDate, others)
      } else {
        await saveAttendance(group.id, lessonDate, [{ student_id: studentId, is_present: newVal }])
      }
      setData(prev => {
        if (!prev) return prev
        return {
          ...prev,
          students: prev.students.map(s => {
            if (s.student_id !== studentId) return s
            const newDates = { ...s.dates, [lessonDate]: newVal }
            if (newVal === null) delete newDates[lessonDate]
            const presentCount = Object.values(newDates).filter(v => v === true).length
            const absentCount = Object.values(newDates).filter(v => v === false).length
            return { ...s, dates: newDates, present_count: presentCount, absent_count: absentCount }
          })
        }
      })
    } catch (e) { toast.error(e.message) }
  }

  async function handleDeleteDate(d) {
    if (!confirm(`${d} sanasidagi barcha yozuvlarni o'chirishni tasdiqlaysizmi?`)) return
    try {
      await deleteAttendanceDate(group.id, d)
      toast.success("O'chirildi")
      await load()
    } catch (e) { toast.error(e.message) }
  }

  function formatDate(d) {
    const [, m, day] = d.split('-')
    return `${day}/${m}`
  }

  const dates = data?.dates || []
  const students = data?.students || []
  const totalLessons = dates.length

  // monthly stats
  const avgAttendance = students.length && totalLessons
    ? Math.round(students.reduce((s, st) => s + st.present_count, 0) / (students.length * totalLessons) * 100)
    : 0

  return (
    <div className="page">
      {/* Header */}
      <div className="page-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <button className="btn-sm" onClick={onBack}>
            <FontAwesomeIcon icon={faArrowLeft} /> Orqaga
          </button>
          <h1 style={{ margin: 0 }}>
            <FontAwesomeIcon icon={faUserGraduate} className="page-icon" />
            {group.name}
          </h1>
          <span className={`status-badge ${group.is_active ? 'active' : 'inactive'}`}>
            {group.is_active ? 'Faol' : 'Yopiq'}
          </span>
        </div>
      </div>

      <div className="group-detail-layout">
        {/* ── Left Panel: Info + Stats ── */}
        <div className="group-detail-sidebar">
          {/* Teacher card */}
          <div className="info-card">
            <div className="info-card-title">
              <FontAwesomeIcon icon={faChalkboardTeacher} /> Ustoz
            </div>
            <div className="info-card-value">
              {data?.teacher_name || group.teacher_name || '—'}
            </div>
            {group.schedule && (
              <div className="info-card-sub">
                <FontAwesomeIcon icon={faCalendarDay} /> {group.schedule}
              </div>
            )}
          </div>

          {/* This month stats */}
          <div className="info-card">
            <div className="info-card-title">
              <FontAwesomeIcon icon={faChartBar} /> {MONTHS[month - 1]} statistika
            </div>
            <div className="stat-row"><span>Darslar soni</span><strong>{totalLessons}</strong></div>
            <div className="stat-row"><span>O'quvchilar</span><strong>{students.length}</strong></div>
            <div className="stat-row">
              <span>O'rtacha davomat</span>
              <strong style={{ color: avgAttendance >= 80 ? '#22c55e' : avgAttendance >= 60 ? '#f59e0b' : '#ef4444' }}>
                {avgAttendance}%
              </strong>
            </div>
          </div>

          {/* Per-student summary */}
          <div className="info-card" style={{ flex: 1 }}>
            <div className="info-card-title">O'quvchilar xulosasi</div>
            <div className="student-summary-list">
              {students.map(s => {
                const pct = totalLessons ? Math.round(s.present_count / totalLessons * 100) : 0
                return (
                  <div key={s.student_id} className="student-summary-row">
                    <span className="student-summary-name">{s.student_name}</span>
                    <span className="student-summary-stats">
                      <span style={{ color: '#22c55e' }}>{s.present_count}</span>
                      /
                      <span style={{ color: '#ef4444' }}>{s.absent_count}</span>
                      {totalLessons > 0 && <span className="text-muted"> ({pct}%)</span>}
                    </span>
                  </div>
                )
              })}
              {students.length === 0 && <div className="muted">O'quvchilar yo'q</div>}
            </div>
          </div>
        </div>

        {/* ── Right Panel: Attendance Grid ── */}
        <div className="group-detail-main">
          {/* Month filter */}
          <div className="toolbar" style={{ marginBottom: '1rem' }}>
            <select className="field-sm" value={month} onChange={e => setMonth(Number(e.target.value))}>
              {MONTHS.map((m, i) => <option key={i} value={i + 1}>{m}</option>)}
            </select>
            <select className="field-sm" value={year} onChange={e => setYear(Number(e.target.value))}>
              {[2024, 2025, 2026, 2027].map(y => <option key={y} value={y}>{y}</option>)}
            </select>

            {addingDate ? (
              <>
                <input
                  className="field-sm"
                  type="date"
                  value={newDate}
                  onChange={e => setNewDate(e.target.value)}
                  style={{ width: 150 }}
                />
                <button className="button primary small" onClick={handleAddDate} disabled={saving || !newDate}>
                  <FontAwesomeIcon icon={faCheck} /> Saqlash
                </button>
                <button className="button secondary small" onClick={() => { setAddingDate(false); setNewDate('') }}>
                  Bekor
                </button>
              </>
            ) : (
              <button className="button primary small" onClick={() => setAddingDate(true)}>
                <FontAwesomeIcon icon={faPlus} /> Dars qo'shish
              </button>
            )}
          </div>

          {loading ? (
            <div className="muted center">Yuklanmoqda...</div>
          ) : (
            <div className="attendance-table-wrap">
              <table className="attendance-table">
                <thead>
                  <tr>
                    <th className="att-name-col">O'quvchi</th>
                    {dates.map(d => (
                      <th key={d} className="att-date-col">
                        <div className="att-date-header">
                          <span>{formatDate(d)}</span>
                          <button
                            className="att-delete-date"
                            onClick={() => handleDeleteDate(d)}
                            title="Sanani o'chirish"
                          >
                            <FontAwesomeIcon icon={faTrash} />
                          </button>
                        </div>
                      </th>
                    ))}
                    <th className="att-total-col">Jami</th>
                    {dates.length === 0 && <th className="text-muted" style={{ fontWeight: 400 }}>Dars qo'shilmagan</th>}
                  </tr>
                </thead>
                <tbody>
                  {students.map(s => (
                    <tr key={s.student_id}>
                      <td className="att-name-col">
                        <div className="att-student-name">{s.student_name}</div>
                        <div className="att-student-phone text-muted">{s.phone}</div>
                      </td>
                      {dates.map(d => {
                        const val = s.dates[d]
                        return (
                          <td
                            key={d}
                            className={`att-cell ${val === true ? 'att-present' : val === false ? 'att-absent' : 'att-empty'}`}
                            onClick={() => handleToggle(s.student_id, d, val)}
                            title="Bosing: Keldi → Kelmadi → Belgilanmagan"
                          >
                            {val === true && <FontAwesomeIcon icon={faCheck} />}
                            {val === false && <FontAwesomeIcon icon={faXmark} />}
                            {val === null || val === undefined ? <FontAwesomeIcon icon={faMinus} className="text-muted" /> : null}
                          </td>
                        )
                      })}
                      <td className="att-total-col">
                        <span style={{ color: '#22c55e', fontWeight: 600 }}>{s.present_count}</span>
                        <span className="text-muted">/{totalLessons}</span>
                      </td>
                      {dates.length === 0 && <td></td>}
                    </tr>
                  ))}
                  {students.length === 0 && (
                    <tr>
                      <td colSpan={dates.length + 2} className="muted center py-4">
                        Guruhda o'quvchilar yo'q
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
