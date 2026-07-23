import { useEffect, useState } from 'react'
import { toast } from 'react-hot-toast'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faPercent, faPlus, faPen, faTrash } from '@fortawesome/free-solid-svg-icons'
import { fetchDiscounts, createDiscount, updateDiscount, deleteDiscount } from '../api'

const EMPTY = { name: '', percent: '', description: '' }

export default function Discounts() {
  const [items, setItems] = useState([])
  const [modal, setModal] = useState(null)
  const [form, setForm] = useState(EMPTY)
  const [saving, setSaving] = useState(false)

  useEffect(() => { load() }, [])

  async function load() {
    try { setItems(await fetchDiscounts()) } catch { toast.error("Yuklab bo'lmadi") }
  }

  function openAdd() { setForm(EMPTY); setModal('add') }
  function openEdit(d) { setForm({ name: d.name, percent: d.percent, description: d.description || '' }); setModal(d) }

  async function handleSave() {
    if (!form.name.trim() || !form.percent) return toast.error("Ism va foiz majburiy")
    setSaving(true)
    try {
      if (modal === 'add') { await createDiscount({ ...form, percent: Number(form.percent) }); toast.success("Qo'shildi") }
      else { await updateDiscount(modal.id, { ...form, percent: Number(form.percent) }); toast.success("Saqlandi") }
      setModal(null); load()
    } catch (e) { toast.error(e.message) }
    finally { setSaving(false) }
  }

  async function handleDelete(d) {
    if (!confirm(`"${d.name}" o'chirilsinmi?`)) return
    try { await deleteDiscount(d.id); load() } catch (e) { toast.error(e.message) }
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1><FontAwesomeIcon icon={faPercent} className="page-icon" /> Chegirmalar</h1>
        <button className="button primary" onClick={openAdd}><FontAwesomeIcon icon={faPlus} /> Qo'shish</button>
      </div>

      <div className="table-wrap">
        <table className="data-table">
          <thead><tr><th>#</th><th>Nomi</th><th>Foiz</th><th>Izoh</th><th>Amallar</th></tr></thead>
          <tbody>
            {items.map((d, i) => (
              <tr key={d.id}>
                <td className="text-muted">{i + 1}</td>
                <td><strong>{d.name}</strong></td>
                <td><span className="badge">{d.percent}%</span></td>
                <td><span className="text-muted">{d.description || '—'}</span></td>
                <td className="actions">
                  <button className="btn-icon" onClick={() => openEdit(d)}><FontAwesomeIcon icon={faPen} /></button>
                  <button className="btn-icon danger" onClick={() => handleDelete(d)}><FontAwesomeIcon icon={faTrash} /></button>
                </td>
              </tr>
            ))}
            {items.length === 0 && <tr><td colSpan={5} className="muted center py-4">Chegirmalar yo'q</td></tr>}
          </tbody>
        </table>
      </div>

      {modal && (
        <div className="modal-overlay" onClick={() => setModal(null)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>{modal === 'add' ? 'Yangi chegirma' : 'Chegirmani tahrirlash'}</h3>
              <button className="modal-close" onClick={() => setModal(null)}>✕</button>
            </div>
            <div className="modal-body">
              <label>Nomi *</label>
              <input className="field" value={form.name} onChange={e => setForm(p => ({ ...p, name: e.target.value }))} placeholder="Chegirma nomi" />
              <label>Foiz (%) *</label>
              <input className="field" type="number" min={1} max={100} value={form.percent} onChange={e => setForm(p => ({ ...p, percent: e.target.value }))} placeholder="10" />
              <label>Izoh</label>
              <textarea className="field" rows={2} value={form.description} onChange={e => setForm(p => ({ ...p, description: e.target.value }))} placeholder="Ixtiyoriy" />
            </div>
            <div className="modal-footer">
              <button className="button secondary" onClick={() => setModal(null)}>Bekor</button>
              <button className="button primary" onClick={handleSave} disabled={saving}>{saving ? 'Saqlanmoqda...' : 'Saqlash'}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
