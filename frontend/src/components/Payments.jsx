import { useEffect, useState } from 'react'
import { toast } from 'react-hot-toast'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faPlus, faTrash, faFileExcel, faCreditCard,
  faChevronDown, faFilter, faPrint, faMoneyBillWave, faPen,
  faTriangleExclamation, faList, faBolt,
} from '@fortawesome/free-solid-svg-icons'
import {
  fetchPayments, createPayment, updatePayment, deletePayment, fetchStudents, fetchGroups,
  exportExcelUrl, receiptUrl, openDownload, fetchPaymentExpected, fetchStudentPaymentSummary,
} from '../api'
import Pagination from './Pagination'
import DateFilter from './DateFilter'

const MONTHS = ['Yanvar','Fevral','Mart','Aprel','May','Iyun','Iyul','Avgust','Sentyabr','Oktyabr','Noyabr','Dekabr']
const NOW = new Date()
const EMPTY = { student_id: '', group_id: '', amount: '', month: NOW.getMonth() + 1, year: NOW.getFullYear(), notes: '' }

export default function Payments({ currentUser }) {
  const isAdmin = currentUser?.role === 'admin'
  const [view, setView] = useState('list')   // 'list' | 'debtors'
  const [data, setData] = useState({ items: [], meta: null })
  const [students, setStudents] = useState([])
  const [groups, setGroups] = useState([])
  const [loading, setLoading] = useState(false)
  const [modal, setModal] = useState(false)
  const [editing, setEditing] = useState(null)   // tahrirlanayotgan to'lov id'si
  const [form, setForm] = useState(EMPTY)
  const [saving, setSaving] = useState(false)
  const [expected, setExpected] = useState(null)   // { expected, paid, remaining }
  const [page, setPage] = useState(1)
  const [filter, setFilter] = useState({ month: NOW.getMonth() + 1, year: NOW.getFullYear() })
  const [dateFilter, setDateFilter] = useState({ preset: 'all', date_from: '', date_to: '' })

  // Oylik holat (statistika kartalari + Qarzdorlar bo'limi) — filter.month/year'ga bog'liq
  const [monthStudents, setMonthStudents] = useState([])
  const [statsLoading, setStatsLoading] = useState(true)
  const [quickPayLoading, setQuickPayLoading] = useState(null)   // student_id

  useEffect(() => {
    fetchStudents({ page_size: 100 }).then(r => setStudents(r.items || []))
    fetchGroups({ page_size: 100 }).then(r => setGroups(r.items || []))
    load(filter, dateFilter, 1)
  }, [])

  useEffect(() => { loadStats(filter.month, filter.year) }, [filter.month, filter.year])

  async function loadStats(month = filter.month, year = filter.year) {
    setStatsLoading(true)
    try {
      const r = await fetchStudents({ is_active: true, month, year, page_size: 100 })
      setMonthStudents(r.items || [])
    } catch { /* jim — statistika ixtiyoriy */ }
    finally { setStatsLoading(false) }
  }

  const debtors = monthStudents
    .filter(s => s.payment_status === 'debtor' || s.payment_status === 'partial')
    .sort((a, b) => Number(b.debt || 0) - Number(a.debt || 0))
  const totalDebt = debtors.reduce((sum, s) => sum + Number(s.debt || 0), 0)
  const totalExpected = monthStudents.reduce((sum, s) => sum + Number(s.owed_month || 0), 0)
  const totalPaidMonth = monthStudents.reduce((sum, s) => sum + Number(s.paid_month || 0), 0)

  async function quickPay(student) {
    setQuickPayLoading(student.id)
    try {
      const sum = await fetchStudentPaymentSummary(student.id, { month: filter.month, year: filter.year })
      const g = sum.groups.find(g => Number(g.remaining) > 0) || sum.groups[0]
      if (!g) return toast.error("Talaba faol guruhda emas")
      setEditing(null)
      setForm({
        student_id: String(student.id),
        group_id: String(g.group_id),
        amount: String(Math.round(g.remaining)),
        month: filter.month,
        year: filter.year,
        notes: '',
      })
      setModal(true)
    } catch (e) { toast.error(e.message) }
    finally { setQuickPayLoading(null) }
  }

  async function afterPaymentChange() {
    load(filter, dateFilter, page)
    loadStats(filter.month, filter.year)
  }

  useEffect(() => {
    const { student_id, group_id, month, year } = form
    if (modal && student_id && group_id && month && year) {
      fetchPaymentExpected({ student_id, group_id, month, year })
        .then(setExpected)
        .catch(() => setExpected(null))
    } else {
      setExpected(null)
    }
  }, [modal, form.student_id, form.group_id, form.month, form.year])

  async function load(f = filter, df = dateFilter, p = page) {
    setLoading(true)
    try {
      const res = await fetchPayments({
        ...f,
        date_from: df.date_from || undefined,
        date_to: df.date_to || undefined,
        page: p, page_size: 25,
      })
      setData(res)
    } catch { toast.error("Yuklab bo'lmadi") }
    finally { setLoading(false) }
  }

  function applyFilter() {
    setPage(1)
    load(filter, dateFilter, 1)
  }

  function handleDateFilter(df) {
    setDateFilter(df)
    setPage(1)
    load(filter, df, 1)
  }

  function handlePageChange(p) {
    setPage(p)
    load(filter, dateFilter, p)
  }

  async function handleSave() {
    if (!form.student_id || !form.group_id || !form.amount) return toast.error("Barcha maydonlarni to'ldiring")
    setSaving(true)
    try {
      if (editing) {
        await updatePayment(editing, {
          amount: parseFloat(form.amount),
          month: parseInt(form.month),
          year: parseInt(form.year),
          notes: form.notes || null,
        })
        toast.success("To'lov yangilandi")
      } else {
        await createPayment({
          student_id: parseInt(form.student_id),
          group_id: parseInt(form.group_id),
          amount: parseFloat(form.amount),
          month: parseInt(form.month),
          year: parseInt(form.year),
          notes: form.notes || null,
        })
        toast.success("To'lov qo'shildi")
      }
      setModal(false)
      setEditing(null)
      setForm(EMPTY)
      afterPaymentChange()
    } catch (e) { toast.error(e.message) }
    finally { setSaving(false) }
  }

  function handleEdit(p) {
    setEditing(p.id)
    setForm({
      student_id: String(p.student_id),
      group_id: String(p.group_id),
      amount: String(p.amount),
      month: p.month,
      year: p.year,
      notes: p.notes || '',
    })
    setModal(true)
  }

  async function handleDelete(id) {
    if (!confirm("To'lov bekor qilinadi va talaba yana to'lanmagan holatga qaytadi. Tasdiqlaysizmi?")) return
    try {
      await deletePayment(id)
      toast.success("To'lov bekor qilindi")
      afterPaymentChange()
    } catch (e) { toast.error(e.message) }
  }

  const payments = data.items || []
  const meta = data.meta
  const total = payments.reduce((s, p) => s + parseFloat(p.amount), 0)

  return (
    <div className="page">
      <div className="page-header">
        <h1>
          <FontAwesomeIcon icon={faCreditCard} className="page-icon" />
          To'lovlar
        </h1>
        <div className="header-actions">
          <button className="button secondary" onClick={() => openDownload(exportExcelUrl(filter.month, filter.year))}>
            <FontAwesomeIcon icon={faFileExcel} /> Excel
          </button>
          <button className="button primary" onClick={() => { setEditing(null); setForm(EMPTY); setModal(true) }}>
            <FontAwesomeIcon icon={faPlus} /> To'lov qo'shish
          </button>
        </div>
      </div>

      <div className="kpi-grid">
        <div className="kpi-card" style={{ borderTop: '3px solid #dc2626' }}>
          <div className="kpi-label"><FontAwesomeIcon icon={faTriangleExclamation} /> Jami qarzdorlik</div>
          <div className="kpi-value" style={{ color: '#dc2626' }}>
            {statsLoading ? '—' : totalDebt.toLocaleString()} <span className="kpi-currency">so'm</span>
          </div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label"><FontAwesomeIcon icon={faTriangleExclamation} /> Qarzdorlar soni</div>
          <div className="kpi-value">{statsLoading ? '—' : debtors.length}</div>
        </div>
        <div className="kpi-card" style={{ borderTop: '3px solid #16a34a' }}>
          <div className="kpi-label"><FontAwesomeIcon icon={faMoneyBillWave} /> Jami to'langan (oy)</div>
          <div className="kpi-value" style={{ color: '#16a34a' }}>
            {statsLoading ? '—' : totalPaidMonth.toLocaleString()} <span className="kpi-currency">so'm</span>
          </div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label"><FontAwesomeIcon icon={faCreditCard} /> Kutilayotgan (oy)</div>
          <div className="kpi-value">
            {statsLoading ? '—' : totalExpected.toLocaleString()} <span className="kpi-currency">so'm</span>
          </div>
        </div>
      </div>

      <div className="toolbar">
        <button className={`button small ${view === 'list' ? 'primary' : 'secondary'}`} onClick={() => setView('list')}>
          <FontAwesomeIcon icon={faList} /> Barcha to'lovlar
        </button>
        <button className={`button small ${view === 'debtors' ? 'primary' : 'secondary'}`} onClick={() => setView('debtors')}>
          <FontAwesomeIcon icon={faTriangleExclamation} /> Qarzdorlar {!statsLoading && `(${debtors.length})`}
        </button>
      </div>

      <div className="toolbar">
        <FontAwesomeIcon icon={faFilter} className="text-muted" />
        <select className="field-sm" value={filter.month} onChange={e => setFilter(p => ({ ...p, month: parseInt(e.target.value) }))}>
          {MONTHS.map((m, i) => <option key={i} value={i + 1}>{m}</option>)}
        </select>
        <select className="field-sm" value={filter.year} onChange={e => setFilter(p => ({ ...p, year: parseInt(e.target.value) }))}>
          {[2024, 2025, 2026, 2027].map(y => <option key={y} value={y}>{y}</option>)}
        </select>
        {view === 'list' && <button className="button secondary small" onClick={applyFilter}>Filtrlash</button>}
        {view === 'list' && (
          <div className="total-badge">
            Sahifada: <strong>{total.toLocaleString()} so'm</strong>
            {meta && <span className="text-muted"> ({meta.total} ta)</span>}
          </div>
        )}
      </div>
      {view === 'list' && (
        <div className="toolbar">
          <DateFilter value={dateFilter} onChange={handleDateFilter} />
        </div>
      )}

      {view === 'debtors' ? (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Talaba</th>
                <th>Guruh(lar)</th>
                <th>Oylik to'lov</th>
                <th>To'langan</th>
                <th>Qarz</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {statsLoading ? (
                <tr><td colSpan={7} className="muted center py-4">Yuklanmoqda...</td></tr>
              ) : debtors.length === 0 ? (
                <tr><td colSpan={7} className="muted center py-4">Bu oy uchun qarzdorlar yo'q 🎉</td></tr>
              ) : debtors.map((s, i) => (
                <tr key={s.id}>
                  <td className="text-muted">{i + 1}</td>
                  <td><strong>{s.full_name}</strong><div className="text-muted" style={{ fontSize: 12 }}>{s.phone1}</div></td>
                  <td>
                    {(s.group_names || []).map((n, gi) => <span key={gi} className="badge" style={{ marginRight: 4 }}>{n}</span>)}
                  </td>
                  <td className="amount">{Number(s.owed_month || 0).toLocaleString()} so'm</td>
                  <td className="amount">{Number(s.paid_month || 0).toLocaleString()} so'm</td>
                  <td className="amount" style={{ color: '#dc2626', fontWeight: 700 }}>{Number(s.debt || 0).toLocaleString()} so'm</td>
                  <td>
                    <button className="button primary small" disabled={quickPayLoading === s.id} onClick={() => quickPay(s)}>
                      <FontAwesomeIcon icon={faBolt} /> {quickPayLoading === s.id ? 'Yuklanmoqda...' : "To'liq to'lash"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : loading ? (
        <div className="muted center py-8">Yuklanmoqda...</div>
      ) : (
        <>
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Talaba</th>
                  <th>Guruh</th>
                  <th>Miqdor</th>
                  <th>Holat</th>
                  <th>Oy / Yil</th>
                  <th>Sana</th>
                  <th>Izoh</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {payments.map((p, i) => (
                  <tr key={p.id}>
                    <td className="text-muted">{(page - 1) * 25 + i + 1}</td>
                    <td>{p.student_name}</td>
                    <td>{p.group_name}</td>
                    <td className="amount">{Number(p.amount).toLocaleString()} so'm</td>
                    <td>
                      {p.status === 'paid'
                        ? <span className="badge" style={{ background: '#dcfce7', color: '#16a34a' }}>To'landi</span>
                        : p.status === 'partial'
                          ? <span className="badge" style={{ background: '#fef3c7', color: '#d97706' }}>Qoldi: {Number(p.remaining || 0).toLocaleString()}</span>
                          : <span className="text-muted">—</span>}
                    </td>
                    <td>{MONTHS[p.month - 1]} {p.year}</td>
                    <td>{new Date(p.paid_at).toLocaleDateString('uz')}</td>
                    <td>{p.notes || <span className="text-muted">—</span>}</td>
                    <td>
                      <button
                        className="btn-icon"
                        title="Chek ko'rish"
                        onClick={() => openDownload(receiptUrl(p.id))}
                      >
                        <FontAwesomeIcon icon={faPrint} />
                      </button>
                      {isAdmin && (
                        <>
                          <button className="btn-icon" title="Tahrirlash" onClick={() => handleEdit(p)}>
                            <FontAwesomeIcon icon={faPen} />
                          </button>
                          <button className="btn-icon danger" title="To'lovni bekor qilish" onClick={() => handleDelete(p.id)}>
                            <FontAwesomeIcon icon={faTrash} />
                          </button>
                        </>
                      )}
                    </td>
                  </tr>
                ))}
                {payments.length === 0 && (
                  <tr><td colSpan={9} className="muted center py-4">To'lovlar yo'q</td></tr>
                )}
              </tbody>
            </table>
          </div>
          <Pagination meta={meta} onPageChange={handlePageChange} />
        </>
      )}

      {modal && (
        <div className="modal-overlay" onClick={() => { setModal(false); setEditing(null) }}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3><FontAwesomeIcon icon={faCreditCard} /> {editing ? "To'lovni tahrirlash" : "Yangi to'lov"}</h3>
              <button className="modal-close" onClick={() => { setModal(false); setEditing(null) }}>✕</button>
            </div>
            <div className="modal-body">
              <label>Talaba *</label>
              <select className="field" value={form.student_id} disabled={!!editing} onChange={e => setForm(p => ({ ...p, student_id: e.target.value }))}>
                <option value="">— Tanlang —</option>
                {students.map(s => <option key={s.id} value={s.id}>{s.full_name} ({s.phone1})</option>)}
              </select>
              <label>Guruh *</label>
              <select className="field" value={form.group_id} disabled={!!editing} onChange={e => setForm(p => ({ ...p, group_id: e.target.value }))}>
                <option value="">— Tanlang —</option>
                {groups.map(g => <option key={g.id} value={g.id}>{g.name}</option>)}
              </select>
              <label>Miqdor (so'm) *</label>
              <div style={{ display: 'flex', gap: 8 }}>
                <input className="field" style={{ flex: 1 }} type="number" value={form.amount} onChange={e => setForm(p => ({ ...p, amount: e.target.value }))} placeholder="500000" />
                {expected && expected.remaining > 0 && (
                  <button type="button" className="button secondary" title="To'liq summani yozish"
                    onClick={() => setForm(p => ({ ...p, amount: String(expected.remaining) }))}>
                    <FontAwesomeIcon icon={faMoneyBillWave} /> To'liq
                  </button>
                )}
              </div>
              {expected && expected.expected > 0 && (() => {
                const entered = parseFloat(form.amount) || 0
                const left = Math.max(0, expected.remaining - entered)
                return (
                  <div style={{ margin: '8px 0 2px', fontSize: 13, lineHeight: 1.7 }}>
                    <div>To'liq oylik: <strong>{expected.expected.toLocaleString()} so'm</strong></div>
                    <div>Avval to'langan: <strong>{expected.paid.toLocaleString()} so'm</strong></div>
                    <div style={{ color: left > 0 ? '#d97706' : '#16a34a', fontWeight: 700 }}>
                      {left > 0 ? `Qoladi: ${left.toLocaleString()} so'm` : "To'liq to'lanadi ✓"}
                    </div>
                  </div>
                )
              })()}
              <div className="row-2">
                <div>
                  <label>Oy *</label>
                  <select className="field" value={form.month} onChange={e => setForm(p => ({ ...p, month: e.target.value }))}>
                    {MONTHS.map((m, i) => <option key={i} value={i + 1}>{m}</option>)}
                  </select>
                </div>
                <div>
                  <label>Yil *</label>
                  <select className="field" value={form.year} onChange={e => setForm(p => ({ ...p, year: e.target.value }))}>
                    {[2024, 2025, 2026, 2027].map(y => <option key={y} value={y}>{y}</option>)}
                  </select>
                </div>
              </div>
              <label>Izoh</label>
              <input className="field" value={form.notes} onChange={e => setForm(p => ({ ...p, notes: e.target.value }))} placeholder="Ixtiyoriy" />
            </div>
            <div className="modal-footer">
              <button className="button secondary" onClick={() => { setModal(false); setEditing(null) }}>Bekor</button>
              <button className="button primary" onClick={handleSave} disabled={saving}>
                {saving ? 'Saqlanmoqda...' : 'Saqlash'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
