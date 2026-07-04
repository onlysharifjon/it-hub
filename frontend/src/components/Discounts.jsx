import { useEffect, useState } from 'react'
import { toast } from 'react-hot-toast'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faPlus, faPen, faTrash, faPercent } from '@fortawesome/free-solid-svg-icons'
import { fetchDiscounts, createDiscount, updateDiscount, deleteDiscount } from '../api'

const EMPTY = { name: '', discount_type: 'percent', value: '10' }

export default function Discounts() {
  const [discounts, setDiscounts] = useState([])
  const [loading, setLoading]     = useState(false)
  const [modal, setModal]         = useState(null)
  const [form, setForm]           = useState(EMPTY)
  const [saving, setSaving]       = useState(false)

  useEffect(() => { load() }, [])

  async function load() {
    setLoading(true)
    try { setDiscounts(await fetchDiscounts()) }
    catch { toast.error("Yuklab bo'lmadi") }
    finally { setLoading(false) }
  }

  function openAdd() { setForm(EMPTY); setModal('add') }
  function openEdit(d) {
    setForm({ name: d.name, discount_type: d.discount_type, value: String(d.value) })
    setModal(d)
  }

  async function handleSave() {
    if (!form.name.trim() || !form.value) return toast.error("Ism va qiymat majburiy")
    const val = parseFloat(form.value)
    if (isNaN(val) || val <= 0) return toast.error("Qiymat noto'g'ri")
    if (form.discount_type === 'percent' && val > 100) return toast.error("Foiz 100 dan oshmasligi kerak")
    setSaving(true)
    try {
      const payload = { name: form.name.trim(), discount_type: form.discount_type, value: val }
      if (modal === 'add') {
        await createDiscount(payload)
        toast.success("Chegirma qo'shildi")
      } else {
        await updateDiscount(modal.id, payload)
        toast.success('Saqlandi')
      }
      setModal(null)
      load()
    } catch (e) { toast.error(e.message) }
    finally { setSaving(false) }
  }

  async function handleDelete(d) {
    if (!confirm(`"${d.name}" chegirmani o'chirishni tasdiqlaysizmi?`)) return
    try {
      await deleteDiscount(d.id)
      toast.success("O'chirildi")
      load()
    } catch (e) { toast.error(e.message) }
  }

  async function handleToggle(d) {
    try {
      await updateDiscount(d.id, { is_active: !d.is_active })
      load()
    } catch { toast.error('Xatolik') }
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1><FontAwesomeIcon icon={faPercent} className="page-icon" /> Chegirmalar</h1>
        <button className="button primary" onClick={openAdd}>
          <FontAwesomeIcon icon={faPlus} /> Chegirma qo'shish
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
                <th>Nomi</th>
                <th>Turi</th>
                <th>Qiymati</th>
                <th>Holat</th>
                <th>Amallar</th>
              </tr>
            </thead>
            <tbody>
              {discounts.map((d, i) => (
                <tr key={d.id} className={!d.is_active ? 'row-inactive' : ''}>
                  <td className="text-muted">{i + 1}</td>
                  <td><strong>{d.name}</strong></td>
                  <td>
                    <span className={`status-badge ${d.discount_type === 'percent' ? 'active' : 'pending'}`}>
                      {d.discount_type === 'percent' ? 'Foizli' : 'Somonli'}
                    </span>
                  </td>
                  <td className="amount">
                    {d.discount_type === 'percent'
                      ? `${Number(d.value)}%`
                      : `${Number(d.value).toLocaleString()} so'm`}
                  </td>
                  <td>
                    <button
                      className={`status-badge ${d.is_active ? 'active' : 'inactive'}`}
                      style={{ cursor: 'pointer', border: 'none', background: 'none' }}
                      onClick={() => handleToggle(d)}
                    >
                      {d.is_active ? 'Faol' : 'Nofaol'}
                    </button>
                  </td>
                  <td className="actions">
                    <button className="btn-icon" onClick={() => openEdit(d)} title="Tahrirlash">
                      <FontAwesomeIcon icon={faPen} />
                    </button>
                    <button className="btn-icon danger" onClick={() => handleDelete(d)} title="O'chirish">
                      <FontAwesomeIcon icon={faTrash} />
                    </button>
                  </td>
                </tr>
              ))}
              {discounts.length === 0 && (
                <tr><td colSpan={6} className="muted center py-4">Chegirmalar yo'q</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {modal && (
        <div className="modal-overlay" onClick={() => setModal(null)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>{modal === 'add' ? 'Yangi chegirma' : 'Chegirmani tahrirlash'}</h3>
              <button className="modal-close" onClick={() => setModal(null)}>✕</button>
            </div>
            <div className="modal-body">
              <label>Chegirma nomi *</label>
              <input
                className="field"
                value={form.name}
                onChange={e => setForm(p => ({ ...p, name: e.target.value }))}
                placeholder="Masalan: Singling uchun, Erta ro'yxat, VIP..."
              />
              <label>Chegirma turi *</label>
              <select
                className="field"
                value={form.discount_type}
                onChange={e => setForm(p => ({ ...p, discount_type: e.target.value }))}
              >
                <option value="percent">Foizli (%)</option>
                <option value="fixed">Somonli (so'm)</option>
              </select>
              <label>
                {form.discount_type === 'percent' ? 'Foiz (%) *' : 'Miqdor (so\'m) *'}
              </label>
              <input
                className="field"
                type="number"
                min="0"
                max={form.discount_type === 'percent' ? 100 : undefined}
                value={form.value}
                onChange={e => setForm(p => ({ ...p, value: e.target.value }))}
                placeholder={form.discount_type === 'percent' ? '10' : '50000'}
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
