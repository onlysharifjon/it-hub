import { useEffect, useState } from 'react'
import { Toaster } from 'react-hot-toast'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faBars } from '@fortawesome/free-solid-svg-icons'
import Sidebar from './components/Sidebar'
import Login from './components/Login'
import Lessons from './components/Lessons'
import Students from './components/Students'
import Groups from './components/Groups'
import GroupDetail from './components/GroupDetail'
import Payments from './components/Payments'
import Dashboard from './components/Dashboard'
import Tariffs from './components/Tariffs'
import Finance from './components/Finance'
import TodayAttendance from './components/TodayAttendance'
import Users from './components/Users'
import TeacherSalaries from './components/TeacherSalaries'
import Expenses from './components/Expenses'
import { fetchMe, login as apiLogin, setToken } from './api'

function readHash() {
  const raw = window.location.hash.replace('#', '').trim()
  return raw || 'lessons'
}

function App() {
  const [currentUser, setCurrentUser] = useState(null)
  const [isAuthed, setIsAuthed] = useState(Boolean(localStorage.getItem('token')))
  const [activePage, setActivePage] = useState(readHash)
  const [selectedCategory, setSelectedCategory] = useState('foundation')
  const [selectedGroup, setSelectedGroup] = useState(() => {
    try { return JSON.parse(sessionStorage.getItem('selectedGroup')) || null } catch { return null }
  })
  const [sidebarOpen, setSidebarOpen] = useState(false)

  // Sync state when user navigates with browser back/forward
  useEffect(() => {
    function onHashChange() {
      const page = readHash()
      setActivePage(page)
      if (page !== 'group_detail') setSelectedGroup(null)
    }
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])

  useEffect(() => {
    if (isAuthed) {
      fetchMe().then(setCurrentUser).catch(() => handleLogout())
    }
  }, [isAuthed])

  async function handleLogin({ username, password }) {
    try {
      await apiLogin(username, password)
      setIsAuthed(true)
    } catch (err) {
      setIsAuthed(false)
      throw err  // let Login.jsx inspect err.detail for block/expiry
    }
  }

  function handleLogout() {
    setToken(null)
    setIsAuthed(false)
    setCurrentUser(null)
    sessionStorage.removeItem('selectedGroup')
    window.location.hash = 'lessons'
    setActivePage('lessons')
  }

  function handleNavigate(page) {
    window.location.hash = page
    setActivePage(page)
    setSidebarOpen(false)
  }

  if (!isAuthed) {
    return (
      <div className="app-shell login-mode">
        <Toaster position="top-right" />
        <Login onSuccess={handleLogin} />
      </div>
    )
  }

  return (
    <div className="app-shell">
      <Toaster position="top-right" />

      {sidebarOpen && <div className="sidebar-overlay" onClick={() => setSidebarOpen(false)} />}

      <Sidebar
        selectedCategory={selectedCategory}
        onSelectCategory={setSelectedCategory}
        currentUser={currentUser}
        onLogout={handleLogout}
        activePage={activePage}
        onNavigate={handleNavigate}
        isOpen={sidebarOpen}
      />

      <main className="content">
        <div className="mobile-topbar">
          <button className="menu-toggle" onClick={() => setSidebarOpen(o => !o)} aria-label="Menu">
            <FontAwesomeIcon icon={faBars} />
          </button>
          <span className="mobile-brand">IT Hub LMS</span>
        </div>

        <div className="page-anim" key={activePage}>
          {activePage === 'lessons' && (
            <Lessons category={selectedCategory} currentUser={currentUser} />
          )}
          {activePage === 'students' && <Students />}
          {activePage === 'groups' && (
            <Groups onOpenGroup={g => {
              sessionStorage.setItem('selectedGroup', JSON.stringify(g))
              setSelectedGroup(g)
              window.location.hash = 'group_detail'
              setActivePage('group_detail')
            }} />
          )}
          {activePage === 'group_detail' && selectedGroup && (
            <GroupDetail group={selectedGroup} onBack={() => handleNavigate('groups')} currentUser={currentUser} />
          )}
          {activePage === 'group_detail' && !selectedGroup && (
            <Groups onOpenGroup={g => {
              sessionStorage.setItem('selectedGroup', JSON.stringify(g))
              setSelectedGroup(g)
              window.location.hash = 'group_detail'
              setActivePage('group_detail')
            }} />
          )}
          {activePage === 'payments' && <Payments />}
          {activePage === 'dashboard' && <Dashboard onNavigate={handleNavigate} />}
          {activePage === 'teacher_salaries' && <TeacherSalaries />}
          {activePage === 'expenses' && <Expenses />}
          {activePage === 'tariffs' && <Tariffs />}
          {activePage === 'finance' && <Finance />}
          {activePage === 'today_attendance' && (
            <TodayAttendance currentUser={currentUser} onOpenGroup={g => {
              sessionStorage.setItem('selectedGroup', JSON.stringify(g))
              setSelectedGroup(g)
              window.location.hash = 'group_detail'
              setActivePage('group_detail')
            }} />
          )}
          {activePage === 'users' && <Users currentUser={currentUser} />}
        </div>
      </main>
    </div>
  )
}

export default App
