import { useEffect, useState } from 'react'
import { TableSkeleton } from './ui/States'
import { toast } from 'react-hot-toast'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faRobot, faUsers, faTag, faGear, faCrown,
  faPlus, faToggleOn, faToggleOff, faCopy, faLink, faChartLine, faPaperPlane,
} from '@fortawesome/free-solid-svg-icons'
import {
  fetchBotEmployees, fetchBotRoles, createBotRole, toggleBotRole,
  setBotEmployeeRole, setBotEmployeeAdmin, fetchBotSetting, setBotSetting,
  createBotInviteLink, sendInvestorStatsNow,
} from '../api'
import DataTable, { RowActions } from './ui/DataTable'
import Badge from './ui/Badge'
import useConfirm from './ui/useConfirm'

const TABS = [
  { key: 'employees', label: 'Xodimlar', icon: faUsers },
  { key: 'roles', label: 'Rollar', icon: faTag },
  { key: 'settings', label: 'Sozlamalar', icon: faGear },
  { key: 'admins', label: 'Admin / CEO', icon: faCrown },
  { key: 'investors', label: 'Investorlar', icon: faChartLine },
]

export default function BotAdmin() {
  const [tab, setTab] = useState('employees')
  const [employees, setEmployees] = useState([])
  const [roles, setRoles] = useState([])
  const [loading, setLoading] = useState(false)

  useEffect(() => { loadAll() }, [])

  async function loadAll() {
    setLoading(true)
    try {
      const [e, r] = await Promise.all([fetchBotEmployees(), fetchBotRoles()])
      setEmployees(e)
      setRoles(r)
    } catch { toast.error("Yuklab bo'lmadi") }
    finally { setLoading(false) }
  }

  return (
    <div className="page">
      <div className="page-header">
        <div className="page-header-text">
          <h1><FontAwesomeIcon icon={faRobot} className="page-icon" /> Bot boshqaruvi</h1>
          <p className="page-subtitle">
            O'zgarishlar botga darhol ta'sir qiladi va xodimga Telegram orqali xabar boradi.
          </p>
        </div>
      </div>

      <div className="tab-bar">
        {TABS.map(t => (
          <button key={t.key} className={`tab-btn ${tab === t.key ? 'active' : ''}`} onClick={() => setTab(t.key)}>
            <FontAwesomeIcon icon={t.icon} /> {t.label}
          </button>
        ))}
      </div>

      {loading ? (
        <TableSkeleton />
      ) : (
        <>
          {tab === 'employees' && <EmployeesTab employees={employees} roles={roles} reload={loadAll} />}
          {tab === 'roles' && <RolesTab roles={roles} reload={loadAll} />}
          {tab === 'settings' && <SettingsTab />}
          {tab === 'admins' && <AdminsTab employees={employees} reload={loadAll} />}
          {tab === 'investors' && <InvestorsTab />}
        </>
      )}
    </div>
  )
}

function EmployeesTab({ employees, roles, reload }) {
  const [busyId, setBusyId] = useState(null)
  const activeRoles = roles.filter(r => r.is_active)

  async function handleRoleChange(emp, roleId) {
    setBusyId(emp.id)
    try {
      await setBotEmployeeRole(emp.id, roleId ? parseInt(roleId) : null)
      toast.success('Rol yangilandi, xodimga xabar yuborildi')
      reload()
    } catch (e) { toast.error(e.message) }
    finally { setBusyId(null) }
  }

  const rows = employees.filter(e => !e.is_admin)

  return (
    <DataTable
      columns={[
        { key: 'full_name', header: 'Ism', sortable: true, render: e => <strong>{e.full_name}</strong> },
        { key: 'username', header: 'Username', sortable: true, render: e => <span className="text-muted">{e.username ? `@${e.username}` : '—'}</span> },
        {
          key: 'role_name', header: 'Hozirgi rol', sortable: true,
          render: e => e.role_name
            ? <Badge variant="primary" size="sm">{e.role_name}</Badge>
            : <span className="text-muted">Rol yo'q</span>,
        },
        {
          key: 'assign', header: 'Rol tayinlash', width: 260,
          render: emp => (
            <select
              className="field-sm"
              value={emp.role_id || ''}
              disabled={busyId === emp.id}
              aria-label="Rol tayinlash"
              onChange={e => handleRoleChange(emp, e.target.value)}
            >
              <option value="">— Rolsiz —</option>
              {activeRoles.map(r => (
                <option key={r.id} value={r.id}>{r.name}{r.is_parent ? ' (Ota-ona)' : ''}</option>
              ))}
            </select>
          ),
        },
      ]}
      rows={rows}
      clientPageSize={25}
      empty={{ title: "Xodimlar yo'q", description: 'Botga /start bosgan xodimlar shu yerda paydo bo\'ladi.' }}
    />
  )
}

function RolesTab({ roles, reload }) {
  const [modal, setModal] = useState(false)
  const [name, setName] = useState('')
  const [isParent, setIsParent] = useState(false)
  const [saving, setSaving] = useState(false)
  const [busyId, setBusyId] = useState(null)

  async function handleCreate() {
    if (!name.trim()) return toast.error('Rol nomini kiriting')
    setSaving(true)
    try {
      await createBotRole({ name: name.trim(), is_parent: isParent })
      toast.success('Rol yaratildi')
      setModal(false)
      setName('')
      setIsParent(false)
      reload()
    } catch (e) { toast.error(e.message) }
    finally { setSaving(false) }
  }

  async function handleToggle(role) {
    setBusyId(role.id)
    try {
      await toggleBotRole(role.id)
      reload()
    } catch (e) { toast.error(e.message) }
    finally { setBusyId(null) }
  }

  return (
    <div>
      <DataTable
        columns={[
          { key: 'name', header: 'Nomi', sortable: true, render: r => <strong>{r.name}</strong> },
          {
            key: 'is_parent', header: 'Ota-ona rolimi?', sortable: true,
            render: r => r.is_parent ? <Badge variant="success" size="sm">Ha</Badge> : <span className="text-muted">Yo'q</span>,
          },
          {
            key: 'is_active', header: 'Holat', sortable: true,
            render: r => <span className={`status-badge ${r.is_active ? 'active' : 'inactive'}`}>{r.is_active ? 'Faol' : 'Nofaol'}</span>,
          },
          {
            key: 'actions', header: '', align: 'right', className: 'actions',
            render: r => (
              <RowActions>
                <button className="btn-icon" disabled={busyId === r.id} onClick={() => handleToggle(r)}
                  title={r.is_active ? 'Nofaol qilish' : 'Faol qilish'}
                  aria-label={r.is_active ? 'Nofaol qilish' : 'Faol qilish'}>
                  <FontAwesomeIcon icon={r.is_active ? faToggleOn : faToggleOff} />
                </button>
              </RowActions>
            ),
          },
        ]}
        rows={roles}
        rowClassName={r => (!r.is_active ? 'row-inactive' : undefined)}
        clientPageSize={25}
        toolbar={
          <button className="button small" onClick={() => setModal(true)}>
            <FontAwesomeIcon icon={faPlus} /> Yangi rol
          </button>
        }
        empty={{ title: "Rollar yo'q", description: 'Bot foydalanuvchilarini guruhlash uchun rol yarating.' }}
      />

      {modal && (
        <div className="modal-overlay" onClick={() => setModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3><FontAwesomeIcon icon={faTag} /> Yangi rol</h3>
              <button className="modal-close" onClick={() => setModal(false)}>✕</button>
            </div>
            <div className="modal-body">
              <label className="form-label">Rol nomi *</label>
              <input className="form-input" type="text" value={name} onChange={e => setName(e.target.value)} placeholder="Masalan: Reception" />
              <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 12, cursor: 'pointer' }}>
                <input type="checkbox" checked={isParent} onChange={e => setIsParent(e.target.checked)} />
                Bu — ota-ona roli (Farzand biriktirish imkoniyati chiqadi)
              </label>
            </div>
            <div className="modal-footer">
              <button className="button secondary" onClick={() => setModal(false)}>Bekor</button>
              <button className="button" onClick={handleCreate} disabled={saving}>
                {saving ? 'Saqlanmoqda...' : 'Yaratish'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function SettingsTab() {
  const [value, setValue] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    fetchBotSetting('default_parent_chat_id')
      .then(r => setValue(r.value || ''))
      .catch(() => toast.error("Yuklab bo'lmadi"))
      .finally(() => setLoading(false))
  }, [])

  async function handleSave() {
    setSaving(true)
    try {
      await setBotSetting('default_parent_chat_id', value.trim())
      toast.success('Saqlandi')
    } catch (e) { toast.error(e.message) }
    finally { setSaving(false) }
  }

  if (loading) return <TableSkeleton />

  return (
    <div style={{ maxWidth: 420, marginTop: 16 }}>
      <label className="form-label">Standart ota-ona Telegram ID</label>
      <p className="text-muted" style={{ fontSize: 12, marginTop: 0 }}>
        Talabaga alohida ota-ona biriktirilmagan hollarda davomat xabarlari shu ID'ga yuboriladi.
      </p>
      <input className="form-input" type="text" value={value} onChange={e => setValue(e.target.value)} placeholder="123456789" />
      <button className="button" style={{ marginTop: 12 }} onClick={handleSave} disabled={saving}>
        {saving ? 'Saqlanmoqda...' : 'Saqlash'}
      </button>
    </div>
  )
}

function AdminsTab({ employees, reload }) {
  const [confirmUI, ask] = useConfirm()
  const [busyId, setBusyId] = useState(null)
  const [pickEmployee, setPickEmployee] = useState('')
  const [pickTier, setPickTier] = useState('admin')
  const [promoting, setPromoting] = useState(false)
  const [linkTier, setLinkTier] = useState('admin')
  const [creatingLink, setCreatingLink] = useState(false)
  const [generatedLink, setGeneratedLink] = useState(null)

  const admins = employees.filter(e => e.is_admin)
  const nonAdmins = employees.filter(e => !e.is_admin)

  async function handleRemove(emp) {
    const ok = await ask({
      title: 'Adminlikdan olish',
      message: `${emp.full_name} adminlikdan olinsinmi?`,
      detail: "Xodim botni boshqara olmaydi, lekin bot foydalanuvchisi bo'lib qoladi.",
      confirmLabel: 'Ha, olib tashlash',
    })
    if (!ok) return
    setBusyId(emp.id)
    try {
      await setBotEmployeeAdmin(emp.id, null)
      toast.success('Adminlikdan olindi')
      reload()
    } catch (e) { toast.error(e.message) }
    finally { setBusyId(null) }
  }

  async function handlePromote() {
    if (!pickEmployee) return toast.error('Xodimni tanlang')
    setPromoting(true)
    try {
      await setBotEmployeeAdmin(parseInt(pickEmployee), pickTier)
      toast.success('Admin huquqi berildi')
      setPickEmployee('')
      reload()
    } catch (e) { toast.error(e.message) }
    finally { setPromoting(false) }
  }

  async function handleCreateLink() {
    setCreatingLink(true)
    setGeneratedLink(null)
    try {
      const r = await createBotInviteLink(linkTier)
      setGeneratedLink(r.link)
    } catch (e) { toast.error(e.message) }
    finally { setCreatingLink(false) }
  }

  function copyLink() {
    navigator.clipboard.writeText(generatedLink).then(
      () => toast.success('Nusxalandi'),
      () => toast.error("Nusxalab bo'lmadi"),
    )
  }

  return (
    <div>
      {confirmUI}
      <div className="ui-section-head">
        <div className="ui-section-head-text">
          <h2>Hozirgi adminlar</h2>
          <p>Botni boshqarish huquqiga ega xodimlar</p>
        </div>
      </div>
      <DataTable
        columns={[
          { key: 'full_name', header: 'Ism', sortable: true, render: a => <strong>{a.full_name}</strong> },
          {
            key: 'is_superadmin', header: 'Daraja', sortable: true,
            render: a => (
              <Badge variant={a.is_superadmin ? 'warning' : 'primary'} size="sm">
                {a.is_superadmin ? 'Superadmin (CEO)' : 'Admin'}
              </Badge>
            ),
          },
          {
            key: 'actions', header: '', align: 'right', className: 'actions',
            render: a => (
              <RowActions>
                <button className="btn-icon danger" disabled={busyId === a.id} onClick={() => handleRemove(a)}
                  title="Adminlikdan olish" aria-label="Adminlikdan olish">
                  <FontAwesomeIcon icon={faCrown} />
                </button>
              </RowActions>
            ),
          },
        ]}
        rows={admins}
        clientPageSize={20}
        empty={{ title: "Adminlar yo'q" }}
      />

      <div className="ui-section-head">
        <div className="ui-section-head-text">
          <h2>Yangi admin tayinlash</h2>
          <p>Xodimni tanlang va darajani belgilang</p>
        </div>
      </div>
      <div className="card">
        <div className="toolbar" style={{ marginBottom: 0 }}>
          <select className="field-sm" style={{ minWidth: 240 }} value={pickEmployee}
            aria-label="Xodim" onChange={e => setPickEmployee(e.target.value)}>
            <option value="">— Xodimni tanlang —</option>
            {nonAdmins.map(e => <option key={e.id} value={e.id}>{e.full_name}</option>)}
          </select>
          <select className="field-sm" style={{ minWidth: 180 }} value={pickTier}
            aria-label="Daraja" onChange={e => setPickTier(e.target.value)}>
            <option value="admin">Oddiy admin</option>
            <option value="superadmin">Superadmin (CEO)</option>
          </select>
          <button className="button" onClick={handlePromote} disabled={promoting}>
            {promoting ? 'Berilmoqda...' : 'Admin qilish'}
          </button>
        </div>
      </div>

      <h3 style={{ marginTop: 24 }}>Admin/CEO havolasi yaratish</h3>
      <p className="text-muted" style={{ fontSize: 12, marginTop: 0 }}>
        Bir martalik havola — kimdir shu havola orqali botga /start bossa, avtomatik shu darajaga ko'tariladi.
      </p>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
        <select className="field" style={{ maxWidth: 200 }} value={linkTier} onChange={e => setLinkTier(e.target.value)}>
          <option value="admin">Admin havolasi</option>
          <option value="superadmin">Superadmin (CEO) havolasi</option>
        </select>
        <button className="button" onClick={handleCreateLink} disabled={creatingLink}>
          <FontAwesomeIcon icon={faLink} /> {creatingLink ? 'Yaratilmoqda...' : 'Havola yaratish'}
        </button>
      </div>
      {generatedLink && (
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 10 }}>
          <code style={{ fontSize: 13, wordBreak: 'break-all' }}>{generatedLink}</code>
          <button className="btn-icon" onClick={copyLink} title="Nusxalash" aria-label="Nusxalash"><FontAwesomeIcon icon={faCopy} /></button>
        </div>
      )}
    </div>
  )
}

const INVESTOR_KEYS = {
  chatId: 'investor_chat_id',
  dailyEnabled: 'investor_daily_stats_enabled',
  dailyTime: 'investor_daily_stats_time',
  newStudentEnabled: 'investor_new_student_enabled',
  lastSent: 'investor_daily_stats_last_sent',
}

function InvestorsTab() {
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [sending, setSending] = useState(false)
  const [chatId, setChatId] = useState('')
  const [dailyEnabled, setDailyEnabled] = useState(false)
  const [dailyTime, setDailyTime] = useState('09:00')
  const [newStudentEnabled, setNewStudentEnabled] = useState(false)
  const [lastSent, setLastSent] = useState('')

  useEffect(() => { load() }, [])

  async function load() {
    setLoading(true)
    try {
      const [c, de, dt, ne, ls] = await Promise.all([
        fetchBotSetting(INVESTOR_KEYS.chatId),
        fetchBotSetting(INVESTOR_KEYS.dailyEnabled),
        fetchBotSetting(INVESTOR_KEYS.dailyTime),
        fetchBotSetting(INVESTOR_KEYS.newStudentEnabled),
        fetchBotSetting(INVESTOR_KEYS.lastSent),
      ])
      setChatId(c.value || '')
      setDailyEnabled(de.value === '1')
      setDailyTime(dt.value || '09:00')
      setNewStudentEnabled(ne.value === '1')
      setLastSent(ls.value || '')
    } catch { toast.error("Yuklab bo'lmadi") }
    finally { setLoading(false) }
  }

  async function handleSave() {
    if (!chatId.trim()) return toast.error('Investorlar guruhi Telegram chat ID kiritilmagan')
    setSaving(true)
    try {
      await Promise.all([
        setBotSetting(INVESTOR_KEYS.chatId, chatId.trim()),
        setBotSetting(INVESTOR_KEYS.dailyEnabled, dailyEnabled ? '1' : '0'),
        setBotSetting(INVESTOR_KEYS.dailyTime, dailyTime || '09:00'),
        setBotSetting(INVESTOR_KEYS.newStudentEnabled, newStudentEnabled ? '1' : '0'),
      ])
      toast.success('Saqlandi')
    } catch (e) { toast.error(e.message) }
    finally { setSaving(false) }
  }

  async function handleSendNow() {
    setSending(true)
    try {
      const r = await sendInvestorStatsNow()
      if (r.ok) { toast.success('Statistika yuborildi'); load() }
      else toast.error(r.detail || "Yuborib bo'lmadi")
    } catch (e) { toast.error(e.message) }
    finally { setSending(false) }
  }

  if (loading) return <TableSkeleton />

  return (
    <div style={{ maxWidth: 480, marginTop: 16 }}>
      <p className="text-muted" style={{ fontSize: 13, marginTop: 0 }}>
        Investorlar Telegram guruhiga avtomatik xabarnomalar — kunlik statistika va
        guruhga yangi talaba qo'shilganda. Faqat superadmin boshqara oladi.
      </p>

      <label className="form-label">Investorlar guruhi Telegram chat ID</label>
      <input
        className="form-input" type="text" value={chatId}
        onChange={e => setChatId(e.target.value)} placeholder="-1001234567890"
      />
      <p className="text-muted" style={{ fontSize: 12, marginTop: 4 }}>
        Botni investorlar guruhiga admin qilib qo'shing, so'ng guruh chat ID'sini shu yerga kiriting.
      </p>

      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 18 }}>
        <button className="btn-icon" onClick={() => setDailyEnabled(v => !v)} title={dailyEnabled ? 'Nofaol qilish' : 'Faol qilish'}>
          <FontAwesomeIcon icon={dailyEnabled ? faToggleOn : faToggleOff} size="lg" />
        </button>
        <div>
          <div style={{ fontWeight: 500 }}>Kunlik statistika yuborish</div>
          <div className="text-muted" style={{ fontSize: 12 }}>Har kuni belgilangan vaqtda avtomatik yuboriladi</div>
        </div>
      </div>
      {dailyEnabled && (
        <div style={{ marginTop: 10 }}>
          <label className="form-label">Yuborish vaqti (Toshkent)</label>
          <input
            className="form-input" type="time" style={{ maxWidth: 140 }}
            value={dailyTime} onChange={e => setDailyTime(e.target.value)}
          />
        </div>
      )}

      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 18 }}>
        <button className="btn-icon" onClick={() => setNewStudentEnabled(v => !v)} title={newStudentEnabled ? 'Nofaol qilish' : 'Faol qilish'}>
          <FontAwesomeIcon icon={newStudentEnabled ? faToggleOn : faToggleOff} size="lg" />
        </button>
        <div>
          <div style={{ fontWeight: 500 }}>Yangi talaba xabarnomasi</div>
          <div className="text-muted" style={{ fontSize: 12 }}>Guruhga yangi talaba qo'shilganda darhol xabar boradi</div>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 10, marginTop: 20, flexWrap: 'wrap' }}>
        <button className="button" onClick={handleSave} disabled={saving}>
          {saving ? 'Saqlanmoqda...' : 'Saqlash'}
        </button>
        <button className="button secondary" onClick={handleSendNow} disabled={sending || !chatId.trim()}>
          <FontAwesomeIcon icon={faPaperPlane} /> {sending ? 'Yuborilmoqda...' : 'Hozir yuborish (sinov)'}
        </button>
      </div>
      {lastSent && (
        <p className="text-muted" style={{ fontSize: 12, marginTop: 10 }}>
          Oxirgi kunlik statistika: {lastSent}
        </p>
      )}
    </div>
  )
}
