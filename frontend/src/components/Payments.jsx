import { PageIntro } from './ui/Workspace'
import { SummaryRow, ProgressRing, ViewTabs } from './ui/Workspace'
import { useEffect, useState } from 'react'
import { toast } from 'react-hot-toast'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faPlus, faTrash, faFileExcel, faCreditCard,
  faFilter, faPrint, faMoneyBillWave, faPen,
  faTriangleExclamation, faList, faBolt, faBullseye,
} from '@fortawesome/free-solid-svg-icons'
import {
  fetchPayments, createPayment, updatePayment, deletePayment, fetchStudents, fetchGroups,
  exportExcelUrl, receiptUrl, openDownload, fetchPaymentExpected, fetchStudentPaymentSummary,
} from '../api'
import DateFilter from './DateFilter'
import DataTable, { RowActions } from './ui/DataTable'
import ConfirmDialog from './ui/ConfirmDialog'
import Badge from './ui/Badge'
import { Metric, MetricStrip } from './ui/Metric'
import Modal from './ui/Modal'
import { Input, Select } from './ui/Field'
import { tashkentNow } from '../utils/datetime'

const MONTHS = ['Yanvar','Fevral','Mart','Aprel','May','Iyun','Iyul','Avgust','Sentyabr','Oktyabr','Noyabr','Dekabr']
const NOW = tashkentNow()
const YEARS = Array.from({ length: 5 }, (_, i) => NOW.getFullYear() - 2 + i)
const fmtn = n => Number(n || 0).toLocaleString('uz-UZ')

const EMPTY = { student_id: '', group_id: '', amount: '', month: NOW.getMonth() + 1, year: NOW.getFullYear(), notes: '', via_sales: false }

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
  const [voidTarget, setVoidTarget] = useState(null)             // bekor qilinayotgan to'lov

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
        via_sales: false,
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
    if (parseFloat(form.amount) <= 0) return toast.error("Miqdor musbat bo'lishi kerak")
    setSaving(true)
    try {
      if (editing) {
        await updatePayment(editing, {
          amount: parseFloat(form.amount),
          month: parseInt(form.month),
          year: parseInt(form.year),
          notes: form.notes || null,
          via_sales: !!form.via_sales,
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
          via_sales: !!form.via_sales,
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
      via_sales: !!p.via_sales,
    })
    setModal(true)
  }

  async function handleVoid() {
    try {
      await deletePayment(voidTarget.id)
      toast.success("To'lov bekor qilindi")
      setVoidTarget(null)
      afterPaymentChange()
    } catch (e) { toast.error(e.message) }
  }

  const payments = data.items || []
  const meta = data.meta
  const total = payments.reduce((s, p) => s + parseFloat(p.amount), 0)

  // ── Ustunlar ──────────────────────────────────────────────────────────
  const paymentColumns = [
    {
      key: 'student_name', header: 'Talaba', sortable: true,
      render: p => (
        <span className="cell-copy">
          <strong>{p.student_name}</strong>
          {p.via_sales && (
            <Badge variant="success" size="sm" title="Sales orqali jalb qilingan">
              <FontAwesomeIcon icon={faBullseye} /> Sales
            </Badge>
          )}
        </span>
      ),
    },
    { key: 'group_name', header: 'Guruh', sortable: true },
    {
      key: 'amount', header: 'Miqdor', align: 'right', sortable: true,
      sortValue: p => Number(p.amount),
      render: p => <span className="amount is-in">{fmtn(p.amount)} so'm</span>,
    },
    {
      key: 'status', header: 'Holat', sortable: true,
      render: p => p.status === 'paid'
        ? <Badge variant="success" size="sm">To'landi</Badge>
        : p.status === 'partial'
          ? <Badge variant="warning" size="sm">Qoldi: {fmtn(p.remaining)}</Badge>
          : <span className="text-muted">—</span>,
    },
    {
      key: 'period', header: 'Oy / Yil', sortable: true,
      sortValue: p => p.year * 12 + p.month,
      render: p => <span className="text-muted">{MONTHS[p.month - 1]} {p.year}</span>,
    },
    {
      key: 'paid_at', header: 'Sana', sortable: true,
      render: p => <span className="muted-sm">{new Date(p.paid_at).toLocaleDateString('uz-UZ')}</span>,
    },
    { key: 'notes', header: 'Izoh', render: p => p.notes ? <span className="cell-clamp">{p.notes}</span> : <span className="text-muted">—</span> },
    {
      key: 'actions', header: '', align: 'right', className: 'actions',
      render: p => (
        <RowActions>
          <button className="btn-icon" title="Chek ko'rish" aria-label="Chek ko'rish"
            onClick={() => openDownload(receiptUrl(p.id)).catch(e => toast.error(e.message || "Yuklab bo'lmadi"))}>
            <FontAwesomeIcon icon={faPrint} />
          </button>
          {isAdmin && (
            <>
              <button className="btn-icon" title="Tahrirlash" aria-label="Tahrirlash" onClick={() => handleEdit(p)}>
                <FontAwesomeIcon icon={faPen} />
              </button>
              <button className="btn-icon danger" title="To'lovni bekor qilish" aria-label="To'lovni bekor qilish"
                onClick={() => setVoidTarget(p)}>
                <FontAwesomeIcon icon={faTrash} />
              </button>
            </>
          )}
        </RowActions>
      ),
    },
  ]

  const debtorColumns = [
    {
      key: 'full_name', header: 'Talaba', sortable: true,
      render: s => (
        <>
          <strong>{s.full_name}</strong>
          <div className="muted-sm">{s.phone1}</div>
        </>
      ),
    },
    {
      key: 'groups', header: 'Guruh(lar)',
      render: s => (
        <div className="chip-row">
          {(s.group_names || []).map((n, gi) => <span key={gi} className="tag">{n}</span>)}
        </div>
      ),
    },
    {
      key: 'owed_month', header: "Oylik to'lov", align: 'right', sortable: true,
      sortValue: s => Number(s.owed_month || 0),
      render: s => <span className="num">{fmtn(s.owed_month)} so'm</span>,
    },
    {
      key: 'paid_month', header: "To'langan", align: 'right', sortable: true,
      sortValue: s => Number(s.paid_month || 0),
      render: s => <span className="amount is-in">{fmtn(s.paid_month)} so'm</span>,
    },
    {
      key: 'debt', header: 'Qarz', align: 'right', sortable: true,
      sortValue: s => Number(s.debt || 0),
      render: s => <span className="amount is-out">{fmtn(s.debt)} so'm</span>,
    },
    {
      key: 'actions', header: '', align: 'right', className: 'actions',
      render: s => (
        <button className="btn-sm primary" disabled={quickPayLoading === s.id} onClick={() => quickPay(s)}>
          <FontAwesomeIcon icon={faBolt} /> {quickPayLoading === s.id ? '...' : "To'liq to'lash"}
        </button>
      ),
    },
  ]

  const collectionPct = totalExpected > 0 ? (totalPaidMonth / totalExpected) * 100 : null

  return (
    <div className="page ledger-studio">
      <PageIntro title={<>To'lovlar</>} description={<>{MONTHS[filter.month - 1]} {filter.year} · to'lov qabul qilish va qarzdorlik</>} actions={<><div className="header-actions">
          <select className="field-sm" value={filter.month} aria-label="Oy"
            onChange={e => setFilter(p => ({ ...p, month: parseInt(e.target.value) }))}>
            {MONTHS.map((m, i) => <option key={i} value={i + 1}>{m}</option>)}
          </select>
          <select className="field-sm" value={filter.year} aria-label="Yil"
            onChange={e => setFilter(p => ({ ...p, year: parseInt(e.target.value) }))}>
            {YEARS.map(y => <option key={y} value={y}>{y}</option>)}
          </select>
          <button className="button secondary" onClick={() => openDownload(exportExcelUrl(filter.month, filter.year)).catch(e => toast.error(e.message || "Yuklab bo'lmadi"))}>
            <FontAwesomeIcon icon={faFileExcel} /> Excel
          </button>
          <button className="button" onClick={() => { setEditing(null); setForm(EMPTY); setModal(true) }}>
            <FontAwesomeIcon icon={faPlus} /> To'lov qo'shish
          </button>
        </div></>} />

      {/* ── Oyning holati: bitta zich qator, karta devori emas ── */}
      <section className="ledger-overview"><div className="ledger-balance"><span className="studio-eyebrow">Oylik to‘lov yig‘ilishi</span><strong>{statsLoading ? '—' : fmtn(totalPaidMonth)}<small>so‘m</small></strong><div><ProgressRing value={collectionPct || 0} label="To‘lov yig‘ilishi" size={52} /><p>{collectionPct == null ? 'Hali ma’lumot yo‘q' : collectionPct.toFixed(0) + '% yig‘ildi'}<span>{MONTHS[filter.month - 1]} {filter.year}</span></p></div></div><div className="ledger-balance-details"><div><span>Kutilayotgan to‘lov</span><strong>{statsLoading ? '—' : fmtn(totalExpected)} <small>so‘m</small></strong></div><button onClick={() => setView('debtors')}><span>Qarzdorlik <small>{debtors.length} talaba →</small></span><strong className="tone-danger">{statsLoading ? '—' : fmtn(totalDebt)} <small>so‘m</small></strong></button><div><span>Sahifadagi to‘lovlar</span><strong>{fmtn(total)} <small>so‘m</small></strong></div></div></section>
      <ViewTabs value={view} onChange={setView} items={[{ key: 'list', label: 'To‘lovlar tarixi', count: meta?.total }, { key: 'debtors', label: 'Qarzdorlar', count: debtors.length }]} />
      <section className="studio-section ledger-records"><div className="studio-section-head"><div><h2>{view === 'list' ? 'To‘lovlar tarixi' : 'To‘lov kutilmoqda'}</h2><p>{MONTHS[filter.month - 1]} {filter.year} · {view === 'list' ? 'Barcha kirimlar va cheklar' : 'Talabalar bo‘yicha qarzdorlik'}</p></div></div>
      <div className="toolbar">
        {view === 'list' && (
          <>
            <DateFilter value={dateFilter} onChange={handleDateFilter} />
            <button className="button secondary small" onClick={applyFilter}>
              <FontAwesomeIcon icon={faFilter} /> Filtrlash
            </button>
          </>
        )}
      </div>

      {view === 'debtors' ? (
        <DataTable
          columns={debtorColumns}
          rows={debtors}
          loading={statsLoading}
          rowKey={s => s.id}
          clientPageSize={25}
          densityToggle densityKey="debtors"
          empty={{
            icon: faMoneyBillWave,
            title: 'Qarzdorlar yo\'q',
            description: `${MONTHS[filter.month - 1]} ${filter.year} uchun barcha to'lovlar yig'ilgan.`,
          }}
        />
      ) : (
        <DataTable
          columns={paymentColumns}
          rows={payments}
          loading={loading}
          meta={meta}
          onPageChange={handlePageChange}
          densityToggle densityKey="payments"
          empty={{
            icon: faCreditCard,
            title: "To'lovlar yo'q",
            description: 'Tanlangan davr uchun yozuv topilmadi — oy/yil yoki sana filtrini o\'zgartiring.',
          }}
        />
      )}

      </section>

      <ConfirmDialog
        open={!!voidTarget}
        title="To'lovni bekor qilish"
        message={voidTarget ? `${voidTarget.student_name} — ${fmtn(voidTarget.amount)} so'm to'lov bekor qilinsinmi?` : ''}
        detail="Talaba yana to'lanmagan holatga qaytadi va qarzdorlar ro'yxatiga tushadi."
        confirmLabel="Ha, bekor qilish"
        onConfirm={handleVoid}
        onClose={() => setVoidTarget(null)}
      />

      <Modal
        open={modal}
        title={editing ? "To'lovni tahrirlash" : "Yangi to'lov"}
        onClose={() => { setModal(false); setEditing(null) }}
        footer={
          <>
            <button className="button secondary" onClick={() => { setModal(false); setEditing(null) }}>Bekor</button>
            <button className="button" onClick={handleSave} disabled={saving}>
              {saving ? 'Saqlanmoqda...' : 'Saqlash'}
            </button>
          </>
        }
      >
        <Select label="Talaba" required value={form.student_id} disabled={!!editing}
          onChange={e => setForm(p => ({ ...p, student_id: e.target.value }))}>
          <option value="">— Tanlang —</option>
          {students.map(s => <option key={s.id} value={s.id}>{s.full_name} ({s.phone1})</option>)}
        </Select>

        {(() => {
          const selectedStudent = students.find(s => String(s.id) === String(form.student_id))
          // Tahrirlashda joriy to'lov o'zi hisoblagan bo'lishi mumkin — shu holda
          // hali ham o'chirib qo'yish (belgini olib tashlash) imkoni qoldiriladi.
          const alreadyCredited = !!selectedStudent?.sales_credited && !(editing && form.via_sales)
          return (
            <div className="ui-field">
              <span className="ui-field-label">Sales atributsiyasi</span>
              <button
                type="button"
                className={`button ${form.via_sales || alreadyCredited ? '' : 'secondary'} small`}
                disabled={alreadyCredited}
                onClick={() => setForm(p => ({ ...p, via_sales: !p.via_sales }))}
              >
                <FontAwesomeIcon icon={faBullseye} />{' '}
                {alreadyCredited ? 'Sales — hisoblangan' : form.via_sales ? 'Sales — belgilandi' : 'Sales orqali kelgan'}
              </button>
              <span className="ui-field-hint">
                {alreadyCredited
                  ? "Bu talaba uchun Sales'ga allaqachon hisoblangan — takroran hisoblanmaydi."
                  : "Talabani sales rolidagi xodim jalb qilgan bo'lsa belgilang. Hisob bir marta yuritiladi."}
              </span>
            </div>
          )
        })()}

        <Select label="Guruh" required value={form.group_id} disabled={!!editing}
          onChange={e => setForm(p => ({ ...p, group_id: e.target.value }))}>
          <option value="">— Tanlang —</option>
          {groups.map(g => <option key={g.id} value={g.id}>{g.name}</option>)}
        </Select>

        <div className="ui-field">
          <span className="ui-field-label">Miqdor (so'm) <span className="ui-field-req">*</span></span>
          <div className="field-row">
            <input className="field" type="number" min="1" value={form.amount}
              onChange={e => setForm(p => ({ ...p, amount: e.target.value }))} placeholder="500000" />
            {expected && expected.remaining > 0 && (
              <button type="button" className="button secondary" style={{ flex: 'none' }}
                title="To'liq summani yozish"
                onClick={() => setForm(p => ({ ...p, amount: String(expected.remaining) }))}>
                <FontAwesomeIcon icon={faMoneyBillWave} /> To'liq
              </button>
            )}
          </div>
        </div>

        {expected && expected.expected > 0 && (() => {
          const entered = parseFloat(form.amount) || 0
          const left = Math.max(0, expected.remaining - entered)
          return (
            <dl className="pay-preview">
              <div><dt>To'liq oylik</dt><dd>{fmtn(expected.expected)} so'm</dd></div>
              <div><dt>Avval to'langan</dt><dd>{fmtn(expected.paid)} so'm</dd></div>
              <div className={left > 0 ? 'is-partial' : 'is-full'}>
                <dt>{left > 0 ? 'Qoladi' : 'Natija'}</dt>
                <dd>{left > 0 ? `${fmtn(left)} so'm` : "To'liq to'lanadi"}</dd>
              </div>
            </dl>
          )
        })()}

        <div className="field-row">
          <Select label="Oy" required value={form.month}
            onChange={e => setForm(p => ({ ...p, month: e.target.value }))}>
            {MONTHS.map((m, i) => <option key={i} value={i + 1}>{m}</option>)}
          </Select>
          <Select label="Yil" required value={form.year}
            onChange={e => setForm(p => ({ ...p, year: e.target.value }))}>
            {YEARS.map(y => <option key={y} value={y}>{y}</option>)}
          </Select>
        </div>

        <Input label="Izoh" value={form.notes}
          onChange={e => setForm(p => ({ ...p, notes: e.target.value }))} placeholder="Ixtiyoriy" />
      </Modal>

    </div>
  )
}
