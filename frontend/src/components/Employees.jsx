import { PageIntro } from './ui/Workspace'
import { useEffect, useState } from 'react'
import { toast } from 'react-hot-toast'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faUsers, faTriangleExclamation, faLink, faChalkboardUser } from '@fortawesome/free-solid-svg-icons'
import { fetchStaffOptions, fetchDisciplineCodes, setStaffTelegramChatId, promoteStaffToTeacher } from '../api'
import StaffWarningModal from './StaffWarningModal'
import ConfirmDialog from './ui/ConfirmDialog'
import DataTable, { RowActions } from './ui/DataTable'
import Modal from './ui/Modal'
import Badge from './ui/Badge'
import { Input } from './ui/Field'
import { ROLE_LABELS, roleColor } from '../constants/domain'

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
  const [promoteTarget, setPromoteTarget] = useState(null) // support → teacher
  const [promoting, setPromoting] = useState(false)

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

  async function handlePromote() {
    setPromoting(true)
    try {
      await promoteStaffToTeacher(promoteTarget.id)
      toast.success(`${promoteTarget.full_name || promoteTarget.username} endi o'qituvchi`)
      setPromoteTarget(null)
      load()
    } catch (e) { toast.error(e.message) }
    finally { setPromoting(false) }
  }

  if (!isAudit) {
    return <div className="page"><p className="muted center py-8">Ruxsat yo'q</p></div>
  }

  const columns = [
    { key: 'full_name', header: 'F.I.O', sortable: true, render: s => <strong>{s.full_name || '—'}</strong> },
    { key: 'username', header: 'Username', sortable: true, render: s => <span className="text-muted">{s.username}</span> },
    {
      key: 'role', header: 'Rol', sortable: true,
      sortValue: s => ROLE_LABELS[s.role] || s.role,
      render: s => <Badge size="sm" color={roleColor(s.role)}>{ROLE_LABELS[s.role] || s.role}</Badge>,
    },
    {
      key: 'telegram_chat_id', header: 'Telegram', sortable: true,
      sortValue: s => (s.telegram_chat_id ? 0 : 1),
      render: s => s.telegram_chat_id
        ? <span className="status-badge active" title={s.telegram_chat_id}>Bog'langan</span>
        : <span className="status-badge inactive">Bog'lanmagan</span>,
    },
    {
      key: 'actions', header: '', align: 'right', className: 'actions',
      render: s => (
        <RowActions>
          {s.role === 'support_teacher' && (
            <button className="btn-icon" title="O'qituvchi qilish" aria-label="O'qituvchi qilish" onClick={() => setPromoteTarget(s)}>
              <FontAwesomeIcon icon={faChalkboardUser} />
            </button>
          )}
          <button className="btn-icon" title="Telegram ID bog'lash" aria-label="Telegram ID bog'lash" onClick={() => openLink(s)}>
            <FontAwesomeIcon icon={faLink} />
          </button>
          <button className="btn-icon danger" title="Ogohlantirish yuborish" aria-label="Ogohlantirish yuborish" onClick={() => setWarningTarget(s)}>
            <FontAwesomeIcon icon={faTriangleExclamation} />
          </button>
        </RowActions>
      ),
    },
  ]

  const linked = staffList.filter(s => s.telegram_chat_id).length

  return (
    <div className="page">
      <PageIntro title={<>Xodimlar</>} description={<>{staffList.length} xodim · {linked} tasi Telegramga bog'langan</>}  />

      <DataTable
        columns={columns}
        rows={staffList}
        loading={loading}
        clientPageSize={25}
        empty={{ icon: faUsers, title: "Xodimlar yo'q", description: 'Hisoblar "Foydalanuvchilar" bo\'limida yaratiladi.' }}
      />

      <Modal
        open={!!linkTarget}
        title={linkTarget ? `Telegram ID — ${linkTarget.full_name || linkTarget.username}` : ''}
        onClose={() => setLinkTarget(null)}
        size="sm"
        footer={
          <>
            <button className="button secondary" onClick={() => setLinkTarget(null)}>Bekor</button>
            <button className="button" onClick={handleSaveLink} disabled={saving}>
              {saving ? 'Saqlanmoqda...' : 'Saqlash'}
            </button>
          </>
        }
      >
        <Input
          label="Telegram chat ID"
          value={linkValue}
          onChange={e => setLinkValue(e.target.value)}
          placeholder="masalan: 123456789"
          hint="Xodim botga /start bosib, keyin /idyubor buyrug'i orqali o'z ID'sini yuboradi — shu ID shu yerga kiritiladi."
        />
      </Modal>

      <ConfirmDialog
        open={!!promoteTarget}
        danger={false}
        title="O'qituvchi qilish"
        message={promoteTarget ? `${promoteTarget.full_name || promoteTarget.username} roli Support Teacher'dan O'qituvchiga o'zgartirilsinmi?` : ''}
        detail="Xodim keyingi so'rovdanoq o'qituvchi huquqlari bilan ishlaydi. O'zgarish audit tarixida saqlanadi."
        confirmLabel="Ha, o'qituvchi qilish"
        loading={promoting}
        onConfirm={handlePromote}
        onClose={() => setPromoteTarget(null)}
      />

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
