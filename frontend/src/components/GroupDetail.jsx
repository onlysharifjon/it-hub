import { useEffect, useState } from 'react'
import { toast } from 'react-hot-toast'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faArrowLeft, faChalkboardTeacher, faCalendarDay,
  faPlus, faTrash, faCheck, faXmark, faMinus,
  faUserGraduate, faChartBar, faPercent,
} from '@fortawesome/free-solid-svg-icons'
import { fetchAttendance, saveAttendance, deleteAttendanceDate, getGroup, fetchDiscounts, applyStudentDiscount } from '../api'

const MONTHS = ['Yanvar','Fevral','Mart','Aprel','May','Iyun','Iyul','Avgust','Sentyabr','Oktyabr','Noyabr','Dekabr']
const NOW = new Date()

const STAGE_COLORS = {
  foundation: { bg: '#eff6ff', color: '#1d4ed8', bar: '#3b82f6' },
  frontend:   { bg: '#f0fdf4', color: '#15803d', bar: '#22c55e' },
  backend:    { bg: '#faf5ff', color: '#7e22ce', bar: '#a855f7' },
}
const STAGE_LABELS = { foundation: 'Foundation', frontend: 'Frontend', backend: 'Backend' }

export default function GroupDetail({ group: groupProp, onBack, currentUser }) {
  const isAdmin   = currentUser?.role === 'admin' || currentUser?.role === 'metodist'
  const isHunter  = currentUser?.role === 'hunter' || currentUser?.role === 'admin'
  const [month, setMonth] = useState(NOW.getMonth() + 1)
  const [year, setYear] = useState(NOW.getFullYear())
  const [group, setGroup] = useState(groupProp)
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [newDate, setNewDate] = useState('')
  const [addingDate, setAddingDate] = useState(false)
  const [saving, setSaving] = useState(false)
  const [discounts, setDiscounts] = useState([])
  const [discountModal, setDiscountModal] = useState(null)  // { member }
  const [selectedDiscount, setSelectedDiscount] = useState('')
  const [applyingSave, setApplyingSave] = useState(false)

  useEffect(() => { load() }, [month, year, groupProp.id])
  useEffect(() => {
    if (isHunter) fetchDiscounts().then(setDiscounts).catch(() => {})
  }, [])

  async function load() {
    setLoading(true)
    try {
      const [att, grp] = await Promise.all([
        fetchAttendance(groupProp.id, month, year),
        getGroup(groupProp.id),
      ])
      setData(att)
      setGroup(grp)
    } catch { toast.error("Yuklab bo'lmadi") }
    finally { setLoading(false) }
  }

  async function handleAddDate(dateOverride) {
    const target = dateOverride || newDate
    if (!target) return
    const existing = data?.dates || []
    if (existing.includes(target)) return toast.error("Bu sana allaqachon mavjud")

    setSaving(true)
    try {
      const records = (data?.students || []).map(s => ({
        student_id: s.student_id,
        is_present: true,
      }))
      await saveAttendance(group.id, target, records)
      if (!dateOverride) { setNewDate(''); setAddingDate(false) }
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

  function openDiscountModal(member) {
    setSelectedDiscount(member.discount_id ? String(member.discount_id) : '')
    setDiscountModal(member)
  }

  async function handleApplyDiscount() {
    setApplyingSave(true)
    try {
      await applyStudentDiscount(
        group.id,
        discountModal.student_id,
        selectedDiscount ? parseInt(selectedDiscount) : null,
      )
      toast.success('Chegirma saqlandi')
      setDiscountModal(null)
      await load()
    } catch (e) { toast.error(e.message) }
    finally { setApplyingSave(false) }
  }

  function formatDate(d) {
    const [, m, day] = d.split('-')
    return `${day}/${m}`
  }

  const dates = data?.dates || []
  const students = data?.students || []
  const totalLessons = dates.length

  const TODAY_STR = NOW.toISOString().slice(0, 10)
  const attendanceDatesSet = new Set(dates)
  const allDaysInMonth = (() => {
    const days = []
    const count = new Date(year, month, 0).getDate()
    for (let d = 1; d <= count; d++) {
      days.push(`${year}-${String(month).padStart(2,'0')}-${String(d).padStart(2,'0')}`)
    }
    return days
  })()

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

          {/* Stage progress card */}
          {group.total_lessons != null && (
            <div className="info-card">
              <div className="info-card-title" style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>Kurs progressi</span>
                <span
                  style={{
                    fontSize: '11px', fontWeight: 600, padding: '2px 8px', borderRadius: 20,
                    background: STAGE_COLORS[group.stage || 'foundation'].bg,
                    color: STAGE_COLORS[group.stage || 'foundation'].color,
                  }}
                >
                  {STAGE_LABELS[group.stage || 'foundation']}
                </span>
              </div>
              <div className="group-progress-bar" style={{ margin: '8px 0 6px' }}>
                <div
                  className="group-progress-fill"
                  style={{
                    width: `${group.progress_pct || 0}%`,
                    background: STAGE_COLORS[group.stage || 'foundation'].bar,
                  }}
                />
              </div>
              <div className="stat-row">
                <span>Bajarildi</span>
                <strong>{group.completed_lessons || 0}/{group.total_lessons} dars ({group.progress_pct || 0}%)</strong>
              </div>
              <div className="stat-row">
                <span>Qoldi</span>
                <strong style={{ color: (group.remaining_lessons || 0) <= 5 ? '#ef4444' : '#0a0a0a' }}>
                  {group.remaining_lessons || group.total_lessons} dars
                  {(group.remaining_lessons || group.total_lessons) <= 5 && ' ⚠'}
                </strong>
              </div>
            </div>
          )}

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
          <div className="info-card" style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
            <div className="info-card-title">O'quvchilar xulosasi</div>
            <div className="student-summary-list" style={{ overflowY: 'auto', scrollbarWidth: 'none', msOverflowStyle: 'none' }}>
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

          {/* Hunter: per-student tariff & discount */}
          {isHunter && (group.members || []).length > 0 && (
            <div className="info-card" style={{ flex: 'none' }}>
              <div className="info-card-title">
                <FontAwesomeIcon icon={faPercent} /> Tarif / Chegirma
              </div>
              {(group.members || []).map(m => {
                const base = m.tariff_price ? Number(m.tariff_price) : null
                const eff  = m.effective_price != null ? Number(m.effective_price) : base
                return (
                  <div key={m.student_id} className="student-summary-row" style={{ flexDirection: 'column', alignItems: 'flex-start', gap: 2 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', width: '100%' }}>
                      <span className="student-summary-name">{m.student_name}</span>
                      <button
                        className="btn-icon"
                        style={{ fontSize: 11 }}
                        onClick={() => openDiscountModal(m)}
                        title="Chegirma belgilash"
                      >
                        <FontAwesomeIcon icon={faPercent} />
                      </button>
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                      {m.tariff_name
                        ? <>
                            <span>{m.tariff_name}: </span>
                            {m.discount_name
                              ? <>
                                  <s style={{ color: '#ef4444' }}>{base?.toLocaleString()} so'm</s>
                                  {' → '}
                                  <strong style={{ color: '#22c55e' }}>{eff?.toLocaleString()} so'm</strong>
                                  <span style={{ marginLeft: 4, color: 'var(--text-muted)' }}>({m.discount_name})</span>
                                </>
                              : <strong>{base?.toLocaleString()} so'm</strong>
                            }
                          </>
                        : <span>Tarif yo'q</span>
                      }
                    </div>
                  </div>
                )
              })}
            </div>
          )}
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
                    {allDaysInMonth.map(d => {
                      const isToday = d === TODAY_STR
                      const hasLesson = attendanceDatesSet.has(d)
                      return (
                        <th
                          key={d}
                          className={`att-date-col${isToday ? ' att-col-today' : ''}${!hasLesson ? ' att-col-nolesson' : ''}`}
                          onClick={!hasLesson && isAdmin ? () => handleAddDate(d) : undefined}
                          title={!hasLesson && isAdmin ? "Bosing: bu kunga dars qo'shish" : undefined}
                          style={!hasLesson && isAdmin ? { cursor: 'pointer' } : undefined}
                        >
                          <div className="att-date-header">
                            <span>{formatDate(d)}</span>
                            {hasLesson && (
                              <button
                                className="att-delete-date"
                                onClick={() => handleDeleteDate(d)}
                                title="Sanani o'chirish"
                              >
                                <FontAwesomeIcon icon={faTrash} />
                              </button>
                            )}
                          </div>
                        </th>
                      )
                    })}
                    <th className="att-total-col">Jami</th>
                  </tr>
                </thead>
                <tbody>
                  {students.map(s => (
                    <tr key={s.student_id}>
                      <td className="att-name-col">
                        <div className="att-student-name">{s.student_name}</div>
                        <div className="att-student-phone text-muted">{s.phone}</div>
                      </td>
                      {allDaysInMonth.map(d => {
                        const isToday = d === TODAY_STR
                        const hasLesson = attendanceDatesSet.has(d)
                        const val = s.dates[d]
                        if (!hasLesson) {
                          return (
                            <td
                              key={d}
                              className={`att-cell-nolesson${isToday ? ' att-cell-today' : ''}${isAdmin ? ' att-cell-nolesson-admin' : ''}`}
                              onClick={isAdmin ? () => handleAddDate(d) : undefined}
                              title={isAdmin ? "Bosing: bu kunga dars qo'shish" : undefined}
                            />
                          )
                        }
                        return (
                          <td
                            key={d}
                            className={`att-cell${isToday ? ' att-cell-today' : ''} ${val === true ? 'att-present' : val === false ? 'att-absent' : 'att-empty'}`}
                            onClick={() => handleToggle(s.student_id, d, val)}
                            title="Bosing: Keldi → Kelmadi → Belgilanmagan"
                          >
                            {val === true && <FontAwesomeIcon icon={faCheck} />}
                            {val === false && <FontAwesomeIcon icon={faXmark} />}
                            {(val === null || val === undefined) && <FontAwesomeIcon icon={faMinus} className="text-muted" />}
                          </td>
                        )
                      })}
                      <td className="att-total-col">
                        <span style={{ color: '#22c55e', fontWeight: 600 }}>{s.present_count}</span>
                        <span className="text-muted">/{totalLessons}</span>
                      </td>
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

      {/* Discount modal */}
      {discountModal && (
        <div className="modal-overlay" onClick={() => setDiscountModal(null)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3><FontAwesomeIcon icon={faPercent} /> {discountModal.student_name} — Chegirma</h3>
              <button className="modal-close" onClick={() => setDiscountModal(null)}>✕</button>
            </div>
            <div className="modal-body">
              {discountModal.tariff_name && (
                <div style={{ marginBottom: 12, padding: '8px 12px', background: 'var(--bg-secondary)', borderRadius: 8, fontSize: 13 }}>
                  Asosiy tarif: <strong>{discountModal.tariff_name}</strong> —{' '}
                  {Number(discountModal.tariff_price).toLocaleString()} so'm/oy
                </div>
              )}
              <label>Chegirma tanlang</label>
              <select
                className="field"
                value={selectedDiscount}
                onChange={e => setSelectedDiscount(e.target.value)}
              >
                <option value="">— Chegirmasiz —</option>
                {discounts.filter(d => d.is_active).map(d => (
                  <option key={d.id} value={d.id}>
                    {d.name} ({d.discount_type === 'percent' ? `${Number(d.value)}%` : `${Number(d.value).toLocaleString()} so'm`})
                  </option>
                ))}
              </select>
              {selectedDiscount && discountModal.tariff_price && (() => {
                const d = discounts.find(x => x.id === parseInt(selectedDiscount))
                if (!d) return null
                const base = Number(discountModal.tariff_price)
                const eff  = d.discount_type === 'percent'
                  ? Math.round(base * (1 - Number(d.value) / 100))
                  : Math.max(0, base - Number(d.value))
                return (
                  <div style={{ marginTop: 8, padding: '8px 12px', background: 'var(--bg-secondary)', borderRadius: 8, fontSize: 13 }}>
                    Chegirmadan keyin: <s style={{ color: '#ef4444' }}>{base.toLocaleString()} so'm</s>
                    {' → '}<strong style={{ color: '#22c55e' }}>{eff.toLocaleString()} so'm</strong>
                  </div>
                )
              })()}
            </div>
            <div className="modal-footer">
              <button className="button secondary" onClick={() => setDiscountModal(null)}>Bekor</button>
              <button className="button primary" onClick={handleApplyDiscount} disabled={applyingSave}>
                {applyingSave ? 'Saqlanmoqda...' : 'Saqlash'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
