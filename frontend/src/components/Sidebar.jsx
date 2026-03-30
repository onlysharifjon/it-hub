import { useState } from 'react'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faBook, faUserGraduate, faUsers, faCreditCard,
  faChartBar, faRightFromBracket,
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
  const isAdmin = currentUser?.role === 'admin'
  const isMetodist = currentUser?.role === 'metodist' || isAdmin

  const avatarLetter = (currentUser?.full_name || currentUser?.username)?.[0]?.toUpperCase() ?? '?'
  const roleLabels = { admin: 'Admin', metodist: 'Metodist', teacher: "O'qituvchi" }

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
          onClick={() => onNavigate('lessons')}
        >
          <FontAwesomeIcon icon={faBook} fixedWidth /> Dars rejalari
        </button>

        {activePage === 'lessons' && (
          <div className="category-list">
            {CATEGORIES.map(c => (
              <button
                key={c.key}
                className={`category-btn ${selectedCategory === c.key ? 'active' : ''}`}
                onClick={() => handleCategoryClick(c.key)}
              >
                {c.label}
              </button>
            ))}
          </div>
        )}

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
            <button
              className={`nav-page-btn ${activePage === 'payments' ? 'active' : ''}`}
              onClick={() => onNavigate('payments')}
            >
              <FontAwesomeIcon icon={faCreditCard} fixedWidth /> To'lovlar
            </button>
            <button
              className={`nav-page-btn ${activePage === 'dashboard' ? 'active' : ''}`}
              onClick={() => onNavigate('dashboard')}
            >
              <FontAwesomeIcon icon={faChartBar} fixedWidth /> Dashboard
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
        <button className="logout-btn" onClick={onLogout} title="Chiqish">
          <FontAwesomeIcon icon={faRightFromBracket} /> Chiqish
        </button>
      </div>
    </aside>
  )
}

export default Sidebar
