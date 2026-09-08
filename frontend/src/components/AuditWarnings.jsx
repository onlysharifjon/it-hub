import { PageIntro } from './ui/Workspace'
import { useEffect, useState } from 'react'
import { toast } from 'react-hot-toast'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faTriangleExclamation, faPlus, faPaperPlane, faBan } from '@fortawesome/free-solid-svg-icons'
import {
  fetchStaffOptions, fetchDisciplineCodes, fetchStaffWarnings,
  resendStaffWarning, cancelStaffWarning,
} from '../api'
import StaffWarningModal from './StaffWarningModal'
import DataTable, { RowActions } from './ui/DataTable'
import ConfirmDialog from './ui/ConfirmDialog'
import Badge from './ui/Badge'

const SEVERITY = {
  gray:   { label: 'Kulrang', variant: 'neutral', rank: 1 },
  yellow: { label: 'Sariq',   variant: 'warning', rank: 2 },
  red:    { label: 'Qizil',   variant: 'danger',  rank: 3 },
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
  const [cancelTarget, setCancelTarget] = useState(null)

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

  async function handleCancel() {
    const w = cancelTarget
    setBusyId(w.id)
    try {
      await cancelStaffWarning(w.id)
      toast.success('Bekor qilindi')
      setCancelTarget(null)
      load(staffFilter || undefined)
    } catch (e) { toast.error(e.message) }
    finally { setBusyId(null) }
  }

  if (!isAudit) {
    return <div className="page"><p className="muted center py-8">Ruxsat yo'q</p></div>
  }

  const columns = [
    { key: 'staff_name', header: 'Xodim', sortable: true, render: w => <strong>{w.staff_name}</strong> },
    {
      key: 'severity', header: 'Daraja', sortable: true,
      sortValue: w => SEVERITY[w.severity]?.rank ?? 0,
      render: w => {
        const sev = SEVERITY[w.severity] || SEVERITY.gray
        return <Badge variant={sev.variant} size="sm">{w.code ? `${w.code} — ${sev.label}` : sev.label}</Badge>
      },
    },
    { key: 'reason', header: 'Sabab', render: w => <span className="cell-clamp">{w.reason}</span> },
    { key: 'issued_by_name', header: 'Kim berdi', sortable: true, render: w => <span className="text-muted">{w.issued_by_name || '—'}</span> },
    {
      key: 'created_at', header: 'Sana', sortable: true,
      render: w => <span className="muted-sm">{new Date(w.created_at).toLocaleString('uz-UZ')}</span>,
    },
    {
      key: 'delivery', header: 'Yetkazish', sortable: true,
      sortValue: w => (w.cancelled_at ? 2 : w.notified_at ? 0 : 1),
      render: w => w.cancelled_at
        ? <span className="status-badge inactive">Bekor qilingan</span>
        : w.notified_at
          ? <span className="status-badge active">Yetkazildi</span>
          : <span className="status-badge pending" title={w.notify_error || ''}>Yetkazilmadi</span>,
    },
    {
      key: 'actions', header: '', align: 'right', className: 'actions',
      render: w => (
        <RowActions>
          {!w.cancelled_at && !w.notified_at && (
            <button className="btn-icon" title="Qayta yuborish" aria-label="Qayta yuborish"
              disabled={busyId === w.id} onClick={() => handleResend(w)}>
              <FontAwesomeIcon icon={faPaperPlane} />
            </button>
          )}
          {!w.cancelled_at && isAdmin && (
            <button className="btn-icon danger" title="Bekor qilish" aria-label="Bekor qilish"
              disabled={busyId === w.id} onClick={() => setCancelTarget(w)}>
              <FontAwesomeIcon icon={faBan} />
            </button>
          )}
        </RowActions>
      ),
    },
  ]

  const activeCount = items.filter(w => !w.cancelled_at).length

  return (
    <div className="page">
      <PageIntro title={<>Ogohlantirishlar</>} description={<>{items.length} yozuv · {activeCount} tasi faol</>} actions={<><div className="header-actions">
          <button className="button" onClick={() => setModal(true)}>
            <FontAwesomeIcon icon={faPlus} /> Ogohlantirish berish
          </button>
        </div></>} />

      <DataTable
        columns={columns}
        rows={items}
        loading={loading}
        rowClassName={w => (w.cancelled_at ? 'row-inactive' : undefined)}
        clientPageSize={25}
        densityToggle densityKey="warnings"
        toolbar={
          <select className="field-sm" value={staffFilter} onChange={e => applyFilter(e.target.value)}
            aria-label="Xodim bo'yicha filtr">
            <option value="">Barcha xodimlar</option>
            {staffList.map(s => <option key={s.id} value={s.id}>{s.full_name || s.username}</option>)}
          </select>
        }
        empty={{
          icon: faTriangleExclamation,
          title: "Ogohlantirishlar yo'q",
          description: staffFilter ? 'Bu xodimga ogohlantirish berilmagan.' : 'Intizomiy yozuvlar shu yerda ko\'rinadi.',
        }}
      />

      <ConfirmDialog
        open={!!cancelTarget}
        danger
        title="Ogohlantirishni bekor qilish"
        message={cancelTarget ? `${cancelTarget.staff_name} uchun bu ogohlantirish bekor qilinsinmi?` : ''}
        detail="Bekor qilingan ogohlantirish tarixda qoladi, lekin faol hisoblanmaydi."
        confirmLabel="Ha, bekor qilish"
        onConfirm={handleCancel}
        onClose={() => setCancelTarget(null)}
      />

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
