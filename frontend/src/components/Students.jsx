import { useEffect, useState } from 'react'
import { toast } from 'react-hot-toast'
import { fetchStudents, createStudent, updateStudent, deleteStudent } from '../api'

const EMPTY = { full_name: '', phone1: '', phone2: '', telegram_id: '', notes: '' }

export default function Students() {
  const [students, setStudents] = useState([])
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(false)
  const [modal, setModal] = useState(null) // null | 'add' | student obj
  const [form, setForm] = useState(EMPTY)
  const [saving, setSaving] = useState(false)

  useEffect(() => { load() }, [])

  async function load(s = search) {
    setLoading(true)
    try {
      const data = await fetchStudents(s ? { search: s } : {})
      setStudents(data)
    } catch { toast.error("Yuklab bo'lmadi") }
    finally { setLoading(false) }
  }

  function openAdd() { setForm(EMPTY); setModal('add') }
  function openEdit(s) { setForm({ full_name: s.full_name, phone1: s.phone1, phone2: s.phone2 || '', telegram_id: s.telegram_id || '', notes: s.notes || '' }); setModal(s) }

  async function handleSave() {
    if (!form.full_name.trim() || !form.phone1.trim()) return toast.error("Ism va telefon majburiy")
    setSaving(true)
    try {
      if (modal === 'add') {
        const s = await createStudent(form)
        setStudents(prev => [s, ...prev])
        toast.success("Talaba qo'shildi")
      } else {
        const s = await updateStudent(modal.id, form)
        setStudents(prev => prev.map(x => x.id === s.id ? s : x))
        toast.success('Saqlandi')
      }
      setModal(null)
    } catch (e) { toast.error(e.message) }
    finally { setSaving(false) }
  }

  async function handleDelete(id) {
    if (!confirm("O'chirishni tasdiqlaysizmi?")) return
    try {
      await deleteStudent(id)
      setStudents(prev => prev.filter(s => s.id !== id))
      toast.success("O'chirildi")
    } catch (e) { toast.error(e.message) }
  }

  async function handleToggle(s) {
    try {
      const updated = await updateStudent(s.id, { is_active: !s.is_active })
      setStudents(prev => prev.map(x => x.id === updated.id ? updated : x))
    } catch { toast.error('Xatolik') }
  }

  function handleSearch(e) {
    setSearch(e.target.value)
    if (e.target.value.length === 0 || e.target.value.length >= 2) load(e.target.value)
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1>Talabalar</h1>
        <button className="button primary" onClick={openAdd}>+ Talaba qo'shish</button>
      </div>

      <div className="toolbar">
        <input className="search-input" placeholder="Ism yoki telefon bo'yicha qidirish..." value={search} onChange={handleSearch} />
        <span className="muted">{students.length} ta talaba</span>
      </div>

      {loading ? <div className="muted center">Yuklanmoqda...</div> : (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Ism Familiya</th>
                <th>Telefon 1</th>
                <th>Telefon 2</th>
                <th>Telegram</th>
                <th>Guruhlar</th>
                <th>Holat</th>
                <th>Amallar</th>
              </tr>
            </thead>
            <tbody>
              {students.map((s, i) => (
                <tr key={s.id} className={!s.is_active ? 'row-inactive' : ''}>
                  <td>{i + 1}</td>
                  <td><strong>{s.full_name}</strong></td>
                  <td>{s.phone1}</td>
                  <td>{s.phone2 || '—'}</td>
                  <td>{s.telegram_id ? `@${s.telegram_id}` : '—'}</td>
                  <td><span className="badge">{s.group_count || 0}</span></td>
                  <td>
                    <span className={`status-badge ${s.is_active ? 'active' : 'inactive'}`}>
                      {s.is_active ? 'Faol' : 'Nofaol'}
                    </span>
                  </td>
                  <td className="actions">
                    <button className="btn-icon" onClick={() => openEdit(s)} title="Tahrirlash">✏️</button>
                    <button className="btn-icon" onClick={() => handleToggle(s)} title={s.is_active ? "O'chirish" : "Faollashtirish"}>
                      {s.is_active ? '🔴' : '🟢'}
                    </button>
                    <button className="btn-icon danger" onClick={() => handleDelete(s.id)} title="O'chirish">🗑️</button>
                  </td>
                </tr>
              ))}
              {students.length === 0 && (
                <tr><td colSpan={8} className="muted center">Talabalar topilmadi</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {modal && (
        <div className="modal-overlay" onClick={() => setModal(null)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>{modal === 'add' ? "Yangi talaba" : "Talabani tahrirlash"}</h3>
              <button className="modal-close" onClick={() => setModal(null)}>✕</button>
            </div>
            <div className="modal-body">
              <label>Ism Familiya *</label>
              <input className="field" value={form.full_name} onChange={e => setForm(p => ({ ...p, full_name: e.target.value }))} placeholder="To'liq ism" />
              <label>Telefon 1 *</label>
              <input className="field" value={form.phone1} onChange={e => setForm(p => ({ ...p, phone1: e.target.value }))} placeholder="+998901234567" />
              <label>Telefon 2</label>
              <input className="field" value={form.phone2} onChange={e => setForm(p => ({ ...p, phone2: e.target.value }))} placeholder="Ixtiyoriy" />
              <label>Telegram ID</label>
              <input className="field" value={form.telegram_id} onChange={e => setForm(p => ({ ...p, telegram_id: e.target.value }))} placeholder="username (@ siz)" />
              <label>Izoh</label>
              <textarea className="field" rows={2} value={form.notes} onChange={e => setForm(p => ({ ...p, notes: e.target.value }))} placeholder="Qo'shimcha ma'lumot..." />
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
