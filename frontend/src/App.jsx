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
import { fetchMe, login as apiLogin, setToken } from './api'

function App() {
  const [currentUser, setCurrentUser] = useState(null)
  const [authError, setAuthError] = useState('')
  const [isAuthed, setIsAuthed] = useState(Boolean(localStorage.getItem('token')))
  const [activePage, setActivePage] = useState('lessons')
  const [selectedCategory, setSelectedCategory] = useState('foundation')
  const [selectedGroup, setSelectedGroup] = useState(null)
  const [sidebarOpen, setSidebarOpen] = useState(false)

  useEffect(() => {
    if (isAuthed) {
      fetchMe().then(setCurrentUser).catch(() => handleLogout())
    }
  }, [isAuthed])

  async function handleLogin({ username, password }) {
    setAuthError('')
    try {
      await apiLogin(username, password)
      setIsAuthed(true)
    } catch (err) {
      setAuthError(err.message || 'Login yoki parol xato')
      setIsAuthed(false)
    }
  }

  function handleLogout() {
    setToken(null)
    setIsAuthed(false)
    setCurrentUser(null)
    setActivePage('lessons')
  }

  function handleNavigate(page) {
    setActivePage(page)
    setSidebarOpen(false)
  }

  if (!isAuthed) {
    return (
      <div className="app-shell login-mode">
        <Toaster position="top-right" />
        <Login onSuccess={handleLogin} error={authError} />
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

        {activePage === 'lessons' && (
          <Lessons category={selectedCategory} currentUser={currentUser} />
        )}
        {activePage === 'students' && <Students />}
        {activePage === 'groups' && (
          <Groups onOpenGroup={g => { setSelectedGroup(g); setActivePage('group_detail') }} />
        )}
        {activePage === 'group_detail' && selectedGroup && (
          <GroupDetail group={selectedGroup} onBack={() => setActivePage('groups')} />
        )}
        {activePage === 'payments' && <Payments />}
        {activePage === 'dashboard' && <Dashboard />}
      </main>
    </div>
  )
}

export default App
