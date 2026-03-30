import { useEffect, useState } from 'react'

function Sidebar({
  months,
  weeksByMonth,
  selectedMonth,
  selectedWeek,
  onSelectMonth,
  onSelectWeek,
  currentUser,
  onLogout,
}) {
  const [expandedMonth, setExpandedMonth] = useState(selectedMonth)

  useEffect(() => {
    setExpandedMonth(selectedMonth)
  }, [selectedMonth])

  const handleMonthClick = (month) => {
    if (expandedMonth === month) {
      setExpandedMonth(null)
    } else {
      setExpandedMonth(month)
      onSelectMonth(month)
    }
  }

  const roleLabel = currentUser?.role === 'metodist' ? 'Metodist' : "O'qituvchi"
  const roleClass = currentUser?.role === 'metodist' ? 'badge-metodist' : 'badge-teacher'
  const avatarLetter = currentUser?.username?.[0]?.toUpperCase() ?? '?'

  return (
    <aside className="sidebar">
      <div className="brand">Metodika</div>

      <nav className="sidebar-nav">
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
                {isExpanded &&
                  weeks.map((week) => (
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
      </nav>

      <div className="sidebar-footer">
        {currentUser && (
          <div className="user-info">
            <div className="avatar">{avatarLetter}</div>
            <div className="user-meta">
              <span className="user-name">{currentUser.username}</span>
              <span className={`role-badge ${roleClass}`}>{roleLabel}</span>
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
