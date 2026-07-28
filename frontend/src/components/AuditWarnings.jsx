import { useEffect, useMemo, useState } from 'react'
import { toast } from 'react-hot-toast'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faTriangleExclamation, faPlus, faPaperPlane, faBan, faTrash } from '@fortawesome/free-solid-svg-icons'
import {
  fetchStaffOptions, fetchDisciplineCodes, fetchStaffWarnings,
  createStaffWarning, resendStaffWarning, cancelStaffWarning, deleteStaffWarning,
} from '../api'

const SEVERITY_LABEL = { gray: 'Kulrang', yellow: 'Sariq', red: 'Qizil' }
const SEVERITY_STYLE = {
  gray:   { background: '#e5e7eb', color: '#374151' },
  yellow: { background: '#fef9c3', color: '#a16207' },
  red:    { background: '#fee2e2', color: '#dc2626' },
}
const EMPTY = { staff_id: '', mode: 'code', discipline_code_id: '', severity: 'gray', reason: '' }

export default function AuditWarnings({ currentUser }) {
  const isAdmin = currentUser?.role === 'admin'
  const isAudit = currentUser?.role === 'audit' || isAdmin

  const [staffList, setStaffList] = useState([])
  const [codes, setCodes] = useState([])
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(false)
  const [modal, setModal] = useState(false)
  const [form, setForm] = useState(EMPTY)
  const [saving, setSaving] = useState(false)
  const [staffFilter, setStaffFilter] = useState('')
  const [busyId, setBusyId] = useState(null)

  useEffect(() => {
    if (!isAudit) return
    fetchStaffOptions().then(setStaffList).catch(() => toast.error("Xodimlar ro'yxatini yuklab bo'lmadi"))
    fetchDisciplineCodes().then(setCodes).catch(() => toast.error("Kodeksni yuklab bo'lmadi"))
    load()
  }, [isAudit])

  async function load(staffId) {
    setLoading(true)
    try { setItems(await fetchStaffWarnings(staffId)) }
    catch { toast.error("Yuklab bo'lmadi") }
    finally { setLoading(false) }
  }

  function applyFilter(id) {
    setStaffFilter(id)
    load(id || undefined)
  }

  const codesBySeverity = useMemo(() => {
    const g = { gray: [], yellow: [], red: [] }
    for (const c of codes) g[c.severity]?.push(c)
    return g
  }, [codes])

  async function handleSave() {
    if (!form.staff_id) return toast.error('Xodimni tanlang')
    const payload = { staff_id: parseInt(form.staff_id) }
    if (form.mode === 'code') {
      if (!form.discipline_code_id) return toast.error('Kodeks moddasini tanlang')
      payload.discipline_code_id = parseInt(form.discipline_code_id)
    } else {
      if (!form.reason.trim()) return toast.error('Sabab kiriting')
      payload.severity = form.severity
      payload.reason = form.reason.trim()
    }
    setSaving(true)
    try {
      const w = await createStaffWarning(payload)
      toast.success(w.notified_at ? 'Ogohlantirish berildi va botga yetkazildi' : 'Ogohlantirish berildi (bot xabari yetkazilmadi — pastda "Qayta yuborish" bilan urinib ko\'ring)')
      setModal(false)
      setForm(EMPTY)
      load(staffFilter || undefined)
    } catch (e) { toast.error(e.message) }
    finally { setSaving(false) }
  }

  async function handleResend(w) {
    setBusyId(w.id)
    try {
      const updated = await resendStaffWarning(w.id)
      toast[updated.notified_at ? 'success' : 'error'](updated.notified_at ? 'Yuborildi' : (updated.notify_error || 'Yuborilmadi'))
      load(staffFilter || undefined)
    } catch (e) { toast.error(e.message) }
    finally { setBusyId(null) }
  }

  async function handleCancel(w) {
    if (!confirm(`${w.staff_name} uchun bu ogohlantirish bekor qilinsinmi?`)) return
    setBusyId(w.id)
    try {
      await cancelStaffWarning(w.id)
      toast.success('Bekor qilindi')
      load(staffFilter || undefined)
    } catch (e) { toast.error(e.message) }
    finally { setBusyId(null) }
  }

  async function handleDelete(w) {
    if (!confirm(`${w.staff_name} uchun bu ogohlantirish butunlay o'chirilsinmi? Bu amalni orqaga qaytarib bo'lmaydi.`)) return
    setBusyId(w.id)
    try {
      await deleteStaffWarning(w.id)
      toast.success("O'chirildi")
      load(staffFilter || undefined)
    } catch (e) { toast.error(e.message) }
    finally { setBusyId(null) }
  }

  if (!isAudit) {
    return <div className="page"><p className="muted center py-8">Ruxsat yo'q</p></div>
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1><FontAwesomeIcon icon={faTriangleExclamation} className="page-icon" /> Ogohlantirishlar</h1>
        <button className="button primary" onClick={() => { setForm(EMPTY); setModal(true) }}>
          <FontAwesomeIcon icon={faPlus} /> Ogohlantirish berish
        </button>
      </div>

      <select className="field" style={{ maxWidth: 320, marginBottom: 12 }}
        value={staffFilter} onChange={e => applyFilter(e.target.value)}>
        <option value="">Barcha xodimlar</option>
        {staffList.map(s => <option key={s.id} value={s.id}>{s.full_name || s.username}</option>)}
      </select>

      {loading ? (
        <div className="muted center py-8">Yuklanmoqda...</div>
      ) : (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Xodim</th>
                <th>Daraja</th>
                <th>Sabab</th>
                <th>Kim berdi</th>
                <th>Sana</th>
                <th>Yetkazish</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {items.map((w, i) => (
                <tr key={w.id} className={w.cancelled_at ? 'row-inactive' : ''}>
                  <td className="text-muted">{i + 1}</td>
                  <td><strong>{w.staff_name}</strong></td>
                  <td>
                    <span className="badge" style={SEVERITY_STYLE[w.severity]}>
                      {w.code ? `${w.code} — ${SEVERITY_LABEL[w.severity]}` : SEVERITY_LABEL[w.severity]}
                    </span>
                  </td>
                  <td style={{ maxWidth: 320 }}>{w.reason}</td>
                  <td className="text-muted">{w.issued_by_name || '—'}</td>
                  <td className="text-muted">{new Date(w.created_at).toLocaleString('uz-UZ')}</td>
                  <td>
                    {w.cancelled_at ? (
                      <span className="status-badge inactive">Bekor qilingan</span>
                    ) : w.notified_at ? (
                      <span className="status-badge active">Yetkazildi</span>
                    ) : (
                      <span className="status-badge inactive" title={w.notify_error || ''}>Yetkazilmadi</span>
                    )}
                  </td>
                  <td>
                    {!w.cancelled_at && !w.notified_at && (
                      <button className="btn-icon" title="Qayta yuborish" disabled={busyId === w.id} onClick={() => handleResend(w)}>
                        <FontAwesomeIcon icon={faPaperPlane} />
                      </button>
                    )}
                    {!w.cancelled_at && isAdmin && (
                      <button className="btn-icon danger" title="Bekor qilish" disabled={busyId === w.id} onClick={() => handleCancel(w)}>
                        <FontAwesomeIcon icon={faBan} />
                      </button>
                    )}
                    {isAdmin && (
                      <button className="btn-icon danger" title="Butunlay o'chirish" disabled={busyId === w.id} onClick={() => handleDelete(w)}>
                        <FontAwesomeIcon icon={faTrash} />
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              {items.length === 0 && (
                <tr><td colSpan={8} className="muted center py-4">Ogohlantirishlar yo'q</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {modal && (
        <div className="modal-overlay" onClick={() => setModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3><FontAwesomeIcon icon={faTriangleExclamation} /> Ogohlantirish berish</h3>
              <button className="modal-close" onClick={() => setModal(false)}>✕</button>
            </div>
            <div className="modal-body">
              <label>Xodim *</label>
              <select className="field" value={form.staff_id} onChange={e => setForm(p => ({ ...p, staff_id: e.target.value }))}>
                <option value="">— Tanlang —</option>
                {staffList.map(s => <option key={s.id} value={s.id}>{s.full_name || s.username}</option>)}
              </select>

              <label>Turi *</label>
              <select className="field" value={form.mode} onChange={e => setForm(p => ({ ...p, mode: e.target.value }))}>
                <option value="code">Ichki tartib kodeksidan</option>
                <option value="freeform">Erkin (kodeksda yo'q holat)</option>
              </select>

              {form.mode === 'code' ? (
                <>
                  <label>Kodeks moddasi *</label>
                  <select className="field" value={form.discipline_code_id}
                    onChange={e => setForm(p => ({ ...p, discipline_code_id: e.target.value }))}>
                    <option value="">— Tanlang —</option>
                    <optgroup label="Kulrang">
                      {codesBySeverity.gray.map(c => <option key={c.id} value={c.id}>{c.short_name}</option>)}
                    </optgroup>
                    <optgroup label="Sariq">
                      {codesBySeverity.yellow.map(c => <option key={c.id} value={c.id}>{c.short_name}</option>)}
                    </optgroup>
                    <optgroup label="Qizil">
                      {codesBySeverity.red.map(c => <option key={c.id} value={c.id}>{c.short_name}</option>)}
                    </optgroup>
                  </select>
                  {form.discipline_code_id && (
                    <p className="text-muted" style={{ fontSize: 12, margin: '4px 0 0' }}>
                      {codes.find(c => c.id === parseInt(form.discipline_code_id))?.text}
                    </p>
                  )}
                </>
              ) : (
                <>
                  <label>Daraja *</label>
                  <select className="field" value={form.severity} onChange={e => setForm(p => ({ ...p, severity: e.target.value }))}>
                    <option value="gray">Kulrang</option>
                    <option value="yellow">Sariq</option>
                    <option value="red">Qizil</option>
                  </select>
                  <label>Sabab *</label>
                  <textarea className="field" rows={3} value={form.reason}
                    onChange={e => setForm(p => ({ ...p, reason: e.target.value }))}
                    placeholder="Ogohlantirish sababini yozing" />
                </>
              )}
            </div>
            <div className="modal-footer">
              <button className="button secondary" onClick={() => setModal(false)}>Bekor</button>
              <button className="button primary" onClick={handleSave} disabled={saving}>
                {saving ? 'Saqlanmoqda...' : 'Berish'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
