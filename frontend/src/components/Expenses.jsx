import { useEffect, useState } from 'react'
import { toast } from 'react-hot-toast'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faReceipt, faPlus, faPen, faTrash } from '@fortawesome/free-solid-svg-icons'
import { fetchExpenses, createExpense, updateExpense, deleteExpense, fetchExpenseStaffOptions } from '../api'
import DataTable, { RowActions } from './ui/DataTable'
import Modal from './ui/Modal'
import ConfirmDialog from './ui/ConfirmDialog'
import Badge from './ui/Badge'
import { Input, Select } from './ui/Field'
import { tashkentNow } from '../utils/datetime'

const MONTHS = ['Yanvar','Fevral','Mart','Aprel','May','Iyun','Iyul','Avgust','Sentyabr','Oktyabr','Noyabr','Dekabr']
const NOW = tashkentNow()
const YEARS = Array.from({ length: 5 }, (_, i) => NOW.getFullYear() - 2 + i)
const fmt = n => Number(n || 0).toLocaleString('uz-UZ')

function fmtDate(isoStr) {
  if (!isoStr) return '—'
  const d = new Date(isoStr)
  return d.toLocaleDateString('uz-UZ', { day: '2-digit', month: '2-digit', year: 'numeric' })
}

export default function Expenses({ currentUser }) {
  // Xarajat qo'shish — admin va hunter; tahrirlash/o'chirish faqat admin.
  const canAdd    = currentUser?.role === 'admin' || currentUser?.role === 'hunter'
  const canManage = currentUser?.role !== 'hunter'
  const [month, setMonth] = useState(NOW.getMonth() + 1)
  const [year,  setYear]  = useState(NOW.getFullYear())
  const [expenses, setExpenses] = useState([])
  const [loading,  setLoading]  = useState(false)
  const [modal,    setModal]    = useState(null)   // null | 'add' | expense obj
  const [form,     setForm]     = useState({ name: '', amount: '', description: '', category: 'other', staff_id: '' })
  const [saving,   setSaving]   = useState(false)
  const [staffOptions, setStaffOptions] = useState([])
  const [deleteTarget, setDeleteTarget] = useState(null)

  useEffect(() => { load() }, [month, year])
  useEffect(() => { if (canAdd) fetchExpenseStaffOptions().then(setStaffOptions).catch(() => {}) }, [canAdd])

  async function load() {
    setLoading(true)
    try { setExpenses(await fetchExpenses(month, year)) }
    catch { toast.error("Yuklab bo'lmadi") }
    finally { setLoading(false) }
  }

  function openAdd() {
    setForm({ name: '', amount: '', description: '', category: 'other', staff_id: '' })
    setModal('add')
  }

  function openEdit(e) {
    setForm({
      name: e.name, amount: String(e.amount), description: e.description || '',
      category: e.category || 'other', staff_id: e.staff_id ? String(e.staff_id) : '',
    })
    setModal(e)
  }

  async function handleSave() {
    if (!form.name.trim())                         { toast.error("Nom kiriting"); return }
    if (!form.amount || Number(form.amount) <= 0)  { toast.error("Summa kiriting"); return }
    if (form.category === 'salary' && !form.staff_id) { toast.error("Xodimni tanlang"); return }
    setSaving(true)
    try {
      const payload = {
        name: form.name,
        amount: parseFloat(form.amount),
        category: form.category,
        staff_id: form.category === 'salary' ? Number(form.staff_id) : null,
      }
      if (modal === 'add') {
        await createExpense({ ...payload, month, year })
        toast.success("Xarajat qo'shildi")
      } else {
        await updateExpense(modal.id, payload)
        toast.success("Saqlandi")
      }
      setModal(null)
      load()
    } catch (err) {
      toast.error(err.message || 'Xato')
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete() {
    try {
      await deleteExpense(deleteTarget.id)
      toast.success("O'chirildi")
      setDeleteTarget(null)
      load()
    } catch (err) {
      toast.error(err.message || 'Xato')
    }
  }

  const total = expenses.reduce((s, e) => s + parseFloat(e.amount), 0)

  const columns = [
    { key: 'name', header: 'Nomi / Sabab', sortable: true, render: e => <strong>{e.name}</strong> },
    {
      key: 'category', header: 'Turi', sortable: true,
      render: e => e.category === 'salary'
        ? <Badge variant="info" size="sm">Oylik — {e.staff_name || '—'}</Badge>
        : <span className="muted-sm">Oddiy</span>,
    },
    {
      key: 'amount', header: 'Summa', align: 'right', sortable: true,
      sortValue: e => Number(e.amount),
      // Sahifadagi HAR BIR qator xarajat — hammasini qizil qilish rangni
      // ma'nosiz qiladi. Qizil faqat pastdagi umumiy summada qoladi.
      render: e => <span className="amount">{fmt(e.amount)} so'm</span>,
    },
    { key: 'month', header: 'Oy', sortable: true, sortValue: e => e.year * 12 + e.month,
      render: e => <span className="text-muted">{MONTHS[e.month - 1]} {e.year}</span> },
    { key: 'created_at', header: 'Kiritilgan', sortable: true,
      render: e => <span className="muted-sm">{fmtDate(e.created_at)}</span> },
    ...(canManage ? [{
      key: 'actions', header: '', align: 'right', className: 'actions',
      render: e => (
        <RowActions>
          <button className="btn-icon" onClick={() => openEdit(e)} title="Tahrirlash" aria-label="Tahrirlash">
            <FontAwesomeIcon icon={faPen} />
          </button>
          <button className="btn-icon danger" onClick={() => setDeleteTarget(e)} title="O'chirish" aria-label="O'chirish">
            <FontAwesomeIcon icon={faTrash} />
          </button>
        </RowActions>
      ),
    }] : []),
  ]

  return (
    <div className="page">
      <div className="page-header">
        <div className="page-header-text">
          <h1><FontAwesomeIcon icon={faReceipt} className="page-icon" /> Tashqi xarajatlar</h1>
          <p className="page-subtitle">
            {MONTHS[month - 1]} {year} · {expenses.length} yozuv · jami{' '}
            <strong className="tone-danger">{fmt(total)} so'm</strong>
          </p>
        </div>
        {canAdd && (
          <div className="header-actions">
            <select className="field-sm" value={month} onChange={e => setMonth(Number(e.target.value))} aria-label="Oy">
              {MONTHS.map((m, i) => <option key={i} value={i + 1}>{m}</option>)}
            </select>
            <select className="field-sm" value={year} onChange={e => setYear(Number(e.target.value))} aria-label="Yil">
              {YEARS.map(y => <option key={y} value={y}>{y}</option>)}
            </select>
            <button className="button" onClick={openAdd}>
              <FontAwesomeIcon icon={faPlus} /> Qo'shish
            </button>
          </div>
        )}
      </div>

      <div className="chart-card is-flush">
        <DataTable
          columns={columns}
          rows={expenses}
          loading={loading}
          clientPageSize={25}
          empty={{
            icon: faReceipt,
            title: `${MONTHS[month - 1]} ${year} uchun xarajat yo'q`,
            description: 'Ijara, kommunal, reklama kabi xarajatlarni shu yerda yuriting.',
            action: canAdd && (
              <button className="button" onClick={openAdd}>
                <FontAwesomeIcon icon={faPlus} /> Qo'shish
              </button>
            ),
          }}
        />
        {expenses.length > 0 && (
          <div className="dash-exp-total">
            <span>Jami</span>
            <strong className="tone-danger">{fmt(total)} so'm</strong>
          </div>
        )}
      </div>

      <ConfirmDialog
        open={!!deleteTarget}
        title="Xarajatni o'chirish"
        message={deleteTarget ? `"${deleteTarget.name}" xarajat o'chirilsinmi?` : ''}
        detail="Bu oyning sof foydasi qayta hisoblanadi."
        confirmLabel="Ha, o'chirish"
        onConfirm={handleDelete}
        onClose={() => setDeleteTarget(null)}
      />

      <Modal
        open={!!modal}
        title={modal === 'add' ? "Xarajat qo'shish" : 'Xarajatni tahrirlash'}
        onClose={() => setModal(null)}
        size="sm"
        footer={
          <>
            <button className="button secondary" onClick={() => setModal(null)}>Bekor</button>
            <button className="button" onClick={handleSave} disabled={saving}>
              {saving ? 'Saqlanmoqda...' : 'Saqlash'}
            </button>
          </>
        }
      >
        <Input
          label="Nomi / Sabab" required value={form.name}
          onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
          placeholder="Ijara, kommunal, reklama..."
        />
        <Input
          label="Summa (so'm)" required type="number" value={form.amount}
          onChange={e => setForm(f => ({ ...f, amount: e.target.value }))}
          placeholder="500000"
        />
        {modal === 'add' && (
          <div className="field-row">
            <Select label="Oy" value={month} onChange={e => setMonth(Number(e.target.value))}>
              {MONTHS.map((m, i) => <option key={i} value={i + 1}>{m}</option>)}
            </Select>
            <Select label="Yil" value={year} onChange={e => setYear(Number(e.target.value))}>
              {YEARS.map(y => <option key={y} value={y}>{y}</option>)}
            </Select>
          </div>
        )}
        <Select
          label="Turi" value={form.category}
          onChange={e => setForm(f => ({ ...f, category: e.target.value }))}
        >
          <option value="other">Oddiy xarajat</option>
          <option value="salary">Xodim oyligi</option>
        </Select>
        {form.category === 'salary' && (
          <Select
            label="Qaysi xodimga" required value={form.staff_id}
            onChange={e => setForm(f => ({ ...f, staff_id: e.target.value }))}
          >
            <option value="">— Tanlang —</option>
            {staffOptions.map(s => <option key={s.id} value={s.id}>{s.full_name || s.username}</option>)}
          </Select>
        )}
      </Modal>

    </div>
  )
}
