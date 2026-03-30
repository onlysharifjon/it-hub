import { useEffect, useState } from 'react'
import { toast } from 'react-hot-toast'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faPlus, faTrash, faFileExcel, faCreditCard,
  faChevronDown, faFilter,
} from '@fortawesome/free-solid-svg-icons'
import { fetchPayments, createPayment, deletePayment, fetchStudents, fetchGroups, exportExcelUrl } from '../api'
import Pagination from './Pagination'

const MONTHS = ['Yanvar','Fevral','Mart','Aprel','May','Iyun','Iyul','Avgust','Sentyabr','Oktyabr','Noyabr','Dekabr']
const NOW = new Date()
const EMPTY = { student_id: '', group_id: '', amount: '', month: NOW.getMonth() + 1, year: NOW.getFullYear(), notes: '' }

export default function Payments() {
  const [data, setData] = useState({ items: [], meta: null })
  const [students, setStudents] = useState([])
  const [groups, setGroups] = useState([])
  const [loading, setLoading] = useState(false)
  const [modal, setModal] = useState(false)
  const [form, setForm] = useState(EMPTY)
  const [saving, setSaving] = useState(false)
  const [page, setPage] = useState(1)
  const [filter, setFilter] = useState({ month: NOW.getMonth() + 1, year: NOW.getFullYear() })

  useEffect(() => {
    fetchStudents({ page_size: 100 }).then(r => setStudents(r.items || []))
    fetchGroups().then(setGroups)
    load(filter, 1)
  }, [])

  async function load(f = filter, p = page) {
    setLoading(true)
    try {
      const res = await fetchPayments({ ...f, page: p, page_size: 25 })
      setData(res)
    } catch { toast.error("Yuklab bo'lmadi") }
    finally { setLoading(false) }
  }

  function applyFilter() {
    setPage(1)
    load(filter, 1)
  }

  function handlePageChange(p) {
    setPage(p)
    load(filter, p)
  }

  async function handleSave() {
    if (!form.student_id || !form.group_id || !form.amount) return toast.error("Barcha maydonlarni to'ldiring")
    setSaving(true)
    try {
      await createPayment({
        student_id: parseInt(form.student_id),
        group_id: parseInt(form.group_id),
        amount: parseFloat(form.amount),
        month: parseInt(form.month),
        year: parseInt(form.year),
        notes: form.notes || null,
      })
      setModal(false)
      setForm(EMPTY)
      toast.success("To'lov qo'shildi")
      load(filter, page)
    } catch (e) { toast.error(e.message) }
    finally { setSaving(false) }
  }

  async function handleDelete(id) {
    if (!confirm("To'lovni o'chirishni tasdiqlaysizmi?")) return
    try {
      await deletePayment(id)
      toast.success("O'chirildi")
      load(filter, page)
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
          <button className="button secondary" onClick={() => window.open(exportExcelUrl(filter.month, filter.year), '_blank')}>
            <FontAwesomeIcon icon={faFileExcel} /> Excel
          </button>
          <button className="button primary" onClick={() => { setForm(EMPTY); setModal(true) }}>
            <FontAwesomeIcon icon={faPlus} /> To'lov qo'shish
          </button>
        </div>
      </div>

      <div className="toolbar">
        <FontAwesomeIcon icon={faFilter} className="text-muted" />
        <select className="field-sm" value={filter.month} onChange={e => setFilter(p => ({ ...p, month: parseInt(e.target.value) }))}>
          {MONTHS.map((m, i) => <option key={i} value={i + 1}>{m}</option>)}
        </select>
        <select className="field-sm" value={filter.year} onChange={e => setFilter(p => ({ ...p, year: parseInt(e.target.value) }))}>
          {[2024, 2025, 2026, 2027].map(y => <option key={y} value={y}>{y}</option>)}
        </select>
        <button className="button secondary small" onClick={applyFilter}>Filtrlash</button>
        <div className="total-badge">
          Sahifada: <strong>{total.toLocaleString()} so'm</strong>
          {meta && <span className="text-muted"> ({meta.total} ta)</span>}
        </div>
      </div>

      {loading ? (
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
                    <td>{MONTHS[p.month - 1]} {p.year}</td>
                    <td>{new Date(p.paid_at).toLocaleDateString('uz')}</td>
                    <td>{p.notes || <span className="text-muted">—</span>}</td>
                    <td>
                      <button className="btn-icon danger" onClick={() => handleDelete(p.id)}>
                        <FontAwesomeIcon icon={faTrash} />
                      </button>
                    </td>
                  </tr>
                ))}
                {payments.length === 0 && (
                  <tr><td colSpan={8} className="muted center py-4">To'lovlar yo'q</td></tr>
                )}
              </tbody>
            </table>
          </div>
          <Pagination meta={meta} onPageChange={handlePageChange} />
        </>
      )}

      {modal && (
        <div className="modal-overlay" onClick={() => setModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3><FontAwesomeIcon icon={faCreditCard} /> Yangi to'lov</h3>
              <button className="modal-close" onClick={() => setModal(false)}>✕</button>
            </div>
            <div className="modal-body">
              <label>Talaba *</label>
              <select className="field" value={form.student_id} onChange={e => setForm(p => ({ ...p, student_id: e.target.value }))}>
                <option value="">— Tanlang —</option>
                {students.map(s => <option key={s.id} value={s.id}>{s.full_name} ({s.phone1})</option>)}
              </select>
              <label>Guruh *</label>
              <select className="field" value={form.group_id} onChange={e => setForm(p => ({ ...p, group_id: e.target.value }))}>
                <option value="">— Tanlang —</option>
                {groups.map(g => <option key={g.id} value={g.id}>{g.name}</option>)}
              </select>
              <label>Miqdor (so'm) *</label>
              <input className="field" type="number" value={form.amount} onChange={e => setForm(p => ({ ...p, amount: e.target.value }))} placeholder="500000" />
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
              <button className="button secondary" onClick={() => setModal(false)}>Bekor</button>
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
