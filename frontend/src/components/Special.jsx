import { useEffect, useState } from 'react'
import { toast } from 'react-hot-toast'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faStar, faPlus, faTrash, faToggleOn, faToggleOff } from '@fortawesome/free-solid-svg-icons'
import {
  fetchSpecialDiscounts, createSpecialDiscount, updateSpecialDiscount, deleteSpecialDiscount,
  fetchStudents, fetchGroups,
} from '../api'

const MONTHS = ['Yanvar','Fevral','Mart','Aprel','May','Iyun','Iyul','Avgust','Sentyabr','Oktyabr','Noyabr','Dekabr']
const NOW = new Date()
const EMPTY = {
  student_id: '', group_id: '', kind: 'free_month',
  amount: '', month: NOW.getMonth() + 1, year: NOW.getFullYear(), reason: '',
}

export default function Special() {
  const [items, setItems] = useState([])
  const [students, setStudents] = useState([])
  const [groups, setGroups] = useState([])
  const [loading, setLoading] = useState(false)
  const [modal, setModal] = useState(false)
  const [form, setForm] = useState(EMPTY)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    load()
    fetchStudents({ page_size: 100 }).then(r => setStudents(r.items || []))
    fetchGroups({ page_size: 100 }).then(r => setGroups(r.items || []))
  }, [])

  async function load() {
    setLoading(true)
    try { setItems(await fetchSpecialDiscounts()) }
    catch { toast.error("Yuklab bo'lmadi") }
    finally { setLoading(false) }
  }

  async function handleSave() {
    if (!form.student_id) return toast.error("Talabani tanlang")
    if (form.kind === 'monthly' && (!form.amount || parseFloat(form.amount) <= 0)) {
      return toast.error("Chegirma summasini kiriting")
    }
    setSaving(true)
    try {
      await createSpecialDiscount({
        student_id: parseInt(form.student_id),
        group_id: form.group_id ? parseInt(form.group_id) : null,
        kind: form.kind,
        amount: form.kind === 'monthly' ? parseFloat(form.amount) : null,
        month: form.kind === 'free_month' ? parseInt(form.month) : null,
        year: form.kind === 'free_month' ? parseInt(form.year) : null,
        reason: form.reason || null,
      })
      toast.success("Chegirma berildi")
      setModal(false)
      setForm(EMPTY)
      load()
    } catch (e) { toast.error(e.message) }
    finally { setSaving(false) }
  }

  async function handleToggle(d) {
    try {
      await updateSpecialDiscount(d.id, { is_active: !d.is_active })
      toast.success(d.is_active ? "Chegirma to'xtatildi" : "Chegirma yoqildi")
      load()
    } catch (e) { toast.error(e.message) }
  }

  async function handleDelete(d) {
    if (!confirm(`${d.student_name} uchun chegirma o'chiriladi. Tasdiqlaysizmi?`)) return
    try {
      await deleteSpecialDiscount(d.id)
      toast.success("O'chirildi")
      load()
    } catch (e) { toast.error(e.message) }
  }

  function kindLabel(d) {
    if (d.kind === 'free_month') {
      return `${MONTHS[(d.month || 1) - 1]} ${d.year} — to'liq bepul`
    }
    return `Har oy ${Number(d.amount).toLocaleString()} so'm (butun kurs)`
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1><FontAwesomeIcon icon={faStar} className="page-icon" /> Special</h1>
        <button className="button primary" onClick={() => { setForm(EMPTY); setModal(true) }}>
          <FontAwesomeIcon icon={faPlus} /> Chegirma berish
        </button>
      </div>

      <p className="text-muted" style={{ fontSize: 13, marginTop: -8 }}>
        Bu yerdagi chegirmalar to'lov hisobiga bevosita ta'sir qiladi — qarzdorlik, Moliya va ota-ona ilovasida ham.
      </p>

      {loading ? (
        <div className="muted center py-8">Yuklanmoqda...</div>
      ) : (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Talaba</th>
                <th>Guruh</th>
                <th>Chegirma</th>
                <th>Sabab</th>
                <th>Kim berdi</th>
                <th>Holat</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {items.map((d, i) => (
                <tr key={d.id} className={!d.is_active ? 'row-inactive' : ''}>
                  <td className="text-muted">{i + 1}</td>
                  <td><strong>{d.student_name}</strong></td>
                  <td>{d.group_name || <span className="text-muted">Barcha guruhlar</span>}</td>
                  <td>
                    <span className="badge" style={{
                      background: d.kind === 'free_month' ? '#dcfce7' : '#dbeafe',
                      color: d.kind === 'free_month' ? '#16a34a' : '#1d4ed8',
                    }}>
                      {kindLabel(d)}
                    </span>
                  </td>
                  <td>{d.reason || <span className="text-muted">—</span>}</td>
                  <td className="text-muted">{d.created_by_name || '—'}</td>
                  <td>
                    <span className={`status-badge ${d.is_active ? 'active' : 'inactive'}`}>
                      {d.is_active ? 'Faol' : "To'xtatilgan"}
                    </span>
                  </td>
                  <td>
                    <button className="btn-icon" title={d.is_active ? "To'xtatish" : 'Yoqish'} onClick={() => handleToggle(d)}>
                      <FontAwesomeIcon icon={d.is_active ? faToggleOn : faToggleOff} />
                    </button>
                    <button className="btn-icon danger" title="O'chirish" onClick={() => handleDelete(d)}>
                      <FontAwesomeIcon icon={faTrash} />
                    </button>
                  </td>
                </tr>
              ))}
              {items.length === 0 && (
                <tr><td colSpan={8} className="muted center py-4">Chegirmalar yo'q</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {modal && (
        <div className="modal-overlay" onClick={() => setModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3><FontAwesomeIcon icon={faStar} /> Special chegirma</h3>
              <button className="modal-close" onClick={() => setModal(false)}>✕</button>
            </div>
            <div className="modal-body">
              <label>Talaba *</label>
              <select className="field" value={form.student_id} onChange={e => setForm(p => ({ ...p, student_id: e.target.value }))}>
                <option value="">— Tanlang —</option>
                {students.map(s => <option key={s.id} value={s.id}>{s.full_name} ({s.phone1})</option>)}
              </select>

              <label>Guruh</label>
              <select className="field" value={form.group_id} onChange={e => setForm(p => ({ ...p, group_id: e.target.value }))}>
                <option value="">Barcha guruhlar</option>
                {groups.map(g => <option key={g.id} value={g.id}>{g.name}</option>)}
              </select>

              <label>Chegirma turi *</label>
              <select className="field" value={form.kind} onChange={e => setForm(p => ({ ...p, kind: e.target.value }))}>
                <option value="free_month">To'liq 1 oylik (tanlangan oy bepul)</option>
                <option value="monthly">Oylik summa (butun kurs davomida)</option>
              </select>

              {form.kind === 'free_month' ? (
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
                      {[2025, 2026, 2027, 2028].map(y => <option key={y} value={y}>{y}</option>)}
                    </select>
                  </div>
                </div>
              ) : (
                <>
                  <label>Oylik chegirma summasi (so'm) *</label>
                  <input className="field" type="number" value={form.amount}
                    onChange={e => setForm(p => ({ ...p, amount: e.target.value }))} placeholder="100000" />
                  <p className="text-muted" style={{ fontSize: 12, margin: '4px 0 0' }}>
                    Har oy to'lovdan shu summa ayiriladi — chegirma to'xtatilguncha.
                  </p>
                </>
              )}

              <label>Sabab / izoh</label>
              <input className="field" value={form.reason} onChange={e => setForm(p => ({ ...p, reason: e.target.value }))} placeholder="Ixtiyoriy" />
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
