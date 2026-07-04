import { useRef, useState } from 'react'
import MinaretLogo from './MinaretLogo'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faBook, faUserGraduate, faUsers, faCreditCard,
  faChartBar, faRightFromBracket, faChevronDown,
  faCalendarCheck, faTag, faWallet, faUserShield,
  faChalkboardTeacher, faReceipt, faCamera,
  faHeadset, faBullseye, faGraduationCap, faPercent,
} from '@fortawesome/free-solid-svg-icons'
import { toast } from 'react-hot-toast'
import { uploadAvatar, API_BASE } from '../api'
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
  const isCallCenter = currentUser?.role === 'call_center'
  const hasCrmAccess = isHunter || isCallCenter || isAdmin

  const [catOpen, setCatOpen] = useState(activePage === 'lessons')
  const [uploading, setUploading] = useState(false)
  const { theme, setTheme } = useTheme()
  const fileInputRef = useRef(null)

  const avatarLetter = (currentUser?.full_name || currentUser?.username)?.[0]?.toUpperCase() ?? '?'
  const avatarUrl    = currentUser?.avatar ? `${API_BASE}/uploads/${currentUser.avatar}` : null
  const roleLabels   = {
    admin: 'Admin', metodist: 'Metodist', teacher: "O'qituvchi",
    hunter: 'Hunter', call_center: 'Call Center',
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
        {/* Metodika — metodist, teacher, admin (Hunter ko'rmaydi) */}
        {!isHunter && (
          <>
            <div className="nav-section-label">Metodika</div>
            {isMetodist && (
              <button
                className={`nav-page-btn ${activePage === 'courses' ? 'active' : ''}`}
                onClick={() => onNavigate('courses')}
              >
                <FontAwesomeIcon icon={faGraduationCap} fixedWidth /> Kurslar
              </button>
            )}
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

        {/* Hunter — Tariflar va Chegirmalar */}
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
              className={`nav-page-btn ${activePage === 'discounts' ? 'active' : ''}`}
              onClick={() => onNavigate('discounts')}
            >
              <FontAwesomeIcon icon={faPercent} fixedWidth /> Chegirmalar
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
              {isHunter ? ' Mening lidlarim' : ' Lidlar'}
            </button>
          </>
        )}

        {/* Davomat — teacher + metodist + admin + call_center + hunter */}
        <div className="nav-section-label mt-3">Davomat</div>
        <button
          className={`nav-page-btn ${activePage === 'today_attendance' ? 'active' : ''}`}
          onClick={() => onNavigate('today_attendance')}
        >
          <FontAwesomeIcon icon={faCalendarCheck} fixedWidth /> Bugungi darslar
        </button>

        {/* LMS */}
        {(isMetodist || isHunter || isCallCenter) && (
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
            {(isCallCenter) && (
              <button
                className={`nav-page-btn ${activePage === 'payments' ? 'active' : ''}`}
                onClick={() => onNavigate('payments')}
              >
                <FontAwesomeIcon icon={faCreditCard} fixedWidth /> To'lovlar
              </button>
            )}
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
    </aside>
  )
}

export default Sidebar
