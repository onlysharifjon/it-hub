import { useEffect, useState } from 'react'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faBook, faUserGraduate, faUsers, faCreditCard,
  faChartBar, faRightFromBracket, faChevronDown, faChevronRight,
} from '@fortawesome/free-solid-svg-icons'

function Sidebar({
  months, weeksByMonth, selectedMonth, selectedWeek,
  onSelectMonth, onSelectWeek, currentUser, onLogout,
  activePage, onNavigate,
}) {
  const [expandedMonth, setExpandedMonth] = useState(selectedMonth)

  useEffect(() => { setExpandedMonth(selectedMonth) }, [selectedMonth])

  const isAdmin = currentUser?.role === 'admin'
  const isMetodist = currentUser?.role === 'metodist' || isAdmin

  const handleMonthClick = (month) => {
    setExpandedMonth(expandedMonth === month ? null : month)
    onSelectMonth(month)
  }

  const avatarLetter = (currentUser?.full_name || currentUser?.username)?.[0]?.toUpperCase() ?? '?'
  const roleLabels = { admin: 'Admin', metodist: 'Metodist', teacher: "O'qituvchi" }

  return (
    <aside className="sidebar">
      <div className="brand">IT Hub LMS</div>

      <nav className="sidebar-nav">
        {/* Metodika */}
        <div className="nav-section-label">Metodika</div>
        <button
          className={`nav-page-btn ${activePage === 'metodika' ? 'active' : ''}`}
          onClick={() => onNavigate('metodika')}
        >
          <FontAwesomeIcon icon={faBook} fixedWidth /> Dars rejalari
        </button>

        {/* Metodika submenu */}
        {activePage === 'metodika' && (
          <div className="month-list">
            {Object.entries(months).map(([month, label]) => {
              const monthNumber = Number(month)
              const isExpanded = expandedMonth === monthNumber
              const isActiveMonth = monthNumber === selectedMonth
              const weeks = weeksByMonth[month] || []
              return (
                <div key={month} className="month-block">
                  <button
                    className={`month ${isActiveMonth ? 'active' : ''}`}
                    onClick={() => handleMonthClick(monthNumber)}
                  >
                    <span className="month-label">{label}</span>
                    <span className={`chevron ${isExpanded ? 'open' : ''}`}>
                      {isExpanded ? '▾' : '▸'}
                    </span>
                  </button>
                  <div
                    className={`weeks ${isExpanded ? 'expanded' : 'collapsed'}`}
                    style={{ maxHeight: isExpanded ? weeks.length * 44 + 12 : 0 }}
                  >
                    {isExpanded && weeks.map((week) => (
                      <button
                        key={week}
                        className={`week ${Number(week) === selectedWeek ? 'active' : ''}`}
                        onClick={() => onSelectWeek(Number(week))}
                      >
                        Hafta {week}
                      </button>
                    ))}
                  </div>
                </div>
              )
            })}
          </div>
        )}

        {/* LMS — metodist + admin */}
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
              className={`nav-page-btn ${activePage === 'groups' ? 'active' : ''}`}
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
