import { lazy, Suspense, useEffect, useState } from 'react'
import { Toaster } from 'react-hot-toast'
import Sidebar from './components/Sidebar'
import Topbar from './components/Topbar'
import Login from './components/Login'
const Lessons = lazy(() => import('./components/Lessons'))
const Students = lazy(() => import('./components/Students'))
const StudentDetail = lazy(() => import('./components/StudentDetail'))
const Groups = lazy(() => import('./components/Groups'))
const GroupDetail = lazy(() => import('./components/GroupDetail'))
const Payments = lazy(() => import('./components/Payments'))
const Dashboard = lazy(() => import('./components/Dashboard'))
const Tariffs = lazy(() => import('./components/Tariffs'))
const Courses = lazy(() => import('./components/Courses'))
const Finance = lazy(() => import('./components/Finance'))
const TodayAttendance = lazy(() => import('./components/TodayAttendance'))
const Users = lazy(() => import('./components/Users'))
const TeacherSalaries = lazy(() => import('./components/TeacherSalaries'))
const Salary = lazy(() => import('./components/Salary'))
const TeacherDashboard = lazy(() => import('./components/TeacherDashboard'))
const Expenses = lazy(() => import('./components/Expenses'))
const Leads = lazy(() => import('./components/Leads'))
const Tree = lazy(() => import('./components/Tree'))
const WorkCenter = lazy(() => import('./components/WorkCenter'))
const TeamActivity = lazy(() => import('./components/TeamActivity'))
const Special = lazy(() => import('./components/Special'))
const Academic = lazy(() => import('./components/Academic'))
const FeedbackInbox = lazy(() => import('./components/FeedbackInbox'))
const Notifications = lazy(() => import('./components/Notifications'))
const ChatBot = lazy(() => import('./components/ChatBot'))
const Parents = lazy(() => import('./components/Parents'))
import PublicIntake from './components/PublicIntake'
const Employees = lazy(() => import('./components/Employees'))
const AuditWarnings = lazy(() => import('./components/AuditWarnings'))
const MyWarnings = lazy(() => import('./components/MyWarnings'))
const BotAdmin = lazy(() => import('./components/BotAdmin'))
import { fetchMe, login as apiLogin, setToken } from './api'

function readHash() {
  const raw = window.location.hash.replace('#', '').trim()
  return raw || 'lessons'
}

// Har bir sahifa qaysi rollar uchun ochiq — Sidebar.jsx dagi navigatsiya
// tugmalarining ko'rinish shartlariga mos (bir joyda saqlanadi). Bu yerda
// yo'q sahifa — cheklovsiz (masalan profil/parol o'zgartirish kabi umumiy
// sahifalar bo'lsa). Maqsad: ruxsati yo'q sahifaga hash orqali (eski link,
// bookmark, qo'lda yozish) kirib, backend 403 "Ruxsat yo'q" bilan urilib
// qolishning oldini olish — buning o'rniga rolga mos boshlang'ich sahifaga
// qaytariladi.
const PAGE_ACCESS = {
  lessons:          ['admin', 'support_teacher', 'teacher'],
  students:         ['admin', 'support_teacher', 'hunter', 'sales', 'call_center'],
  student_detail:   ['admin', 'support_teacher', 'hunter', 'sales', 'call_center'],
  groups:           ['admin', 'support_teacher', 'hunter', 'sales', 'call_center'],
  // group_detail — LMS rollariga QO'SHIMCHA teacher ham kiradi (o'z guruhi, GroupDetail/backend o'zi tekshiradi)
  group_detail:     ['admin', 'support_teacher', 'hunter', 'sales', 'call_center', 'teacher'],
  payments:         ['admin', 'hunter'],
  dashboard:        ['admin'],
  teacher_salaries: ['admin'],
  salary:           ['admin'],
  expenses:         ['admin', 'hunter'],
  tariffs:          ['admin'],
  courses:          ['admin'],
  finance:          ['admin'],
  special:          ['admin'],
  users:            ['admin'],
  bot_admin:        ['admin'],
  teacher_dashboard: ['teacher'],
  today_attendance: ['admin', 'support_teacher', 'teacher', 'hunter', 'sales', 'call_center'],
  leads:            ['admin', 'hunter', 'sales', 'call_center'],
  tree:             ['admin', 'hunter', 'sales', 'call_center'],
  work_center:      ['admin', 'hunter', 'call_center'],
  team_activity:    ['admin'],
  notifications:    ['admin', 'hunter', 'sales', 'call_center'],
  chatbot:          ['admin', 'hunter'],
  parents:          ['admin', 'hunter'],
  feedbacks:        ['admin', 'call_center'],
  academic:         ['admin', 'support_teacher', 'teacher'],
  employees:        ['admin', 'audit'],
  audit_warnings:   ['admin', 'audit'],
  my_warnings:      ['support_teacher', 'teacher', 'hunter', 'sales', 'call_center'],
}

const DEFAULT_PAGE_BY_ROLE = {
  admin:           'lessons',
  support_teacher: 'lessons',
  teacher:         'teacher_dashboard',
  hunter:          'payments',
  sales:           'leads',
  call_center:     'leads',
  audit:           'employees',
}

function pageAllowedForRole(page, role) {
  const allowed = PAGE_ACCESS[page]
  if (!allowed) return true   // ro'yxatda yo'q sahifa — cheklanmagan
  return allowed.includes(role)
}

// Ommaviy (auth talab qilmaydigan) qabul formasi: #intake/<slug>
function readIntakeSlug() {
  const raw = window.location.hash.replace('#', '').trim()
  const m = raw.match(/^intake\/([A-Za-z0-9_-]+)$/)
  return m ? m[1] : null
}

function ScrollToTop() {
  const [visible, setVisible] = useState(false)
  useEffect(() => {
    const el = document.querySelector('.content')
    if (!el) return
    const onScroll = () => setVisible(el.scrollTop > 50)
    el.addEventListener('scroll', onScroll)
    return () => el.removeEventListener('scroll', onScroll)
  }, [])
  if (!visible) return null
  return (
    <button
      className="scroll-top-btn"
      onClick={() => document.querySelector('.content')?.scrollTo({ top: 0, behavior: 'smooth' })}
      title="Tepaga"
    >
      ↑
    </button>
  )
}

function App() {
  const [currentUser, setCurrentUser] = useState(null)
  const [isAuthed, setIsAuthed] = useState(Boolean(localStorage.getItem('token')))
  const [activePage, setActivePage] = useState(readHash)
  const [selectedCategory, setSelectedCategory] = useState('foundation')
  const [selectedGroup, setSelectedGroup] = useState(() => {
    try { return JSON.parse(sessionStorage.getItem('selectedGroup')) || null } catch { return null }
  })
  // Guruh qaysi sahifadan ochilgani — "Orqaga" o'sha sahifaga qaytarishi uchun
  // (masalan o'qituvchi "Mening guruhlarim"dan ochsa, admin-only "Guruhlar"ga
  // emas, "Mening guruhlarim"ga qaytishi kerak).
  const [groupDetailOrigin, setGroupDetailOrigin] = useState(() => sessionStorage.getItem('groupDetailOrigin') || 'groups')
  const [selectedStudent, setSelectedStudent] = useState(() => {
    try { return JSON.parse(sessionStorage.getItem('selectedStudent')) || null } catch { return null }
  })
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [intakeSlug, setIntakeSlug] = useState(readIntakeSlug)

  // Sync state when user navigates with browser back/forward
  useEffect(() => {
    function onHashChange() {
      setIntakeSlug(readIntakeSlug())
      const page = readHash()
      setActivePage(page)
      if (page !== 'group_detail') setSelectedGroup(null)
      if (page !== 'student_detail') setSelectedStudent(null)
    }
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])

  useEffect(() => {
    if (isAuthed) {
      fetchMe().then(setCurrentUser).catch(() => handleLogout())
    }
  }, [isAuthed])

  // Rolga ruxsat etilmagan sahifaga (eski hash/bookmark, qo'lda yozilgan
  // link) tushib qolinsa — backend 403 "Ruxsat yo'q" bilan urilib, bo'sh/
  // xato holatda qolish o'rniga, rolga mos boshlang'ich sahifaga qaytaradi.
  useEffect(() => {
    if (!currentUser) return
    if (!pageAllowedForRole(activePage, currentUser.role)) {
      handleNavigate(DEFAULT_PAGE_BY_ROLE[currentUser.role] || 'lessons')
    }
  }, [currentUser, activePage])

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
    sessionStorage.removeItem('selectedStudent')
    window.location.hash = 'lessons'
    setActivePage('lessons')
  }

  function handleNavigate(page) {
    window.location.hash = page
    setActivePage(page)
    setSidebarOpen(false)
  }

  useEffect(() => {
    const content = document.querySelector('.content')
    if (content) content.scrollTop = 0
  }, [activePage])

  // Ommaviy qabul formasi — auth talab qilinmaydi
  if (intakeSlug) {
    return (
      <>
        <Toaster position="top-right" />
        <PublicIntake slug={intakeSlug} />
      </>
    )
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
    <div className="app-shell" data-role={currentUser?.role}>
      <a href="#main-content" className="skip-link" onClick={e => { e.preventDefault(); document.getElementById('main-content')?.focus() }}>Asosiy kontentga o'tish</a>
      <Toaster position="top-right" />

      {sidebarOpen && <div className="sidebar-overlay" onClick={() => setSidebarOpen(false)} />}

      <Sidebar
        selectedCategory={selectedCategory}
        onSelectCategory={setSelectedCategory}
        currentUser={currentUser}
        activePage={activePage}
        onNavigate={handleNavigate}
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />

      <ScrollToTop />
      <main className="content" id="main-content" tabIndex={-1}>
        <Topbar
          activePage={activePage}
          currentUser={currentUser}
          onNavigate={handleNavigate}
          onAvatarUpdate={setCurrentUser}
          onLogout={handleLogout}
          onToggleMenu={() => setSidebarOpen(o => !o)}
        />

        {/* `data-module` — sahifaning semantik rangini beradi (styles.css
            dagi [data-module] qoidalari). Sarlavha ikonkasi va sahifaga xos
            urg'ular shu bitta atributdan rang oladi; hech bir sahifa o'z
            rangini qo'lda yozmaydi. */}
        <Suspense fallback={<div className="workspace-route-loading" role="status"><span /><p>Sahifa yuklanmoqda…</p></div>}>
        <div className="page-anim" data-module={activePage} key={activePage}>
          {activePage === 'lessons' && (
            <Lessons category={selectedCategory} onSelectCategory={setSelectedCategory} currentUser={currentUser} />
          )}
          {activePage === 'students' && (
            <Students currentUser={currentUser} onOpenStudent={s => {
              sessionStorage.setItem('selectedStudent', JSON.stringify(s))
              setSelectedStudent(s)
              window.location.hash = 'student_detail'
              setActivePage('student_detail')
            }} />
          )}
          {activePage === 'student_detail' && selectedStudent && (
            <StudentDetail
              student={selectedStudent}
              onBack={() => handleNavigate('students')}
              currentUser={currentUser}
              onChanged={s => { setSelectedStudent(s); sessionStorage.setItem('selectedStudent', JSON.stringify(s)) }}
            />
          )}
          {activePage === 'student_detail' && !selectedStudent && (
            <Students currentUser={currentUser} onOpenStudent={s => {
              sessionStorage.setItem('selectedStudent', JSON.stringify(s))
              setSelectedStudent(s)
              window.location.hash = 'student_detail'
              setActivePage('student_detail')
            }} />
          )}
          {activePage === 'groups' && (
            <Groups onOpenGroup={g => {
              sessionStorage.setItem('selectedGroup', JSON.stringify(g))
              sessionStorage.setItem('groupDetailOrigin', 'groups')
              setSelectedGroup(g)
              setGroupDetailOrigin('groups')
              window.location.hash = 'group_detail'
              setActivePage('group_detail')
            }} />
          )}
          {activePage === 'group_detail' && selectedGroup && (
            <GroupDetail group={selectedGroup} onBack={() => handleNavigate(groupDetailOrigin)} currentUser={currentUser} />
          )}
          {activePage === 'group_detail' && !selectedGroup && (
            <Groups onOpenGroup={g => {
              sessionStorage.setItem('selectedGroup', JSON.stringify(g))
              sessionStorage.setItem('groupDetailOrigin', 'groups')
              setSelectedGroup(g)
              setGroupDetailOrigin('groups')
              window.location.hash = 'group_detail'
              setActivePage('group_detail')
            }} />
          )}
          {activePage === 'payments' && <Payments currentUser={currentUser} />}
          {activePage === 'dashboard' && <Dashboard onNavigate={handleNavigate} />}
          {activePage === 'teacher_salaries' && <TeacherSalaries />}
          {activePage === 'salary' && <Salary />}
          {activePage === 'expenses' && <Expenses currentUser={currentUser} />}
          {activePage === 'tariffs' && <Tariffs />}
          {activePage === 'courses' && <Courses />}
          {activePage === 'finance' && <Finance onNavigate={handleNavigate} />}
          {activePage === 'teacher_dashboard' && (
            <TeacherDashboard currentUser={currentUser} onNavigate={handleNavigate} onOpenGroup={g => {
              sessionStorage.setItem('selectedGroup', JSON.stringify(g))
              sessionStorage.setItem('groupDetailOrigin', 'teacher_dashboard')
              setSelectedGroup(g)
              setGroupDetailOrigin('teacher_dashboard')
              window.location.hash = 'group_detail'
              setActivePage('group_detail')
            }} />
          )}
          {activePage === 'today_attendance' && (
            <TodayAttendance currentUser={currentUser} onOpenGroup={g => {
              sessionStorage.setItem('selectedGroup', JSON.stringify(g))
              sessionStorage.setItem('groupDetailOrigin', 'today_attendance')
              setSelectedGroup(g)
              setGroupDetailOrigin('today_attendance')
              window.location.hash = 'group_detail'
              setActivePage('group_detail')
            }} />
          )}
          {activePage === 'leads' && <Leads currentUser={currentUser} />}
          {activePage === 'tree' && <Tree currentUser={currentUser} />}
          {activePage === 'work_center' && <WorkCenter currentUser={currentUser} />}
          {activePage === 'team_activity' && <TeamActivity />}
          {activePage === 'special' && <Special />}
          {activePage === 'academic' && <Academic currentUser={currentUser} />}
          {activePage === 'feedbacks' && <FeedbackInbox currentUser={currentUser} />}
          {activePage === 'notifications' && <Notifications />}
          {activePage === 'chatbot' && <ChatBot />}
          {activePage === 'parents' && <Parents currentUser={currentUser} />}
          {activePage === 'users' && <Users currentUser={currentUser} />}
          {activePage === 'employees' && <Employees currentUser={currentUser} />}
          {activePage === 'audit_warnings' && <AuditWarnings currentUser={currentUser} />}
          {activePage === 'my_warnings' && <MyWarnings />}
          {activePage === 'bot_admin' && <BotAdmin />}
        </div>
        </Suspense>
      </main>
    </div>
  )
}

export default App
