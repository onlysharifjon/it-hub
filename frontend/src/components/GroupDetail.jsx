import Overlay from './ui/Overlay'
import { useEffect, useState } from 'react'
import { toast } from 'react-hot-toast'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faArrowLeft, faChalkboardTeacher, faCalendarDay,
  faPlus, faTrash, faCheck, faXmark, faMinus,
  faUserGraduate, faChartBar, faTag, faBookOpen, faPaperPlane,
  faVideo, faArrowRightToBracket, faArrowRightFromBracket, faAward,
} from '@fortawesome/free-solid-svg-icons'
import { fetchAttendance, saveAttendance, deleteAttendanceDate, getGroup, fetchNextLesson, fetchHomeworks, createHomework, fetchGroupCameraAttendance, tashkentToday, generateGroupCertificates, fetchGroupCertificates } from '../api'
import useConfirm from './ui/useConfirm'
import GroupCertificates from './GroupCertificates'
import { STAGE_COLORS, STAGE_LABELS } from '../constants/domain'
import { tashkentNow } from '../utils/datetime'

const MONTHS = ['Yanvar','Fevral','Mart','Aprel','May','Iyun','Iyul','Avgust','Sentyabr','Oktyabr','Noyabr','Dekabr']
const NOW = tashkentNow()


// JS getDay(): Yak=0, Du=1, Se=2, Chor=3, Pay=4, Ju=5, Shan=6
const DOW_SHORT = ['Ya', 'Du', 'Se', 'Ch', 'Pa', 'Ju', 'Sh']
const dowLabel = (d) => DOW_SHORT[new Date(`${d}T00:00:00`).getDay()]

const DAY_WORDS_JS = {
  du: 1, dush: 1, dushanba: 1,
  se: 2, sesh: 2, seshanba: 2,
  chor: 3, chorshanba: 3,
  pay: 4, payshanba: 4,
  ju: 5, jum: 5, juma: 5,
  shan: 6, shanba: 6,
  yak: 0, yakshanba: 0,
}

// Guruh jadvalidan dars bo'ladigan hafta kunlarini (getDay qiymatlari) aniqlaydi.
// null => jadval noma'lum (cheklovsiz).
function scheduledWeekdays(schedule) {
  if (!schedule) return null
  const s = schedule.toLowerCase()
  if (s.includes('toq'))  return new Set([1, 3, 5])   // Du, Chor, Ju
  if (s.includes('juft')) return new Set([2, 4, 6])   // Se, Pay, Shan
  const set = new Set()
  for (const t of s.split(/[\s,\-/]+/)) {
    if (DAY_WORDS_JS[t] != null) set.add(DAY_WORDS_JS[t])
  }
  return set.size ? set : null
}

export default function GroupDetail({ group: groupProp, onBack, currentUser }) {
  const [confirmUI, ask] = useConfirm()
  const isAdmin   = currentUser?.role === 'admin' || currentUser?.role === 'support_teacher'
  const isHunter  = currentUser?.role === 'hunter' || currentUser?.role === 'admin'
  // Yo'qlama qilish (sana qo'shish/o'chirish): admin, metodist, hunter, teacher
  const canEditAttendance = isAdmin || currentUser?.role === 'hunter' || currentUser?.role === 'teacher'
  // Sertifikat bo'limi: hunter, admin va shu guruhning o'qituvchisi
  const canCertificates = isHunter || currentUser?.role === 'teacher'
  const [month, setMonth] = useState(NOW.getMonth() + 1)
  const [year, setYear] = useState(NOW.getFullYear())
  const [group, setGroup] = useState(groupProp)
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [newDate, setNewDate] = useState('')
  const [addingDate, setAddingDate] = useState(false)
  const [saving, setSaving] = useState(false)

  // Metodika bo'yicha navbatdagi dars + uy vazifasi
  const [nextLesson, setNextLesson] = useState(null)
  const [homeworks, setHomeworks] = useState([])
  const [hwModal, setHwModal] = useState(false)
  const [hwText, setHwText] = useState('')
  const [hwSending, setHwSending] = useState(false)

  // Kamera davomati tab
  const [mainTab, setMainTab] = useState('attendance')   // 'attendance' | 'camera'
  const [camData, setCamData] = useState([])
  const [camDays, setCamDays] = useState(7)
  const [camLoading, setCamLoading] = useState(false)

  // Sertifikat generatsiyasi (hunter/admin/o'qituvchi)
  const [certModal, setCertModal] = useState(false)
  const [certCourse, setCertCourse] = useState('')
  const [certDate, setCertDate] = useState('')
  const [certSigner, setCertSigner] = useState("Sharifjon Mo'minov")
  const [certGenerating, setCertGenerating] = useState(false)
  const [certRecords, setCertRecords] = useState(null)     // ko'rsatilayotgan sertifikatlar | null
  const [existingCerts, setExistingCerts] = useState(null) // avval tayyorlangan sertifikatlar (bo'lsa) — tugma matni/xatti-harakati uchun

  useEffect(() => { load() }, [month, year, groupProp.id])
  useEffect(() => {
    if (!canEditAttendance) return
    fetchNextLesson(groupProp.id).then(setNextLesson).catch(() => {})
    fetchHomeworks(groupProp.id).then(setHomeworks).catch(() => {})
  }, [groupProp.id])
  useEffect(() => {
    if (!canCertificates) return
    fetchGroupCertificates(groupProp.id).then(setExistingCerts)
      .catch(e => console.error('Sertifikatlar holatini tekshirib bo\'lmadi:', e.message))
  }, [groupProp.id])

  async function loadCam(days = camDays) {
    setCamLoading(true)
    try {
      const rows = await fetchGroupCameraAttendance(groupProp.id, days)
      setCamData(rows)
    } catch { toast.error("Kamera ma'lumotlari yuklanmadi") }
    finally { setCamLoading(false) }
  }

  useEffect(() => {
    if (mainTab === 'camera') loadCam(camDays)
  }, [mainTab, groupProp.id])

  function openHwModal() {
    setHwText(nextLesson?.homework || '')
    setHwModal(true)
  }

  function openCertModal() {
    // Sertifikatlar avval tayyorlangan bo'lsa — to'g'ridan-to'g'ri ko'rsatiladi,
    // qayta sozlash/generatsiya modalisiz.
    if (existingCerts && existingCerts.length > 0) {
      setCertRecords(existingCerts)
      return
    }
    setCertCourse(STAGE_LABELS[group.stage] || '')
    setCertDate(tashkentNow().toLocaleDateString('uz-UZ'))
    setCertSigner("Sharifjon Mo'minov")
    setCertModal(true)
  }

  async function handleGenerateCerts() {
    setCertGenerating(true)
    try {
      const records = await generateGroupCertificates(group.id, {
        course_label: certCourse,
        issue_date: certDate,
        signer_name: certSigner,
        signer_title: 'CEO',
      })
      setCertRecords(records)
      setExistingCerts(records)
      setCertModal(false)
    } catch (e) {
      toast.error(e.message || "Sertifikatlarni generatsiya qilib bo'lmadi")
    } finally {
      setCertGenerating(false)
    }
  }

  async function handleSendHomework() {
    if (!hwText.trim()) return toast.error("Uy vazifasi matnini kiriting")
    setHwSending(true)
    try {
      const hw = await createHomework(group.id, {
        text: hwText,
        lesson_id: nextLesson?.lesson_id || null,
        lesson_number: nextLesson?.lesson_number || null,
        lesson_title: nextLesson?.lesson_title || null,
      })
      if (hw.telegram_sent) toast.success("Saqlandi va Telegramga yuborildi ✓")
      else toast(`Saqlandi. Telegram: ${hw.telegram_error || 'yuborilmadi'}`, { icon: '⚠️' })
      setHwModal(false)
      fetchHomeworks(group.id).then(setHomeworks).catch(() => {})
    } catch (e) { toast.error(e.message) }
    finally { setHwSending(false) }
  }

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
    if (schedSet && !schedSet.has(new Date(`${target}T00:00:00`).getDay())) {
      return toast.error("Bu kun guruh jadvali bo'yicha dars kuni emas")
    }

    setSaving(true)
    try {
      const records = (data?.students || []).map(s => ({
        student_id: s.student_id,
        is_present: null,
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
      await saveAttendance(group.id, lessonDate, [{ student_id: studentId, is_present: newVal }])
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
    const ok = await ask({
      title: 'Dars kunini o\'chirish',
      message: `${d} sanasidagi barcha davomat yozuvlari o'chirilsinmi?`,
      detail: "Bu kun o'qituvchi maoshi va to'lov hisobiga ta'sir qiladi.",
      confirmLabel: "Ha, o'chirish",
    })
    if (!ok) return
    try {
      await deleteAttendanceDate(group.id, d)
      toast.success("O'chirildi")
      await load()
    } catch (e) { toast.error(e.message) }
  }

  const dates = data?.dates || []
  const students = data?.students || []
  const totalLessons = dates.length

  const TODAY_STR = tashkentToday()
  const attendanceDatesSet = new Set(dates)
  const schedSet = scheduledWeekdays(group.schedule)
  const isScheduledDay = (d) => !!schedSet && schedSet.has(new Date(`${d}T00:00:00`).getDay())
  const allDaysInMonth = (() => {
    const days = []
    const count = new Date(year, month, 0).getDate()
    for (let d = 1; d <= count; d++) {
      days.push(`${year}-${String(month).padStart(2,'0')}-${String(d).padStart(2,'0')}`)
    }
    return days
  })()

  // "Kurs progressi" endi TANLANGAN OYGA nisbatan hisoblanadi (kurs umumiy 24
  // darsiga emas): jadval bo'yicha shu oyda bo'lishi kerak bo'lgan darslar soniga
  // nisbatan, shu oyda haqiqatda o'tkazilgan (sana qo'shilgan) darslar soni.
  const monthScheduledTotal = schedSet ? allDaysInMonth.filter(isScheduledDay).length : totalLessons
  const monthCompleted = totalLessons
  const monthRemaining = Math.max(0, monthScheduledTotal - monthCompleted)
  const monthPct = monthScheduledTotal > 0 ? Math.round(monthCompleted / monthScheduledTotal * 100) : 0

  // monthly stats
  const avgAttendance = students.length && totalLessons
    ? Math.round(students.reduce((s, st) => s + st.present_count, 0) / (students.length * totalLessons) * 100)
    : 0

  return (
    <div className="page">
      {confirmUI}
      {/* Header */}
      <div className="page-header">
        <div className="detail-title">
          <button className="btn-sm" onClick={onBack} aria-label="Orqaga">
            <FontAwesomeIcon icon={faArrowLeft} /> Orqaga
          </button>
          <h1>
            <FontAwesomeIcon icon={faUserGraduate} className="page-icon" />
            {group.name}
          </h1>
          <span className={`status-badge ${group.is_active ? 'active' : 'inactive'}`}>
            {group.is_active ? 'Faol' : 'Yopiq'}
          </span>
        </div>
        {canCertificates && (
          <button className="button small" onClick={openCertModal}>
            <FontAwesomeIcon icon={faAward} />
            {existingCerts && existingCerts.length > 0 ? 'Sertifikatlarni ko\'rish' : 'Sertifikat tayyorlash'}
          </button>
        )}
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
                <FontAwesomeIcon icon={faCalendarDay} /> {group.schedule}{group.lesson_time ? ` — soat ${group.lesson_time}` : ''}
              </div>
            )}
          </div>

          {/* Stage progress card */}
          {group.total_lessons != null && (
            <div className="info-card">
              <div className="info-card-title" style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>Oylik progress — {MONTHS[month - 1]}</span>
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
                    width: `${monthPct}%`,
                    background: STAGE_COLORS[group.stage || 'foundation'].bar,
                  }}
                />
              </div>
              <div className="stat-row">
                <span>Bajarildi</span>
                <strong>{monthCompleted}/{monthScheduledTotal} dars ({monthPct}%)</strong>
              </div>
              <div className="stat-row">
                <span>Qoldi</span>
                <strong style={{ color: monthRemaining <= 1 ? 'var(--danger)' : 'var(--text)' }}>
                  {monthRemaining} dars
                  {monthRemaining <= 1 && monthScheduledTotal > 0 && ' ⚠'}
                </strong>
              </div>
            </div>
          )}

          {/* Bugungi dars — metodika bo'yicha */}
          {canEditAttendance && nextLesson && (
            <div className="info-card">
              <div className="info-card-title">
                <FontAwesomeIcon icon={faBookOpen} /> Bugungi dars (metodika)
              </div>
              <div className="stat-row">
                <span>Dars</span>
                <strong>#{nextLesson.lesson_number} / {nextLesson.total_lessons}</strong>
              </div>
              {nextLesson.lesson_title ? (
                <div style={{ fontSize: 13, fontWeight: 600, margin: '6px 0' }}>{nextLesson.lesson_title}</div>
              ) : (
                <div className="text-muted" style={{ fontSize: 12, margin: '6px 0' }}>
                  Metodikada bu dars kiritilmagan
                </div>
              )}
              {nextLesson.homework && (
                <div style={{ fontSize: 12, color: 'var(--text-muted)', whiteSpace: 'pre-wrap', maxHeight: 60, overflow: 'hidden' }}>
                  📝 {nextLesson.homework}
                </div>
              )}
              <button className="button small" style={{ width: '100%', marginTop: 10 }} onClick={openHwModal}>
                <FontAwesomeIcon icon={faPaperPlane} /> Uy vazifasi yuborish
              </button>
              {homeworks.length > 0 && (
                <div style={{ marginTop: 10 }}>
                  {homeworks.slice(0, 3).map(hw => (
                    <div key={hw.id} style={{ fontSize: 11, color: 'var(--text-muted)', display: 'flex', justifyContent: 'space-between', gap: 6, padding: '3px 0' }}>
                      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {new Date(hw.lesson_date + 'T00:00:00').toLocaleDateString('uz')}{hw.lesson_number ? ` · ${hw.lesson_number}-dars` : ''}
                      </span>
                      <span title={hw.telegram_error || ''}>{hw.telegram_sent ? '✅' : '⚠️'}</span>
                    </div>
                  ))}
                </div>
              )}
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
              <strong style={{ color: avgAttendance >= 80 ? 'var(--success)' : avgAttendance >= 60 ? 'var(--warning)' : 'var(--danger)' }}>
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
                      <span style={{ color: 'var(--success)' }}>{s.present_count}</span>
                      /
                      <span style={{ color: 'var(--danger)' }}>{s.absent_count}</span>
                      {totalLessons > 0 && <span className="text-muted"> ({pct}%)</span>}
                    </span>
                  </div>
                )
              })}
              {students.length === 0 && <div className="muted">O'quvchilar yo'q</div>}
            </div>
          </div>

          {/* Hunter: per-student tariff */}
          {isHunter && (group.members || []).length > 0 && (
            <div className="info-card" style={{ flex: 'none' }}>
              <div className="info-card-title">
                <FontAwesomeIcon icon={faTag} /> Tarif
              </div>
              {(group.members || []).map(m => {
                const base = m.tariff_price ? Number(m.tariff_price) : null
                return (
                  <div key={m.student_id} className="student-summary-row" style={{ flexDirection: 'column', alignItems: 'flex-start', gap: 2 }}>
                    <span className="student-summary-name">{m.student_name}</span>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                      {m.tariff_name
                        ? <><span>{m.tariff_name}: </span><strong>{base?.toLocaleString()} so'm</strong></>
                        : <span>Tarif yo'q</span>
                      }
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* ── Right Panel: Attendance Grid + Camera ── */}
        <div className="group-detail-main">

          {/* Tab switcher */}
          <div className="tab-bar" style={{ marginBottom: '1rem' }}>
            <button
              className={`tab-btn ${mainTab === 'attendance' ? 'active' : ''}`}
              onClick={() => setMainTab('attendance')}
            >
              <FontAwesomeIcon icon={faChartBar} /> Yo'qlama
            </button>
            <button
              className={`tab-btn ${mainTab === 'camera' ? 'active' : ''}`}
              onClick={() => setMainTab('camera')}
            >
              <FontAwesomeIcon icon={faVideo} /> Kamera davomati
            </button>
          </div>

          {/* ── Camera attendance tab ── */}
          {mainTab === 'camera' && (
            <div>
              {/* Days filter */}
              <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
                {[1, 7, 14, 30].map(d => (
                  <button
                    key={d}
                    className={`button ${camDays === d ? 'primary' : 'secondary'} small`}
                    onClick={() => { setCamDays(d); loadCam(d) }}
                  >
                    {d === 1 ? 'Bugun' : `${d} kun`}
                  </button>
                ))}
              </div>

              {camLoading ? (
                <div className="muted center py-4">Yuklanmoqda...</div>
              ) : camData.length === 0 ? (
                <div className="muted center py-4">Bu davrda kamera yozuvi topilmadi</div>
              ) : (
                <div className="table-wrap">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>O'quvchi</th>
                        <th>Sana</th>
                        <th>Kun</th>
                        <th>Soat</th>
                        <th>Holat</th>
                      </tr>
                    </thead>
                    <tbody>
                      {camData.map(r => {
                        const dt   = new Date(r.detected_at)
                        const date = dt.toLocaleDateString('uz-UZ', { year: 'numeric', month: '2-digit', day: '2-digit' })
                        const day  = dt.toLocaleDateString('uz-UZ', { weekday: 'short' })
                        const time = dt.toLocaleTimeString('uz-UZ', { hour: '2-digit', minute: '2-digit' })
                        const isKeldi = r.event_type === 'keldi'
                        return (
                          <tr key={r.id}>
                            <td><strong>{r.student_name}</strong></td>
                            <td>{date}</td>
                            <td style={{ color: 'var(--muted)', fontSize: 12 }}>{day}</td>
                            <td><strong>{time}</strong></td>
                            <td>
                              <span style={{
                                display: 'inline-flex', alignItems: 'center', gap: 5,
                                padding: '2px 10px', borderRadius: 999, fontSize: 12, fontWeight: 600,
                                background: isKeldi ? 'var(--success-bg)' : 'var(--danger-bg)',
                                color:      isKeldi ? 'var(--success-text)' : 'var(--danger-text)',
                              }}>
                                <FontAwesomeIcon icon={isKeldi ? faArrowRightToBracket : faArrowRightFromBracket} />
                                {isKeldi ? 'Keldi' : 'Ketdi'}
                              </span>
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {/* ── Yo'qlama tab ── */}
          {mainTab === 'attendance' && <>
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
                <button
                  className="button small"
                  onClick={handleAddDate}
                  disabled={saving || !newDate || (schedSet && newDate && !schedSet.has(new Date(`${newDate}T00:00:00`).getDay()))}
                >
                  <FontAwesomeIcon icon={faCheck} /> Saqlash
                </button>
                <button className="button secondary small" onClick={() => { setAddingDate(false); setNewDate('') }}>
                  Bekor
                </button>
                {schedSet && newDate && !schedSet.has(new Date(`${newDate}T00:00:00`).getDay()) && (
                  <span className="muted" style={{ fontSize: '0.8rem' }}>Bu kun dars kuni emas</span>
                )}
              </>
            ) : (
              <button className="button small" onClick={() => setAddingDate(true)}>
                <FontAwesomeIcon icon={faPlus} /> Dars qo'shish
              </button>
            )}
          </div>

          <div className="att-legend">
            <span className="att-legend-item"><span className="att-mark att-legend-present"><FontAwesomeIcon icon={faCheck} /></span> Keldi</span>
            <span className="att-legend-item"><span className="att-mark att-legend-absent"><FontAwesomeIcon icon={faXmark} /></span> Kelmadi</span>
            <span className="att-legend-item"><span className="att-mark att-legend-empty"><FontAwesomeIcon icon={faMinus} /></span> Belgilanmagan</span>
            <span className="att-legend-item"><span className="att-legend-swatch" /> Dars kuni (jadval bo'yicha)</span>
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
                      const scheduled = isScheduledDay(d)
                      const fillable = hasLesson || scheduled
                      return (
                        <th
                          key={d}
                          className={`att-date-col${isToday ? ' att-col-today' : ''}${scheduled ? ' att-col-scheduled' : ''}${!fillable ? ' att-col-nolesson' : ''}`}
                        >
                          <div className="att-date-header">
                            <span className="att-dow">{dowLabel(d)}</span>
                            <span className="att-daynum">{Number(d.slice(8, 10))}</span>
                            {hasLesson && (
                              <button
                                className="att-delete-date"
                                onClick={(e) => { e.stopPropagation(); handleDeleteDate(d) }}
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
                        const scheduled = isScheduledDay(d)
                        const fillable = hasLesson || scheduled
                        const val = s.dates[d]
                        if (!fillable) {
                          return (
                            <td
                              key={d}
                              className={`att-cell-nolesson${isToday ? ' att-cell-today' : ''}`}
                            />
                          )
                        }
                        return (
                          <td
                            key={d}
                            className={`att-cell${isToday ? ' att-cell-today' : ''}${scheduled ? ' att-col-scheduled' : ''} ${val === true ? 'att-present' : val === false ? 'att-absent' : 'att-empty'}`}
                            onClick={() => handleToggle(s.student_id, d, val)}
                            title="Bosing: Keldi → Kelmadi → Belgilanmagan"
                          >
                            <span className="att-mark">
                              {val === true && <FontAwesomeIcon icon={faCheck} />}
                              {val === false && <FontAwesomeIcon icon={faXmark} />}
                              {(val === null || val === undefined) && <FontAwesomeIcon icon={faMinus} />}
                            </span>
                          </td>
                        )
                      })}
                      <td className="att-total-col">
                        <span className="att-total-pill">
                          <span style={{ color: 'var(--success)', fontWeight: 700 }}>{s.present_count}</span>
                          <span className="text-muted">/{totalLessons}</span>
                        </span>
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
          </>}
        </div>
      </div>

      {/* Uy vazifasi modal */}
      {hwModal && (
        <Overlay className="modal-overlay" onClick={() => setHwModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3><FontAwesomeIcon icon={faPaperPlane} /> Uy vazifasi — {group.name}</h3>
              <button className="modal-close" onClick={() => setHwModal(false)}>✕</button>
            </div>
            <div className="modal-body">
              {nextLesson && (
                <div style={{ marginBottom: 12, padding: '8px 12px', background: 'var(--bg-secondary, var(--surface-2))', borderRadius: 8, fontSize: 13 }}>
                  <div><strong>#{nextLesson.lesson_number}-dars</strong> (metodika bo'yicha)</div>
                  {nextLesson.lesson_title && <div>{nextLesson.lesson_title}</div>}
                </div>
              )}
              <label>Uy vazifasi matni *</label>
              <textarea
                className="field"
                rows={6}
                value={hwText}
                onChange={e => setHwText(e.target.value)}
                placeholder="Uy vazifasini yozing..."
                style={{ resize: 'vertical', minHeight: 100 }}
              />
              <div className="text-muted" style={{ fontSize: 12, marginTop: 6 }}>
                {group.telegram_chat_id
                  ? <>Saqlanadi va guruh Telegram chatiga yuboriladi ✓</>
                  : <>⚠️ Guruhga Telegram chat ID biriktirilmagan — faqat bazaga saqlanadi. Guruhni tahrirlashda chat ID kiriting.</>}
              </div>
            </div>
            <div className="modal-footer">
              <button className="button secondary" onClick={() => setHwModal(false)}>Bekor</button>
              <button className="button" onClick={handleSendHomework} disabled={hwSending}>
                <FontAwesomeIcon icon={faPaperPlane} /> {hwSending ? 'Yuborilmoqda...' : 'Saqlash va yuborish'}
              </button>
            </div>
          </div>
        </Overlay>
      )}

      {/* Sertifikat sozlamalari modal */}
      {certModal && (
        <Overlay className="modal-overlay" onClick={() => setCertModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3><FontAwesomeIcon icon={faAward} /> Sertifikat — {group.name}</h3>
              <button className="modal-close" onClick={() => setCertModal(false)}>✕</button>
            </div>
            <div className="modal-body">
              <div className="text-muted" style={{ fontSize: 13, marginBottom: 12 }}>
                Guruhdagi barcha {(group.members || []).length} o'quvchi uchun sertifikat tayyorlanadi.
                Har bir sertifikatda ism, sana, imzo va raqamni alohida ham tahrirlab, "Saqlash" bilan yozib qo'yish mumkin.
              </div>
              <label>Kurs nomi</label>
              <input className="field" value={certCourse} onChange={e => setCertCourse(e.target.value)} placeholder="Masalan: Frontend" maxLength={40} />
              <label style={{ marginTop: 10, display: 'block' }}>Berilgan sana</label>
              <input className="field" value={certDate} onChange={e => setCertDate(e.target.value)} placeholder="03.09.2026" maxLength={20} />
              <label style={{ marginTop: 10, display: 'block' }}>Imzo (CEO)</label>
              <input className="field" value={certSigner} onChange={e => setCertSigner(e.target.value)} placeholder="F.I.O." maxLength={60} />
            </div>
            <div className="modal-footer">
              <button className="button secondary" onClick={() => setCertModal(false)}>Bekor</button>
              <button className="button" disabled={certGenerating} onClick={handleGenerateCerts}>
                <FontAwesomeIcon icon={faAward} /> {certGenerating ? 'Generatsiya qilinmoqda...' : 'Generatsiya qilish'}
              </button>
            </div>
          </div>
        </Overlay>
      )}

      {certRecords && (
        <GroupCertificates
          group={group}
          records={certRecords}
          onClose={() => setCertRecords(null)}
        />
      )}
    </div>
  )
}
