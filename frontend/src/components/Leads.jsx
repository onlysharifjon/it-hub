import { useEffect, useState } from 'react'
import { toast } from 'react-hot-toast'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faPlus, faMagnifyingGlass, faPhone, faCircle,
  faPen, faTrash, faFilter,
} from '@fortawesome/free-solid-svg-icons'
import { fetchLeads, createLead, updateLeadStatus, deleteLead } from '../api'

const STATUS_META = {
  new:       { label: 'Yangi',        color: '#6366f1', bg: '#eef2ff' },
  called:    { label: "Qo'ng'iroq",   color: '#0369a1', bg: '#f0f9ff' },
  will_come: { label: 'Keladi',       color: '#16a34a', bg: '#dcfce7' },
  rejected:  { label: 'Rad etildi',   color: '#dc2626', bg: '#fee2e2' },
  callback:  { label: 'Qayta ring',   color: '#d97706', bg: '#fef3c7' },
  enrolled:  { label: "Ro'yxatda",    color: '#0f766e', bg: '#ccfbf1' },
}

const COURSES = [
  { key: '',          label: 'Kurs tanlang' },
  { key: 'foundation',label: 'Foundation' },
  { key: 'frontend',  label: 'Frontend' },
  { key: 'backend',   label: 'Backend' },
]

const EMPTY_FORM = { full_name: '', phone: '', course_interest: '', notes: '' }

export default function Leads({ currentUser }) {
  const isHunter     = currentUser?.role === 'hunter'
  const isCallCenter = currentUser?.role === 'call_center'
  const isAdmin      = currentUser?.role === 'admin'

  const [leads, setLeads]       = useState([])
  const [loading, setLoading]   = useState(false)
  const [search, setSearch]     = useState('')
  const [filterStatus, setFilterStatus] = useState('')

  // Add lead modal (hunter / admin)
  const [addModal, setAddModal] = useState(false)
  const [form, setForm]         = useState(EMPTY_FORM)
  const [saving, setSaving]     = useState(false)

  // Status update modal (call_center / admin)
  const [statusModal, setStatusModal] = useState(null)   // lead object
  const [statusForm, setStatusForm]   = useState({ status: '', callback_at: '', notes: '' })

  useEffect(() => { load() }, [])

  async function load() {
    setLoading(true)
    try {
      const data = await fetchLeads({ search: search || undefined, status: filterStatus || undefined })
      setLeads(data)
    } catch { toast.error("Yuklab bo'lmadi") }
    finally { setLoading(false) }
  }

  function handleSearch(e) {
    const val = e.target.value
    setSearch(val)
  }
  async function applySearch(e) {
    if (e.key === 'Enter') await load()
  }

  async function applyFilter(s) {
    setFilterStatus(s)
    setLoading(true)
    try {
      const data = await fetchLeads({ search: search || undefined, status: s || undefined })
      setLeads(data)
    } catch { toast.error("Yuklab bo'lmadi") }
    finally { setLoading(false) }
  }

  async function handleAdd() {
    if (!form.full_name.trim() || !form.phone.trim()) return toast.error('Ism va telefon majburiy')
    setSaving(true)
    try {
      await createLead(form)
      toast.success("Lid qo'shildi")
      setAddModal(false)
      setForm(EMPTY_FORM)
      load()
    } catch (e) { toast.error(e.message) }
    finally { setSaving(false) }
  }

  function openStatusModal(lead) {
    setStatusModal(lead)
    setStatusForm({ status: lead.status, callback_at: lead.callback_at ? lead.callback_at.slice(0, 16) : '', notes: lead.notes || '' })
  }

  async function handleStatusSave() {
    if (!statusForm.status) return toast.error('Holat tanlang')
    const needsTime = ['will_come', 'callback'].includes(statusForm.status)
    if (needsTime && !statusForm.callback_at) return toast.error('Vaqtni kiriting')
    setSaving(true)
    try {
      await updateLeadStatus(statusModal.id, {
        status: statusForm.status,
        callback_at: statusForm.callback_at || null,
        notes: statusForm.notes || null,
      })
      toast.success('Holat yangilandi')
      setStatusModal(null)
      load()
    } catch (e) { toast.error(e.message) }
    finally { setSaving(false) }
  }

  async function handleDelete(lead) {
    if (!confirm(`"${lead.full_name}" lidini o'chirish?`)) return
    try {
      await deleteLead(lead.id)
      toast.success("O'chirildi")
      load()
    } catch (e) { toast.error(e.message) }
  }

  const canAddLead      = isHunter || isAdmin
  const canUpdateStatus = isCallCenter || isAdmin
  const canDelete       = isHunter || isAdmin

  return (
    <div className="page">
      <div className="page-header">
        <h1>Lidlar</h1>
        {canAddLead && (
          <button className="button primary" onClick={() => setAddModal(true)}>
            <FontAwesomeIcon icon={faPlus} /> Lid qo'shish
          </button>
        )}
      </div>

      {/* Toolbar */}
      <div className="toolbar">
        <div className="search-wrap">
          <FontAwesomeIcon icon={faMagnifyingGlass} className="search-icon" />
          <input
            className="search-input"
            placeholder="Ism yoki telefon..."
            value={search}
            onChange={handleSearch}
            onKeyDown={applySearch}
          />
        </div>
        <span style={{ flex: 1 }} />
        <span className="toolbar-count">Jami: <strong>{leads.length}</strong> ta lid</span>
      </div>

      {/* Status filter pills */}
      <div className="leads-filter-row">
        <button
          className={`df-preset${filterStatus === '' ? ' active' : ''}`}
          onClick={() => applyFilter('')}
        >Barchasi</button>
        {Object.entries(STATUS_META).map(([key, meta]) => (
          <button
            key={key}
            className={`df-preset${filterStatus === key ? ' active' : ''}`}
            onClick={() => applyFilter(key)}
          >
            <FontAwesomeIcon icon={faCircle} style={{ color: meta.color, fontSize: 8, marginRight: 5 }} />
            {meta.label}
          </button>
        ))}
      </div>

      {/* Table */}
      {loading ? (
        <div className="muted center py-8">Yuklanmoqda...</div>
      ) : (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Ism Familiya</th>
                <th><FontAwesomeIcon icon={faPhone} /> Telefon</th>
                <th>Kurs</th>
                <th>Holat</th>
                <th>Vaqt / Izoh</th>
                {!isHunter && <th>Hunter</th>}
                <th>Amallar</th>
              </tr>
            </thead>
            <tbody>
              {leads.map((lead, i) => {
                const meta = STATUS_META[lead.status] || STATUS_META.new
                return (
                  <tr key={lead.id}>
                    <td className="text-muted">{i + 1}</td>
                    <td><strong>{lead.full_name}</strong></td>
                    <td>{lead.phone}</td>
                    <td>
                      {lead.course_interest
                        ? <span className="badge">{lead.course_interest}</span>
                        : <span className="text-muted">—</span>}
                    </td>
                    <td>
                      <span className="lead-status-badge" style={{ background: meta.bg, color: meta.color }}>
                        {meta.label}
                      </span>
                    </td>
                    <td style={{ fontSize: 12, maxWidth: 200 }}>
                      {lead.callback_at && (
                        <div style={{ color: 'var(--warning)', fontWeight: 600 }}>
                          {new Date(lead.callback_at).toLocaleString('uz-UZ', { dateStyle: 'short', timeStyle: 'short' })}
                        </div>
                      )}
                      {lead.notes && <div className="text-muted" style={{ marginTop: 2 }}>{lead.notes}</div>}
                    </td>
                    {!isHunter && (
                      <td className="text-muted" style={{ fontSize: 12 }}>
                        {lead.created_by_name || '—'}
                      </td>
                    )}
                    <td className="actions">
                      {canUpdateStatus && (
                        <button className="btn-icon" title="Holat o'zgartirish" onClick={() => openStatusModal(lead)}>
                          <FontAwesomeIcon icon={faPen} />
                        </button>
                      )}
                      {canDelete && (
                        <button className="btn-icon danger" title="O'chirish" onClick={() => handleDelete(lead)}>
                          <FontAwesomeIcon icon={faTrash} />
                        </button>
                      )}
                    </td>
                  </tr>
                )
              })}
              {leads.length === 0 && (
                <tr>
                  <td colSpan={isHunter ? 7 : 8} className="muted center py-4">
                    Lidlar topilmadi
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Add Lead Modal */}
      {addModal && (
        <div className="modal-overlay" onClick={() => setAddModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Yangi lid</h3>
              <button className="modal-close" onClick={() => setAddModal(false)}>✕</button>
            </div>
            <div className="modal-body">
              <label>Ism Familiya *</label>
              <input className="field" value={form.full_name}
                onChange={e => setForm(p => ({ ...p, full_name: e.target.value }))}
                placeholder="To'liq ism" />
              <label><FontAwesomeIcon icon={faPhone} /> Telefon *</label>
              <input className="field" value={form.phone}
                onChange={e => setForm(p => ({ ...p, phone: e.target.value }))}
                placeholder="+998901234567" />
              <label>Qiziqayotgan kurs</label>
              <select className="field" value={form.course_interest}
                onChange={e => setForm(p => ({ ...p, course_interest: e.target.value }))}>
                {COURSES.map(c => <option key={c.key} value={c.key}>{c.label}</option>)}
              </select>
              <label>Izoh</label>
              <textarea className="field" rows={2} value={form.notes}
                onChange={e => setForm(p => ({ ...p, notes: e.target.value }))}
                placeholder="Qo'shimcha ma'lumot..." />
            </div>
            <div className="modal-footer">
              <button className="button secondary" onClick={() => setAddModal(false)}>Bekor</button>
              <button className="button primary" onClick={handleAdd} disabled={saving}>
                {saving ? 'Saqlanmoqda...' : 'Qo\'shish'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Status Update Modal */}
      {statusModal && (
        <div className="modal-overlay" onClick={() => setStatusModal(null)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>{statusModal.full_name} — holat</h3>
              <button className="modal-close" onClick={() => setStatusModal(null)}>✕</button>
            </div>
            <div className="modal-body">
              <label>Holat *</label>
              <div className="leads-status-grid">
                {Object.entries(STATUS_META).map(([key, meta]) => (
                  <button
                    key={key}
                    className={`leads-status-opt${statusForm.status === key ? ' selected' : ''}`}
                    style={statusForm.status === key
                      ? { background: meta.bg, borderColor: meta.color, color: meta.color }
                      : {}}
                    onClick={() => setStatusForm(p => ({ ...p, status: key }))}
                  >
                    <FontAwesomeIcon icon={faCircle} style={{ color: meta.color, fontSize: 8 }} />
                    {meta.label}
                  </button>
                ))}
              </div>

              {['will_come', 'callback'].includes(statusForm.status) && (
                <>
                  <label style={{ marginTop: 14 }}>
                    {statusForm.status === 'will_come' ? 'Kelish vaqti *' : 'Qayta qo\'ng\'iroq vaqti *'}
                  </label>
                  <input
                    className="field"
                    type="datetime-local"
                    value={statusForm.callback_at}
                    onChange={e => setStatusForm(p => ({ ...p, callback_at: e.target.value }))}
                  />
                </>
              )}

              <label style={{ marginTop: 14 }}>Izoh</label>
              <textarea className="field" rows={2}
                value={statusForm.notes}
                onChange={e => setStatusForm(p => ({ ...p, notes: e.target.value }))}
                placeholder="Qo'shimcha ma'lumot..." />
            </div>
            <div className="modal-footer">
              <button className="button secondary" onClick={() => setStatusModal(null)}>Bekor</button>
              <button className="button primary" onClick={handleStatusSave} disabled={saving}>
                {saving ? 'Saqlanmoqda...' : 'Saqlash'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
