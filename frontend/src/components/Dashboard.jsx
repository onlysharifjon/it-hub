import { useEffect, useState } from 'react'
import { toast } from 'react-hot-toast'
import { fetchStatsOverview, exportExcelUrl } from '../api'

const MONTHS = ['Yan','Fev','Mar','Apr','May','Iyu','Iyl','Avg','Sen','Okt','Noy','Dek']

export default function Dashboard() {
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchStatsOverview()
      .then(setStats)
      .catch(() => toast.error("Statistika yuklanmadi"))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="page"><div className="muted center">Yuklanmoqda...</div></div>
  if (!stats) return <div className="page"><div className="muted center">Ma'lumot yo'q</div></div>

  const change = stats.income_change_pct
  const changeSign = change >= 0 ? '+' : ''
  const changeColor = change >= 0 ? '#22c55e' : '#ef4444'

  const maxIncome = Math.max(...stats.monthly_history.map(m => parseFloat(m.total_income)), 1)

  return (
    <div className="page">
      <div className="page-header">
        <h1>Dashboard</h1>
        <button className="button secondary" onClick={() => window.open(exportExcelUrl(), '_blank')}>
          📊 Excel eksport
        </button>
      </div>

      {/* KPI Cards */}
      <div className="kpi-grid">
        <div className="kpi-card">
          <div className="kpi-label">Jami talabalar</div>
          <div className="kpi-value">{stats.total_students}</div>
          <div className="kpi-sub">Faol: {stats.active_students}</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">Guruhlar</div>
          <div className="kpi-value">{stats.total_groups}</div>
          <div className="kpi-sub">Faol: {stats.active_groups}</div>
        </div>
        <div className="kpi-card highlight">
          <div className="kpi-label">Bu oy daromad</div>
          <div className="kpi-value">{Number(stats.this_month_income).toLocaleString()} <span className="kpi-currency">so'm</span></div>
          <div className="kpi-sub" style={{ color: changeColor }}>
            {changeSign}{change.toFixed(1)}% o'tgan oyga nisbatan
          </div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">O'tgan oy daromad</div>
          <div className="kpi-value">{Number(stats.last_month_income).toLocaleString()} <span className="kpi-currency">so'm</span></div>
        </div>
      </div>

      {/* Monthly Chart */}
      <div className="chart-card">
        <h2>So'nggi 12 oy daromadi</h2>
        <div className="bar-chart">
          {stats.monthly_history.map((m, i) => {
            const h = Math.max((parseFloat(m.total_income) / maxIncome) * 180, 4)
            const isCurrentMonth = i === stats.monthly_history.length - 1
            return (
              <div key={i} className="bar-col">
                <div className="bar-amount">{m.total_income > 0 ? (Number(m.total_income) / 1000).toFixed(0) + 'k' : ''}</div>
                <div
                  className={`bar ${isCurrentMonth ? 'bar-current' : ''}`}
                  style={{ height: h }}
                  title={`${MONTHS[m.month - 1]} ${m.year}: ${Number(m.total_income).toLocaleString()} so'm`}
                />
                <div className="bar-label">{MONTHS[m.month - 1]}</div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Monthly Table */}
      <div className="chart-card">
        <h2>Oylik statistika</h2>
        <table className="data-table">
          <thead>
            <tr>
              <th>Oy</th>
              <th>Yil</th>
              <th>Daromad</th>
              <th>To'lovlar soni</th>
              <th>O'tgan oyga nisbatan</th>
            </tr>
          </thead>
          <tbody>
            {[...stats.monthly_history].reverse().map((m, i, arr) => {
              const prev = arr[i + 1]
              const diff = prev ? parseFloat(m.total_income) - parseFloat(prev.total_income) : 0
              const diffPct = prev && parseFloat(prev.total_income) > 0
                ? ((diff / parseFloat(prev.total_income)) * 100).toFixed(1)
                : null
              return (
                <tr key={i}>
                  <td>{MONTHS[m.month - 1]}</td>
                  <td>{m.year}</td>
                  <td className="amount">{Number(m.total_income).toLocaleString()} so'm</td>
                  <td>{m.payment_count}</td>
                  <td>
                    {diffPct !== null ? (
                      <span style={{ color: diff >= 0 ? '#22c55e' : '#ef4444', fontWeight: 600 }}>
                        {diff >= 0 ? '+' : ''}{diffPct}%
                      </span>
                    ) : '—'}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
