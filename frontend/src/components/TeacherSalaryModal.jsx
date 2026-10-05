import { useEffect, useState } from 'react'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faChevronLeft, faChevronRight, faChevronDown, faChevronUp, faMoneyBillWave,
} from '@fortawesome/free-solid-svg-icons'
import { fetchTeacherDashboard, fetchMySalary, fetchSalaryBreakdown } from '../api'
import Modal from './ui/Modal'
import DataTable from './ui/DataTable'
import { EmptyState, CardSkeleton, ErrorState } from './ui/States'
import { tashkentNow } from '../utils/datetime'

const MONTHS = ['Yanvar','Fevral','Mart','Aprel','May','Iyun',
                 'Iyul','Avgust','Sentyabr','Oktyabr','Noyabr','Dekabr']

const STAGE_STYLE = {
  foundation: { bg: 'var(--primary-light)', color: 'var(--primary-text)', label: 'Foundation' },
  fullstack:  { bg: 'var(--accent-light)', color: 'var(--accent-text)', label: 'Fullstack'  },
  frontend:   { bg: 'var(--success-bg)', color: 'var(--success-text)', label: 'Frontend'   },
  backend:    { bg: 'var(--accent-light)', color: 'var(--accent-text)', label: 'Backend'    },
}

function fmt(n) {
  if (n == null || n === 0) return '0 so\'m'
  return Number(n).toLocaleString('uz-UZ') + ' so\'m'
}

/** O'qituvchining shaxsiy oylik maoshi — faqat profil menyusidan ochiladi. */
export default function TeacherSalaryModal({ open, onClose, currentUser }) {
  const now = tashkentNow()
  const [month, setMonth] = useState(now.getMonth() + 1)
  const [year,  setYear]  = useState(now.getFullYear())
  const [groups, setGroups] = useState([])
  const [salaryInfo, setSalaryInfo] = useState(null)
  const [salaryBreakdown, setSalaryBreakdown] = useState(null)
  const [showBreakdown, setShowBreakdown] = useState(false)
  const [expanded, setExpanded] = useState({})
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => { if (open) load() }, [open, month, year])

  async function load() {
    setLoading(true); setError(null)
    try {
      const [d, s, b] = await Promise.all([
        fetchTeacherDashboard(month, year),
        fetchMySalary(month, year).catch(() => null),
        currentUser?.id ? fetchSalaryBreakdown(currentUser.id, month, year).catch(() => null) : null,
      ])
      setGroups((d?.groups || []).slice().sort((a, b) => (a.name || '').localeCompare(b.name || '')))
      setSalaryInfo(s)
      setSalaryBreakdown(b)
    } catch (e) { setError(e.message) } finally {
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

  return (
    <Modal open={open} title="Oylik maoshim" onClose={onClose} size="xl">
      <div className="td-monthnav" style={{ marginBottom: 16 }}>
        <button className="btn-icon" onClick={prevMonth} aria-label="Oldingi oy"><FontAwesomeIcon icon={faChevronLeft} /></button>
        <span className="td-monthnav-label">{MONTHS[month - 1]} {year}</span>
        <button className="btn-icon" onClick={nextMonth} aria-label="Keyingi oy"><FontAwesomeIcon icon={faChevronRight} /></button>
      </div>

      {error && <ErrorState title="Maosh ma’lumotlarini yuklab bo‘lmadi" onRetry={load} />}
      {loading && <CardSkeleton count={2} height={96} />}

      {!loading && !error && (
        <>
          {salaryInfo && (
            <div className="td-salary">
              <div className="td-salary-main">
                <span className="td-salary-label">{MONTHS[month - 1]} {year} rasmiy oylik</span>
                <span className="td-salary-value">{fmt(salaryInfo.salary)}</span>
                <span className="td-salary-note">
                  {salaryInfo.is_internship
                    ? "stajirovka — shu oy uchun oylik 0"
                    : salaryInfo.auto
                      ? `5,000,000 + talaba ulushi: ${fmt(Number(salaryInfo.salary) - 5000000)} (avtomatik)`
                      : `qo'lda belgilangan (formula: ${fmt(salaryInfo.auto_salary)})`}
                </span>
                {salaryBreakdown && salaryBreakdown.items?.length > 0 && (
                  <button className="button link" onClick={() => setShowBreakdown(v => !v)}>
                    {showBreakdown ? 'Tafsilotni yopish' : 'Qanday hisoblandi?'}
                  </button>
                )}
              </div>
              <dl className="td-salary-facts">
                <div>
                  <dt>To'langan</dt>
                  <dd className="tone-success">{fmt(salaryInfo.paid)}</dd>
                </div>
                <div>
                  <dt>Qolgan</dt>
                  <dd className={Number(salaryInfo.remaining) > 0 ? 'tone-warning' : 'tone-success'}>
                    {fmt(salaryInfo.remaining)}
                  </dd>
                </div>
              </dl>
            </div>
          )}

          {showBreakdown && salaryBreakdown && (
            <div className="card">
              <p className="muted-sm" style={{ marginBottom: 12 }}>
                Formula: 50 000 so'm 12 ta darsga to'g'ri keladi (1 dars = 4 167 so'm),
                talaba qatnashgan darslar soniga ko'paytiriladi.
              </p>
              <DataTable
                columns={[
                  { key: 'group_name', header: 'Guruh', sortable: true },
                  { key: 'student_name', header: 'Talaba', sortable: true },
                  { key: 'lessons_held', header: 'Oydagi darslar', align: 'right', sortable: true },
                  { key: 'attended', header: 'Qatnashgan', align: 'right', sortable: true },
                  { key: 'per_lesson', header: '1 dars narxi', align: 'right',
                    render: it => <span className="text-muted">{fmt(it.per_lesson)}</span> },
                  { key: 'share', header: 'Ulush', align: 'right', sortable: true,
                    sortValue: it => Number(it.share),
                    render: it => <strong className="tone-success">{fmt(it.share)}</strong> },
                ]}
                rows={salaryBreakdown.items}
                rowKey={(it, i) => i}
                clientPageSize={20}
                empty={{ title: "Davomat yozuvi yo'q" }}
              />
            </div>
          )}

          <p className="muted-sm td-salary-hint">
            Guruhlar bo'yicha tafsilot — tarixiy/taxminiy ma'lumot, rasmiy oylikka kirmaydi.
          </p>

          {groups.length === 0 ? (
            <EmptyState icon={faMoneyBillWave} title="Guruhlar yo'q" />
          ) : (
            <div className="td-grouplist">
              {groups.map(g => {
                const st = STAGE_STYLE[g.stage] || STAGE_STYLE.foundation
                const isOpen = expanded[g.id]
                const students = g.student_salaries || []

                return (
                  <article key={g.id} className={`td-acc${isOpen ? ' is-open' : ''}`}>
                    <button className="td-acc-head" onClick={() => setExpanded(p => ({ ...p, [g.id]: !p[g.id] }))} aria-expanded={isOpen}>
                      <span className="ui-badge ui-badge-sm" style={{ background: st.bg, color: st.color }}>{st.label}</span>
                      {g.is_active === false && <span className="status-badge inactive">Yopiq</span>}
                      <span className="td-acc-name">{g.name}</span>
                      <span className="td-acc-figure">
                        <em>{g.month_lessons_held} dars · {g.student_count} talaba</em>
                        <b>{fmt(g.month_salary)}</b>
                      </span>
                      <FontAwesomeIcon icon={isOpen ? faChevronUp : faChevronDown} className="td-acc-chevron" />
                    </button>

                    {isOpen && (
                      <div className="td-acc-body">
                        <p className="td-formula">
                          Formula: 50 000 so'm / 12 dars × kelgan darslar soni
                          (1 dars = <strong>{fmt(g.per_lesson)}</strong>/talaba)
                        </p>
                        <div className="table-wrap">
                          <table className="data-table is-compact">
                            <thead>
                              <tr>
                                <th>Talaba</th>
                                <th style={{ textAlign: 'center' }}>Kelgan dars</th>
                                <th style={{ textAlign: 'right' }}>Hissa</th>
                              </tr>
                            </thead>
                            <tbody>
                              {students.length === 0 && (
                                <tr>
                                  <td colSpan={3} className="muted center py-4">Bu oy davomat ma'lumoti yo'q</td>
                                </tr>
                              )}
                              {students.map(s => (
                                <tr key={s.student_id}>
                                  <td>{s.student_name}</td>
                                  <td style={{ textAlign: 'center' }} className={s.attended > 0 ? 'tone-info' : 'text-muted'}>
                                    {s.attended}
                                  </td>
                                  <td style={{ textAlign: 'right' }} className={s.salary_share > 0 ? 'tone-success' : 'text-muted'}>
                                    {fmt(s.salary_share)}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                            <tfoot>
                              <tr className="td-acc-total">
                                <td><strong>Jami</strong></td>
                                <td style={{ textAlign: 'center' }} className="tone-info">{g.month_lessons_held} dars</td>
                                <td style={{ textAlign: 'right' }} className="tone-success">{fmt(g.month_salary)}</td>
                              </tr>
                            </tfoot>
                          </table>
                        </div>
                      </div>
                    )}
                  </article>
                )
              })}
            </div>
          )}
        </>
      )}
    </Modal>
  )
}
