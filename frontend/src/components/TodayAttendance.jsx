import { useEffect, useState } from 'react'
import { toast } from 'react-hot-toast'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faCalendarCheck, faCheck, faXmark,
  faArrowLeft, faUsers, faChalkboardTeacher, faCalendarDay,
  faUmbrellaBeach, faPlus, faTrash,
} from '@fortawesome/free-solid-svg-icons'
import { fetchTodayGroups, fetchAttendance, saveAttendance, fetchHolidays, createHoliday, deleteHoliday } from '../api'

const TODAY_STR = new Date().toISOString().slice(0, 10)
const DAY_NAMES = ['Yakshanba', 'Dushanba', 'Seshanba', 'Chorshanba', 'Payshanba', 'Juma', 'Shanba']

function formatDateLabel(dateStr) {
  const d = new Date(dateStr + 'T00:00:00')
  return `${DAY_NAMES[d.getDay()]}, ${d.toLocaleDateString('uz-UZ', { day: 'numeric', month: 'long', year: 'numeric' })}`
}

export default function TodayAttendance({ currentUser }) {
  const isAdmin = currentUser?.role === 'admin' || currentUser?.role === 'metodist'
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
    if (!confirm("Dam olish kunini o'chirishni tasdiqlaysizmi?")) return
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

  // ── Attendance form ───────────────────────────────────────────────────────
  if (activeGroup) {
    const presentCount = Object.values(attendance).filter(v => v === true).length
    const absentCount = Object.values(attendance).filter(v => v === false).length

    return (
      <div className="page">
        <div className="page-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <button className="btn-sm" onClick={() => setActiveGroup(null)}>
              <FontAwesomeIcon icon={faArrowLeft} /> Orqaga
            </button>
            <h1 style={{ margin: 0 }}>
              <FontAwesomeIcon icon={faCalendarCheck} className="page-icon" />
              {activeGroup.name}
            </h1>
          </div>
          <div style={{ fontSize: 13, color: '#737373' }}>{formatDateLabel(selectedDate)}</div>
        </div>

        {attLoading ? (
          <div className="muted center py-8">Yuklanmoqda...</div>
        ) : (
          <>
            <div className="toolbar" style={{ marginBottom: '1rem', gap: 8 }}>
              <span className="text-muted" style={{ fontSize: 13 }}>Barchasi:</span>
              <button className="button secondary small" onClick={() => markAll(true)}>
                <FontAwesomeIcon icon={faCheck} style={{ color: '#22c55e' }} /> Keldi
              </button>
              <button className="button secondary small" onClick={() => markAll(false)}>
                <FontAwesomeIcon icon={faXmark} style={{ color: '#ef4444' }} /> Kelmadi
              </button>
              <div style={{ marginLeft: 'auto', display: 'flex', gap: 12, fontSize: 13 }}>
                <span style={{ color: '#22c55e', fontWeight: 600 }}>✓ {presentCount} keldi</span>
                <span style={{ color: '#ef4444', fontWeight: 600 }}>✗ {absentCount} kelmadi</span>
              </div>
            </div>

            <div className="today-att-list">
              {students.map(s => {
                const present = attendance[s.student_id]
                return (
                  <div
                    key={s.student_id}
                    className={`today-att-row ${present ? 'att-row-present' : 'att-row-absent'}`}
                    onClick={() => toggleStudent(s.student_id)}
                  >
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
                  </div>
                )
              })}
              {students.length === 0 && (
                <div className="muted center py-4">Guruhda o'quvchilar yo'q</div>
              )}
            </div>

            {students.length > 0 && (
              <div style={{ marginTop: 16, display: 'flex', justifyContent: 'flex-end' }}>
                <button className="button primary" onClick={handleSave} disabled={saving}>
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
    <div className="page">
      <div className="page-header">
        <h1>
          <FontAwesomeIcon icon={faCalendarCheck} className="page-icon" />
          {isAdmin ? 'Davomat' : 'Bugungi darslar'}
        </h1>
      </div>

      {/* Date picker — admin sees any date, teacher fixed to today */}
      <div className="toolbar" style={{ marginBottom: 16 }}>
        <FontAwesomeIcon icon={faCalendarDay} className="text-muted" />
        {isAdmin ? (
          <>
            <input
              type="date"
              className="field-sm"
              value={selectedDate}
              onChange={e => setSelectedDate(e.target.value)}
              style={{ width: 160 }}
            />
            <span className="text-muted" style={{ fontSize: 13 }}>{formatDateLabel(selectedDate)}</span>
            {selectedDate !== TODAY_STR && (
              <button className="button secondary small" onClick={() => setSelectedDate(TODAY_STR)}>
                Bugun
              </button>
            )}
          </>
        ) : (
          <span style={{ fontSize: 13, fontWeight: 500 }}>{formatDateLabel(selectedDate)}</span>
        )}
        {isSuperAdmin && (
          <button className="button secondary small" style={{ marginLeft: 'auto' }} onClick={() => setHolidayModal(true)}>
            <FontAwesomeIcon icon={faUmbrellaBeach} /> Dam olish kunlari
          </button>
        )}
      </div>

      {activeHoliday && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 10,
          padding: '12px 16px', marginBottom: 16, borderRadius: 10,
          background: '#fef3c7', color: '#92400e', border: '1px solid #fcd34d',
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
        <div className="today-groups-grid">
          {groups.map(g => (
            <div key={g.id} className={`today-group-card ${g.attendance_taken ? 'att-taken' : ''}`}>
              <div className="today-group-header">
                <div>
                  <div className="today-group-name">{g.name}</div>
                  <div className="today-group-meta">
                    <FontAwesomeIcon icon={faChalkboardTeacher} style={{ fontSize: 11 }} />
                    {' '}{g.teacher_name || '—'}
                  </div>
                </div>
                {g.attendance_taken ? (
                  <div className="today-att-done">
                    <FontAwesomeIcon icon={faCheck} /> Bajarildi
                  </div>
                ) : (
                  <div className="today-att-pending">Kutilmoqda</div>
                )}
              </div>
              <div className="today-group-info">
                <span><FontAwesomeIcon icon={faUsers} style={{ fontSize: 11 }} /> {g.student_count} o'quvchi</span>
                {g.schedule && <span>{g.schedule}</span>}
              </div>
              <button
                className={`button ${g.attendance_taken ? 'secondary' : 'primary'} small`}
                style={{ width: '100%', marginTop: 10 }}
                onClick={() => openGroupAttendance(g)}
              >
                <FontAwesomeIcon icon={faCalendarCheck} />
                {g.attendance_taken ? ' Ko\'rish / Tahrirlash' : ' Davomat olish'}
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Holiday manage modal (faqat superadmin) */}
      {holidayModal && (
        <div className="modal-overlay" onClick={() => setHolidayModal(false)}>
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
              <button className="button primary" style={{ marginTop: 10 }} onClick={handleHolidaySave} disabled={hSaving}>
                <FontAwesomeIcon icon={faPlus} /> {hSaving ? 'Saqlanmoqda...' : "Qo'shish"}
              </button>

              {holidays.length > 0 && (
                <div style={{ marginTop: 16 }}>
                  <label>Belgilangan kunlar ({selectedDate.slice(0, 4)})</label>
                  {holidays.map(h => (
                    <div key={h.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 10px', borderRadius: 8, background: 'var(--bg-secondary, #f5f5f5)', marginBottom: 6 }}>
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
        </div>
      )}
    </div>
  )
}
