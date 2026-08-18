import { useEffect, useState } from 'react'
import { toast } from 'react-hot-toast'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faUsers, faPaperPlane, faTriangleExclamation, faLink } from '@fortawesome/free-solid-svg-icons'
import { fetchStaffOptions, fetchDisciplineCodes, setStaffTelegramChatId } from '../api'
import StaffWarningModal from './StaffWarningModal'

const ROLE_LABELS = {
  admin: 'Admin', metodist: 'Metodist', teacher: "O'qituvchi",
  hunter: 'Hunter', call_center: 'Call Center', sales: 'Sales', audit: 'Audit',
}

export default function Employees({ currentUser }) {
  const isAdmin = currentUser?.role === 'admin'
  const isAudit = currentUser?.role === 'audit' || isAdmin

  const [staffList, setStaffList] = useState([])
  const [codes, setCodes] = useState([])
  const [loading, setLoading] = useState(false)
  const [linkTarget, setLinkTarget] = useState(null)   // staff row being linked
  const [linkValue, setLinkValue] = useState('')
  const [saving, setSaving] = useState(false)
  const [warningTarget, setWarningTarget] = useState(null) // staff row to warn

  useEffect(() => {
    if (!isAudit) return
    load()
    fetchDisciplineCodes().then(setCodes).catch(() => toast.error("Kodeksni yuklab bo'lmadi"))
  }, [isAudit])

  async function load() {
    setLoading(true)
    try { setStaffList(await fetchStaffOptions()) }
    catch { toast.error("Xodimlar ro'yxatini yuklab bo'lmadi") }
    finally { setLoading(false) }
  }

  function openLink(staff) {
    setLinkTarget(staff)
    setLinkValue(staff.telegram_chat_id || '')
  }

  async function handleSaveLink() {
    setSaving(true)
    try {
      await setStaffTelegramChatId(linkTarget.id, linkValue.trim() || null)
      toast.success('Telegram ID saqlandi')
      setLinkTarget(null)
      load()
    } catch (e) { toast.error(e.message) }
    finally { setSaving(false) }
  }

  if (!isAudit) {
    return <div className="page"><p className="muted center py-8">Ruxsat yo'q</p></div>
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1><FontAwesomeIcon icon={faUsers} className="page-icon" /> Xodimlar</h1>
      </div>

      {loading ? (
        <div className="muted center py-8">Yuklanmoqda...</div>
      ) : (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>#</th>
                <th>F.I.O</th>
                <th>Username</th>
                <th>Rol</th>
                <th>Telegram</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {staffList.map((s, i) => (
                <tr key={s.id}>
                  <td className="text-muted">{i + 1}</td>
                  <td><strong>{s.full_name || '—'}</strong></td>
                  <td className="text-muted">{s.username}</td>
                  <td><span className="badge">{ROLE_LABELS[s.role] || s.role}</span></td>
                  <td>
                    {s.telegram_chat_id ? (
                      <span className="status-badge active" title={s.telegram_chat_id}>Bog'langan</span>
                    ) : (
                      <span className="status-badge inactive">Bog'lanmagan</span>
                    )}
                  </td>
                  <td>
                    <button className="btn-icon" title="Telegram ID bog'lash" onClick={() => openLink(s)}>
                      <FontAwesomeIcon icon={faLink} />
                    </button>
                    <button className="btn-icon" title="Ogohlantirish yuborish" onClick={() => setWarningTarget(s)}>
                      <FontAwesomeIcon icon={faTriangleExclamation} />
                    </button>
                  </td>
                </tr>
              ))}
              {staffList.length === 0 && (
                <tr><td colSpan={6} className="muted center py-4">Xodimlar yo'q</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {linkTarget && (
        <div className="modal-overlay" onClick={() => setLinkTarget(null)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3><FontAwesomeIcon icon={faPaperPlane} /> Telegram ID — {linkTarget.full_name || linkTarget.username}</h3>
              <button className="modal-close" onClick={() => setLinkTarget(null)}>✕</button>
            </div>
            <div className="modal-body">
              <label>Telegram chat ID</label>
              <input className="field" value={linkValue} onChange={e => setLinkValue(e.target.value)}
                placeholder="masalan: 123456789" />
              <p className="text-muted" style={{ fontSize: 12, margin: '8px 0 0' }}>
                Xodim botga <strong>/start</strong> bosib, keyin <strong>/idyubor</strong> buyrug'i orqali
                o'z ID'sini yuboradi — shu ID shu yerga kiritiladi.
              </p>
            </div>
            <div className="modal-footer">
              <button className="button secondary" onClick={() => setLinkTarget(null)}>Bekor</button>
              <button className="button primary" onClick={handleSaveLink} disabled={saving}>
                {saving ? 'Saqlanmoqda...' : 'Saqlash'}
              </button>
            </div>
          </div>
        </div>
      )}

      {warningTarget && (
        <StaffWarningModal
          staffList={staffList}
          codes={codes}
          initialStaffId={warningTarget.id}
          onClose={() => setWarningTarget(null)}
          onSaved={() => {}}
        />
      )}
    </div>
  )
}
