import { useEffect, useState } from 'react'
import { toast } from 'react-hot-toast'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faFileExcel, faChartBar, faUsers, faUserGraduate,
  faMoneyBillWave, faArrowTrendUp, faArrowTrendDown,
  faPlus, faPen, faTrash, faXmark,
} from '@fortawesome/free-solid-svg-icons'
import {
  fetchStatsOverview, exportExcelUrl, openDownload,
  fetchExpenses, createExpense, updateExpense, deleteExpense,
} from '../api'

const MONTHS = ['Yanvar','Fevral','Mart','Aprel','May','Iyun','Iyul','Avgust','Sentyabr','Oktyabr','Noyabr','Dekabr']
const MONTHS_SHORT = ['Yan','Fev','Mar','Apr','May','Iyu','Iyl','Avg','Sen','Okt','Noy','Dek']

const THIS_YEAR = new Date().getFullYear()
const THIS_MONTH = new Date().getMonth() + 1
const YEARS = Array.from({ length: 5 }, (_, i) => THIS_YEAR - 2 + i)

const fmt = n => Number(n || 0).toLocaleString()

export default function Dashboard({ onNavigate }) {
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [year, setYear] = useState(THIS_YEAR)

  // Expenses state
  const [expMonth, setExpMonth] = useState(THIS_MONTH)
  const [expYear, setExpYear] = useState(THIS_YEAR)
  const [expenses, setExpenses] = useState([])
  const [expLoading, setExpLoading] = useState(false)
  const [expModal, setExpModal] = useState(null) // null | 'add' | expense obj
  const [expForm, setExpForm] = useState({ name: '', amount: '' })
  const [expSaving, setExpSaving] = useState(false)

  useEffect(() => {
    setLoading(true)
    fetchStatsOverview(year)
      .then(setStats)
      .catch(() => toast.error("Statistika yuklanmadi"))
      .finally(() => setLoading(false))
  }, [year])

  useEffect(() => { loadExpenses() }, [expMonth, expYear])

  async function loadExpenses() {
    setExpLoading(true)
    try { setExpenses(await fetchExpenses(expMonth, expYear)) }
    catch { toast.error("Xarajatlar yuklanmadi") }
    finally { setExpLoading(false) }
  }

  function openAddExp() { setExpForm({ name: '', amount: '' }); setExpModal('add') }
  function openEditExp(e) { setExpForm({ name: e.name, amount: e.amount }); setExpModal(e) }

  async function handleSaveExp() {
    if (!expForm.name.trim()) { toast.error("Nom kiriting"); return }
    if (!expForm.amount || Number(expForm.amount) <= 0) { toast.error("Summa kiriting"); return }
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
      // Refresh stats too (expenses affect net profit)
      fetchStatsOverview(year).then(setStats)
    } catch (err) {
      toast.error(err.message || 'Xato')
    } finally {
      setExpSaving(false)
    }
  }

  async function handleDeleteExp(e) {
    if (!confirm(`"${e.name}" o'chirilsinmi?`)) return
    try {
      await deleteExpense(e.id)
      toast.success("O'chirildi")
      loadExpenses()
      fetchStatsOverview(year).then(setStats)
    } catch (err) {
      toast.error(err.message || 'Xato')
    }
  }

  if (loading) return <div className="page"><div className="muted center">Yuklanmoqda...</div></div>
  if (!stats) return <div className="page"><div className="muted center">Ma'lumot yo'q</div></div>

  const change = stats.income_change_pct
  const changeSign = change >= 0 ? '+' : ''
  const changeColor = change >= 0 ? '#22c55e' : '#ef4444'
  const maxIncome = Math.max(...stats.monthly_history.map(m => parseFloat(m.total_income)), 1)

  const netProfit = parseFloat(stats.net_profit || 0)
  const netColor = netProfit >= 0 ? '#16a34a' : '#dc2626'

  const totalExp = parseFloat(stats.expenses || 0) + parseFloat(stats.teacher_salary || 0)

  const expTotal = expenses.reduce((s, e) => s + parseFloat(e.amount), 0)

  return (
    <div className="page">
      <div className="page-header">
        <h1><FontAwesomeIcon icon={faChartBar} className="page-icon" /> Dashboard</h1>
        <div className="header-actions">
          <select className="field-sm" value={year} onChange={e => setYear(parseInt(e.target.value))}>
            {YEARS.map(y => <option key={y} value={y}>{y}</option>)}
          </select>
          <button className="button secondary" onClick={() => openDownload(exportExcelUrl())}>
            <FontAwesomeIcon icon={faFileExcel} /> Excel
          </button>
        </div>
      </div>

      {/* ── Talabalar & Guruhlar ── */}
      <div className="kpi-grid">
        <div className="kpi-card">
          <div className="kpi-label"><FontAwesomeIcon icon={faUserGraduate} /> Jami talabalar</div>
          <div className="kpi-value">{stats.total_students}</div>
          <div className="kpi-sub">Faol: {stats.active_students}</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label"><FontAwesomeIcon icon={faUsers} /> Guruhlar</div>
          <div className="kpi-value">{stats.total_groups}</div>
          <div className="kpi-sub">Faol: {stats.active_groups}</div>
        </div>
        <div className="kpi-card highlight">
          <div className="kpi-label"><FontAwesomeIcon icon={faMoneyBillWave} /> Bu oy tushum</div>
          <div className="kpi-value">{fmt(stats.this_month_income)} <span className="kpi-currency">so'm</span></div>
          <div className="kpi-sub" style={{ color: changeColor }}>
            <FontAwesomeIcon icon={change >= 0 ? faArrowTrendUp : faArrowTrendDown} />
            {' '}{changeSign}{change.toFixed(1)}% o'tgan oyga nisbatan
          </div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label"><FontAwesomeIcon icon={faMoneyBillWave} /> O'tgan oy tushum</div>
          <div className="kpi-value">{fmt(stats.last_month_income)} <span className="kpi-currency">so'm</span></div>
        </div>
      </div>

      {/* ── P&L Bu oy ── */}
      <div className="section-title" style={{ margin: '24px 0 12px', fontWeight: 700, fontSize: 15, color: '#374151' }}>
        Bu oy moliyaviy natija
      </div>
      <div className="kpi-grid" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))' }}>
        <div className="kpi-card" style={{ borderTop: '3px solid #22c55e' }}>
          <div className="kpi-label">Umumiy tushum</div>
          <div className="kpi-value" style={{ color: '#16a34a', fontSize: 20 }}>{fmt(stats.this_month_income)}</div>
          <div className="kpi-sub">so'm</div>
        </div>
        <div
          className="kpi-card kpi-card-link"
          style={{ borderTop: '3px solid #3b82f6', cursor: 'pointer' }}
          onClick={() => onNavigate('teacher_salaries')}
          title="Batafsil ko'rish"
        >
          <div className="kpi-label">O'qituvchi maoshi ↗</div>
          <div className="kpi-value" style={{ color: '#2563eb', fontSize: 20 }}>{fmt(stats.teacher_salary)}</div>
          <div className="kpi-sub">so'm · davomatga qarab</div>
        </div>
        <div
          className="kpi-card kpi-card-link"
          style={{ borderTop: '3px solid #f59e0b', cursor: 'pointer' }}
          onClick={() => onNavigate('expenses')}
          title="Batafsil ko'rish"
        >
          <div className="kpi-label">Tashqi xarajatlar ↗</div>
          <div className="kpi-value" style={{ color: '#d97706', fontSize: 20 }}>{fmt(stats.external_expenses)}</div>
          <div className="kpi-sub">so'm</div>
        </div>
        <div className="kpi-card" style={{ borderTop: '3px solid #ef4444' }}>
          <div className="kpi-label">Umumiy chiqim</div>
          <div className="kpi-value" style={{ color: '#dc2626', fontSize: 20 }}>{fmt(stats.total_expenses)}</div>
          <div className="kpi-sub">so'm</div>
        </div>
        <div className="kpi-card" style={{ borderTop: `3px solid ${netColor}`, background: netProfit >= 0 ? '#f0fdf4' : '#fef2f2' }}>
          <div className="kpi-label">Sof foyda</div>
          <div className="kpi-value" style={{ color: netColor, fontSize: 22, fontWeight: 800 }}>
            {netProfit >= 0 ? '' : '−'}{fmt(Math.abs(netProfit))}
          </div>
          <div className="kpi-sub" style={{ color: netColor }}>so'm</div>
        </div>
      </div>

      {/* ── Xarajatlar bo'limi ── */}
      <div className="chart-card" style={{ marginTop: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16, flexWrap: 'wrap', gap: 8 }}>
          <h2 style={{ margin: 0 }}>Tashqi xarajatlar</h2>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <select className="field-sm" value={expMonth} onChange={e => setExpMonth(Number(e.target.value))}>
              {MONTHS.map((m, i) => <option key={i} value={i + 1}>{m}</option>)}
            </select>
            <select className="field-sm" value={expYear} onChange={e => setExpYear(Number(e.target.value))}>
              {YEARS.map(y => <option key={y} value={y}>{y}</option>)}
            </select>
            <button className="button primary" onClick={openAddExp}>
              <FontAwesomeIcon icon={faPlus} /> Qo'shish
            </button>
          </div>
        </div>

        {expLoading ? (
          <div className="muted center">Yuklanmoqda...</div>
        ) : expenses.length > 0 ? (
          <>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Nomi</th>
                  <th style={{ textAlign: 'right' }}>Summa</th>
                  <th style={{ textAlign: 'right' }}>Amallar</th>
                </tr>
              </thead>
              <tbody>
                {expenses.map(e => (
                  <tr key={e.id}>
                    <td style={{ fontWeight: 500 }}>{e.name}</td>
                    <td style={{ textAlign: 'right', fontWeight: 600, color: '#dc2626' }}>{fmt(e.amount)} so'm</td>
                    <td>
                      <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
                        <button className="button small secondary" onClick={() => openEditExp(e)}><FontAwesomeIcon icon={faPen} /></button>
                        <button className="button small secondary" onClick={() => handleDeleteExp(e)}>
                          <FontAwesomeIcon icon={faTrash} style={{ color: '#ef4444' }} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr>
                  <td style={{ fontWeight: 700 }}>Jami</td>
                  <td style={{ textAlign: 'right', fontWeight: 700, color: '#dc2626' }}>{fmt(expTotal)} so'm</td>
                  <td />
                </tr>
              </tfoot>
            </table>
          </>
        ) : (
          <div className="muted center" style={{ padding: '20px 0' }}>
            {MONTHS[expMonth - 1]} {expYear} uchun xarajatlar yo'q
          </div>
        )}
      </div>

      {/* ── Monthly Chart ── */}
      <div className="chart-card">
        <h2>{year} yil daromadi</h2>
        <div className="bar-chart">
          {stats.monthly_history.map((m, i) => {
            const h = Math.max((parseFloat(m.total_income) / maxIncome) * 180, 4)
            const isCurrentMonth = m.month === new Date().getMonth() + 1 && m.year === new Date().getFullYear()
            return (
              <div key={i} className="bar-col">
                <div className="bar-amount">{m.total_income > 0 ? (Number(m.total_income) / 1000).toFixed(0) + 'k' : ''}</div>
                <div
                  className={`bar ${isCurrentMonth ? 'bar-current' : ''}`}
                  style={{ height: h }}
                  title={`${MONTHS_SHORT[m.month - 1]} ${m.year}: ${fmt(m.total_income)} so'm | Sof: ${fmt(m.net_profit)} so'm`}
                />
                <div className="bar-label">{MONTHS_SHORT[m.month - 1]}</div>
              </div>
            )
          })}
        </div>
      </div>

      {/* ── Monthly Table ── */}
      <div className="chart-card">
        <h2>Oylik statistika</h2>
        <div style={{ overflowX: 'auto' }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Oy</th>
                <th style={{ textAlign: 'right' }}>Tushum</th>
                <th style={{ textAlign: 'right' }}>O'qt. maoshi</th>
                <th style={{ textAlign: 'right' }}>Tashqi xarajat</th>
                <th style={{ textAlign: 'right' }}>Jami chiqim</th>
                <th style={{ textAlign: 'right' }}>Sof foyda</th>
                <th style={{ textAlign: 'center' }}>To'lovlar</th>
              </tr>
            </thead>
            <tbody>
              {[...stats.monthly_history].reverse().map((m, i) => {
                const np = parseFloat(m.net_profit || 0)
                return (
                  <tr key={i}>
                    <td>{MONTHS_SHORT[m.month - 1]} {m.year}</td>
                    <td style={{ textAlign: 'right', color: '#16a34a', fontWeight: 600 }}>{fmt(m.total_income)}</td>
                    <td style={{ textAlign: 'right', color: '#2563eb' }}>{fmt(m.teacher_salary)}</td>
                    <td style={{ textAlign: 'right', color: '#d97706' }}>{fmt(m.external_expenses)}</td>
                    <td style={{ textAlign: 'right', color: '#dc2626' }}>{fmt(m.total_expenses)}</td>
                    <td style={{ textAlign: 'right', fontWeight: 700, color: np >= 0 ? '#16a34a' : '#dc2626' }}>
                      {np >= 0 ? '' : '−'}{fmt(Math.abs(np))}
                    </td>
                    <td style={{ textAlign: 'center', color: '#6b7280' }}>{m.payment_count}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* ── Expense Modal ── */}
      {expModal && (
        <div className="modal-overlay" onClick={() => setExpModal(null)}>
          <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: 380 }}>
            <div className="modal-header">
              <h3>{expModal === 'add' ? 'Xarajat qo\'shish' : 'Xarajatni tahrirlash'}</h3>
              <button className="modal-close" onClick={() => setExpModal(null)}><FontAwesomeIcon icon={faXmark} /></button>
            </div>
            <div className="modal-body">
              <div className="form-group">
                <label className="form-label">Nomi *</label>
                <input className="form-input" value={expForm.name}
                  onChange={e => setExpForm(f => ({ ...f, name: e.target.value }))}
                  placeholder="Ijara, kommunal, reklama..." />
              </div>
              <div className="form-group">
                <label className="form-label">Summa (so'm) *</label>
                <input className="form-input" type="number" value={expForm.amount}
                  onChange={e => setExpForm(f => ({ ...f, amount: e.target.value }))}
                  placeholder="100000" />
              </div>
            </div>
            <div className="modal-footer">
              <button className="button secondary" onClick={() => setExpModal(null)}>Bekor</button>
              <button className="button primary" onClick={handleSaveExp} disabled={expSaving}>
                {expSaving ? 'Saqlanmoqda...' : 'Saqlash'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
