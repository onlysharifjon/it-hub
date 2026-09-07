import { useEffect, useState } from 'react'
import { toast } from 'react-hot-toast'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faUserShield, faPlus, faLock, faLockOpen,
  faPen, faSearch, faXmark, faTrash, faPaperPlane,
} from '@fortawesome/free-solid-svg-icons'
import {
  fetchUsers, createUser, updateUser, blockUser, unblockUser, deleteUserPermanent, broadcastToStaff,
} from '../api'
import Badge from './ui/Badge'
import DataTable, { RowActions } from './ui/DataTable'
import { ROLE_LABELS, ROLE_OPTIONS, roleColor, USER_STATUS, userStatus } from '../constants/domain'

function StatusBadge({ user }) {
  const { label, variant } = USER_STATUS[userStatus(user)] || USER_STATUS.inactive
  return <Badge variant={variant} size="sm">{label}</Badge>
}

const emptyForm = { username: '', full_name: '', password: '', role: 'teacher', expires_at: '', telegram_chat_id: '' }

export default function Users() {
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(false)
  const [search, setSearch] = useState('')

  // Create / Edit modal
  const [modal, setModal] = useState(null)  // null | 'create' | 'edit'
  const [form, setForm] = useState(emptyForm)
  const [editId, setEditId] = useState(null)
  const [saving, setSaving] = useState(false)

  // Block modal
  const [blockModal, setBlockModal] = useState(null)  // null | user object
  const [blockForm, setBlockForm] = useState({ reason: '', contact: '' })
  const [blocking, setBlocking] = useState(false)

  // Permanent delete modal
  const [deleteModal, setDeleteModal] = useState(null)  // null | user object
  const [deleting, setDeleting] = useState(false)

  // Telegram orqali barcha xodimlarga xabar yuborish
  const [broadcastModal, setBroadcastModal] = useState(false)
  const [broadcastText, setBroadcastText] = useState('')
  const [broadcasting, setBroadcasting] = useState(false)

  async function handleBroadcast() {
    if (!broadcastText.trim()) { toast.error('Xabar matnini kiriting'); return }
    setBroadcasting(true)
    try {
      const r = await broadcastToStaff(broadcastText.trim())
      if (r.sent > 0) {
        toast.success(`Yuborildi: ${r.sent}/${r.total} xodimga`)
        setBroadcastModal(false)
        setBroadcastText('')
      } else {
        toast.error(
          `Hech kimga yetmadi (0/${r.total}).` +
          (r.sample_errors?.length ? ` Sabab: ${r.sample_errors[0]}` : ''),
          { duration: 8000 }
        )
      }
    } catch (e) { toast.error(e.message) }
    finally { setBroadcasting(false) }
  }

  useEffect(() => { load() }, [])

  async function load() {
    setLoading(true)
    try {
      const res = await fetchUsers()
      setUsers(Array.isArray(res) ? res : (res.items || []))
    }
    catch { toast.error("Foydalanuvchilar yuklanmadi") }
    finally { setLoading(false) }
  }

  function openCreate() {
    setForm(emptyForm)
    setEditId(null)
    setModal('create')
  }

  function openEdit(u) {
    setForm({
      username: u.username,
      full_name: u.full_name || '',
      password: '',
      role: u.role,
      expires_at: u.expires_at ? u.expires_at.slice(0, 10) : '',
      telegram_chat_id: u.telegram_chat_id || '',
    })
    setEditId(u.id)
    setModal('edit')
  }

  async function handleSave() {
    setSaving(true)
    try {
      const payload = {
        full_name: form.full_name || null,
        role: form.role,
        expires_at: form.expires_at ? form.expires_at + 'T00:00:00' : null,
        telegram_chat_id: form.telegram_chat_id.trim() || null,
      }
      if (modal === 'create') {
        if (!form.username.trim()) { toast.error('Username kerak'); setSaving(false); return }
        if (form.password.length < 8) { toast.error("Parol kamida 8 ta belgi"); setSaving(false); return }
        await createUser({ ...payload, username: form.username, password: form.password })
        toast.success('Foydalanuvchi yaratildi')
      } else {
        if (form.password && form.password.length < 8) { toast.error("Parol kamida 8 ta belgi"); setSaving(false); return }
        const p = { ...payload }
        if (form.password) p.password = form.password
        await updateUser(editId, p)
        toast.success("Saqlandi")
      }
      setModal(null)
      load()
    } catch (err) {
      toast.error(err.message || 'Xato')
    } finally {
      setSaving(false)
    }
  }

  function openBlock(u) {
    setBlockForm({ reason: '', contact: '' })
    setBlockModal(u)
  }

  async function handleBlock() {
    if (!blockForm.reason.trim()) { toast.error('Sabab kiriting'); return }
    if (!blockForm.contact.trim()) { toast.error('Kontakt kiriting'); return }
    setBlocking(true)
    try {
      await blockUser(blockModal.id, { reason: blockForm.reason, contact: blockForm.contact })
      toast.success('Akkount bloklandi')
      setBlockModal(null)
      load()
    } catch (err) {
      toast.error(err.message || 'Xato')
    } finally {
      setBlocking(false)
    }
  }

  async function handleUnblock(u) {
    try {
      await unblockUser(u.id)
      toast.success('Blok olib tashlandi')
      load()
    } catch (err) {
      toast.error(err.message || 'Xato')
    }
  }

  function openDelete(u) {
    setDeleteModal(u)
  }

  async function handleDeletePermanent() {
    setDeleting(true)
    try {
      await deleteUserPermanent(deleteModal.id)
      toast.success("Akkount butunlay o'chirildi (bog'liq ma'lumotlar backup qilindi)")
      setDeleteModal(null)
      load()
    } catch (err) {
      toast.error(err.message || 'Xato')
    } finally {
      setDeleting(false)
    }
  }

  const filtered = users.filter(u =>
    !search ||
    u.username.toLowerCase().includes(search.toLowerCase()) ||
    (u.full_name || '').toLowerCase().includes(search.toLowerCase())
  )

  const userColumns = [
    {
      key: 'full_name', header: 'Ism', sortable: true,
      render: u => <strong>{u.full_name || '—'}</strong>,
    },
    { key: 'username', header: 'Username', sortable: true, render: u => <span className="text-muted">{u.username}</span> },
    {
      key: 'role', header: 'Rol', sortable: true,
      sortValue: u => ROLE_LABELS[u.role] || u.role,
      render: u => <Badge size="sm" color={roleColor(u.role)}>{ROLE_LABELS[u.role] || u.role}</Badge>,
    },
    {
      key: 'status', header: 'Holat', sortable: true,
      sortValue: u => userStatus(u),
      render: u => <StatusBadge user={u} />,
    },
    {
      key: 'expires_at', header: 'Muddati', sortable: true,
      sortValue: u => u.expires_at || '9999',
      render: u => (
        <span className="muted-sm">
          {u.expires_at ? new Date(u.expires_at).toLocaleDateString('uz-UZ') : '∞'}
        </span>
      ),
    },
    {
      key: 'actions', header: '', align: 'right', className: 'actions',
      render: u => (
        <RowActions>
          <button className="btn-icon" onClick={() => openEdit(u)} title="Tahrirlash" aria-label="Tahrirlash">
            <FontAwesomeIcon icon={faPen} />
          </button>
          {u.blocked_at ? (
            <button className="btn-icon success" onClick={() => handleUnblock(u)} title="Blokni olib tashlash" aria-label="Blokni olib tashlash">
              <FontAwesomeIcon icon={faLockOpen} />
            </button>
          ) : (
            <button className="btn-icon danger" onClick={() => openBlock(u)} title="Bloklash" aria-label="Bloklash">
              <FontAwesomeIcon icon={faLock} />
            </button>
          )}
          <button className="btn-icon danger" onClick={() => openDelete(u)} title="Butunlay o'chirish" aria-label="Butunlay o'chirish">
            <FontAwesomeIcon icon={faTrash} />
          </button>
        </RowActions>
      ),
    },
  ]

  return (
    <div className="page">
      <div className="page-header">
        <h1><FontAwesomeIcon icon={faUserShield} className="page-icon" /> Foydalanuvchilar</h1>
        <div className="header-actions">
          <button className="button secondary" onClick={() => { setBroadcastText(''); setBroadcastModal(true) }}>
            <FontAwesomeIcon icon={faPaperPlane} /> Telegram orqali xabar
          </button>
          <button className="button" onClick={openCreate}>
            <FontAwesomeIcon icon={faPlus} /> Yangi foydalanuvchi
          </button>
        </div>
      </div>

      <div className="toolbar">
        <div className="search-wrap">
          <FontAwesomeIcon icon={faSearch} className="search-icon" />
          <input
            className="search-input"
            placeholder="Qidirish..."
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>
      </div>

      <DataTable
        columns={userColumns}
        rows={filtered}
        loading={loading}
        clientPageSize={25}
        densityToggle densityKey="users"
        empty={{
          icon: faUserShield,
          title: search ? 'Hech narsa topilmadi' : "Foydalanuvchilar yo'q",
          description: search ? "Qidiruv so'zini o'zgartirib ko'ring." : 'Xodim hisoblarini shu yerdan yarating.',
          action: !search && (
            <button className="button" onClick={openCreate}>
              <FontAwesomeIcon icon={faPlus} /> Yangi foydalanuvchi
            </button>
          ),
        }}
      />

      {/* ── Create / Edit Modal ── */}
      {modal && (
        <div className="modal-overlay" onClick={() => setModal(null)}>
          <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: 440 }}>
            <div className="modal-header">
              <h3>{modal === 'create' ? 'Yangi foydalanuvchi' : 'Foydalanuvchini tahrirlash'}</h3>
              <button className="modal-close" onClick={() => setModal(null)}>
                <FontAwesomeIcon icon={faXmark} />
              </button>
            </div>
            <div className="modal-body">
              {modal === 'create' && (
                <div className="form-group">
                  <label className="form-label">Username *</label>
                  <input className="form-input" type="text" value={form.username}
                    onChange={e => setForm(f => ({ ...f, username: e.target.value }))}
                    placeholder="foydalanuvchi_nomi" />
                </div>
              )}
              <div className="form-group">
                <label className="form-label">Ism familiya</label>
                <input className="form-input" type="text" value={form.full_name}
                  onChange={e => setForm(f => ({ ...f, full_name: e.target.value }))}
                  placeholder="To'liq ism" />
              </div>
              <div className="form-group">
                <label className="form-label">{modal === 'create' ? 'Parol *' : "Yangi parol (o'zgartirish uchun)"}</label>
                <input className="form-input" type="password" value={form.password}
                  onChange={e => setForm(f => ({ ...f, password: e.target.value }))}
                  placeholder={modal === 'create' ? 'Kamida 8 ta belgi' : "Bo'sh qoldiring — o'zgarmaydi (kamida 8 ta belgi)"} />
              </div>
              <div className="form-group">
                <label className="form-label">Rol</label>
                <select className="form-input" value={form.role}
                  onChange={e => setForm(f => ({ ...f, role: e.target.value }))}>
                  {ROLE_OPTIONS.map(o => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Muddati (bo'sh = cheksiz)</label>
                <input className="form-input" type="date" value={form.expires_at}
                  onChange={e => setForm(f => ({ ...f, expires_at: e.target.value }))} />
              </div>
              <div className="form-group">
                <label className="form-label">Telegram ID (bot bildirishnomasi uchun)</label>
                <input className="form-input" type="text" value={form.telegram_chat_id}
                  onChange={e => setForm(f => ({ ...f, telegram_chat_id: e.target.value }))}
                  placeholder="Masalan: 123456789" />
                <p className="text-muted" style={{ fontSize: 12, margin: '4px 0 0' }}>
                  Xodim botga /start bosib, o'z Telegram ID'sini yuborishi kerak — shuni shu yerga kiriting.
                  Audit ogohlantirishlari shu ID'ga yuboriladi.
                </p>
              </div>
            </div>
            <div className="modal-footer">
              <button className="button secondary" onClick={() => setModal(null)}>Bekor</button>
              <button className="button" onClick={handleSave} disabled={saving}>
                {saving ? 'Saqlanmoqda...' : 'Saqlash'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Block Modal ── */}
      {blockModal && (
        <div className="modal-overlay" onClick={() => setBlockModal(null)}>
          <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: 400 }}>
            <div className="modal-header">
              <h3>Akkountni bloklash</h3>
              <button className="modal-close" onClick={() => setBlockModal(null)}>
                <FontAwesomeIcon icon={faXmark} />
              </button>
            </div>
            <div className="modal-body">
              <p style={{ fontSize: 13, color: 'var(--text-2)', marginBottom: 16 }}>
                <strong>{blockModal.full_name || blockModal.username}</strong> akkauntini bloklayapsiz.
                Foydalanuvchi tizimga kira olmaydi.
              </p>
              <div className="form-group">
                <label className="form-label">Sabab *</label>
                <textarea className="form-input" rows={3} value={blockForm.reason}
                  onChange={e => setBlockForm(f => ({ ...f, reason: e.target.value }))}
                  placeholder="Blok sababi..." style={{ resize: 'vertical' }} />
              </div>
              <div className="form-group">
                <label className="form-label">Bog'lanish kontakti *</label>
                <input className="form-input" type="text" value={blockForm.contact}
                  onChange={e => setBlockForm(f => ({ ...f, contact: e.target.value }))}
                  placeholder="+998 90 123 45 67 yoki Telegram: @username" />
              </div>
            </div>
            <div className="modal-footer">
              <button className="button secondary" onClick={() => setBlockModal(null)}>Bekor</button>
              <button className="button danger" onClick={handleBlock} disabled={blocking}>
                {blocking ? 'Yuklanmoqda...' : (
                  <><FontAwesomeIcon icon={faLock} /> Bloklash</>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Permanent Delete Modal ── */}
      {deleteModal && (
        <div className="modal-overlay" onClick={() => setDeleteModal(null)}>
          <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: 420 }}>
            <div className="modal-header">
              <h3>Akkauntni butunlay o'chirish</h3>
              <button className="modal-close" onClick={() => setDeleteModal(null)}>
                <FontAwesomeIcon icon={faXmark} />
              </button>
            </div>
            <div className="modal-body">
              <p style={{ fontSize: 13, color: 'var(--danger-text)', fontWeight: 600, marginBottom: 8 }}>
                Diqqat! Bu amalni orqaga qaytarib bo'lmaydi.
              </p>
              <p style={{ fontSize: 13, color: 'var(--text-2)', marginBottom: 16 }}>
                <strong>{deleteModal.full_name || deleteModal.username}</strong> ({deleteModal.username}) akkaunti
                bazadan butunlay o'chiriladi. Unga bog'liq barcha yozuvlar (to'lov, lid, chegirma va h.k.) o'chirilmaydi,
                lekin ularga tegishli "kim qildi" ma'lumoti serverda backup faylga saqlanadi.
              </p>
              <p style={{ fontSize: 14, fontWeight: 600 }}>
                Rostdan ham <strong>@{deleteModal.username}</strong> ni o'chirmoqchimisiz?
              </p>
            </div>
            <div className="modal-footer">
              <button className="button secondary" onClick={() => setDeleteModal(null)}>Bekor</button>
              <button className="button danger" onClick={handleDeletePermanent} disabled={deleting}>
                {deleting ? 'O\'chirilmoqda...' : (
                  <><FontAwesomeIcon icon={faTrash} /> Ha, o'chirish</>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {broadcastModal && (
        <div className="modal-overlay" onClick={() => setBroadcastModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3><FontAwesomeIcon icon={faPaperPlane} /> Barcha xodimlarga xabar</h3>
              <button className="modal-close" onClick={() => setBroadcastModal(false)}>✕</button>
            </div>
            <div className="modal-body">
              <p className="text-muted" style={{ fontSize: 13, marginTop: 0 }}>
                Xabar Telegram orqali — profilida Telegram ID'si to'ldirilgan barcha faol xodimlarga yuboriladi.
              </p>
              <label className="form-label">Xabar matni *</label>
              <textarea className="form-input" rows={5} value={broadcastText}
                onChange={e => setBroadcastText(e.target.value)}
                placeholder="Xabar matnini shu yerga yozing..." />
            </div>
            <div className="modal-footer">
              <button className="button secondary" onClick={() => setBroadcastModal(false)}>Bekor</button>
              <button className="button" onClick={handleBroadcast} disabled={broadcasting}>
                {broadcasting ? 'Yuborilmoqda...' : 'Yuborish'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
