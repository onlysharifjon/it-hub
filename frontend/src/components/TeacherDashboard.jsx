import { SummaryRow, ViewTabs, Initials, ProgressRing } from './ui/Workspace'
import { PageIntro } from './ui/Workspace'
import { useEffect, useState } from 'react'
import { toast } from 'react-hot-toast'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faUsers, faWallet, faChalkboardTeacher,
  faArrowRight, faChevronLeft, faChevronRight,
  faCalendarDays, faChartLine, faMoneyBillWave, faBookOpen, faClipboardCheck, faGraduationCap,
  faChevronDown, faChevronUp, faMagnifyingGlass, faXmark, faAward,
} from '@fortawesome/free-solid-svg-icons'
import {
  fetchTeacherDashboard, fetchMySalary, fetchSalaryBreakdown,
  fetchMyCertificateGroups, fetchGroupCertificates, generateGroupCertificates,
} from '../api'
import GroupCertificates from './GroupCertificates'
import { Metric, MetricStrip } from './ui/Metric'
import Meter from './ui/Meter'
import Modal from './ui/Modal'
import DataTable from './ui/DataTable'
import { Input } from './ui/Field'
import { EmptyState, CardSkeleton, ErrorState } from './ui/States'
import { tashkentNow } from '../utils/datetime'

const MONTHS = ['Yanvar','Fevral','Mart','Aprel','May','Iyun',
                 'Iyul','Avgust','Sentyabr','Oktyabr','Noyabr','Dekabr']

const STAGE_STYLE = {
  foundation: { bg: 'var(--primary-light)', color: 'var(--primary-text)', bar: 'var(--primary)', label: 'Foundation' },
  fullstack:  { bg: 'var(--accent-light)', color: 'var(--accent-text)', bar: 'var(--accent)', label: 'Fullstack'  },
  frontend:   { bg: 'var(--success-bg)', color: 'var(--success-text)', bar: 'var(--success)', label: 'Frontend'   },
  backend:    { bg: 'var(--accent-light)', color: 'var(--accent-text)', bar: 'var(--accent)', label: 'Backend'    },
}

function fmt(n) {
  if (n == null || n === 0) return '0 so\'m'
  return Number(n).toLocaleString('uz-UZ') + ' so\'m'
}

export default function TeacherDashboard({ currentUser, onOpenGroup, onNavigate }) {
  const now = tashkentNow()
  const [month, setMonth] = useState(now.getMonth() + 1)
  const [year,  setYear]  = useState(now.getFullYear())
  const [data,  setData]  = useState(null)
  const [error, setError] = useState(null)
  const [salaryInfo, setSalaryInfo] = useState(null)
  const [salaryBreakdown, setSalaryBreakdown] = useState(null)
  const [showBreakdown, setShowBreakdown] = useState(false)
  const [loading, setLoading] = useState(false)
  const [tab, setTab] = useState('groups') // 'groups' | 'salary' | 'certificates'
  const [expanded, setExpanded] = useState({})
  const [dayFilter, setDayFilter] = useState('all') // 'all' | 'Juft kunlar' | 'Toq kunlar'
  const [studentSearch, setStudentSearch] = useState('')

  // Sertifikatlar tab
  const [certGroups, setCertGroups] = useState(null)
  const [certGroupsLoading, setCertGroupsLoading] = useState(false)
  const [certTarget, setCertTarget] = useState(null)       // qaysi guruh uchun modal/generatsiya ochilgan
  const [certModal, setCertModal] = useState(false)
  const [certCourse, setCertCourse] = useState('')
  const [certDate, setCertDate] = useState('')
  const [certSigner, setCertSigner] = useState("Sharifjon Mo'minov")
  const [certGenerating, setCertGenerating] = useState(false)
  const [certRecords, setCertRecords] = useState(null)     // ko'rsatilayotgan sertifikatlar

  useEffect(() => { load() }, [month, year])
  useEffect(() => {
    if (tab === 'certificates' && certGroups === null) loadCertGroups()
  }, [tab])

  async function loadCertGroups() {
    setCertGroupsLoading(true)
    try {
      setCertGroups(await fetchMyCertificateGroups())
    } catch {
      toast.error("Guruhlar ro'yxatini yuklab bo'lmadi")
    } finally {
      setCertGroupsLoading(false)
    }
  }

  async function handleCertGroupClick(g) {
    setCertTarget(g)
    if (g.certificate_count > 0) {
      try {
        setCertRecords(await fetchGroupCertificates(g.id))
      } catch {
        toast.error("Sertifikatlarni yuklab bo'lmadi")
      }
      return
    }
    setCertCourse(STAGE_STYLE[g.stage]?.label || '')
    setCertDate(tashkentNow().toLocaleDateString('uz-UZ'))
    setCertSigner("Sharifjon Mo'minov")
    setCertModal(true)
  }

  async function handleGenerateCerts() {
    if (!certTarget) return
    setCertGenerating(true)
    try {
      const records = await generateGroupCertificates(certTarget.id, {
        course_label: certCourse,
        issue_date: certDate,
        signer_name: certSigner,
        signer_title: 'CEO',
      })
      setCertRecords(records)
      setCertModal(false)
      setCertGroups(prev => prev.map(g => (g.id === certTarget.id ? { ...g, certificate_count: records.length } : g)))
    } catch (e) {
      toast.error(e.message || "Sertifikatlarni generatsiya qilib bo'lmadi")
    } finally {
      setCertGenerating(false)
    }
  }

  async function load() {
    setLoading(true); setError(null)
    try {
      const [d, s, b] = await Promise.all([
        fetchTeacherDashboard(month, year),
        fetchMySalary(month, year).catch(() => null),
        currentUser?.id ? fetchSalaryBreakdown(currentUser.id, month, year).catch(() => null) : null,
      ])
      setData(d)
      setSalaryInfo(s)
      setSalaryBreakdown(b)
    } catch (e) { setError(e.message); setData(null) } finally {
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
  const filteredGroups = (dayFilter === 'all' ? groups : groups.filter(g => g.schedule === dayFilter))
    .slice()
    .sort((a, b) => dayFilter === 'all'
      ? (a.name || '').localeCompare(b.name || '')
      : (a.lesson_time || '99:99').localeCompare(b.lesson_time || '99:99'))

  const searchQuery = studentSearch.trim().toLowerCase()
  const studentMatches = searchQuery
    ? groups.flatMap(g =>
        (g.student_salaries || [])
          .filter(s => (s.student_name || '').toLowerCase().includes(searchQuery))
          .map(s => ({ student_id: s.student_id, student_name: s.student_name, group: g }))
      )
    : []

  return (
    <div className="page td-page teacher-studio">
      <header className="teacher-welcome">
        <div className="teacher-welcome-copy"><span className="teacher-kicker"><i /> O‘qituvchi kabineti</span><h1>Salom, {currentUser?.full_name || currentUser?.username}.</h1><p>Har bir dars — yangi imkoniyat.<br /> Guruhlaringiz va natijalaringiz shu yerda.</p>
          <button className="button" onClick={() => onNavigate?.('today_attendance')}><FontAwesomeIcon icon={faCalendarDays} /> Bugungi darslar <FontAwesomeIcon icon={faArrowRight} /></button>
        </div>
        <div className="teacher-welcome-side"><div className="teacher-date"><span>Hisobot davri</span><div className="td-monthnav"><button className="btn-icon" onClick={prevMonth} aria-label="Oldingi oy"><FontAwesomeIcon icon={faChevronLeft} /></button><span className="td-monthnav-label">{MONTHS[month - 1]} {year}</span><button className="btn-icon" onClick={nextMonth} aria-label="Keyingi oy"><FontAwesomeIcon icon={faChevronRight} /></button></div></div><div className="teacher-profile-stamp"><Initials name={currentUser?.full_name || currentUser?.username} /><div><strong>Bilim. Amaliyot. Natija.</strong><span>MINAR Academy · ustozlar maydoni</span></div></div></div>
      </header>
      <nav className="teacher-shortcuts" aria-label="O‘qituvchi tezkor amallari">
        {[{ page: 'today_attendance', icon: faClipboardCheck, title: 'Davomat', text: 'Bugungi darslar va qatnashuv' }, { page: 'academic', icon: faGraduationCap, title: 'Baholar va izohlar', text: 'Talabalar natijalarini kuzatish' }, { page: 'lessons', icon: faBookOpen, title: 'Dars rejalari', text: 'Qo‘llanma va uyga vazifalar' }].map(item => <button key={item.page} onClick={() => onNavigate?.(item.page)}><span className="teacher-shortcut-icon"><FontAwesomeIcon icon={item.icon} /></span><span><strong>{item.title}</strong><small>{item.text}</small></span><FontAwesomeIcon icon={faArrowRight} /></button>)}
      </nav>
      {error && <ErrorState title="Kabinet ma’lumotlarini yuklab bo‘lmadi" onRetry={load} />}

      {data && <SummaryRow items={[{ label: 'Faol guruhlar', value: data.total_groups, sub: 'Sizga biriktirilgan' }, { label: 'Jami talabalar', value: data.total_students, sub: 'Barcha guruhlarda' }, { label: MONTHS[month - 1] + ' maoshi', value: Number(salaryInfo?.salary ?? data.total_salary ?? 0).toLocaleString('uz-UZ'), unit: 'so‘m', tone: 'success', sub: salaryInfo?.is_internship ? 'Stajirovka' : salaryInfo?.auto ? 'Avtomatik hisoblangan' : 'Qo‘lda belgilangan' }]} />}
      <div className="teacher-workspace-bar"><ViewTabs value={tab} onChange={setTab} items={[{ key: 'groups', label: 'Guruhlarim', count: groups.length }, { key: 'salary', label: 'Maosh hisobi' }, { key: 'certificates', label: 'Sertifikatlar' }]} />      {/* O'quvchini ismi bo'yicha qidirish — o'qituvchi eng ko'p qiladigan amal */}
      <div className="td-search">
        <div className="search-wrap">
          <FontAwesomeIcon icon={faMagnifyingGlass} className="search-icon" />
          <input
            type="text"
            className={`search-input${studentSearch ? ' has-clear' : ''}`}
            value={studentSearch}
            onChange={e => setStudentSearch(e.target.value)}
            placeholder="O'quvchi ismi bo'yicha qidirish..."
            aria-label="O'quvchi qidirish"
          />
          {studentSearch && (
            <button className="search-clear" onClick={() => setStudentSearch('')} aria-label="Tozalash">
              <FontAwesomeIcon icon={faXmark} />
            </button>
          )}
        </div>

        {searchQuery && (
          <div className="td-search-results">
            {studentMatches.length === 0 && (
              <div className="td-search-empty">"{studentSearch}" bo'yicha o'quvchi topilmadi</div>
            )}
            {studentMatches.map((m, i) => (
              <button
                key={`${m.group.id}-${m.student_id}-${i}`}
                className="td-search-item"
                onClick={() => { setStudentSearch(''); onOpenGroup(m.group) }}
              >
                <span className="td-search-name">{m.student_name}</span>
                <span className="td-search-group">{m.group.name}</span>
                <FontAwesomeIcon icon={faArrowRight} />
              </button>
            ))}
          </div>
        )}
      </div>

</div>

      {!loading && tab !== 'certificates' && groups.length > 0 && (
        <div className="toolbar">
          <div className="segmented" role="group" aria-label="Kun bo'yicha filtr">
            <button className={dayFilter === 'all' ? 'active' : ''} onClick={() => setDayFilter('all')}>Barchasi</button>
            <button className={dayFilter === 'Juft kunlar' ? 'active' : ''} onClick={() => setDayFilter('Juft kunlar')}>Juft kunlar</button>
            <button className={dayFilter === 'Toq kunlar' ? 'active' : ''} onClick={() => setDayFilter('Toq kunlar')}>Toq kunlar</button>
          </div>
        </div>
      )}

      {loading && <CardSkeleton count={3} height={132} />}

      {/* ── TAB: GURUHLAR ── */}
      {!loading && tab === 'groups' && (
        filteredGroups.length === 0 ? (
          <EmptyState
            icon={faUsers}
            title={groups.length === 0 ? 'Sizga guruh biriktirilmagan' : 'Bu filtrga mos guruh yo\'q'}
            description={groups.length === 0
              ? 'Guruh biriktirilgach, u shu yerda paydo bo\'ladi.'
              : 'Boshqa kun filtrini tanlab ko\'ring.'}
          />
        ) : (
          <div className="teacher-class-grid">
            {filteredGroups.map((g, index) => {
              const st = STAGE_STYLE[g.stage] || STAGE_STYLE.foundation
              return <article className="teacher-class" key={g.id} style={{ '--class-color': st.bar, '--class-index': index }}>
                <header><span className="teacher-class-icon"><FontAwesomeIcon icon={faChalkboardTeacher} /></span><span className="teacher-course-tag">{st.label}</span>{g.is_active === false && <span className="status-badge inactive">Yopiq</span>}<span className="teacher-class-number">{String(index + 1).padStart(2,'0')}</span></header>
                <h2>{g.name}</h2><p className="teacher-class-schedule"><FontAwesomeIcon icon={faCalendarDays} />{g.schedule || 'Jadval belgilanmagan'}<span>{g.lesson_time || '—'}</span></p>
                <div className="teacher-class-progress"><ProgressRing value={g.progress_pct} size={74} label={g.name + ' kurs progressi'} /><div><strong>{g.completed_lessons ?? 0}<small> / {g.total_lessons ?? 0} dars</small></strong><span>Kurs davomiyligi</span></div><span className="teacher-class-students"><FontAwesomeIcon icon={faUsers} /><b>{g.student_count ?? 0}</b> talaba</span></div>
                <div className="teacher-class-facts"><span>Boshlangan<strong>{g.start_date || '—'}</strong></span><span>{MONTHS[month - 1]} ulushi<strong>{fmt(g.month_salary)}</strong></span></div>
                <footer><span>Guruh bilan ishlash</span><button className="button secondary" onClick={() => onOpenGroup(g)}>Guruhni ochish <FontAwesomeIcon icon={faArrowRight} /></button></footer>
              </article>
            })}
          </div>
        )
      )}

      {/* ── TAB: MAOSH ── */}
      {!loading && tab === 'salary' && (
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
                Formula: har guruhda 50 000 so'm shu oydagi o'tilgan darslar soniga bo'linadi,
                so'ng talaba qatnashgan darslar soniga ko'paytiriladi.
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

          {filteredGroups.length === 0 ? (
            <EmptyState
              icon={faMoneyBillWave}
              title={groups.length === 0 ? "Guruhlar yo'q" : 'Bu filtrga mos guruh yo\'q'}
            />
          ) : (
            <div className="td-grouplist">
              {filteredGroups.map(g => {
                const st = STAGE_STYLE[g.stage] || STAGE_STYLE.foundation
                const isOpen = expanded[g.id]
                const students = g.student_salaries || []

                return (
                  <article key={g.id} className={`td-acc${isOpen ? ' is-open' : ''}`}>
                    <button className="td-acc-head" onClick={() => toggleExpand(g.id)} aria-expanded={isOpen}>
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
                          Formula: 50 000 so'm / {g.month_lessons_held} dars × kelgan darslar soni
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

      {/* ── TAB: SERTIFIKATLAR ── */}
      {!loading && tab === 'certificates' && (
        certGroupsLoading ? (
          <CardSkeleton count={3} height={72} />
        ) : !certGroups || certGroups.length === 0 ? (
          <EmptyState icon={faAward} title="Sizga guruh biriktirilmagan" />
        ) : (
          <div className="td-grouplist">
            {certGroups.map(g => {
              const st = STAGE_STYLE[g.stage] || STAGE_STYLE.foundation
              const ready = g.certificate_count > 0
              return (
                <div key={g.id} className="td-certrow">
                  <span className="ui-badge ui-badge-sm" style={{ background: st.bg, color: st.color }}>{st.label}</span>
                  {g.is_active === false && <span className="status-badge inactive">Yopiq</span>}
                  <span className="td-acc-name">{g.name}</span>
                  <span className="muted-sm">{g.student_count} talaba</span>
                  <span className={`ui-badge ui-badge-sm ${ready ? 'ui-badge-success' : 'ui-badge-neutral'}`}>
                    {ready ? `${g.certificate_count} ta tayyor` : 'Hali tayyorlanmagan'}
                  </span>
                  <button className="button small secondary" onClick={() => handleCertGroupClick(g)}>
                    <FontAwesomeIcon icon={faAward} /> {ready ? "Ko'rish" : 'Tayyorlash'}
                  </button>
                </div>
              )
            })}
          </div>
        )
      )}

      <Modal
        open={certModal && !!certTarget}
        title={certTarget ? `Sertifikat — ${certTarget.name}` : ''}
        onClose={() => setCertModal(false)}
        footer={
          <>
            <button className="button secondary" onClick={() => setCertModal(false)}>Bekor</button>
            <button className="button" disabled={certGenerating} onClick={handleGenerateCerts}>
              <FontAwesomeIcon icon={faAward} /> {certGenerating ? 'Generatsiya qilinmoqda...' : 'Generatsiya qilish'}
            </button>
          </>
        }
      >
        <p className="muted-sm">
          Guruhdagi barcha {certTarget?.student_count} o'quvchi uchun sertifikat tayyorlanadi.
          Har bir sertifikatda ism, sana, imzo va raqamni alohida tahrirlab, "Saqlash" bilan
          yozib qo'yish mumkin.
        </p>
        <Input label="Kurs nomi" value={certCourse} maxLength={40}
          onChange={e => setCertCourse(e.target.value)} placeholder="Masalan: Frontend" />
        <Input label="Berilgan sana" value={certDate} maxLength={20}
          onChange={e => setCertDate(e.target.value)} placeholder="03.09.2026" />
        <Input label="Imzo (CEO)" value={certSigner} maxLength={60}
          onChange={e => setCertSigner(e.target.value)} placeholder="F.I.O." />
      </Modal>

      {certRecords && certTarget && (
        <GroupCertificates
          group={certTarget}
          records={certRecords}
          onClose={() => { setCertRecords(null); setCertTarget(null) }}
        />
      )}
    </div>
  )
}

function InfoChip({ icon, text, tone }) {
  return (
    <div className={`td-chip ${tone ? `tone-${tone}` : ''}`.trim()}>
      <FontAwesomeIcon icon={icon} />
      {text}
    </div>
  )
}

function TabBtn({ active, onClick, icon, children }) {
  return (
    <button className={`tab-btn ${active ? 'active' : ''}`.trim()} onClick={onClick}>
      <FontAwesomeIcon icon={icon} /> {children}
    </button>
  )
}
