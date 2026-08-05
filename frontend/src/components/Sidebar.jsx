import { useEffect, useRef, useState } from 'react'
import MinaretLogo from './MinaretLogo'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faBook, faUserGraduate, faUsers, faCreditCard,
  faChartBar, faRightFromBracket, faChevronDown,
  faCalendarCheck, faTag, faWallet, faUserShield,
  faChalkboardTeacher, faReceipt, faCamera,
  faHeadset, faBullseye, faStar, faBell, faBookOpen,
  faPen, faGraduationCap, faCommentDots, faPeopleRoof,
  faTriangleExclamation, faRobot, faComments,
} from '@fortawesome/free-solid-svg-icons'
import { toast } from 'react-hot-toast'
import { uploadAvatar, updateProfile, fetchFeedbackNewCount, createExpense, API_BASE } from '../api'
import { useTheme } from '../ThemeContext'

const CATEGORIES = [
  { key: 'foundation', label: 'Foundation' },
  { key: 'frontend',   label: 'Frontend' },
  { key: 'backend',    label: 'Backend' },
]

function Sidebar({
  selectedCategory, onSelectCategory,
  currentUser, onAvatarUpdate, onLogout,
  activePage, onNavigate, isOpen,
}) {
  const isAdmin      = currentUser?.role === 'admin'
  const isMetodist   = currentUser?.role === 'metodist' || isAdmin
  const isTeacher    = currentUser?.role === 'teacher'
  const isHunter     = currentUser?.role === 'hunter'
  const isSales      = currentUser?.role === 'sales'
  const isCallCenter = currentUser?.role === 'call_center'
  const isAudit       = currentUser?.role === 'audit'
  const hasCrmAccess = isHunter || isSales || isCallCenter || isAdmin

  const [catOpen, setCatOpen] = useState(activePage === 'lessons')
  const [uploading, setUploading] = useState(false)
  const [profileOpen, setProfileOpen] = useState(false)
  const [profileForm, setProfileForm] = useState({ full_name: '', current_password: '', password: '', password2: '' })
  const [savingProfile, setSavingProfile] = useState(false)
  const [expenseOpen, setExpenseOpen] = useState(false)
  const [expenseForm, setExpenseForm] = useState({ name: '', amount: '' })
  const [savingExpense, setSavingExpense] = useState(false)
  const { theme, setTheme } = useTheme()
  const fileInputRef = useRef(null)

  // Yangi (hal qilinmagan) o'quvchi izohlari soni — qizil badge (hunter/call_center/admin)
  const canSeeFeedbacks = isHunter || isCallCenter || isAdmin
  const [feedbackCount, setFeedbackCount] = useState(0)
  useEffect(() => {
    if (!canSeeFeedbacks) return
    let alive = true
    async function refresh() {
      try {
        const r = await fetchFeedbackNewCount()
        if (alive) setFeedbackCount(r.count || 0)
      } catch { /* jim — badge ikkilamchi */ }
    }
    refresh()
    const t = setInterval(refresh, 60000)
    window.addEventListener('feedbacks-changed', refresh)
    return () => { alive = false; clearInterval(t); window.removeEventListener('feedbacks-changed', refresh) }
  }, [canSeeFeedbacks])

  function openProfile() {
    setProfileForm({ full_name: currentUser?.full_name || '', current_password: '', password: '', password2: '' })
    setProfileOpen(true)
  }

  async function handleProfileSave() {
    const payload = {}
    const name = profileForm.full_name.trim()
    if (name !== (currentUser?.full_name || '')) payload.full_name = name
    if (profileForm.password) {
      if (profileForm.password.length < 8) { toast.error("Yangi parol kamida 8 belgi bo'lsin"); return }
      if (profileForm.password !== profileForm.password2) { toast.error('Parollar mos kelmadi'); return }
      if (!profileForm.current_password) { toast.error('Joriy parolni kiriting'); return }
      payload.password = profileForm.password
      payload.current_password = profileForm.current_password
    }
    if (Object.keys(payload).length === 0) { setProfileOpen(false); return }
    setSavingProfile(true)
    try {
      const updated = await updateProfile(payload)
      onAvatarUpdate?.(updated)
      toast.success('Profil yangilandi')
      setProfileOpen(false)
    } catch (err) {
      toast.error(err.message || 'Xatolik')
    } finally {
      setSavingProfile(false)
    }
  }

  function openExpense() {
    setExpenseForm({ name: '', amount: '' })
    setExpenseOpen(true)
  }

  async function handleExpenseSave() {
    if (!expenseForm.name.trim())                         { toast.error("Nom kiriting"); return }
    if (!expenseForm.amount || Number(expenseForm.amount) <= 0) { toast.error("Summa kiriting"); return }
    setSavingExpense(true)
    try {
      const now = new Date()
      await createExpense({
        name: expenseForm.name,
        amount: parseFloat(expenseForm.amount),
        month: now.getMonth() + 1,
        year: now.getFullYear(),
      })
      toast.success("Xarajat qo'shildi")
      setExpenseOpen(false)
    } catch (err) {
      toast.error(err.message || 'Xatolik')
    } finally {
      setSavingExpense(false)
    }
  }

  const avatarLetter = (currentUser?.full_name || currentUser?.username)?.[0]?.toUpperCase() ?? '?'
  const avatarUrl    = currentUser?.avatar ? `${API_BASE}/uploads/${currentUser.avatar}` : null
  const roleLabels   = {
    admin: 'Admin', metodist: 'Metodist', teacher: "O'qituvchi",
    hunter: 'Hunter', call_center: 'Call Center', sales: 'Sales', audit: 'Audit',
  }

  async function handleAvatarFile(e) {
    const file = e.target.files[0]
    if (!file) return
    setUploading(true)
    try {
      const updated = await uploadAvatar(file)
      onAvatarUpdate?.(updated)
      toast.success('Rasm yangilandi')
    } catch (err) {
      toast.error(err.message || 'Yuklash xatosi')
    } finally {
      setUploading(false)
      e.target.value = ''
    }
  }

  function handleLessonsClick() {
    if (activePage === 'lessons') {
      setCatOpen(v => !v)
    } else {
      onNavigate('lessons')
      setCatOpen(true)
    }
  }

  function handleCategoryClick(key) {
    onSelectCategory(key)
    if (activePage !== 'lessons') onNavigate('lessons')
  }

  return (
    <aside className={`sidebar${isOpen ? ' mobile-open' : ''}`}>
      <div className="brand">
        <MinaretLogo size={38} className="brand-minaret" />
        <span>Minar LMS</span>
      </div>

      <nav className="sidebar-nav">
        {/* Metodika — metodist, teacher, admin (Hunter, Sales, Call Center, Audit ko'rmaydi) */}
        {!isHunter && !isSales && !isCallCenter && !isAudit && (
          <>
            <div className="nav-section-label">Metodika</div>
            <button
              className={`nav-page-btn ${activePage === 'lessons' ? 'active' : ''}`}
              onClick={handleLessonsClick}
            >
              <FontAwesomeIcon icon={faBook} fixedWidth />
              <span style={{ flex: 1 }}>Dars rejalari</span>
              <span className={`cat-chevron${catOpen && activePage === 'lessons' ? ' open' : ''}`}>
                <FontAwesomeIcon icon={faChevronDown} />
              </span>
            </button>

            <div className={`category-list-wrap${catOpen && activePage === 'lessons' ? ' open' : ''}`}>
              <div className="category-list">
                {CATEGORIES.map((c, i) => (
                  <button
                    key={c.key}
                    className={`category-btn ${selectedCategory === c.key ? 'active' : ''}`}
                    onClick={() => handleCategoryClick(c.key)}
                    style={{ animationDelay: `${i * 40}ms` }}
                  >
                    {c.label}
                  </button>
                ))}
              </div>
            </div>
          </>
        )}

        {/* Hunter — Tariflar, Special va To'lovlar */}
        {isHunter && (
          <>
            <div className="nav-section-label">Narxlar</div>
            <button
              className={`nav-page-btn ${activePage === 'tariffs' ? 'active' : ''}`}
              onClick={() => onNavigate('tariffs')}
            >
              <FontAwesomeIcon icon={faTag} fixedWidth /> Kurs tariflari
            </button>
            <button
              className={`nav-page-btn ${activePage === 'special' ? 'active' : ''}`}
              onClick={() => onNavigate('special')}
            >
              <FontAwesomeIcon icon={faStar} fixedWidth /> Special
            </button>
            <button
              className={`nav-page-btn ${activePage === 'payments' ? 'active' : ''}`}
              onClick={() => onNavigate('payments')}
            >
              <FontAwesomeIcon icon={faCreditCard} fixedWidth /> To'lovlar
            </button>
          </>
        )}

        {/* Teacher only — My dashboard */}
        {isTeacher && (
          <>
            <div className="nav-section-label mt-3">Mening panelim</div>
            <button
              className={`nav-page-btn ${activePage === 'teacher_dashboard' ? 'active' : ''}`}
              onClick={() => onNavigate('teacher_dashboard')}
            >
              <FontAwesomeIcon icon={faChalkboardTeacher} fixedWidth /> Mening guruhlarim
            </button>
          </>
        )}

        {/* CRM — hunter, call_center, admin */}
        {hasCrmAccess && (
          <>
            <div className="nav-section-label mt-3">CRM</div>
            <button
              className={`nav-page-btn ${activePage === 'leads' ? 'active' : ''}`}
              onClick={() => onNavigate('leads')}
            >
              <FontAwesomeIcon icon={isHunter ? faBullseye : faHeadset} fixedWidth />
              {' Lidlar'}
            </button>
            <button
              className={`nav-page-btn ${activePage === 'notifications' ? 'active' : ''}`}
              onClick={() => onNavigate('notifications')}
            >
              <FontAwesomeIcon icon={faBell} fixedWidth /> Notifications
            </button>
            {(isHunter || isAdmin) && (
              <button
                className={`nav-page-btn ${activePage === 'chatbot' ? 'active' : ''}`}
                onClick={() => onNavigate('chatbot')}
              >
                <FontAwesomeIcon icon={faComments} fixedWidth /> Chatbot
              </button>
            )}
            {canSeeFeedbacks && (
              <button
                className={`nav-page-btn ${activePage === 'feedbacks' ? 'active' : ''}`}
                onClick={() => onNavigate('feedbacks')}
              >
                <FontAwesomeIcon icon={faCommentDots} fixedWidth />
                <span style={{ flex: 1 }}>Izohlar</span>
                {feedbackCount > 0 && <span className="nav-badge">{feedbackCount > 99 ? '99+' : feedbackCount}</span>}
              </button>
            )}
            {(isHunter || isAdmin) && (
              <button
                className={`nav-page-btn ${activePage === 'parents' ? 'active' : ''}`}
                onClick={() => onNavigate('parents')}
              >
                <FontAwesomeIcon icon={faPeopleRoof} fixedWidth /> Ota-onalar
              </button>
            )}
            {isHunter && (
              <button className="nav-page-btn" onClick={openExpense}>
                <FontAwesomeIcon icon={faReceipt} fixedWidth /> Xarajat qo'shish
              </button>
            )}
          </>
        )}

        {/* Akademik — teacher + metodist + hunter + admin (baholar, izohlar, sertifikatlar, tadbirlar) */}
        {!isCallCenter && !isSales && !isAudit && (
          <>
            <div className="nav-section-label mt-3">Akademik</div>
            <button
              className={`nav-page-btn ${activePage === 'academic' ? 'active' : ''}`}
              onClick={() => onNavigate('academic')}
            >
              <FontAwesomeIcon icon={faGraduationCap} fixedWidth /> Baholar va izohlar
            </button>
          </>
        )}

        {/* Davomat — teacher + metodist + admin + call_center + hunter (Audit ko'rmaydi) */}
        {!isAudit && (
          <>
            <div className="nav-section-label mt-3">Davomat</div>
            <button
              className={`nav-page-btn ${activePage === 'today_attendance' ? 'active' : ''}`}
              onClick={() => onNavigate('today_attendance')}
            >
              <FontAwesomeIcon icon={faCalendarCheck} fixedWidth /> Bugungi darslar
            </button>
          </>
        )}

        {/* Audit — ogohlantirishlar (audit va admin) */}
        {(isAudit || isAdmin) && (
          <>
            <div className="nav-section-label mt-3">Audit</div>
            <button
              className={`nav-page-btn ${activePage === 'audit_warnings' ? 'active' : ''}`}
              onClick={() => onNavigate('audit_warnings')}
            >
              <FontAwesomeIcon icon={faTriangleExclamation} fixedWidth /> Ogohlantirishlar
            </button>
          </>
        )}

        {/* Boshqa xodimlar — faqat o'ziga berilgan ogohlantirishlarni ko'radi */}
        {!isAudit && !isAdmin && (
          <>
            <div className="nav-section-label mt-3">Mening</div>
            <button
              className={`nav-page-btn ${activePage === 'my_warnings' ? 'active' : ''}`}
              onClick={() => onNavigate('my_warnings')}
            >
              <FontAwesomeIcon icon={faTriangleExclamation} fixedWidth /> Ogohlantirishlarim
            </button>
          </>
        )}

        {/* LMS */}
        {(isMetodist || isHunter || isSales || isCallCenter) && (
          <>
            <div className="nav-section-label mt-3">LMS</div>
            <button
              className={`nav-page-btn ${activePage === 'students' ? 'active' : ''}`}
              onClick={() => onNavigate('students')}
            >
              <FontAwesomeIcon icon={faUserGraduate} fixedWidth /> Talabalar
            </button>
            <button
              className={`nav-page-btn ${activePage === 'groups' || activePage === 'group_detail' ? 'active' : ''}`}
              onClick={() => onNavigate('groups')}
            >
              <FontAwesomeIcon icon={faUsers} fixedWidth /> Guruhlar
            </button>
          </>
        )}

        {/* Admin only */}
        {isAdmin && (
          <>
            <div className="nav-section-label mt-3">Moliya</div>
            <button
              className={`nav-page-btn ${activePage === 'finance' ? 'active' : ''}`}
              onClick={() => onNavigate('finance')}
            >
              <FontAwesomeIcon icon={faWallet} fixedWidth /> Moliya
            </button>
            <button
              className={`nav-page-btn ${activePage === 'payments' ? 'active' : ''}`}
              onClick={() => onNavigate('payments')}
            >
              <FontAwesomeIcon icon={faCreditCard} fixedWidth /> To'lovlar
            </button>
            <button
              className={`nav-page-btn ${activePage === 'tariffs' ? 'active' : ''}`}
              onClick={() => onNavigate('tariffs')}
            >
              <FontAwesomeIcon icon={faTag} fixedWidth /> Tariflar
            </button>
            <button
              className={`nav-page-btn ${activePage === 'courses' ? 'active' : ''}`}
              onClick={() => onNavigate('courses')}
            >
              <FontAwesomeIcon icon={faBookOpen} fixedWidth /> Kurslar
            </button>
            <button
              className={`nav-page-btn ${activePage === 'special' ? 'active' : ''}`}
              onClick={() => onNavigate('special')}
            >
              <FontAwesomeIcon icon={faStar} fixedWidth /> Special
            </button>
            <button
              className={`nav-page-btn ${activePage === 'teacher_salaries' ? 'active' : ''}`}
              onClick={() => onNavigate('teacher_salaries')}
            >
              <FontAwesomeIcon icon={faChalkboardTeacher} fixedWidth /> O'qituvchi maoshi
            </button>
            <button
              className={`nav-page-btn ${activePage === 'expenses' ? 'active' : ''}`}
              onClick={() => onNavigate('expenses')}
            >
              <FontAwesomeIcon icon={faReceipt} fixedWidth /> Xarajatlar
            </button>
            <button
              className={`nav-page-btn ${activePage === 'dashboard' ? 'active' : ''}`}
              onClick={() => onNavigate('dashboard')}
            >
              <FontAwesomeIcon icon={faChartBar} fixedWidth /> Dashboard
            </button>
            <div className="nav-section-label mt-3">Boshqaruv</div>
            <button
              className={`nav-page-btn ${activePage === 'users' ? 'active' : ''}`}
              onClick={() => onNavigate('users')}
            >
              <FontAwesomeIcon icon={faUserShield} fixedWidth /> Foydalanuvchilar
            </button>
            <button
              className={`nav-page-btn ${activePage === 'bot_admin' ? 'active' : ''}`}
              onClick={() => onNavigate('bot_admin')}
            >
              <FontAwesomeIcon icon={faRobot} fixedWidth /> Bot boshqaruvi
            </button>
          </>
        )}
      </nav>

      <div className="sidebar-footer">
        {currentUser && (
          <div className="user-info">
            <button
              className={`avatar avatar-btn${uploading ? ' uploading' : ''}`}
              onClick={() => fileInputRef.current?.click()}
              title="Rasm yuklash"
              disabled={uploading}
            >
              {avatarUrl
                ? <img src={avatarUrl} alt="avatar" className="avatar-img" />
                : avatarLetter}
              <span className="avatar-overlay">
                <FontAwesomeIcon icon={faCamera} />
              </span>
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/jpeg,image/png,image/webp,image/gif"
              style={{ display: 'none' }}
              onChange={handleAvatarFile}
            />
            <div className="user-meta">
              <span className="user-name">{currentUser.full_name || currentUser.username}</span>
              <span className="role-badge">{roleLabels[currentUser.role] || currentUser.role}</span>
            </div>
            <button className="profile-edit-btn" onClick={openProfile} title="Profilni tahrirlash">
              <FontAwesomeIcon icon={faPen} />
            </button>
          </div>
        )}

        <div className="theme-switcher">
          <span className="theme-switcher-label">Tema</span>
          <div className="theme-dots">
            <button
              className={`theme-dot theme-dot-light${theme === 'light' ? ' active' : ''}`}
              onClick={() => setTheme('light')}
              title="Kunduzgi"
            />
            <button
              className={`theme-dot theme-dot-dark${theme === 'dark' ? ' active' : ''}`}
              onClick={() => setTheme('dark')}
              title="Tungi"
            />
            <button
              className={`theme-dot theme-dot-ocean${theme === 'ocean' ? ' active' : ''}`}
              onClick={() => setTheme('ocean')}
              title="Ocean"
            />
          </div>
        </div>

        <button className="logout-btn" onClick={onLogout}>
          <FontAwesomeIcon icon={faRightFromBracket} /> Chiqish
        </button>
      </div>

      {profileOpen && (
        <div className="modal-overlay" onClick={() => setProfileOpen(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Profilni tahrirlash</h3>
              <button className="modal-close" onClick={() => setProfileOpen(false)}>✕</button>
            </div>
            <div className="modal-body">
              <label>Login</label>
              <input className="field" value={currentUser?.username || ''} disabled />
              <label>To'liq ism</label>
              <input
                className="field"
                value={profileForm.full_name}
                onChange={e => setProfileForm(p => ({ ...p, full_name: e.target.value }))}
                placeholder="Ism Familiya"
              />
              <hr style={{ border: 'none', borderTop: '1px solid var(--border, #e5e7eb)', margin: '16px 0' }} />
              <p style={{ fontSize: 13, opacity: 0.7, margin: '0 0 8px' }}>Parolni o'zgartirish (ixtiyoriy)</p>
              <label>Joriy parol</label>
              <input
                className="field"
                type="password"
                value={profileForm.current_password}
                onChange={e => setProfileForm(p => ({ ...p, current_password: e.target.value }))}
                placeholder="••••••••"
                autoComplete="current-password"
              />
              <label>Yangi parol</label>
              <input
                className="field"
                type="password"
                value={profileForm.password}
                onChange={e => setProfileForm(p => ({ ...p, password: e.target.value }))}
                placeholder="Kamida 8 belgi"
                autoComplete="new-password"
              />
              <label>Yangi parolni takrorlang</label>
              <input
                className="field"
                type="password"
                value={profileForm.password2}
                onChange={e => setProfileForm(p => ({ ...p, password2: e.target.value }))}
                placeholder="••••••••"
                autoComplete="new-password"
              />
            </div>
            <div className="modal-footer">
              <button className="button secondary" onClick={() => setProfileOpen(false)}>Bekor</button>
              <button className="button primary" onClick={handleProfileSave} disabled={savingProfile}>
                {savingProfile ? 'Saqlanmoqda...' : 'Saqlash'}
              </button>
            </div>
          </div>
        </div>
      )}

      {expenseOpen && (
        <div className="modal-overlay" onClick={() => setExpenseOpen(false)}>
          <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: 400 }}>
            <div className="modal-header">
              <h3>Xarajat qo'shish</h3>
              <button className="modal-close" onClick={() => setExpenseOpen(false)}>✕</button>
            </div>
            <div className="modal-body">
              <div className="form-group">
                <label className="form-label">Nomi / Sabab *</label>
                <input
                  className="form-input"
                  value={expenseForm.name}
                  onChange={e => setExpenseForm(f => ({ ...f, name: e.target.value }))}
                  placeholder="Ijara, kommunal, reklama..."
                />
              </div>
              <div className="form-group">
                <label className="form-label">Summa (so'm) *</label>
                <input
                  className="form-input"
                  type="number"
                  value={expenseForm.amount}
                  onChange={e => setExpenseForm(f => ({ ...f, amount: e.target.value }))}
                  placeholder="500000"
                />
              </div>
            </div>
            <div className="modal-footer">
              <button className="button secondary" onClick={() => setExpenseOpen(false)}>Bekor</button>
              <button className="button primary" onClick={handleExpenseSave} disabled={savingExpense}>
                {savingExpense ? 'Saqlanmoqda...' : 'Saqlash'}
              </button>
            </div>
          </div>
        </div>
      )}
    </aside>
  )
}

export default Sidebar
