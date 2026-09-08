import { useEffect, useRef, useState } from 'react'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faMagnifyingGlass, faBars,
  faRightFromBracket, faPen, faCamera, faPlus, faChevronDown,
} from '@fortawesome/free-solid-svg-icons'
import { toast } from 'react-hot-toast'
import { uploadAvatar, updateProfile, API_BASE } from '../api'
import { ROLE_LABELS } from '../constants/domain'
import Modal from './ui/Modal'
import { Input } from './ui/Field'
import NotificationBell from './NotificationBell'
import CommandPalette from './CommandPalette'
import ThemeToggle from './ui/ThemeToggle'
import BrandLogo from './ui/BrandLogo'
import { flatNav } from '../constants/nav'

/** Tezkor amallar — rolga qarab (faqat foydalanuvchi kira oladigan sahifalar). */
const QUICK_ACTIONS = [
  { key: 'leads',    label: 'Yangi lid',    roles: ['hunter', 'sales', 'call_center', 'admin'] },
  { key: 'students', label: 'Yangi talaba', roles: ['admin', 'support_teacher', 'hunter', 'sales', 'call_center'] },
  { key: 'payments', label: "To'lov qabul", roles: ['admin', 'hunter'] },
]

export default function Topbar({ currentUser, activePage, onNavigate, onAvatarUpdate, onLogout, onToggleMenu }) {
  const role = currentUser?.role
  const [paletteOpen, setPaletteOpen] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  const [quickOpen, setQuickOpen] = useState(false)
  const [profileOpen, setProfileOpen] = useState(false)
  const [profileForm, setProfileForm] = useState({ full_name: '', current_password: '', password: '', password2: '' })
  const [profileErrors, setProfileErrors] = useState({})
  const [savingProfile, setSavingProfile] = useState(false)
  const [uploading, setUploading] = useState(false)
  const fileInputRef = useRef(null)
  const menuRef = useRef(null)
  const quickRef = useRef(null)

  // Cmd/Ctrl+K — global qidiruv
  useEffect(() => {
    function onKey(e) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setPaletteOpen(true)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  // Tashqariga bosilganda menyularni yopish
  useEffect(() => {
    function onClick(e) {
      if (menuRef.current && !menuRef.current.contains(e.target)) setMenuOpen(false)
      if (quickRef.current && !quickRef.current.contains(e.target)) setQuickOpen(false)
    }
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [])

  const avatarLetter = (currentUser?.full_name || currentUser?.username)?.[0]?.toUpperCase() ?? '?'
  const avatarUrl = currentUser?.avatar ? `${API_BASE}/uploads/${currentUser.avatar}` : null
  const quickActions = QUICK_ACTIONS.filter(a => a.roles.includes(role))
  const currentNav = flatNav(role).find(item => item.key === activePage || item.alsoActiveOn?.includes(activePage))

  function openProfile() {
    setProfileForm({ full_name: currentUser?.full_name || '', current_password: '', password: '', password2: '' })
    setProfileErrors({})
    setProfileOpen(true)
    setMenuOpen(false)
  }

  async function handleAvatarFile(e) {
    const file = e.target.files[0]
    if (!file) return
    setUploading(true)
    try {
      const updated = await uploadAvatar(file)
      onAvatarUpdate?.(updated)
      toast.success('Rasm yangilandi')
    } catch (err) { toast.error(err.message || 'Yuklash xatosi') }
    finally { setUploading(false); e.target.value = '' }
  }

  async function handleProfileSave() {
    const payload = {}
    const errs = {}
    const name = profileForm.full_name.trim()
    if (name !== (currentUser?.full_name || '')) payload.full_name = name
    if (profileForm.password) {
      if (profileForm.password.length < 8) errs.password = "Kamida 8 belgi bo'lsin"
      if (profileForm.password !== profileForm.password2) errs.password2 = 'Parollar mos kelmadi'
      if (!profileForm.current_password) errs.current_password = 'Joriy parolni kiriting'
      payload.password = profileForm.password
      payload.current_password = profileForm.current_password
    }
    setProfileErrors(errs)
    if (Object.keys(errs).length) return
    if (Object.keys(payload).length === 0) { setProfileOpen(false); return }
    setSavingProfile(true)
    try {
      const updated = await updateProfile(payload)
      onAvatarUpdate?.(updated)
      toast.success('Profil yangilandi')
      setProfileOpen(false)
    } catch (err) { toast.error(err.message || 'Xatolik') }
    finally { setSavingProfile(false) }
  }

  return (
    <>
      <header className="topbar">
        <button className="topbar-menu-btn" onClick={onToggleMenu} aria-label="Menyu">
          <FontAwesomeIcon icon={faBars} />
        </button>

        {/* Mobil qatlamda yon panel ekrandan tashqarida — brend faqat shu
            yerda ko'rinadi. Desktopda esa yon panel brendni ko'rsatib turadi,
            shuning uchun bu element yashiriladi (takrorlamaslik uchun). */}
        <BrandLogo variant="mark" size="lg" className="topbar-brand" />

        <div className="workspace-breadcrumb" aria-label="Joriy bo‘lim"><span>{currentNav?.group || 'Ish maydoni'}</span><span aria-hidden="true">/</span><strong>{currentNav?.label || 'Minar Academy'}</strong></div>

        <button className="topbar-search" onClick={() => setPaletteOpen(true)}>
          <FontAwesomeIcon icon={faMagnifyingGlass} />
          <span>Qidirish...</span>
          <kbd>Ctrl K</kbd>
        </button>

        <div className="topbar-actions">
          {quickActions.length > 0 && (
            <div className="topbar-quick" ref={quickRef}>
              <button className="button small" onClick={() => setQuickOpen(v => !v)} aria-expanded={quickOpen}>
                <FontAwesomeIcon icon={faPlus} /> Yangi
                <FontAwesomeIcon icon={faChevronDown} style={{ fontSize: 10 }} />
              </button>
              {quickOpen && (
                <div className="topbar-dropdown">
                  {quickActions.map(a => (
                    <button key={a.key} className="topbar-dropdown-item"
                      onClick={() => { setQuickOpen(false); onNavigate(a.key) }}>
                      {a.label}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          <NotificationBell onNavigate={onNavigate} />

          <ThemeToggle />

          <div className="topbar-profile" ref={menuRef}>
            <div className="topbar-profile-copy"><strong>{currentUser?.full_name || currentUser?.username}</strong><span>{ROLE_LABELS[role] || role}</span></div>
            <button className="topbar-avatar" onClick={() => setMenuOpen(v => !v)} aria-expanded={menuOpen} aria-label="Profil menyusi">
              {avatarUrl ? <img src={avatarUrl} alt="" /> : avatarLetter}
            </button>
            {menuOpen && (
              <div className="topbar-dropdown is-right">
                <div className="topbar-user">
                  <div className="topbar-user-name">{currentUser?.full_name || currentUser?.username}</div>
                  <div className="topbar-user-role">{ROLE_LABELS[role] || role}</div>
                </div>
                <button className="topbar-dropdown-item" onClick={() => { setMenuOpen(false); fileInputRef.current?.click() }} disabled={uploading}>
                  <FontAwesomeIcon icon={faCamera} fixedWidth /> {uploading ? 'Yuklanmoqda...' : 'Rasm yuklash'}
                </button>
                <button className="topbar-dropdown-item" onClick={openProfile}>
                  <FontAwesomeIcon icon={faPen} fixedWidth /> Profilni tahrirlash
                </button>
                <button className="topbar-dropdown-item is-danger" onClick={onLogout}>
                  <FontAwesomeIcon icon={faRightFromBracket} fixedWidth /> Chiqish
                </button>
              </div>
            )}
          </div>
        </div>

        <input
          ref={fileInputRef} type="file" style={{ display: 'none' }}
          accept="image/jpeg,image/png,image/webp,image/gif"
          onChange={handleAvatarFile}
        />
      </header>

      <CommandPalette
        open={paletteOpen}
        onClose={() => setPaletteOpen(false)}
        role={role}
        onNavigate={onNavigate}
      />

      <Modal
        open={profileOpen}
        title="Profilni tahrirlash"
        onClose={() => setProfileOpen(false)}
        size="sm"
        footer={
          <>
            <button className="button secondary" onClick={() => setProfileOpen(false)}>Bekor</button>
            <button className="button" onClick={handleProfileSave} disabled={savingProfile}>
              {savingProfile ? 'Saqlanmoqda...' : 'Saqlash'}
            </button>
          </>
        }
      >
        <Input label="F.I.O" value={profileForm.full_name}
          onChange={e => setProfileForm(p => ({ ...p, full_name: e.target.value }))} />
        <Input label="Joriy parol" type="password" value={profileForm.current_password}
          error={profileErrors.current_password}
          onChange={e => setProfileForm(p => ({ ...p, current_password: e.target.value }))}
          hint="Faqat parolni o'zgartirmoqchi bo'lsangiz to'ldiring" />
        <Input label="Yangi parol" type="password" value={profileForm.password}
          error={profileErrors.password}
          onChange={e => setProfileForm(p => ({ ...p, password: e.target.value }))} />
        <Input label="Yangi parolni tasdiqlang" type="password" value={profileForm.password2}
          error={profileErrors.password2}
          onChange={e => setProfileForm(p => ({ ...p, password2: e.target.value }))} />
      </Modal>
    </>
  )
}
