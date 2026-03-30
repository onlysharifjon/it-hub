import { useEffect, useState } from 'react'

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
      <div className="brand">🎓 IT Hub LMS</div>

      <nav className="sidebar-nav">
        {/* Metodika */}
        <div className="nav-section-label">Metodika</div>
        <button
          className={`nav-page-btn ${activePage === 'metodika' ? 'active' : ''}`}
          onClick={() => onNavigate('metodika')}
        >
          📚 Dars rejalari
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
              👨‍🎓 Talabalar
            </button>
            <button
              className={`nav-page-btn ${activePage === 'groups' ? 'active' : ''}`}
              onClick={() => onNavigate('groups')}
            >
              👥 Guruhlar
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
              💳 To'lovlar
            </button>
            <button
              className={`nav-page-btn ${activePage === 'dashboard' ? 'active' : ''}`}
              onClick={() => onNavigate('dashboard')}
            >
              📊 Dashboard
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
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
            <polyline points="16 17 21 12 16 7"/>
            <line x1="21" y1="12" x2="9" y2="12"/>
          </svg>
          Chiqish
        </button>
      </div>
    </aside>
  )
}

export default Sidebar
