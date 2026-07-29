import { useEffect, useState } from 'react'
import { toast } from 'react-hot-toast'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faRobot, faUsers, faTag, faGear, faCrown,
  faPlus, faToggleOn, faToggleOff, faCopy, faLink,
} from '@fortawesome/free-solid-svg-icons'
import {
  fetchBotEmployees, fetchBotRoles, createBotRole, toggleBotRole,
  setBotEmployeeRole, setBotEmployeeAdmin, fetchBotSetting, setBotSetting,
  createBotInviteLink,
} from '../api'

const TABS = [
  { key: 'employees', label: 'Xodimlar', icon: faUsers },
  { key: 'roles', label: 'Rollar', icon: faTag },
  { key: 'settings', label: 'Sozlamalar', icon: faGear },
  { key: 'admins', label: 'Admin / CEO', icon: faCrown },
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
        <h1><FontAwesomeIcon icon={faRobot} className="page-icon" /> Bot boshqaruvi</h1>
      </div>
      <p className="text-muted" style={{ fontSize: 13, marginTop: -8 }}>
        Telegram bot'ning o'z xodim/rol/sozlama ma'lumotlari — bu yerdagi o'zgarishlar
        botga darhol ta'sir qiladi va xodimga Telegram orqali xabar boradi.
      </p>

      <div className="tab-bar">
        {TABS.map(t => (
          <button key={t.key} className={`tab-btn ${tab === t.key ? 'active' : ''}`} onClick={() => setTab(t.key)}>
            <FontAwesomeIcon icon={t.icon} /> {t.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="muted center py-8">Yuklanmoqda...</div>
      ) : (
        <>
          {tab === 'employees' && <EmployeesTab employees={employees} roles={roles} reload={loadAll} />}
          {tab === 'roles' && <RolesTab roles={roles} reload={loadAll} />}
          {tab === 'settings' && <SettingsTab />}
          {tab === 'admins' && <AdminsTab employees={employees} reload={loadAll} />}
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

  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            <th>#</th>
            <th>Ism</th>
            <th>Username</th>
            <th>Hozirgi rol</th>
            <th>Rol tayinlash</th>
          </tr>
        </thead>
        <tbody>
          {employees.filter(e => !e.is_admin).map((emp, i) => (
            <tr key={emp.id}>
              <td className="text-muted">{i + 1}</td>
              <td style={{ fontWeight: 500 }}>{emp.full_name}</td>
              <td className="text-muted">{emp.username ? `@${emp.username}` : '—'}</td>
              <td>{emp.role_name
                ? <span className="badge" style={{ background: '#dbeafe', color: '#1d4ed8' }}>{emp.role_name}</span>
                : <span className="text-muted">Rol yo'q</span>}
              </td>
              <td>
                <select
                  className="field" style={{ maxWidth: 260 }}
                  value={emp.role_id || ''}
                  disabled={busyId === emp.id}
                  onChange={e => handleRoleChange(emp, e.target.value)}
                >
                  <option value="">— Rolsiz —</option>
                  {activeRoles.map(r => (
                    <option key={r.id} value={r.id}>{r.name}{r.is_parent ? ' (Ota-ona)' : ''}</option>
                  ))}
                </select>
              </td>
            </tr>
          ))}
          {employees.filter(e => !e.is_admin).length === 0 && (
            <tr><td colSpan={5} className="muted center py-4">Xodimlar yo'q</td></tr>
          )}
        </tbody>
      </table>
    </div>
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
      <div style={{ display: 'flex', justifyContent: 'flex-end', margin: '12px 0' }}>
        <button className="button primary" onClick={() => setModal(true)}>
          <FontAwesomeIcon icon={faPlus} /> Yangi rol
        </button>
      </div>
      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>#</th>
              <th>Nomi</th>
              <th>Ota-ona rolimi?</th>
              <th>Holat</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {roles.map((r, i) => (
              <tr key={r.id} className={!r.is_active ? 'row-inactive' : ''}>
                <td className="text-muted">{i + 1}</td>
                <td style={{ fontWeight: 500 }}>{r.name}</td>
                <td>{r.is_parent ? <span className="badge" style={{ background: '#dcfce7', color: '#16a34a' }}>Ha</span> : <span className="text-muted">Yo'q</span>}</td>
                <td><span className={`status-badge ${r.is_active ? 'active' : 'inactive'}`}>{r.is_active ? 'Faol' : 'Nofaol'}</span></td>
                <td>
                  <button className="btn-icon" disabled={busyId === r.id} onClick={() => handleToggle(r)} title={r.is_active ? 'Nofaol qilish' : 'Faol qilish'}>
                    <FontAwesomeIcon icon={r.is_active ? faToggleOn : faToggleOff} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

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
              <button className="button primary" onClick={handleCreate} disabled={saving}>
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

  if (loading) return <div className="muted center py-8">Yuklanmoqda...</div>

  return (
    <div style={{ maxWidth: 420, marginTop: 16 }}>
      <label className="form-label">Standart ota-ona Telegram ID</label>
      <p className="text-muted" style={{ fontSize: 12, marginTop: 0 }}>
        Talabaga alohida ota-ona biriktirilmagan hollarda davomat xabarlari shu ID'ga yuboriladi.
      </p>
      <input className="form-input" type="text" value={value} onChange={e => setValue(e.target.value)} placeholder="123456789" />
      <button className="button primary" style={{ marginTop: 12 }} onClick={handleSave} disabled={saving}>
        {saving ? 'Saqlanmoqda...' : 'Saqlash'}
      </button>
    </div>
  )
}

function AdminsTab({ employees, reload }) {
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
    if (!confirm(`${emp.full_name} adminlikdan olinsinmi?`)) return
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
      <h3 style={{ marginTop: 16 }}>Hozirgi adminlar</h3>
      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>#</th>
              <th>Ism</th>
              <th>Daraja</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {admins.map((a, i) => (
              <tr key={a.id}>
                <td className="text-muted">{i + 1}</td>
                <td style={{ fontWeight: 500 }}>{a.full_name}</td>
                <td>
                  <span className="badge" style={{ background: a.is_superadmin ? '#fef9c3' : '#dbeafe', color: a.is_superadmin ? '#a16207' : '#1d4ed8' }}>
                    {a.is_superadmin ? 'Superadmin (CEO)' : 'Admin'}
                  </span>
                </td>
                <td>
                  <button className="btn-icon danger" disabled={busyId === a.id} onClick={() => handleRemove(a)} title="Adminlikdan olish">
                    <FontAwesomeIcon icon={faCrown} />
                  </button>
                </td>
              </tr>
            ))}
            {admins.length === 0 && <tr><td colSpan={4} className="muted center py-4">Adminlar yo'q</td></tr>}
          </tbody>
        </table>
      </div>

      <h3 style={{ marginTop: 24 }}>Yangi admin tayinlash</h3>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
        <select className="field" style={{ maxWidth: 260 }} value={pickEmployee} onChange={e => setPickEmployee(e.target.value)}>
          <option value="">— Xodimni tanlang —</option>
          {nonAdmins.map(e => <option key={e.id} value={e.id}>{e.full_name}</option>)}
        </select>
        <select className="field" style={{ maxWidth: 200 }} value={pickTier} onChange={e => setPickTier(e.target.value)}>
          <option value="admin">Oddiy admin</option>
          <option value="superadmin">Superadmin (CEO)</option>
        </select>
        <button className="button primary" onClick={handlePromote} disabled={promoting}>
          {promoting ? 'Berilmoqda...' : 'Admin qilish'}
        </button>
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
        <button className="button primary" onClick={handleCreateLink} disabled={creatingLink}>
          <FontAwesomeIcon icon={faLink} /> {creatingLink ? 'Yaratilmoqda...' : 'Havola yaratish'}
        </button>
      </div>
      {generatedLink && (
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 10 }}>
          <code style={{ fontSize: 13, wordBreak: 'break-all' }}>{generatedLink}</code>
          <button className="btn-icon" onClick={copyLink} title="Nusxalash"><FontAwesomeIcon icon={faCopy} /></button>
        </div>
      )}
    </div>
  )
}
