import { useEffect, useState } from 'react'
import { toast } from 'react-hot-toast'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faPen, faTrash, faToggleOn, faToggleOff, faPlus,
  faMagnifyingGlass, faUserGraduate, faPhone,
} from '@fortawesome/free-solid-svg-icons'
import { faTelegram as faTelegramBrand } from '@fortawesome/free-brands-svg-icons'
import { fetchStudents, createStudent, updateStudent, deleteStudent } from '../api'
import Pagination from './Pagination'

const EMPTY = { full_name: '', phone1: '', phone2: '', telegram_id: '', notes: '' }

export default function Students() {
  const [data, setData] = useState({ items: [], meta: null })
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)
  const [modal, setModal] = useState(null)
  const [form, setForm] = useState(EMPTY)
  const [saving, setSaving] = useState(false)

  useEffect(() => { load(search, page) }, [page])

  async function load(s = search, p = page) {
    setLoading(true)
    try {
      const res = await fetchStudents({ search: s || undefined, page: p, page_size: 20 })
      setData(res)
    } catch { toast.error("Yuklab bo'lmadi") }
    finally { setLoading(false) }
  }

  function handleSearch(e) {
    const val = e.target.value
    setSearch(val)
    setPage(1)
    if (val.length === 0 || val.length >= 2) load(val, 1)
  }

  function handlePageChange(p) {
    setPage(p)
    load(search, p)
  }

  function openAdd() { setForm(EMPTY); setModal('add') }
  function openEdit(s) {
    setForm({ full_name: s.full_name, phone1: s.phone1, phone2: s.phone2 || '', telegram_id: s.telegram_id || '', notes: s.notes || '' })
    setModal(s)
  }

  async function handleSave() {
    if (!form.full_name.trim() || !form.phone1.trim()) return toast.error("Ism va telefon majburiy")
    setSaving(true)
    try {
      if (modal === 'add') {
        await createStudent(form)
        toast.success("Talaba qo'shildi")
      } else {
        await updateStudent(modal.id, form)
        toast.success('Saqlandi')
      }
      setModal(null)
      load(search, page)
    } catch (e) { toast.error(e.message) }
    finally { setSaving(false) }
  }

  async function handleDelete(id) {
    if (!confirm("O'chirishni tasdiqlaysizmi?")) return
    try {
      await deleteStudent(id)
      toast.success("O'chirildi")
      load(search, page)
    } catch (e) { toast.error(e.message) }
  }

  async function handleToggle(s) {
    try {
      await updateStudent(s.id, { is_active: !s.is_active })
      load(search, page)
    } catch { toast.error('Xatolik') }
  }

  const students = data.items || []
  const meta = data.meta

  return (
    <div className="page">
      <div className="page-header">
        <h1>
          <FontAwesomeIcon icon={faUserGraduate} className="page-icon" />
          Talabalar
        </h1>
        <button className="button primary" onClick={openAdd}>
          <FontAwesomeIcon icon={faPlus} /> Talaba qo'shish
        </button>
      </div>

      <div className="toolbar">
        <div className="search-wrap">
          <FontAwesomeIcon icon={faMagnifyingGlass} className="search-icon" />
          <input
            className="search-input"
            placeholder="Ism yoki telefon..."
            value={search}
            onChange={handleSearch}
          />
        </div>
        {meta && <span className="muted">Jami: {meta.total} ta talaba</span>}
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
                  <th>Ism Familiya</th>
                  <th><FontAwesomeIcon icon={faPhone} /> Telefon 1</th>
                  <th><FontAwesomeIcon icon={faPhone} /> Telefon 2</th>
                  <th>Telegram</th>
                  <th>Guruhlar</th>
                  <th>Holat</th>
                  <th>Amallar</th>
                </tr>
              </thead>
              <tbody>
                {students.map((s, i) => (
                  <tr key={s.id} className={!s.is_active ? 'row-inactive' : ''}>
                    <td className="text-muted">{(page - 1) * 20 + i + 1}</td>
                    <td><strong>{s.full_name}</strong></td>
                    <td>{s.phone1}</td>
                    <td>{s.phone2 || <span className="text-muted">—</span>}</td>
                    <td>
                      {s.telegram_id
                        ? <span className="tg-badge"><FontAwesomeIcon icon={faTelegramBrand} /> {s.telegram_id}</span>
                        : <span className="text-muted">—</span>}
                    </td>
                    <td><span className="badge">{s.group_count || 0}</span></td>
                    <td>
                      <span className={`status-badge ${s.is_active ? 'active' : 'inactive'}`}>
                        {s.is_active ? 'Faol' : 'Nofaol'}
                      </span>
                    </td>
                    <td className="actions">
                      <button className="btn-icon" onClick={() => openEdit(s)} title="Tahrirlash">
                        <FontAwesomeIcon icon={faPen} />
                      </button>
                      <button className="btn-icon" onClick={() => handleToggle(s)} title={s.is_active ? "O'chirish" : "Faollashtirish"}>
                        <FontAwesomeIcon icon={s.is_active ? faToggleOn : faToggleOff} style={{ color: s.is_active ? '#22c55e' : '#ef4444' }} />
                      </button>
                      <button className="btn-icon danger" onClick={() => handleDelete(s.id)} title="O'chirish">
                        <FontAwesomeIcon icon={faTrash} />
                      </button>
                    </td>
                  </tr>
                ))}
                {students.length === 0 && (
                  <tr><td colSpan={8} className="muted center py-4">Talabalar topilmadi</td></tr>
                )}
              </tbody>
            </table>
          </div>
          <Pagination meta={meta} onPageChange={handlePageChange} />
        </>
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
              <label><FontAwesomeIcon icon={faPhone} /> Telefon 1 *</label>
              <input className="field" value={form.phone1} onChange={e => setForm(p => ({ ...p, phone1: e.target.value }))} placeholder="+998901234567" />
              <label><FontAwesomeIcon icon={faPhone} /> Telefon 2</label>
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
