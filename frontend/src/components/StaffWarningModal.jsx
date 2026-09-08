import Overlay from './ui/Overlay'
import { useMemo, useState } from 'react'
import { toast } from 'react-hot-toast'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faTriangleExclamation } from '@fortawesome/free-solid-svg-icons'
import { createStaffWarning } from '../api'

export default function StaffWarningModal({ staffList, codes, initialStaffId, onClose, onSaved }) {
  const [form, setForm] = useState({
    staff_id: initialStaffId ? String(initialStaffId) : '',
    mode: 'code',
    discipline_code_id: '',
    severity: 'gray',
    reason: '',
  })
  const [saving, setSaving] = useState(false)

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
      toast.success(w.notified_at ? 'Ogohlantirish berildi va botga yetkazildi' : 'Ogohlantirish berildi (bot xabari yetkazilmadi — "Qayta yuborish" bilan urinib ko\'ring)')
      onSaved?.(w)
      onClose()
    } catch (e) { toast.error(e.message) }
    finally { setSaving(false) }
  }

  return (
    <Overlay className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h3><FontAwesomeIcon icon={faTriangleExclamation} /> Ogohlantirish berish</h3>
          <button className="modal-close" onClick={onClose}>✕</button>
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
          <button className="button secondary" onClick={onClose}>Bekor</button>
          <button className="button" onClick={handleSave} disabled={saving}>
            {saving ? 'Saqlanmoqda...' : 'Berish'}
          </button>
        </div>
      </div>
    </Overlay>
  )
}
