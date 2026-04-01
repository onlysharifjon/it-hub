import { useEffect, useState } from 'react'
import { toast } from 'react-hot-toast'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faChalkboardTeacher, faChevronDown, faChevronRight,
  faUsers, faCheck,
} from '@fortawesome/free-solid-svg-icons'
import { fetchTeacherSalaries } from '../api'

const MONTHS = ['Yanvar','Fevral','Mart','Aprel','May','Iyun','Iyul','Avgust','Sentyabr','Oktyabr','Noyabr','Dekabr']
const NOW = new Date()
const fmt = n => Number(n || 0).toLocaleString()

const STAGE_COLORS = {
  foundation: { bg: '#eff6ff', color: '#1d4ed8' },
  frontend:   { bg: '#f0fdf4', color: '#15803d' },
  backend:    { bg: '#faf5ff', color: '#7e22ce' },
}

export default function TeacherSalaries() {
  const [month, setMonth] = useState(NOW.getMonth() + 1)
  const [year,  setYear]  = useState(NOW.getFullYear())
  const [data,  setData]  = useState(null)
  const [loading, setLoading] = useState(false)
  const [expanded, setExpanded] = useState({})       // teacher_id → bool
  const [expandedGroup, setExpandedGroup] = useState({}) // group_id → bool

  useEffect(() => { load() }, [month, year])

  async function load() {
    setLoading(true)
    try { setData(await fetchTeacherSalaries(month, year)) }
    catch { toast.error("Yuklab bo'lmadi") }
    finally { setLoading(false) }
  }

  function toggleTeacher(id) {
    setExpanded(p => ({ ...p, [id]: !p[id] }))
  }
  function toggleGroup(id) {
    setExpandedGroup(p => ({ ...p, [id]: !p[id] }))
  }

  const teachers = data?.teachers || []

  return (
    <div className="page">
      <div className="page-header">
        <h1>
          <FontAwesomeIcon icon={faChalkboardTeacher} className="page-icon" />
          O'qituvchi maoshlari
        </h1>
      </div>

      {/* Month selector */}
      <div className="toolbar">
        <select className="field-sm" value={month} onChange={e => setMonth(Number(e.target.value))}>
          {MONTHS.map((m, i) => <option key={i} value={i + 1}>{m}</option>)}
        </select>
        <select className="field-sm" value={year} onChange={e => setYear(Number(e.target.value))}>
          {[2024, 2025, 2026, 2027].map(y => <option key={y} value={y}>{y}</option>)}
        </select>
        <span className="text-muted" style={{ fontSize: 12 }}>
          Formula: maosh/talaba ÷ 12 × kelgan darslar
        </span>
      </div>

      {loading ? (
        <div className="muted center py-8">Yuklanmoqda...</div>
      ) : data ? (
        <>
          {/* Total KPI */}
          <div className="finance-kpi-row" style={{ marginBottom: 24 }}>
            <div className="finance-kpi" style={{ borderTop: '3px solid #3b82f6' }}>
              <div className="finance-kpi-label">Jami o'qituvchi maoshi</div>
              <div className="finance-kpi-value">{fmt(data.total_teacher_salary)}</div>
              <div className="finance-kpi-sub">so'm · {MONTHS[month - 1]} {year}</div>
            </div>
            <div className="finance-kpi" style={{ borderTop: '3px solid #22c55e' }}>
              <div className="finance-kpi-label">O'qituvchilar soni</div>
              <div className="finance-kpi-value">{teachers.length}</div>
              <div className="finance-kpi-sub">faol guruhlar bo'yicha</div>
            </div>
          </div>

          {/* Per-teacher list */}
          <div className="finance-groups">
            {teachers.map(t => (
              <div key={t.teacher_id} className="finance-group-card">

                {/* Teacher header */}
                <div
                  className="finance-group-header"
                  onClick={() => toggleTeacher(t.teacher_id)}
                  style={{ cursor: 'pointer' }}
                >
                  <div className="finance-group-name">
                    <FontAwesomeIcon
                      icon={expanded[t.teacher_id] ? faChevronDown : faChevronRight}
                      style={{ fontSize: 11, marginRight: 8, color: '#737373' }}
                    />
                    <strong>{t.teacher_name}</strong>
                    <span className="text-muted" style={{ fontSize: 12, marginLeft: 8 }}>
                      {t.groups.length} guruh
                    </span>
                  </div>
                  <div className="finance-group-stats">
                    <span style={{ fontWeight: 700, color: '#2563eb', fontSize: 15 }}>
                      {fmt(t.total_salary)} so'm
                    </span>
                  </div>
                </div>

                {/* Groups breakdown */}
                {expanded[t.teacher_id] && (
                  <div className="finance-unpaid-list">
                    {t.groups.map(g => (
                      <div key={g.group_id} style={{ marginBottom: 12 }}>

                        {/* Group row */}
                        <div
                          style={{
                            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                            padding: '8px 12px', background: 'var(--surface-2)', borderRadius: 8,
                            cursor: 'pointer',
                          }}
                          onClick={() => toggleGroup(g.group_id)}
                        >
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <FontAwesomeIcon
                              icon={expandedGroup[g.group_id] ? faChevronDown : faChevronRight}
                              style={{ fontSize: 10, color: '#737373' }}
                            />
                            <span style={{ fontWeight: 500 }}>{g.group_name}</span>
                            <span
                              style={{
                                fontSize: 10, fontWeight: 600, padding: '2px 6px', borderRadius: 12,
                                background: STAGE_COLORS[g.stage]?.bg || '#f3f4f6',
                                color: STAGE_COLORS[g.stage]?.color || '#374151',
                              }}
                            >
                              {g.stage}
                            </span>
                          </div>
                          <div style={{ display: 'flex', gap: 16, fontSize: 12, color: '#4b5563', alignItems: 'center' }}>
                            <span>
                              <FontAwesomeIcon icon={faUsers} style={{ marginRight: 4 }} />
                              {g.students.length} o'quvchi
                            </span>
                            <span>Jami kelgan: <strong>{g.total_attended}</strong></span>
                            <span style={{ fontSize: 11, color: '#6b7280' }}>
                              {fmt(g.teacher_pay_per_student)}/talaba/oy
                            </span>
                            <span style={{ fontWeight: 700, color: '#2563eb' }}>
                              {fmt(g.group_salary)} so'm
                            </span>
                          </div>
                        </div>

                        {/* Student details */}
                        {expandedGroup[g.group_id] && (
                          <table className="data-table" style={{ fontSize: 12.5, marginTop: 4 }}>
                            <thead>
                              <tr>
                                <th>O'quvchi</th>
                                <th style={{ textAlign: 'center' }}>Kelgan darslar</th>
                                <th style={{ textAlign: 'right' }}>Maosh ulushi</th>
                              </tr>
                            </thead>
                            <tbody>
                              {g.students.map(s => (
                                <tr key={s.student_id}>
                                  <td style={{ fontWeight: 500 }}>{s.student_name}</td>
                                  <td style={{ textAlign: 'center' }}>
                                    <span style={{ fontWeight: 600, color: s.attended > 0 ? '#2563eb' : '#9ca3af' }}>
                                      {s.attended}
                                    </span>
                                    <span className="text-muted" style={{ fontSize: 11 }}>/12</span>
                                  </td>
                                  <td style={{ textAlign: 'right', fontWeight: 600 }}>
                                    {s.attended > 0
                                      ? <>{fmt(s.salary_share)} so'm</>
                                      : <span className="text-muted">—</span>
                                    }
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                            <tfoot>
                              <tr>
                                <td style={{ fontWeight: 700 }}>Jami</td>
                                <td style={{ textAlign: 'center', fontWeight: 700 }}>{g.total_attended}</td>
                                <td style={{ textAlign: 'right', fontWeight: 700, color: '#2563eb' }}>
                                  {fmt(g.group_salary)} so'm
                                </td>
                              </tr>
                            </tfoot>
                          </table>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}

            {teachers.length === 0 && (
              <div className="muted center py-8">
                <div style={{ fontSize: 36, marginBottom: 8 }}>📋</div>
                <div>Bu oyda maosh hisoblash uchun davomat ma'lumoti yo'q</div>
                <div className="text-muted" style={{ fontSize: 12, marginTop: 4 }}>
                  Guruhlarda "O'qituvchi haqi" va davomat belgilang
                </div>
              </div>
            )}
          </div>
        </>
      ) : null}
    </div>
  )
}
