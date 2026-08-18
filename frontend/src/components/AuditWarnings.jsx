import { useEffect, useState } from 'react'
import { toast } from 'react-hot-toast'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faTriangleExclamation, faPlus, faPaperPlane, faBan } from '@fortawesome/free-solid-svg-icons'
import {
  fetchStaffOptions, fetchDisciplineCodes, fetchStaffWarnings,
  resendStaffWarning, cancelStaffWarning,
} from '../api'
import StaffWarningModal from './StaffWarningModal'

const SEVERITY_LABEL = { gray: 'Kulrang', yellow: 'Sariq', red: 'Qizil' }
const SEVERITY_STYLE = {
  gray:   { background: '#e5e7eb', color: '#374151' },
  yellow: { background: '#fef9c3', color: '#a16207' },
  red:    { background: '#fee2e2', color: '#dc2626' },
}

export default function AuditWarnings({ currentUser }) {
  const isAdmin = currentUser?.role === 'admin'
  const isAudit = currentUser?.role === 'audit' || isAdmin

  const [staffList, setStaffList] = useState([])
  const [codes, setCodes] = useState([])
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(false)
  const [modal, setModal] = useState(false)
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

  if (!isAudit) {
    return <div className="page"><p className="muted center py-8">Ruxsat yo'q</p></div>
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1><FontAwesomeIcon icon={faTriangleExclamation} className="page-icon" /> Ogohlantirishlar</h1>
        <button className="button primary" onClick={() => setModal(true)}>
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
        <StaffWarningModal
          staffList={staffList}
          codes={codes}
          onClose={() => setModal(false)}
          onSaved={() => load(staffFilter || undefined)}
        />
      )}
    </div>
  )
}
