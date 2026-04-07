import { useEffect, useState } from 'react'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faUsers, faWallet, faChalkboardTeacher,
  faArrowRight, faChevronLeft, faChevronRight,
  faCalendarDays, faChartLine, faMoneyBillWave,
  faChevronDown, faChevronUp,
} from '@fortawesome/free-solid-svg-icons'
import { fetchTeacherDashboard } from '../api'

const MONTHS = ['Yanvar','Fevral','Mart','Aprel','May','Iyun',
                 'Iyul','Avgust','Sentyabr','Oktyabr','Noyabr','Dekabr']

const STAGE_STYLE = {
  foundation: { bg: '#eff6ff', color: '#1d4ed8', bar: '#3b82f6', label: 'Foundation' },
  frontend:   { bg: '#f0fdf4', color: '#15803d', bar: '#22c55e', label: 'Frontend'   },
  backend:    { bg: '#faf5ff', color: '#7e22ce', bar: '#a855f7', label: 'Backend'    },
}

function fmt(n) {
  if (n == null || n === 0) return '0 so\'m'
  return Number(n).toLocaleString('uz-UZ') + ' so\'m'
}

export default function TeacherDashboard({ currentUser, onOpenGroup }) {
  const now = new Date()
  const [month, setMonth] = useState(now.getMonth() + 1)
  const [year,  setYear]  = useState(now.getFullYear())
  const [data,  setData]  = useState(null)
  const [loading, setLoading] = useState(false)
  const [tab, setTab] = useState('groups') // 'groups' | 'salary'
  const [expanded, setExpanded] = useState({})

  useEffect(() => { load() }, [month, year])

  async function load() {
    setLoading(true)
    try {
      const d = await fetchTeacherDashboard(month, year)
      setData(d)
    } finally {
      setLoading(false)
    }
  }

  function prevMonth() {
    if (month === 1) { setMonth(12); setYear(y => y - 1) }
    else setMonth(m => m - 1)
  }
  function nextMonth() {
    if (month === 12) { setMonth(1); setYear(y => y + 1) }
    else setMonth(m => m + 1)
  }

  function toggleExpand(id) {
    setExpanded(prev => ({ ...prev, [id]: !prev[id] }))
  }

  const groups = data?.groups || []

  return (
    <div style={{ maxWidth: 900, margin: '0 auto', padding: '24px 16px' }}>

      {/* Header */}
      <div style={{ marginBottom: 20 }}>
        <h2 style={{ margin: 0, fontSize: 22, fontWeight: 700, color: '#111827' }}>
          <FontAwesomeIcon icon={faChalkboardTeacher} style={{ marginRight: 10, color: '#6366f1' }} />
          Salom, {currentUser?.full_name || currentUser?.username}
        </h2>
        <p style={{ margin: '4px 0 0', color: '#6b7280', fontSize: 14 }}>
          O'qituvchi paneli
        </p>
      </div>

      {/* KPI cards */}
      {data && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: 12, marginBottom: 24 }}>
          <KpiCard icon={faChalkboardTeacher} label="Faol guruhlar"   value={data.total_groups}   unit=""        color="#6366f1" bg="#eef2ff" />
          <KpiCard icon={faUsers}             label="Jami talabalar"  value={data.total_students} unit=" ta"     color="#0891b2" bg="#ecfeff" />
          <KpiCard icon={faWallet}            label={`${MONTHS[month-1]} maoshi`} value={fmt(data.total_salary)} unit="" color="#16a34a" bg="#f0fdf4" isText />
        </div>
      )}

      {/* Month picker + Tabs */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12, marginBottom: 20 }}>

        {/* Month nav */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <button onClick={prevMonth} style={navBtn}><FontAwesomeIcon icon={faChevronLeft} /></button>
          <span style={{ fontWeight: 600, fontSize: 15, minWidth: 130, textAlign: 'center' }}>
            {MONTHS[month - 1]} {year}
          </span>
          <button onClick={nextMonth} style={navBtn}><FontAwesomeIcon icon={faChevronRight} /></button>
        </div>

        {/* Tabs */}
        <div style={{ display: 'flex', gap: 8 }}>
          <TabBtn active={tab === 'groups'} onClick={() => setTab('groups')} icon={faUsers}>
            Guruhlarim
          </TabBtn>
          <TabBtn active={tab === 'salary'} onClick={() => setTab('salary')} icon={faMoneyBillWave}>
            Maosh hisobi
          </TabBtn>
        </div>
      </div>

      {loading && <p style={{ color: '#9ca3af', textAlign: 'center', padding: 32 }}>Yuklanmoqda…</p>}

      {/* ── TAB: GURUHLAR ── */}
      {!loading && tab === 'groups' && (
        <>
          {groups.length === 0 && (
            <div style={{ textAlign: 'center', padding: '48px 0', color: '#9ca3af' }}>
              Sizga hech qanday guruh biriktirilmagan
            </div>
          )}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            {groups.map(g => {
              const st = STAGE_STYLE[g.stage] || STAGE_STYLE.foundation
              return (
                <div key={g.id} style={{
                  background: '#fff',
                  border: '1px solid #e5e7eb',
                  borderRadius: 14,
                  overflow: 'hidden',
                  boxShadow: '0 1px 4px rgba(0,0,0,0.05)',
                }}>
                  {/* Top strip */}
                  <div style={{ height: 4, background: st.bar }} />

                  <div style={{ padding: '16px 20px' }}>
                    {/* Row 1: badge + name + button */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
                      <span style={{
                        background: st.bg, color: st.color,
                        borderRadius: 7, padding: '4px 12px',
                        fontWeight: 700, fontSize: 12,
                      }}>{st.label}</span>

                      <span style={{ fontWeight: 700, fontSize: 16, color: '#111827', flex: 1 }}>
                        {g.name}
                      </span>

                      <button
                        onClick={() => onOpenGroup(g)}
                        style={{
                          background: '#6366f1', color: '#fff',
                          border: 'none', borderRadius: 8,
                          padding: '7px 16px', cursor: 'pointer',
                          fontWeight: 600, fontSize: 13,
                          display: 'flex', alignItems: 'center', gap: 6,
                        }}
                      >
                        Ochish <FontAwesomeIcon icon={faArrowRight} />
                      </button>
                    </div>

                    {/* Row 2: info chips */}
                    <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginTop: 12 }}>
                      <InfoChip icon={faUsers} text={`${g.student_count} talaba`} />
                      <InfoChip icon={faCalendarDays} text={g.schedule || 'Jadvalsiz'} />
                      <InfoChip icon={faChartLine} text={`Boshlangan: ${g.start_date || '—'}`} />
                      <InfoChip
                        icon={faMoneyBillWave}
                        text={`${MONTHS[month-1]}: ${fmt(g.month_salary)}`}
                        color="#16a34a"
                      />
                    </div>

                    {/* Progress bar */}
                    <div style={{ marginTop: 14 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: '#6b7280', marginBottom: 5 }}>
                        <span>Kurs progressi</span>
                        <span>{g.completed_lessons}/{g.total_lessons} dars · {g.progress_pct}%</span>
                      </div>
                      <div style={{ height: 8, background: '#f3f4f6', borderRadius: 99, overflow: 'hidden' }}>
                        <div style={{
                          height: '100%',
                          width: `${g.progress_pct}%`,
                          background: st.bar,
                          borderRadius: 99,
                          transition: 'width .4s',
                        }} />
                      </div>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </>
      )}

      {/* ── TAB: MAOSH ── */}
      {!loading && tab === 'salary' && (
        <>
          {/* Summary */}
          {data && (
            <div style={{
              background: '#f0fdf4',
              border: '1px solid #bbf7d0',
              borderRadius: 12,
              padding: '14px 20px',
              marginBottom: 20,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              gap: 12,
            }}>
              <div>
                <div style={{ fontSize: 13, color: '#15803d' }}>{MONTHS[month-1]} {year} umumiy maosh</div>
                <div style={{ fontSize: 24, fontWeight: 800, color: '#15803d' }}>{fmt(data.total_salary)}</div>
              </div>
              <div style={{ fontSize: 13, color: '#6b7280' }}>
                {groups.length} guruh · {data.total_students} talaba
              </div>
            </div>
          )}

          {groups.length === 0 && (
            <div style={{ textAlign: 'center', padding: '48px 0', color: '#9ca3af' }}>
              Guruhlar yo'q
            </div>
          )}

          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {groups.map(g => {
              const st = STAGE_STYLE[g.stage] || STAGE_STYLE.foundation
              const isOpen = expanded[g.id]
              const students = g.student_salaries || []

              return (
                <div key={g.id} style={{
                  background: '#fff',
                  border: '1px solid #e5e7eb',
                  borderRadius: 12,
                  overflow: 'hidden',
                }}>
                  {/* Header row — clickable */}
                  <div
                    onClick={() => toggleExpand(g.id)}
                    style={{
                      display: 'flex', alignItems: 'center',
                      gap: 12, padding: '14px 20px',
                      cursor: 'pointer',
                      background: isOpen ? '#fafafa' : '#fff',
                      borderBottom: isOpen ? '1px solid #e5e7eb' : 'none',
                    }}
                  >
                    <span style={{
                      background: st.bg, color: st.color,
                      borderRadius: 7, padding: '3px 10px',
                      fontWeight: 700, fontSize: 12, flexShrink: 0,
                    }}>{st.label}</span>

                    <span style={{ fontWeight: 700, fontSize: 15, color: '#111827', flex: 1 }}>
                      {g.name}
                    </span>

                    <div style={{ textAlign: 'right', marginRight: 8 }}>
                      <div style={{ fontSize: 11, color: '#9ca3af' }}>
                        {g.month_lessons_held} dars · {g.student_count} talaba
                      </div>
                      <div style={{ fontSize: 16, fontWeight: 800, color: '#16a34a' }}>
                        {fmt(g.month_salary)}
                      </div>
                    </div>

                    <FontAwesomeIcon
                      icon={isOpen ? faChevronUp : faChevronDown}
                      style={{ color: '#9ca3af', fontSize: 13 }}
                    />
                  </div>

                  {/* Expanded — talabalar bo'yicha */}
                  {isOpen && (
                    <div style={{ padding: '0 20px 16px' }}>
                      <div style={{ fontSize: 12, color: '#6b7280', margin: '12px 0 8px', fontWeight: 600 }}>
                        Talabalar bo'yicha ({MONTHS[month-1]} {year})
                      </div>

                      {/* Formula */}
                      <div style={{
                        background: '#f8fafc', borderRadius: 8,
                        padding: '8px 12px', marginBottom: 10,
                        fontSize: 12, color: '#64748b',
                      }}>
                        Formula: <strong>{fmt(g.teacher_pay_per_student)}</strong> × kelgan darslar soni (1 dars = {fmt(g.teacher_pay_per_student)}/talaba)
                      </div>

                      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                        <thead>
                          <tr style={{ background: '#f9fafb' }}>
                            <th style={th}>Talaba</th>
                            <th style={{ ...th, textAlign: 'center' }}>Kelgan dars</th>
                            <th style={{ ...th, textAlign: 'right' }}>Hissa</th>
                          </tr>
                        </thead>
                        <tbody>
                          {students.length === 0 && (
                            <tr>
                              <td colSpan={3} style={{ padding: '10px 8px', color: '#9ca3af', textAlign: 'center' }}>
                                Bu oy davomat ma'lumoti yo'q
                              </td>
                            </tr>
                          )}
                          {students.map(s => (
                            <tr key={s.student_id} style={{ borderBottom: '1px solid #f3f4f6' }}>
                              <td style={{ padding: '8px 8px', color: '#374151' }}>{s.student_name}</td>
                              <td style={{ padding: '8px 8px', textAlign: 'center', color: s.attended > 0 ? '#0891b2' : '#d1d5db', fontWeight: 600 }}>
                                {s.attended}
                              </td>
                              <td style={{ padding: '8px 8px', textAlign: 'right', fontWeight: 700, color: s.salary_share > 0 ? '#16a34a' : '#9ca3af' }}>
                                {fmt(s.salary_share)}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                        <tfoot>
                          <tr style={{ borderTop: '2px solid #e5e7eb', background: '#f0fdf4' }}>
                            <td style={{ padding: '8px 8px', fontWeight: 700, color: '#374151' }}>Jami</td>
                            <td style={{ padding: '8px 8px', textAlign: 'center', fontWeight: 700, color: '#0891b2' }}>
                              {g.month_lessons_held} dars
                            </td>
                            <td style={{ padding: '8px 8px', textAlign: 'right', fontWeight: 800, color: '#16a34a', fontSize: 15 }}>
                              {fmt(g.month_salary)}
                            </td>
                          </tr>
                        </tfoot>
                      </table>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </>
      )}
    </div>
  )
}

function KpiCard({ icon, label, value, unit = '', color, bg, isText }) {
  return (
    <div style={{ background: bg, borderRadius: 12, padding: '16px 18px', display: 'flex', alignItems: 'center', gap: 12 }}>
      <div style={{
        width: 40, height: 40, background: '#fff', borderRadius: 10,
        display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
      }}>
        <FontAwesomeIcon icon={icon} style={{ color, fontSize: 18 }} />
      </div>
      <div>
        <div style={{ fontSize: 12, color: '#6b7280' }}>{label}</div>
        <div style={{ fontSize: isText ? 14 : 22, fontWeight: 800, color: '#111827', marginTop: 2 }}>
          {isText ? value : `${value}${unit}`}
        </div>
      </div>
    </div>
  )
}

function InfoChip({ icon, text, color = '#6b7280' }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 13, color }}>
      <FontAwesomeIcon icon={icon} style={{ fontSize: 12 }} />
      {text}
    </div>
  )
}

function TabBtn({ active, onClick, icon, children }) {
  return (
    <button onClick={onClick} style={{
      display: 'flex', alignItems: 'center', gap: 6,
      padding: '8px 16px', borderRadius: 8, border: 'none',
      cursor: 'pointer', fontWeight: 600, fontSize: 13,
      background: active ? '#6366f1' : '#f3f4f6',
      color: active ? '#fff' : '#374151',
      transition: 'all .15s',
    }}>
      <FontAwesomeIcon icon={icon} />
      {children}
    </button>
  )
}

const navBtn = {
  background: '#f3f4f6', border: 'none', borderRadius: 8,
  width: 34, height: 34, cursor: 'pointer',
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  color: '#374151',
}

const th = {
  padding: '8px 8px', textAlign: 'left',
  fontSize: 12, fontWeight: 600, color: '#6b7280',
  borderBottom: '1px solid #e5e7eb',
}
