import { useEffect, useState } from 'react'
import { toast } from 'react-hot-toast'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faPlus, faPen, faTrash, faTag } from '@fortawesome/free-solid-svg-icons'
import { fetchTariffs, createTariff, updateTariff, deleteTariff } from '../api'

const EMPTY = { name: '', price: '100000', description: '' }

export default function Tariffs() {
  const [tariffs, setTariffs] = useState([])
  const [loading, setLoading] = useState(false)
  const [modal, setModal] = useState(null)
  const [form, setForm] = useState(EMPTY)
  const [saving, setSaving] = useState(false)

  useEffect(() => { load() }, [])

  async function load() {
    setLoading(true)
    try { setTariffs(await fetchTariffs()) }
    catch { toast.error("Yuklab bo'lmadi") }
    finally { setLoading(false) }
  }

  function openAdd() { setForm(EMPTY); setModal('add') }
  function openEdit(t) {
    setForm({ name: t.name, price: String(t.price), description: t.description || '' })
    setModal(t)
  }

  async function handleSave() {
    if (!form.name.trim() || !form.price) return toast.error("Ism va narx majburiy")
    setSaving(true)
    try {
      const payload = { name: form.name, price: parseFloat(form.price), description: form.description || null }
      if (modal === 'add') {
        await createTariff(payload)
        toast.success("Tarif qo'shildi")
      } else {
        await updateTariff(modal.id, payload)
        toast.success('Saqlandi')
      }
      setModal(null)
      load()
    } catch (e) { toast.error(e.message) }
    finally { setSaving(false) }
  }

  async function handleDelete(t) {
    if (!confirm(`"${t.name}" tarifni o'chirishni tasdiqlaysizmi?`)) return
    try {
      await deleteTariff(t.id)
      toast.success("O'chirildi")
      load()
    } catch (e) { toast.error(e.message) }
  }

  async function handleToggle(t) {
    try {
      await updateTariff(t.id, { is_active: !t.is_active })
      load()
    } catch { toast.error('Xatolik') }
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1><FontAwesomeIcon icon={faTag} className="page-icon" /> Tariflar</h1>
        <button className="button primary" onClick={openAdd}>
          <FontAwesomeIcon icon={faPlus} /> Tarif qo'shish
        </button>
      </div>

      {loading ? (
        <div className="muted center py-8">Yuklanmoqda...</div>
      ) : (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Tarif nomi</th>
                <th>Narx (so'm/oy)</th>
                <th>Tavsif</th>
                <th>Holat</th>
                <th>Amallar</th>
              </tr>
            </thead>
            <tbody>
              {tariffs.map((t, i) => (
                <tr key={t.id} className={!t.is_active ? 'row-inactive' : ''}>
                  <td className="text-muted">{i + 1}</td>
                  <td><strong>{t.name}</strong></td>
                  <td className="amount">{Number(t.price).toLocaleString()} so'm</td>
                  <td>{t.description || <span className="text-muted">—</span>}</td>
                  <td>
                    <span className={`status-badge ${t.is_active ? 'active' : 'inactive'}`}>
                      {t.is_active ? 'Faol' : 'Nofaol'}
                    </span>
                  </td>
                  <td className="actions">
                    <button className="btn-icon" onClick={() => openEdit(t)} title="Tahrirlash">
                      <FontAwesomeIcon icon={faPen} />
                    </button>
                    <button className="btn-icon danger" onClick={() => handleDelete(t)} title="O'chirish">
                      <FontAwesomeIcon icon={faTrash} />
                    </button>
                  </td>
                </tr>
              ))}
              {tariffs.length === 0 && (
                <tr><td colSpan={6} className="muted center py-4">Tariflar yo'q</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {modal && (
        <div className="modal-overlay" onClick={() => setModal(null)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>{modal === 'add' ? 'Yangi tarif' : 'Tarifni tahrirlash'}</h3>
              <button className="modal-close" onClick={() => setModal(null)}>✕</button>
            </div>
            <div className="modal-body">
              <label>Tarif nomi *</label>
              <input
                className="field"
                value={form.name}
                onChange={e => setForm(p => ({ ...p, name: e.target.value }))}
                placeholder="Masalan: Standart, Premium, 3 oylik..."
              />
              <label>Narx (so'm/oy) *</label>
              <input
                className="field"
                type="number"
                value={form.price}
                onChange={e => setForm(p => ({ ...p, price: e.target.value }))}
                placeholder="100000"
              />
              <label>Tavsif</label>
              <textarea
                className="field"
                rows={2}
                value={form.description}
                onChange={e => setForm(p => ({ ...p, description: e.target.value }))}
                placeholder="Qo'shimcha ma'lumot..."
              />
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
