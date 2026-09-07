import { useEffect, useState } from 'react'
import { toast } from 'react-hot-toast'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faChalkboardTeacher, faChevronDown, faChevronRight,
  faUsers, faCheck,
} from '@fortawesome/free-solid-svg-icons'
import { fetchTeacherSalaries } from '../api'
import { Metric, MetricStrip } from './ui/Metric'
import { TableSkeleton } from './ui/States'
import { STAGE_COLORS } from '../constants/domain'
import { tashkentNow } from '../utils/datetime'

const MONTHS = ['Yanvar','Fevral','Mart','Aprel','May','Iyun','Iyul','Avgust','Sentyabr','Oktyabr','Noyabr','Dekabr']
const NOW = tashkentNow()
const YEARS = Array.from({ length: 5 }, (_, i) => NOW.getFullYear() - 2 + i)
const fmt = n => Number(n || 0).toLocaleString()


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
        <div className="page-header-text">
          <h1><FontAwesomeIcon icon={faChalkboardTeacher} className="page-icon" /> O'qituvchi maoshlari</h1>
          <p className="page-subtitle">
            Formula: 50 000 so'm / oydagi darslar soni × talaba kelgan darslar soni
          </p>
        </div>
        <div className="header-actions">
          <select className="field-sm" value={month} onChange={e => setMonth(Number(e.target.value))} aria-label="Oy">
            {MONTHS.map((m, i) => <option key={i} value={i + 1}>{m}</option>)}
          </select>
          <select className="field-sm" value={year} onChange={e => setYear(Number(e.target.value))} aria-label="Yil">
            {YEARS.map(y => <option key={y} value={y}>{y}</option>)}
          </select>
        </div>
      </div>

      {loading ? (
        <TableSkeleton />
      ) : data ? (
        <>
          <MetricStrip columns={3}>
            <Metric label="Jami o'qituvchi maoshi" value={fmt(data.total_teacher_salary)} unit="so'm"
              sub={`${MONTHS[month - 1]} ${year}`} />
            <Metric label="O'qituvchilar" value={teachers.length} sub="faol guruhlar bo'yicha" />
            <Metric label="O'rtacha maosh"
              value={teachers.length ? fmt(Math.round(Number(data.total_teacher_salary) / teachers.length)) : '—'}
              unit="so'm" sub="bitta o'qituvchiga" />
          </MetricStrip>

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
                      style={{ fontSize: 11, marginRight: 8, color: 'var(--muted)' }}
                    />
                    <strong>{t.teacher_name}</strong>
                    <span className="text-muted" style={{ fontSize: 12, marginLeft: 8 }}>
                      {t.groups.length} guruh
                    </span>
                  </div>
                  <div className="finance-group-stats">
                    <span style={{ fontWeight: 700, color: 'var(--primary)', fontSize: 15 }}>
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
                              style={{ fontSize: 10, color: 'var(--muted)' }}
                            />
                            <span style={{ fontWeight: 500 }}>{g.group_name}</span>
                            <span
                              style={{
                                fontSize: 10, fontWeight: 600, padding: '2px 6px', borderRadius: 12,
                                background: STAGE_COLORS[g.stage]?.bg || 'var(--surface-2)',
                                color: STAGE_COLORS[g.stage]?.color || 'var(--text-2)',
                              }}
                            >
                              {g.stage}
                            </span>
                          </div>
                          <div style={{ display: 'flex', gap: 16, fontSize: 12, color: 'var(--text-2)', alignItems: 'center' }}>
                            <span>
                              <FontAwesomeIcon icon={faUsers} style={{ marginRight: 4 }} />
                              {g.students.length} o'quvchi
                            </span>
                            <span>Jami kelgan: <strong>{g.total_attended}</strong></span>
                            <span style={{ fontSize: 11, color: 'var(--muted)' }}>
                              {fmt(g.per_lesson)}/dars/talaba
                            </span>
                            <span style={{ fontWeight: 700, color: 'var(--primary)' }}>
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
                                    <span style={{ fontWeight: 600, color: s.attended > 0 ? 'var(--primary)' : 'var(--muted)' }}>
                                      {s.attended}
                                    </span>
                                    <span className="text-muted" style={{ fontSize: 11 }}>/{g.total_lessons_held || '–'}</span>
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
                                <td style={{ textAlign: 'right', fontWeight: 700, color: 'var(--primary)' }}>
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
