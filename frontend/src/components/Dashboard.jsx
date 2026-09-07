import { useEffect, useState } from 'react'
import { toast } from 'react-hot-toast'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faFileExcel, faChartBar, faMoneyBillWave,
  faPlus, faPen, faTrash, faFilter, faReceipt,
  faUserGraduate, faChalkboardTeacher, faClockRotateLeft, faArrowTrendUp,
} from '@fortawesome/free-solid-svg-icons'
import {
  fetchStatsOverview, exportExcelUrl, openDownload,
  fetchExpenses, createExpense, updateExpense, deleteExpense,
  fetchLeadStats, fetchFinanceMonthly, fetchLeads,
  fetchStudentGrowth, fetchTeacherSalaries, fetchAuditLogs,
} from '../api'
import KpiCard from './ui/KpiCard'
import { BarChart, Waterfall } from './ui/Chart'
import { Metric, MetricStrip } from './ui/Metric'
import Meter from './ui/Meter'
import Badge from './ui/Badge'
import AttentionPanel from './ui/Attention'
import SectionHead from './ui/SectionHead'
import Modal from './ui/Modal'
import ConfirmDialog from './ui/ConfirmDialog'
import DataTable from './ui/DataTable'
import { Input } from './ui/Field'
import { CardSkeleton, ErrorState } from './ui/States'
import { tashkentNow } from '../utils/datetime'

const MONTHS = ['Yanvar','Fevral','Mart','Aprel','May','Iyun','Iyul','Avgust','Sentyabr','Oktyabr','Noyabr','Dekabr']
const MONTHS_SHORT = ['Yan','Fev','Mar','Apr','May','Iyu','Iyl','Avg','Sen','Okt','Noy','Dek']

const NOW = tashkentNow()
const THIS_YEAR = NOW.getFullYear()
const THIS_MONTH = NOW.getMonth() + 1
const YEARS = Array.from({ length: 5 }, (_, i) => THIS_YEAR - 2 + i)

const fmt = n => Number(n || 0).toLocaleString('uz-UZ')

// Audit jurnali yozuvlarini o'qiladigan matnga aylantirish (AuditLogPanel bilan bir xil)
const AUDIT_ACTIONS = {
  create:    { label: "Qo'shildi",            variant: 'success' },
  update:    { label: 'Tahrirlandi',          variant: 'primary' },
  delete:    { label: "O'chirildi",           variant: 'danger' },
  reorder:   { label: "Tartib o'zgardi",      variant: 'warning' },
  block:     { label: 'Bloklandi',            variant: 'danger' },
  unblock:   { label: 'Blok olib tashlandi',  variant: 'success' },
  archive:   { label: 'Arxivlandi',           variant: 'neutral' },
  unarchive: { label: 'Arxivdan chiqarildi',  variant: 'primary' },
}
const ENTITY_LABELS = {
  lesson: 'dars rejasi', student: 'talaba', group: 'guruh',
  user: 'foydalanuvchi', payment: "to'lov", expense: 'xarajat',
}

export default function Dashboard({ onNavigate }) {
  const [stats, setStats] = useState(null)
  const [leadStats, setLeadStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [year, setYear] = useState(THIS_YEAR)
  const [finance, setFinance] = useState(null)
  const [overdueLeads, setOverdueLeads] = useState(null)
  const [growth, setGrowth] = useState(null)
  const [teacherPerf, setTeacherPerf] = useState(null)
  const [activity, setActivity] = useState(null)

  // Xarajatlar (shu sahifada boshqariladi)
  const [expMonth, setExpMonth] = useState(THIS_MONTH)
  const [expYear, setExpYear] = useState(THIS_YEAR)
  const [expenses, setExpenses] = useState([])
  const [expLoading, setExpLoading] = useState(false)
  const [expModal, setExpModal] = useState(null)      // null | 'add' | expense
  const [expForm, setExpForm] = useState({ name: '', amount: '' })
  const [expErrors, setExpErrors] = useState({})
  const [expSaving, setExpSaving] = useState(false)
  const [expDelete, setExpDelete] = useState(null)

  useEffect(() => { loadStats() }, [year])
  useEffect(() => { loadExpenses() }, [expMonth, expYear])

  // Lid konversiyasi alohida endpoint'dan — /stats/overview'da bu ma'lumot yo'q
  useEffect(() => {
    fetchLeadStats().then(setLeadStats).catch(() => { /* ixtiyoriy ko'rsatkich */ })
  }, [])

  // "E'tibor talab qiladi" paneli uchun — yig'ilmagan to'lovlar va kechikkan
  // lidlar /stats/overview'da yo'q, shuning uchun alohida so'raladi. Ikkalasi
  // ham ixtiyoriy: yuklanmasa panel shunchaki o'sha bandni ko'rsatmaydi.
  useEffect(() => {
    fetchFinanceMonthly(THIS_MONTH, THIS_YEAR).then(setFinance).catch(() => {})
    fetchLeads({ overdue: true }).then(l => setOverdueLeads(l.length)).catch(() => {})
    // O'qituvchi natijalari va oxirgi o'zgarishlar — ikkalasi ham ixtiyoriy
    // (yuklanmasa tegishli blok ko'rsatilmaydi, sahifa ishlayveradi).
    fetchTeacherSalaries(THIS_MONTH, THIS_YEAR).then(setTeacherPerf).catch(() => {})
    fetchAuditLogs({ page_size: 8 }).then(r => setActivity(r.items || [])).catch(() => {})
  }, [])

  useEffect(() => { fetchStudentGrowth(year).then(setGrowth).catch(() => {}) }, [year])

  async function loadStats() {
    setLoading(true)
    setError(null)
    try { setStats(await fetchStatsOverview(year)) }
    catch (e) { setError(e) }
    finally { setLoading(false) }
  }

  async function loadExpenses() {
    setExpLoading(true)
    try { setExpenses(await fetchExpenses(expMonth, expYear)) }
    catch { toast.error("Xarajatlar yuklanmadi") }
    finally { setExpLoading(false) }
  }

  function openAddExp() { setExpForm({ name: '', amount: '' }); setExpErrors({}); setExpModal('add') }
  function openEditExp(e) { setExpForm({ name: e.name, amount: e.amount }); setExpErrors({}); setExpModal(e) }

  async function handleSaveExp() {
    const errs = {}
    if (!expForm.name.trim()) errs.name = 'Nom kiriting'
    if (!expForm.amount || Number(expForm.amount) <= 0) errs.amount = "Summa 0 dan katta bo'lishi kerak"
    setExpErrors(errs)
    if (Object.keys(errs).length) return

    setExpSaving(true)
    try {
      const payload = { name: expForm.name, amount: parseFloat(expForm.amount), month: expMonth, year: expYear }
      if (expModal === 'add') {
        await createExpense(payload)
        toast.success("Xarajat qo'shildi")
      } else {
        await updateExpense(expModal.id, { name: expForm.name, amount: parseFloat(expForm.amount) })
        toast.success("Saqlandi")
      }
      setExpModal(null)
      loadExpenses()
      loadStats()   // xarajat sof foydaga ta'sir qiladi
    } catch (err) { toast.error(err.message || 'Xato') }
    finally { setExpSaving(false) }
  }

  async function handleDeleteExp() {
    try {
      await deleteExpense(expDelete.id)
      toast.success("O'chirildi")
      setExpDelete(null)
      loadExpenses()
      loadStats()
    } catch (err) { toast.error(err.message || 'Xato') }
  }

  if (loading) {
    return (
      <div className="page">
        <div className="page-header"><h1><FontAwesomeIcon icon={faChartBar} className="page-icon" /> Dashboard</h1></div>
        <div className="kpi-grid"><CardSkeleton count={4} height={112} /></div>
        <div className="kpi-grid" style={{ marginTop: 20 }}><CardSkeleton count={6} height={92} /></div>
      </div>
    )
  }
  if (error) return <div className="page"><ErrorState message={error.message} onRetry={loadStats} /></div>
  if (!stats) return <div className="page"><ErrorState title="Ma'lumot yo'q" onRetry={loadStats} /></div>

  const history = stats.monthly_history || []
  const netProfit = parseFloat(stats.net_profit || 0)
  const expTotal = expenses.reduce((s, e) => s + parseFloat(e.amount), 0)

  // Sparkline'lar uchun — joriy oygacha bo'lgan tushum tarixi
  const incomeSpark = history.slice(0, THIS_MONTH).map(m => Number(m.total_income))
  const profitSpark = history.slice(0, THIS_MONTH).map(m => Number(m.net_profit))

  // Lid konversiyasi: "won" bosqichlaridagi lidlar / jami
  const wonCount = leadStats?.stages?.filter(s => s.kind === 'won').reduce((a, s) => a + s.count, 0) ?? null
  const conversion = leadStats?.total ? (wonCount / leadStats.total) * 100 : null

  // Joriy yilda hali kelmagan oylarda foyda chizig'i chizilmaydi: nol qiymat
  // "foyda nolga tushdi" degandek ko'rinib, bo'lmagan ma'lumotni ko'rsatardi.
  const lastKnownMonth = year === THIS_YEAR ? THIS_MONTH : 12
  const chartData = history.map(m => ({
    label: MONTHS_SHORT[m.month - 1],
    value: Number(m.total_income),
    compare: Number(m.total_expenses),
    // Umuman harakat bo'lmagan oy (tushum ham, chiqim ham 0) — bu "foyda nol"
    // emas, "ma'lumot yo'q". Nol deb chizilsa chiziq tekis turib, o'sha
    // oylarda natija bo'lgandek ko'rinadi.
    line: (m.month <= lastKnownMonth && (Number(m.total_income) || Number(m.total_expenses)))
      ? Number(m.net_profit)
      : null,
  }))
  const currentMonthIdx = year === THIS_YEAR ? THIS_MONTH - 1 : -1

  // ── "E'tibor talab qiladi" — passiv hisobotni ish ro'yxatiga aylantiradi ──
  const teacherSalary = Number(stats.teacher_salary || 0)
  const externalExp   = Number(stats.external_expenses || 0)
  const monthIncome   = Number(stats.this_month_income || 0)
  const collectionPct = finance?.total_expected > 0
    ? (finance.total_actual / finance.total_expected) * 100
    : null
  const unpaidCount = finance
    ? finance.groups.reduce((n, g) => n + g.unpaid_count, 0)
    : null

  const alerts = []
  if (finance && finance.total_deficit > 0) {
    alerts.push({
      id: 'debt',
      level: collectionPct != null && collectionPct < 60 ? 'critical' : 'warning',
      title: "Yig'ilmagan to'lovlar",
      detail: `${unpaidCount} o'quvchi · yig'ilish ${collectionPct?.toFixed(0)}%`,
      value: `${fmt(finance.total_deficit)} so'm`,
      actionLabel: 'Moliya',
      onAction: () => onNavigate('finance'),
    })
  }
  if (stats.attendance_rate < 75) {
    alerts.push({
      id: 'attendance',
      level: stats.attendance_rate < 60 ? 'critical' : 'warning',
      title: 'Davomat past',
      detail: 'Bu oy belgilangan darslar bo\'yicha',
      value: `${stats.attendance_rate}%`,
      actionLabel: 'Davomat',
      onAction: () => onNavigate('today_attendance'),
    })
  }
  if (overdueLeads > 0) {
    alerts.push({
      id: 'leads',
      level: overdueLeads >= 20 ? 'warning' : 'info',
      title: 'Kechikkan lidlar',
      detail: "Kelish/qo'ng'iroq vaqti o'tib ketgan",
      value: `${overdueLeads} ta`,
      actionLabel: 'Lidlar',
      onAction: () => onNavigate('leads'),
    })
  }
  if (netProfit < 0) {
    alerts.push({
      id: 'loss',
      level: 'critical',
      title: 'Oy zarar bilan ketyapti',
      detail: `Chiqim tushumdan ${fmt(Math.abs(netProfit))} so'm ko'p`,
      value: `−${fmt(Math.abs(netProfit))}`,
      actionLabel: 'Xarajatlar',
      onAction: () => onNavigate('expenses'),
    })
  }
  if (conversion != null && conversion < 10 && leadStats?.total > 20) {
    alerts.push({
      id: 'conversion',
      level: 'info',
      title: 'Lid konversiyasi past',
      detail: `${wonCount} ta to'ladi / ${leadStats.total} ta lid`,
      value: `${conversion.toFixed(1)}%`,
      actionLabel: 'Lidlar',
      onAction: () => onNavigate('leads'),
    })
  }

  // ── O'sish: shu yil qo'shilgan / yil boshidagi baza ──────────────────────
  const growthMonths = growth?.months || []
  const joinedThisYear = growthMonths.reduce((n, m) => n + m.joined, 0)
  const growthPct = growth?.starting_total
    ? (joinedThisYear / growth.starting_total) * 100
    : null
  const growthChart = growthMonths.map(m => ({
    label: MONTHS_SHORT[m.month - 1],
    value: m.joined,
    line: m.cumulative,
  }))

  // ── O'qituvchi natijalari: davomat + maosh ulushi ───────────────────────
  const teacherRows = (teacherPerf?.teachers || [])
    .filter(t => t.teacher_id != null)
    .map(t => {
      let attended = 0, possible = 0, students = 0
      for (const g of t.groups) {
        attended += g.total_attended || 0
        students += (g.students || []).length
        possible += (g.total_lessons_held || 0) * (g.students || []).length
      }
      return {
        ...t,
        students,
        groups_count: t.groups.length,
        attendance_pct: possible > 0 ? (attended / possible) * 100 : null,
      }
    })
    .sort((a, b) => (b.attendance_pct ?? -1) - (a.attendance_pct ?? -1))

  const expenseColumns = [
    { key: 'name', header: 'Nomi', sortable: true, render: e => <strong>{e.name}</strong> },
    {
      key: 'amount', header: 'Summa', sortable: true, align: 'right',
      sortValue: e => Number(e.amount),
      render: e => <span className="amount tone-danger">{fmt(e.amount)} so'm</span>,
    },
    {
      key: 'actions', header: '', align: 'right', className: 'actions',
      render: e => (
        <>
          <button className="btn-icon" onClick={() => openEditExp(e)} title="Tahrirlash" aria-label="Tahrirlash">
            <FontAwesomeIcon icon={faPen} />
          </button>
          <button className="btn-icon danger" onClick={() => setExpDelete(e)} title="O'chirish" aria-label="O'chirish">
            <FontAwesomeIcon icon={faTrash} />
          </button>
        </>
      ),
    },
  ]

  return (
    <div className="page">
      <div className="page-header">
        <h1><FontAwesomeIcon icon={faChartBar} className="page-icon" /> Dashboard</h1>
        <div className="header-actions">
          <span className="dash-filter-label"><FontAwesomeIcon icon={faFilter} /> Yil</span>
          <select className="field-sm" value={year} onChange={e => setYear(parseInt(e.target.value))}>
            {YEARS.map(y => <option key={y} value={y}>{y}</option>)}
          </select>
          <button
            className="button secondary"
            onClick={() => openDownload(exportExcelUrl()).catch(e => toast.error(e.message || "Yuklab bo'lmadi"))}
          >
            <FontAwesomeIcon icon={faFileExcel} /> Excel
          </button>
        </div>
      </div>

      {/* ── 1-daraja: oyning bitta asosiy raqami + P&L parchalanishi ──
           Ilgari bu yerda 10 ta bir xil og'irlikdagi KPI kartasi bor edi.
           Endi bitta yetakchi raqam va uning qanday hosil bo'lgani. ── */}
      <section className="dash-primary" aria-label="Oylik moliyaviy natija">
        <KpiCard
          size="lg" tone="primary"
          label={`${MONTHS[THIS_MONTH - 1]} tushumi`}
          value={fmt(stats.this_month_income)} unit="so'm"
          icon={faMoneyBillWave}
          trend={stats.income_change_pct} trendLabel="o'tgan oyga"
          spark={incomeSpark}
          onClick={() => onNavigate('payments')}
          hint="To'lovlar sahifasiga o'tish"
        />

        <div className="dash-pl">
          <SectionHead
            title="Pul qayerga ketdi"
            description={`${MONTHS[THIS_MONTH - 1]} · tushumdan sof foydagacha`}
          />
          <Waterfall
            start={{ label: 'Tushum', value: monthIncome }}
            steps={[
              { label: "O'qituvchi maoshi", value: teacherSalary, onClick: () => onNavigate('teacher_salaries') },
              { label: 'Tashqi xarajatlar', value: externalExp, onClick: () => onNavigate('expenses') },
            ]}
            result={{ label: 'Sof foyda', value: netProfit }}
            format={fmt}
          />
        </div>
      </section>

      {/* ── 2-daraja: nima e'tibor talab qiladi ── */}
      <AttentionPanel items={alerts} />

      {/* ── 3-daraja: operatsion ko'rsatkichlar — zich qator, karta devori emas ── */}
      <SectionHead
        title="Operatsion ko'rsatkichlar"
        description="Raqamni bosib tegishli bo'limga o'ting"
      />
      <MetricStrip columns={6}>
        <Metric
          label="Talabalar" value={fmt(stats.total_students)}
          sub={`${stats.active_students} faol`}
          onClick={() => onNavigate('students')}
        />
        <Metric
          label="Guruhlar" value={fmt(stats.total_groups)}
          sub={`${stats.active_groups} faol`}
          onClick={() => onNavigate('groups')}
        />
        <Metric
          label="O'qituvchilar" value={fmt(stats.total_teachers)}
          sub="faol xodimlar"
          onClick={() => onNavigate('teacher_salaries')}
        />
        <Metric
          label="Davomat" value={`${stats.attendance_rate}%`}
          tone={stats.attendance_rate >= 80 ? 'success' : stats.attendance_rate >= 60 ? 'warning' : 'danger'}
          sub="bu oy"
          onClick={() => onNavigate('today_attendance')}
        />
        <Metric
          label="Lid konversiyasi"
          value={conversion == null ? '—' : `${conversion.toFixed(1)}%`}
          tone={conversion == null ? undefined : conversion >= 20 ? 'success' : 'warning'}
          sub={leadStats ? `${wonCount}/${leadStats.total} lid` : '...'}
          onClick={() => onNavigate('leads')}
        />
        <Metric
          label="To'lov yig'ilishi"
          value={collectionPct == null ? '—' : `${collectionPct.toFixed(0)}%`}
          tone={collectionPct == null ? undefined : collectionPct >= 80 ? 'success' : collectionPct >= 60 ? 'warning' : 'danger'}
          sub={unpaidCount != null ? `${unpaidCount} to'lamagan` : '...'}
          onClick={() => onNavigate('finance')}
        />
      </MetricStrip>

      {/* ── Yillik grafik: tushum vs chiqim ── */}
      <div className="chart-card">
        <div className="chart-card-head">
          <h2>{year} yil — tushum va chiqim</h2>
        </div>
        <BarChart
          data={chartData}
          seriesLabel="Tushum"
          compareLabel="Chiqim"
          lineLabel="Sof foyda"
          highlightIndex={currentMonthIdx}
          height={240}
        />
      </div>

      {/* ── O'quvchi o'sishi ── */}
      {growthMonths.length > 0 && (
        <div className="chart-card">
          <div className="chart-card-head">
            <h2><FontAwesomeIcon icon={faArrowTrendUp} className="page-icon" /> O'quvchi o'sishi — {year}</h2>
            <div className="chart-card-actions">
              <span className="dash-filter-label">
                Yil boshida <strong>{fmt(growth.starting_total)}</strong> · qo'shildi{' '}
                <strong className="tone-success">+{fmt(joinedThisYear)}</strong>
                {growthPct != null && <> ({growthPct.toFixed(0)}%)</>}
              </span>
            </div>
          </div>
          <BarChart
            data={growthChart}
            seriesLabel="Yangi o'quvchilar"
            lineLabel="Jami (kumulyativ)"
            highlightIndex={currentMonthIdx}
            height={200}
          />
        </div>
      )}

      {/* ── O'qituvchi natijalari ── */}
      {teacherRows.length > 0 && (
        <div className="chart-card is-flush">
          <div className="chart-card-head">
            <h2><FontAwesomeIcon icon={faChalkboardTeacher} className="page-icon" /> O'qituvchi natijalari</h2>
            <div className="chart-card-actions">
              <span className="dash-filter-label">{MONTHS[THIS_MONTH - 1]} · davomat bo'yicha saralangan</span>
            </div>
          </div>
          <DataTable
            columns={[
              { key: 'teacher_name', header: "O'qituvchi", sortable: true, render: t => <strong>{t.teacher_name}</strong> },
              { key: 'groups_count', header: 'Guruh', align: 'right', sortable: true },
              { key: 'students', header: 'Talaba', align: 'right', sortable: true },
              {
                key: 'attendance_pct', header: 'Davomat', width: 180, sortable: true,
                sortValue: t => t.attendance_pct ?? -1,
                render: t => t.attendance_pct == null
                  ? <span className="text-muted">—</span>
                  : <Meter value={t.attendance_pct} showValue tone="auto" size="sm" />,
              },
              {
                key: 'total_salary', header: 'Maosh ulushi', align: 'right', sortable: true,
                sortValue: t => Number(t.total_salary),
                render: t => <span className="num">{fmt(t.total_salary)} so'm</span>,
              },
            ]}
            rows={teacherRows}
            rowKey={t => t.teacher_id}
            onRowClick={() => onNavigate('teacher_salaries')}
            empty={{ title: "Ma'lumot yo'q" }}
          />
        </div>
      )}

      {/* ── Oxirgi harakatlar ── */}
      {activity && activity.length > 0 && (
        <div className="card">
          <div className="card-head">
            <div>
              <div className="card-title">
                <FontAwesomeIcon icon={faClockRotateLeft} className="page-icon" /> Oxirgi o'zgarishlar
              </div>
              <div className="card-sub">Dars rejalaridagi tahrirlar — kim, nima va qachon</div>
            </div>
            <button className="button ghost small" onClick={() => onNavigate('lessons')}>
              Dars rejalari
            </button>
          </div>
          <ul className="activity-list">
            {activity.map(a => {
              const act = AUDIT_ACTIONS[a.action] || { label: a.action, variant: 'neutral' }
              return (
                <li key={a.id} className="activity-item">
                  <Badge variant={act.variant} size="sm">{act.label}</Badge>
                  <div className="activity-body">
                    <div className="activity-title">
                      <strong>{a.changed_by_username || 'Tizim'}</strong>{' '}
                      <span className="text-muted">
                        {ENTITY_LABELS[a.entity_type] || a.entity_type}
                        {a.entity_id ? ` #${a.entity_id}` : ''}
                      </span>
                    </div>
                  </div>
                  <time className="activity-time">
                    {new Date(a.changed_at).toLocaleString('uz-UZ', {
                      day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit',
                    })}
                  </time>
                </li>
              )
            })}
          </ul>
        </div>
      )}

      {/* ── Tashqi xarajatlar ── */}
      <div className="chart-card">
        <div className="chart-card-head">
          <h2>Tashqi xarajatlar</h2>
          <div className="chart-card-actions">
            <select className="field-sm" value={expMonth} onChange={e => setExpMonth(Number(e.target.value))}>
              {MONTHS.map((m, i) => <option key={i} value={i + 1}>{m}</option>)}
            </select>
            <select className="field-sm" value={expYear} onChange={e => setExpYear(Number(e.target.value))}>
              {YEARS.map(y => <option key={y} value={y}>{y}</option>)}
            </select>
            <button className="button" onClick={openAddExp}>
              <FontAwesomeIcon icon={faPlus} /> Qo'shish
            </button>
          </div>
        </div>

        <DataTable
          columns={expenseColumns}
          rows={expenses}
          loading={expLoading}
          empty={{
            icon: faReceipt,
            title: `${MONTHS[expMonth - 1]} ${expYear} uchun xarajat yo'q`,
            description: 'Ijara, kommunal, reklama kabi xarajatlarni shu yerda yuriting.',
            action: <button className="button" onClick={openAddExp}><FontAwesomeIcon icon={faPlus} /> Qo'shish</button>,
          }}
        />
        {expenses.length > 0 && (
          <div className="dash-exp-total">
            <span>Jami</span>
            <strong className="tone-danger">{fmt(expTotal)} so'm</strong>
          </div>
        )}
      </div>

      {/* ── Oylik statistika ── */}
      <div className="chart-card">
        <div className="chart-card-head"><h2>Oylik statistika</h2></div>
        <DataTable
          columns={[
            { key: 'month', header: 'Oy', sortable: true, sortValue: m => m.month,
              render: m => `${MONTHS_SHORT[m.month - 1]} ${m.year}` },
            { key: 'total_income', header: 'Tushum', align: 'right', sortable: true,
              sortValue: m => Number(m.total_income),
              render: m => <span className="tone-success">{fmt(m.total_income)}</span> },
            { key: 'teacher_salary', header: "O'qt. maoshi", align: 'right', sortable: true,
              sortValue: m => Number(m.teacher_salary),
              render: m => <span className="tone-primary">{fmt(m.teacher_salary)}</span> },
            { key: 'external_expenses', header: 'Tashqi xarajat', align: 'right', sortable: true,
              sortValue: m => Number(m.external_expenses),
              render: m => <span className="tone-warning">{fmt(m.external_expenses)}</span> },
            { key: 'total_expenses', header: 'Jami chiqim', align: 'right', sortable: true,
              sortValue: m => Number(m.total_expenses),
              render: m => <span className="tone-danger">{fmt(m.total_expenses)}</span> },
            { key: 'net_profit', header: 'Sof foyda', align: 'right', sortable: true,
              sortValue: m => Number(m.net_profit),
              render: m => {
                const np = parseFloat(m.net_profit || 0)
                return <strong className={np >= 0 ? 'tone-success' : 'tone-danger'}>
                  {np < 0 ? '−' : ''}{fmt(Math.abs(np))}
                </strong>
              } },
            { key: 'payment_count', header: "To'lovlar", align: 'center', sortable: true,
              render: m => <span className="text-muted">{m.payment_count}</span> },
          ]}
          rows={[...history].reverse()}
          rowKey={(m) => `${m.year}-${m.month}`}
          empty="Ma'lumot yo'q"
        />
      </div>

      {/* ── Xarajat oynasi ── */}
      <Modal
        open={!!expModal}
        title={expModal === 'add' ? "Xarajat qo'shish" : 'Xarajatni tahrirlash'}
        onClose={() => setExpModal(null)}
        size="sm"
        footer={
          <>
            <button className="button secondary" onClick={() => setExpModal(null)}>Bekor</button>
            <button className="button" onClick={handleSaveExp} disabled={expSaving}>
              {expSaving ? 'Saqlanmoqda...' : 'Saqlash'}
            </button>
          </>
        }
      >
        <Input
          label="Nomi" required
          value={expForm.name} error={expErrors.name}
          onChange={e => setExpForm(f => ({ ...f, name: e.target.value }))}
          placeholder="Ijara, kommunal, reklama..."
        />
        <Input
          label="Summa (so'm)" required type="number"
          value={expForm.amount} error={expErrors.amount}
          onChange={e => setExpForm(f => ({ ...f, amount: e.target.value }))}
          placeholder="100000"
        />
      </Modal>

      <ConfirmDialog
        open={!!expDelete}
        title="Xarajatni o'chirish"
        message={expDelete ? `"${expDelete.name}" o'chirilsinmi?` : ''}
        confirmLabel="Ha, o'chirish"
        onConfirm={handleDeleteExp}
        onClose={() => setExpDelete(null)}
      />
    </div>
  )
}
