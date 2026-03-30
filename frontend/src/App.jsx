import { useEffect, useMemo, useState } from 'react'
import { Toaster, toast } from 'react-hot-toast'
import Sidebar from './components/Sidebar'
import LessonList from './components/LessonList'
import LessonDetail from './components/LessonDetail'
import ProgressBar from './components/ProgressBar'
import Login from './components/Login'
import AddLessonModal from './components/AddLessonModal'
import AuditLogPanel from './components/AuditLogPanel'
import Students from './components/Students'
import Groups from './components/Groups'
import Payments from './components/Payments'
import Dashboard from './components/Dashboard'
import {
  fetchLessons, fetchMe, updateLesson, createLesson,
  deleteLesson, reorderLessons, login as apiLogin, setToken,
} from './api'

const MONTH_LABELS = { 1: '1-oy', 2: '2-oy', 3: '3-oy' }

function App() {
  const [lessons, setLessons] = useState([])
  const [currentUser, setCurrentUser] = useState(null)
  const [selectedMonth, setSelectedMonth] = useState(1)
  const [selectedWeek, setSelectedWeek] = useState(1)
  const [selectedLessonId, setSelectedLessonId] = useState(null)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [authError, setAuthError] = useState('')
  const [isAuthed, setIsAuthed] = useState(Boolean(localStorage.getItem('token')))
  const [showAddModal, setShowAddModal] = useState(false)
  const [showAuditPanel, setShowAuditPanel] = useState(false)
  const [activePage, setActivePage] = useState('metodika')

  const isMetodist = currentUser?.role === 'metodist' || currentUser?.role === 'admin'

  useEffect(() => {
    if (isAuthed) {
      fetchMe().then(setCurrentUser).catch(() => handleLogout())
      loadLessons()
    }
  }, [isAuthed])

  useEffect(() => {
    const firstWeek = weeksByMonth[selectedMonth]?.[0]
    if (firstWeek && firstWeek !== selectedWeek) setSelectedWeek(firstWeek)
  }, [selectedMonth])

  const weeksByMonth = useMemo(() => {
    const grouped = lessons.reduce((acc, lesson) => {
      acc[lesson.month] = acc[lesson.month] || new Set()
      acc[lesson.month].add(lesson.week)
      return acc
    }, {})
    const result = {}
    Object.entries(grouped).forEach(([month, weeks]) => {
      result[month] = [...weeks].sort((a, b) => a - b)
    })
    return result
  }, [lessons])

  const filteredLessons = useMemo(
    () => lessons
      .filter((l) => l.month === selectedMonth && l.week === selectedWeek)
      .sort((a, b) => a.lesson_number - b.lesson_number),
    [lessons, selectedMonth, selectedWeek],
  )

  const selectedLesson = lessons.find((l) => l.id === selectedLessonId)

  async function loadLessons() {
    setLoading(true)
    setError('')
    try {
      const data = await fetchLessons()
      setLessons(data)
      if (!selectedLessonId && data.length > 0) setSelectedLessonId(data[0].id)
      if (data.length > 0 && !weeksByMonth[selectedMonth]?.length) {
        setSelectedMonth(data[0].month)
        setSelectedWeek(data[0].week)
      }
    } catch {
      setError("Ma'lumotlarni yuklashda xatolik yuz berdi")
    } finally {
      setLoading(false)
    }
  }

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
    setLessons([])
    setSelectedLessonId(null)
    setActivePage('metodika')
  }

  async function handleSave(updates) {
    if (!selectedLessonId) return
    setSaving(true)
    try {
      const updated = await updateLesson(selectedLessonId, updates)
      setLessons((prev) => prev.map((l) => (l.id === updated.id ? updated : l)))
      toast.success('Saqlandi!')
    } catch {
      toast.error('Saqlashda xatolik')
    } finally {
      setSaving(false)
    }
  }

  async function handleAddLesson(payload) {
    try {
      const newLesson = await createLesson(payload)
      setLessons((prev) => [...prev, newLesson].sort((a, b) => a.lesson_number - b.lesson_number))
      setSelectedMonth(newLesson.month)
      setSelectedWeek(newLesson.week)
      setSelectedLessonId(newLesson.id)
      setShowAddModal(false)
      toast.success("Yangi dars qo'shildi!")
    } catch (err) {
      toast.error(err.message || "Dars qo'shishda xatolik")
    }
  }

  async function handleDeleteLesson(id) {
    try {
      await deleteLesson(id)
      const remaining = lessons.filter((l) => l.id !== id)
      setLessons(remaining)
      if (selectedLessonId === id) setSelectedLessonId(remaining[0]?.id ?? null)
      toast.success("Dars o'chirildi")
    } catch {
      toast.error("O'chirishda xatolik")
    }
  }

  async function handleReorder(items) {
    try {
      const updated = await reorderLessons(items)
      setLessons((prev) => {
        const map = Object.fromEntries(updated.map((l) => [l.id, l]))
        return prev.map((l) => map[l.id] ?? l)
      })
    } catch {
      toast.error('Tartib almashtirishda xatolik')
    }
  }

  const progress = useMemo(() => {
    const total = lessons.length || 1
    const filled = lessons.filter((l) => l.guide?.trim() && l.homework?.trim()).length
    return Math.round((filled / total) * 100)
  }, [lessons])

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
      <Sidebar
        months={MONTH_LABELS}
        weeksByMonth={weeksByMonth}
        selectedMonth={selectedMonth}
        selectedWeek={selectedWeek}
        onSelectMonth={setSelectedMonth}
        onSelectWeek={setSelectedWeek}
        currentUser={currentUser}
        onLogout={handleLogout}
        activePage={activePage}
        onNavigate={setActivePage}
      />

      <main className="content">
        {/* ── Metodika sahifasi ── */}
        {activePage === 'metodika' && (
          <>
            <header className="header">
              <div>
                <p className="eyebrow">O'quv metodikasi</p>
                <h1>36 ta dars rejalari</h1>
              </div>
              <div className="header-right">
                {isMetodist && (
                  <button className="button secondary icon-btn" onClick={() => setShowAuditPanel(true)}>
                    &#9679; Tarix
                  </button>
                )}
                <ProgressBar value={progress} />
              </div>
            </header>

            {error && <div className="error">{error}</div>}

            <div className="panels">
              <section className="panel">
                <div className="panel-head">
                  <h2>Hafta {selectedWeek} darslari</h2>
                  <div className="panel-head-actions">
                    {loading && <span className="tag">Yuklanmoqda...</span>}
                    {isMetodist && (
                      <button className="button primary small" onClick={() => setShowAddModal(true)}>
                        + Dars
                      </button>
                    )}
                  </div>
                </div>
                <LessonList
                  lessons={filteredLessons}
                  selectedLessonId={selectedLessonId}
                  onSelectLesson={setSelectedLessonId}
                  canEdit={isMetodist}
                  onReorder={handleReorder}
                  onDelete={handleDeleteLesson}
                />
              </section>

              <section className="panel">
                <div className="panel-head">
                  <h2>Dars tafsilotlari</h2>
                  {saving && <span className="tag">Saqlanmoqda...</span>}
                </div>
                {selectedLesson ? (
                  <LessonDetail
                    lesson={selectedLesson}
                    onSave={handleSave}
                    saving={saving}
                    canEdit={isMetodist}
                  />
                ) : (
                  <div className="muted">Dars tanlang</div>
                )}
              </section>
            </div>

            {showAddModal && (
              <AddLessonModal
                onSave={handleAddLesson}
                onClose={() => setShowAddModal(false)}
                existingNumbers={lessons.map((l) => l.lesson_number)}
              />
            )}
            {showAuditPanel && <AuditLogPanel onClose={() => setShowAuditPanel(false)} />}
          </>
        )}

        {activePage === 'students' && <Students />}
        {activePage === 'groups' && <Groups />}
        {activePage === 'payments' && <Payments />}
        {activePage === 'dashboard' && <Dashboard />}
      </main>
    </div>
  )
}

export default App
