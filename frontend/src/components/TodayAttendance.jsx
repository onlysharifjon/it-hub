import { PageIntro, SummaryRow, Initials } from './ui/Workspace'
import { shiftDay } from '../utils/datetime'
import Overlay from './ui/Overlay'
import { useEffect, useState } from 'react'
import { toast } from 'react-hot-toast'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faCalendarCheck, faCheck, faXmark,
  faArrowLeft, faUsers, faChalkboardTeacher, faCalendarDay,
  faUmbrellaBeach, faPlus, faTrash, faClock, faChevronLeft, faChevronRight,
} from '@fortawesome/free-solid-svg-icons'
import { fetchTodayGroups, fetchAttendance, saveAttendance, fetchHolidays, createHoliday, deleteHoliday, tashkentToday } from '../api'
import useConfirm from './ui/useConfirm'

const TODAY_STR = tashkentToday()
const DAY_NAMES = ['Yakshanba', 'Dushanba', 'Seshanba', 'Chorshanba', 'Payshanba', 'Juma', 'Shanba']
const MONTH_NAMES = ['Yanvar', 'Fevral', 'Mart', 'Aprel', 'May', 'Iyun', 'Iyul', 'Avgust', 'Sentabr', 'Oktabr', 'Noyabr', 'Dekabr']

function formatDateLabel(dateStr) {
  const d = new Date(dateStr + 'T00:00:00')
  return `${DAY_NAMES[d.getDay()]}, ${d.getDate()} ${MONTH_NAMES[d.getMonth()].toLowerCase()} ${d.getFullYear()}`
}

export default function TodayAttendance({ currentUser }) {
  const [confirmUI, ask] = useConfirm()
  const isAdmin = currentUser?.role === 'admin' || currentUser?.role === 'support_teacher'
  const isSuperAdmin = currentUser?.role === 'admin'

  const [selectedDate, setSelectedDate] = useState(TODAY_STR)
  const [groups, setGroups] = useState([])
  const [loading, setLoading] = useState(false)

  // Attendance form state
  const [activeGroup, setActiveGroup] = useState(null)
  const [students, setStudents] = useState([])
  const [attendance, setAttendance] = useState({})
  const [saving, setSaving] = useState(false)
  const [attLoading, setAttLoading] = useState(false)

  // Holidays (dam olish kunlari)
  const [holidays, setHolidays] = useState([])
  const [holidayModal, setHolidayModal] = useState(false)
  const [hForm, setHForm] = useState({ name: '', start_date: TODAY_STR, end_date: TODAY_STR })
  const [hSaving, setHSaving] = useState(false)

  useEffect(() => { load(selectedDate) }, [selectedDate])
  useEffect(() => { loadHolidays() }, [selectedDate.slice(0, 4)])

  async function loadHolidays() {
    try { setHolidays(await fetchHolidays(parseInt(selectedDate.slice(0, 4)))) }
    catch { /* jim — banner shart emas */ }
  }

  const activeHoliday = holidays.find(h => selectedDate >= h.start_date && selectedDate <= h.end_date)

  async function handleHolidaySave() {
    if (!hForm.name.trim()) return toast.error("Nomini kiriting")
    if (!hForm.start_date || !hForm.end_date) return toast.error("Sanalarni kiriting")
    if (hForm.end_date < hForm.start_date) return toast.error("Tugash sanasi boshlanishdan oldin bo'lmasin")
    setHSaving(true)
    try {
      await createHoliday(hForm)
      toast.success("Dam olish kuni belgilandi")
      setHForm({ name: '', start_date: TODAY_STR, end_date: TODAY_STR })
      await loadHolidays()
    } catch (e) { toast.error(e.message) }
    finally { setHSaving(false) }
  }

  async function handleHolidayDelete(id) {
    const ok = await ask({
      title: 'Dam olish kunini o\'chirish',
      message: "Bu dam olish kuni o'chirilsinmi?",
      detail: "O'sha kun yana odatdagi dars kuni sifatida hisoblanadi.",
      confirmLabel: "Ha, o'chirish",
    })
    if (!ok) return
    try {
      await deleteHoliday(id)
      toast.success("O'chirildi")
      await loadHolidays()
    } catch (e) { toast.error(e.message) }
  }

  async function load(d = selectedDate) {
    setLoading(true)
    try { setGroups(await fetchTodayGroups(d)) }
    catch { toast.error("Yuklab bo'lmadi") }
    finally { setLoading(false) }
  }

  async function openGroupAttendance(g) {
    setActiveGroup({ ...g, date: selectedDate })
    setAttLoading(true)
    try {
      const d = new Date(selectedDate + 'T00:00:00')
      const data = await fetchAttendance(g.id, d.getMonth() + 1, d.getFullYear())
      const studentList = data.students || []
      setStudents(studentList)
      const initial = {}
      studentList.forEach(s => {
        const existing = s.dates?.[selectedDate]
        initial[s.student_id] = existing !== undefined ? existing : true
      })
      setAttendance(initial)
    } catch { toast.error("Yuklab bo'lmadi") }
    finally { setAttLoading(false) }
  }

  function toggleStudent(studentId) {
    setAttendance(prev => ({ ...prev, [studentId]: !prev[studentId] }))
  }

  function markAll(val) {
    const next = {}
    students.forEach(s => { next[s.student_id] = val })
    setAttendance(next)
  }

  async function handleSave() {
    if (!activeGroup) return
    setSaving(true)
    try {
      const records = students.map(s => ({
        student_id: s.student_id,
        is_present: attendance[s.student_id] ?? true,
      }))
      await saveAttendance(activeGroup.id, selectedDate, records)
      toast.success("Davomat saqlandi")
      setActiveGroup(null)
      load(selectedDate)
    } catch (e) { toast.error(e.message) }
    finally { setSaving(false) }
  }

  const weekDay = (new Date(selectedDate + 'T12:00:00').getDay() + 6) % 7
  const weekDates = Array.from({ length: 7 }, (_, i) => shiftDay(selectedDate, i - weekDay))
  const groupsDone = groups.filter(g => g.attendance_taken).length

  // ── Attendance form ───────────────────────────────────────────────────────
  if (activeGroup) {
    const presentCount = Object.values(attendance).filter(v => v === true).length
    const absentCount = Object.values(attendance).filter(v => v === false).length

    return (
      <div className="page attendance-studio attendance-roster-page">
        {confirmUI}
        <div className="page-header">
          <div className="detail-title">
            <button className="btn-sm" onClick={() => setActiveGroup(null)} aria-label="Orqaga">
              <FontAwesomeIcon icon={faArrowLeft} /> Orqaga
            </button>
            <h1>
              <FontAwesomeIcon icon={faCalendarCheck} className="page-icon" />
              {activeGroup.name}
            </h1>
          </div>
          <div className="muted-sm">{formatDateLabel(selectedDate)}</div>
        </div>

        {attLoading ? (
          <div className="muted center py-8">Yuklanmoqda...</div>
        ) : (
          <>
            <SummaryRow items={[{ label: 'Guruhdagi talabalar', value: students.length }, { label: 'Darsda', value: presentCount, tone: 'success' }, { label: 'Kelmagan', value: absentCount, tone: absentCount ? 'danger' : undefined }]} />
            <div className="toolbar" style={{ marginBottom: '1rem', gap: 8 }}>
              <span className="text-muted" style={{ fontSize: 13 }}>Barchasi:</span>
              <button className="button secondary small" onClick={() => markAll(true)}>
                <FontAwesomeIcon icon={faCheck} style={{ color: 'var(--success)' }} /> Keldi
              </button>
              <button className="button secondary small" onClick={() => markAll(false)}>
                <FontAwesomeIcon icon={faXmark} style={{ color: 'var(--danger)' }} /> Kelmadi
              </button>
              <div style={{ marginLeft: 'auto', display: 'flex', gap: 12, fontSize: 13 }}>
                <span style={{ color: 'var(--success)', fontWeight: 600 }}>✓ {presentCount} keldi</span>
                <span style={{ color: 'var(--danger)', fontWeight: 600 }}>✗ {absentCount} kelmadi</span>
              </div>
            </div>

            <div className="today-att-list">
              {students.map((s, index) => {
                const present = attendance[s.student_id]
                return (
                  <button type="button" aria-pressed={!!present}
                    key={s.student_id}
                    className={`today-att-row ${present ? 'att-row-present' : 'att-row-absent'}`}
                    onClick={() => toggleStudent(s.student_id)}
                  >
                    <span className="attendance-row-number">{String(index + 1).padStart(2, '0')}</span><Initials name={s.student_name} />
                    <div className="today-att-info">
                      <div className="today-att-name">{s.student_name}</div>
                      <div className="today-att-phone text-muted">{s.phone}</div>
                    </div>
                    <div className={`today-att-toggle ${present ? 'toggle-present' : 'toggle-absent'}`}>
                      {present
                        ? <><FontAwesomeIcon icon={faCheck} /> Keldi</>
                        : <><FontAwesomeIcon icon={faXmark} /> Kelmadi</>
                      }
                    </div>
                  </button>
                )
              })}
              {students.length === 0 && (
                <div className="muted center py-4">Guruhda o'quvchilar yo'q</div>
              )}
            </div>

            {students.length > 0 && (
              <div style={{ marginTop: 16, display: 'flex', justifyContent: 'flex-end' }}>
                <button className="button" onClick={handleSave} disabled={saving}>
                  <FontAwesomeIcon icon={faCalendarCheck} />
                  {saving ? ' Saqlanmoqda...' : ' Davomatni saqlash'}
                </button>
              </div>
            )}
          </>
        )}
      </div>
    )
  }

  // ── Groups list ───────────────────────────────────────────────────────────
  return (
    <div className="page attendance-studio">
      {confirmUI}
      <PageIntro title="Bugungi darslar" eyebrow="Dars jadvali va davomat" description="Darslarni rejalashtiring. Davomatni bir joyda belgilang." actions={<>
        {isAdmin && <input type="date" className="field-sm" aria-label="Dars sanasi" value={selectedDate} onChange={e => { if (e.target.value) setSelectedDate(e.target.value) }} />}
        {isSuperAdmin && <button className="button secondary" onClick={() => setHolidayModal(true)}><FontAwesomeIcon icon={faUmbrellaBeach} /> Dam olish kunlari</button>}
      </>} />
      <div className="schedule-week"><div className="schedule-week-title"><strong>{MONTH_NAMES[Number(selectedDate.slice(5, 7)) - 1] + ' ' + selectedDate.slice(0, 4)}</strong><div>{isAdmin && <><button aria-label="Oldingi hafta" onClick={() => setSelectedDate(shiftDay(selectedDate, -7))}><FontAwesomeIcon icon={faChevronLeft} /></button><button aria-label="Keyingi hafta" onClick={() => setSelectedDate(shiftDay(selectedDate, 7))}><FontAwesomeIcon icon={faChevronRight} /></button></>}{selectedDate !== TODAY_STR && isAdmin && <button onClick={() => setSelectedDate(TODAY_STR)}>Bugun</button>}</div></div><div className="schedule-days">{weekDates.map((date, i) => <button key={date} disabled={!isAdmin && date !== TODAY_STR} aria-pressed={date === selectedDate} className={(date === selectedDate ? 'is-selected' : '') + (date === TODAY_STR ? ' is-today' : '')} onClick={() => setSelectedDate(date)}><span>{['Dush', 'Sesh', 'Chor', 'Pay', 'Jum', 'Shan', 'Yak'][i]}</span><strong>{Number(date.slice(-2))}</strong><i /></button>)}</div></div>
      <div className="schedule-overview"><div><h2>{formatDateLabel(selectedDate)}</h2><p>{loading ? 'Jadval yuklanmoqda...' : groups.length + ' ta dars · ' + groups.reduce((n, g) => n + Number(g.student_count || 0), 0) + ' ta talaba'}</p></div><div className="schedule-completion"><span>{groupsDone}/{groups.length} davomat olindi</span><div><i style={{ width: (groups.length ? groupsDone / groups.length * 100 : 0) + '%' }} /></div></div></div>

      {activeHoliday && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 10,
          padding: '12px 16px', marginBottom: 16, borderRadius: 10,
          background: 'var(--warning-bg)', color: 'var(--warning-text)', border: '1px solid var(--warning)',
          fontWeight: 600, fontSize: 14,
        }}>
          <FontAwesomeIcon icon={faUmbrellaBeach} style={{ fontSize: 20 }} />
          <div>
            Dam olish kuni: {activeHoliday.name}
            <div style={{ fontWeight: 400, fontSize: 12, marginTop: 2 }}>
              {new Date(activeHoliday.start_date + 'T00:00:00').toLocaleDateString('uz')} — {new Date(activeHoliday.end_date + 'T00:00:00').toLocaleDateString('uz')}
            </div>
          </div>
        </div>
      )}

      {loading ? (
        <div className="muted center py-8">Yuklanmoqda...</div>
      ) : groups.length === 0 ? (
        <div className="muted center py-8">
          <div style={{ fontSize: 40, marginBottom: 12 }}>📅</div>
          <div>{isAdmin ? 'Bu kunda guruhlar topilmadi' : 'Bugun dars yo\'q'}</div>
        </div>
      ) : (
        <div className="schedule-list">
          {[...groups].sort((a,b) => (a.lesson_time || '99:99').localeCompare(b.lesson_time || '99:99')).map(g => <article key={g.id} className={'schedule-lesson' + (g.attendance_taken ? ' is-complete' : '')}>
            <div className="schedule-time"><strong>{g.lesson_time || '—'}</strong><span>{g.schedule || 'Dars vaqti'}</span></div>
            <div className="schedule-line"><i /></div>
            <div className="schedule-lesson-body"><div className="schedule-lesson-title"><span className="studio-eyebrow">{g.course_name || 'Guruh darsi'}</span><h3>{g.name}</h3><div><Initials name={g.teacher_name} /><span>{g.teacher_name || 'Ustoz biriktirilmagan'}</span></div></div><div className="schedule-lesson-size"><FontAwesomeIcon icon={faUsers} /><strong>{g.student_count}</strong><span>talaba</span></div><div className="schedule-lesson-action"><span className={'schedule-status' + (g.attendance_taken ? ' is-done' : '')}><i />{g.attendance_taken ? 'Davomat olindi' : 'Davomat kutilmoqda'}</span><button className={'button small ' + (g.attendance_taken ? 'secondary' : '')} onClick={() => openGroupAttendance(g)}>{g.attendance_taken ? 'Ko‘rish / Tahrirlash' : 'Davomat olish'}<span>→</span></button></div></div>
          </article>)}
        </div>
      )}

      {/* Holiday manage modal (faqat superadmin) */}
      {holidayModal && (
        <Overlay className="modal-overlay" onClick={() => setHolidayModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3><FontAwesomeIcon icon={faUmbrellaBeach} /> Dam olish kunlari</h3>
              <button className="modal-close" onClick={() => setHolidayModal(false)}>✕</button>
            </div>
            <div className="modal-body">
              <label>Nomi / sababi *</label>
              <input className="field" value={hForm.name} placeholder="Masalan: Navro'z bayrami"
                onChange={e => setHForm(p => ({ ...p, name: e.target.value }))} />
              <div className="row-2">
                <div>
                  <label>Boshlanish sanasi *</label>
                  <input className="field" type="date" value={hForm.start_date}
                    onChange={e => setHForm(p => ({ ...p, start_date: e.target.value, end_date: p.end_date < e.target.value ? e.target.value : p.end_date }))} />
                </div>
                <div>
                  <label>Tugash sanasi *</label>
                  <input className="field" type="date" value={hForm.end_date} min={hForm.start_date}
                    onChange={e => setHForm(p => ({ ...p, end_date: e.target.value }))} />
                </div>
              </div>
              <button className="button" style={{ marginTop: 10 }} onClick={handleHolidaySave} disabled={hSaving}>
                <FontAwesomeIcon icon={faPlus} /> {hSaving ? 'Saqlanmoqda...' : "Qo'shish"}
              </button>

              {holidays.length > 0 && (
                <div style={{ marginTop: 16 }}>
                  <label>Belgilangan kunlar ({selectedDate.slice(0, 4)})</label>
                  {holidays.map(h => (
                    <div key={h.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 10px', borderRadius: 8, background: 'var(--bg-secondary, var(--surface-2))', marginBottom: 6 }}>
                      <div>
                        <div style={{ fontWeight: 600, fontSize: 13 }}>{h.name}</div>
                        <div className="text-muted" style={{ fontSize: 12 }}>
                          {new Date(h.start_date + 'T00:00:00').toLocaleDateString('uz')} — {new Date(h.end_date + 'T00:00:00').toLocaleDateString('uz')}
                        </div>
                      </div>
                      <button className="btn-icon danger" onClick={() => handleHolidayDelete(h.id)}>
                        <FontAwesomeIcon icon={faTrash} />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </Overlay>
      )}
    </div>
  )
}
