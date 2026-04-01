import { useState } from 'react'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faBook, faUserGraduate, faUsers, faCreditCard,
  faChartBar, faRightFromBracket, faChevronDown,
  faCalendarCheck, faTag, faWallet, faUserShield,
  faChalkboardTeacher, faReceipt,
} from '@fortawesome/free-solid-svg-icons'

const CATEGORIES = [
  { key: 'foundation', label: 'Foundation' },
  { key: 'frontend',   label: 'Frontend' },
  { key: 'backend',    label: 'Backend' },
]

function Sidebar({
  selectedCategory, onSelectCategory,
  currentUser, onLogout,
  activePage, onNavigate, isOpen,
}) {
  const isAdmin    = currentUser?.role === 'admin'
  const isMetodist = currentUser?.role === 'metodist' || isAdmin

  const [catOpen, setCatOpen] = useState(activePage === 'lessons')

  const avatarLetter = (currentUser?.full_name || currentUser?.username)?.[0]?.toUpperCase() ?? '?'
  const roleLabels   = { admin: 'Admin', metodist: 'Metodist', teacher: "O'qituvchi" }

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
      <div className="brand">IT Hub LMS</div>

      <nav className="sidebar-nav">
        {/* Darslar */}
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

        {/* Davomat — teacher + metodist + admin */}
        <div className="nav-section-label mt-3">Davomat</div>
        <button
          className={`nav-page-btn ${activePage === 'today_attendance' ? 'active' : ''}`}
          onClick={() => onNavigate('today_attendance')}
        >
          <FontAwesomeIcon icon={faCalendarCheck} fixedWidth /> Bugungi darslar
        </button>

        {/* LMS */}
        {isMetodist && (
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
            <div className="avatar">{avatarLetter}</div>
            <div className="user-meta">
              <span className="user-name">{currentUser.full_name || currentUser.username}</span>
              <span className="role-badge">{roleLabels[currentUser.role] || currentUser.role}</span>
            </div>
          </div>
        )}
        <button className="logout-btn" onClick={onLogout}>
          <FontAwesomeIcon icon={faRightFromBracket} /> Chiqish
        </button>
      </div>
    </aside>
  )
}

export default Sidebar
