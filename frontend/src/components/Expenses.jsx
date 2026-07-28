import { useEffect, useState } from 'react'
import { toast } from 'react-hot-toast'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faReceipt, faPlus, faPen, faTrash, faXmark,
} from '@fortawesome/free-solid-svg-icons'
import { fetchExpenses, createExpense, updateExpense, deleteExpense } from '../api'

const MONTHS = ['Yanvar','Fevral','Mart','Aprel','May','Iyun','Iyul','Avgust','Sentyabr','Oktyabr','Noyabr','Dekabr']
const NOW = new Date()
const fmt = n => Number(n || 0).toLocaleString()

function fmtDate(isoStr) {
  if (!isoStr) return '—'
  const d = new Date(isoStr)
  return d.toLocaleDateString('uz-UZ', { day: '2-digit', month: '2-digit', year: 'numeric' })
}

export default function Expenses() {
  const [month, setMonth] = useState(NOW.getMonth() + 1)
  const [year,  setYear]  = useState(NOW.getFullYear())
  const [expenses, setExpenses] = useState([])
  const [loading,  setLoading]  = useState(false)
  const [modal,    setModal]    = useState(null)   // null | 'add' | expense obj
  const [form,     setForm]     = useState({ name: '', amount: '', description: '' })
  const [saving,   setSaving]   = useState(false)

  useEffect(() => { load() }, [month, year])

  async function load() {
    setLoading(true)
    try { setExpenses(await fetchExpenses(month, year)) }
    catch { toast.error("Yuklab bo'lmadi") }
    finally { setLoading(false) }
  }

  function openAdd() {
    setForm({ name: '', amount: '', description: '' })
    setModal('add')
  }

  function openEdit(e) {
    setForm({ name: e.name, amount: String(e.amount), description: e.description || '' })
    setModal(e)
  }

  async function handleSave() {
    if (!form.name.trim())                         { toast.error("Nom kiriting"); return }
    if (!form.amount || Number(form.amount) <= 0)  { toast.error("Summa kiriting"); return }
    setSaving(true)
    try {
      if (modal === 'add') {
        await createExpense({
          name: form.name,
          amount: parseFloat(form.amount),
          month, year,
        })
        toast.success("Xarajat qo'shildi")
      } else {
        await updateExpense(modal.id, {
          name: form.name,
          amount: parseFloat(form.amount),
        })
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

  async function handleDelete(e) {
    if (!confirm(`"${e.name}" xarajatni o'chirishni tasdiqlaysizmi?`)) return
    try {
      await deleteExpense(e.id)
      toast.success("O'chirildi")
      load()
    } catch (err) {
      toast.error(err.message || 'Xato')
    }
  }

  const total = expenses.reduce((s, e) => s + parseFloat(e.amount), 0)

  return (
    <div className="page">
      <div className="page-header">
        <h1>
          <FontAwesomeIcon icon={faReceipt} className="page-icon" />
          Tashqi xarajatlar
        </h1>
        <button className="button primary" onClick={openAdd}>
          <FontAwesomeIcon icon={faPlus} /> Qo'shish
        </button>
      </div>

      {/* Filters */}
      <div className="toolbar">
        <select className="field-sm" value={month} onChange={e => setMonth(Number(e.target.value))}>
          {MONTHS.map((m, i) => <option key={i} value={i + 1}>{m}</option>)}
        </select>
        <select className="field-sm" value={year} onChange={e => setYear(Number(e.target.value))}>
          {[2024, 2025, 2026, 2027].map(y => <option key={y} value={y}>{y}</option>)}
        </select>
        {expenses.length > 0 && (
          <span style={{ marginLeft: 'auto', fontWeight: 600, color: '#dc2626', fontSize: 14 }}>
            Jami: {fmt(total)} so'm
          </span>
        )}
      </div>

      {loading ? (
        <div className="muted center py-8">Yuklanmoqda...</div>
      ) : (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Nomi / Sabab</th>
                <th style={{ textAlign: 'right' }}>Summa</th>
                <th>Oy</th>
                <th>Kiritilgan sana</th>
                <th style={{ textAlign: 'right' }}>Amallar</th>
              </tr>
            </thead>
            <tbody>
              {expenses.map((e, i) => (
                <tr key={e.id}>
                  <td className="text-muted">{i + 1}</td>
                  <td style={{ fontWeight: 500 }}>{e.name}</td>
                  <td style={{ textAlign: 'right', fontWeight: 600, color: '#dc2626' }}>
                    {fmt(e.amount)} so'm
                  </td>
                  <td className="text-muted">{MONTHS[e.month - 1]} {e.year}</td>
                  <td className="text-muted" style={{ fontSize: 12 }}>{fmtDate(e.created_at)}</td>
                  <td>
                    <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
                      <button className="button small secondary" onClick={() => openEdit(e)}>
                        <FontAwesomeIcon icon={faPen} />
                      </button>
                      <button className="button small secondary" onClick={() => handleDelete(e)}>
                        <FontAwesomeIcon icon={faTrash} style={{ color: '#ef4444' }} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {expenses.length === 0 && (
                <tr>
                  <td colSpan={6} className="muted center py-4">
                    {MONTHS[month - 1]} {year} uchun xarajatlar yo'q
                  </td>
                </tr>
              )}
            </tbody>
            {expenses.length > 0 && (
              <tfoot>
                <tr>
                  <td colSpan={2} style={{ fontWeight: 700 }}>Jami</td>
                  <td style={{ textAlign: 'right', fontWeight: 700, color: '#dc2626' }}>
                    {fmt(total)} so'm
                  </td>
                  <td colSpan={3} />
                </tr>
              </tfoot>
            )}
          </table>
        </div>
      )}

      {/* Modal */}
      {modal && (
        <div className="modal-overlay" onClick={() => setModal(null)}>
          <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: 400 }}>
            <div className="modal-header">
              <h3>{modal === 'add' ? "Xarajat qo'shish" : 'Xarajatni tahrirlash'}</h3>
              <button className="modal-close" onClick={() => setModal(null)}>
                <FontAwesomeIcon icon={faXmark} />
              </button>
            </div>
            <div className="modal-body">
              <div className="form-group">
                <label className="form-label">Nomi / Sabab *</label>
                <input
                  className="form-input"
                  type="text"
                  value={form.name}
                  onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                  placeholder="Ijara, kommunal, reklama..."
                />
              </div>
              <div className="form-group">
                <label className="form-label">Summa (so'm) *</label>
                <input
                  className="form-input"
                  type="number"
                  value={form.amount}
                  onChange={e => setForm(f => ({ ...f, amount: e.target.value }))}
                  placeholder="500000"
                />
              </div>
              {modal === 'add' && (
                <div className="form-group">
                  <label className="form-label">Oy</label>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <select className="form-input" value={month} onChange={e => setMonth(Number(e.target.value))}>
                      {MONTHS.map((m, i) => <option key={i} value={i + 1}>{m}</option>)}
                    </select>
                    <select className="form-input" style={{ maxWidth: 100 }} value={year} onChange={e => setYear(Number(e.target.value))}>
                      {[2024, 2025, 2026, 2027].map(y => <option key={y} value={y}>{y}</option>)}
                    </select>
                  </div>
                </div>
              )}
            </div>
            <div className="modal-footer">
              <button className="button secondary" onClick={() => setModal(null)}>Bekor</button>
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
