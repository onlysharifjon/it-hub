import { useEffect, useMemo, useState } from 'react'
import { toast } from 'react-hot-toast'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faPlus, faLayerGroup, faCode, faServer, faClockRotateLeft } from '@fortawesome/free-solid-svg-icons'
import LessonList from './LessonList'
import LessonDetail from './LessonDetail'
import AuditLogPanel from './AuditLogPanel'
import AddLessonModal from './AddLessonModal'
import ProgressBar from './ProgressBar'
import { fetchLessons, createLesson, updateLesson, deleteLesson, reorderLessons } from '../api'
import useConfirm from './ui/useConfirm'

const CATEGORY_LABELS = {
  foundation: 'Foundation',
  frontend: 'Frontend',
  backend: 'Backend',
}

export default function Lessons({ category, onSelectCategory, currentUser }) {
  const [confirmUI, ask] = useConfirm()
  const [lessons, setLessons] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [showAdd, setShowAdd] = useState(false)
  const [showAudit, setShowAudit] = useState(false)

  const isMetodist = currentUser?.role === 'support_teacher' || currentUser?.role === 'admin'

  useEffect(() => {
    load()
  }, [category])

  async function load() {
    setLoading(true)
    try {
      const data = await fetchLessons(category)
      setLessons(data)
      setSelectedId(data[0]?.id ?? null)
    } catch {
      toast.error("Darslarni yuklab bo'lmadi")
    } finally {
      setLoading(false)
    }
  }

  async function handleSave(updates) {
    if (!selectedId) return
    setSaving(true)
    try {
      const updated = await updateLesson(selectedId, updates)
      setLessons(prev => prev.map(l => l.id === updated.id ? updated : l))
      toast.success('Saqlandi')
    } catch {
      toast.error('Saqlashda xatolik')
    } finally {
      setSaving(false)
    }
  }

  async function handleAdd(payload) {
    const newLesson = await createLesson({ ...payload, category })
    setLessons(prev => [...prev, newLesson].sort((a, b) => a.lesson_number - b.lesson_number))
    setSelectedId(newLesson.id)
    setShowAdd(false)
    toast.success("Dars qo'shildi")
  }

  async function handleDelete(lesson) {
    const ok = await ask({
      title: 'Darsni o\'chirish',
      message: `"${lesson.title}" darsi o'chirilsinmi?`,
      detail: "Dars rejasi, qo'llanma va uy vazifasi matni ham o'chadi.",
      confirmLabel: "Ha, o'chirish",
    })
    if (!ok) return
    await deleteLesson(lesson.id)
    const remaining = lessons.filter(l => l.id !== lesson.id)
    setLessons(remaining)
    if (selectedId === lesson.id) setSelectedId(remaining[0]?.id ?? null)
    toast.success("O'chirildi")
  }

  async function handleReorder(items) {
    try {
      const updated = await reorderLessons(items)
      setLessons(prev => {
        const map = Object.fromEntries(updated.map(l => [l.id, l]))
        return prev.map(l => map[l.id] ?? l)
      })
    } catch {
      toast.error('Tartib almashtirishda xatolik')
    }
  }

  const selectedLesson = lessons.find(l => l.id === selectedId)

  const progress = useMemo(() => {
    if (!lessons.length) return 0
    const filled = lessons.filter(l => l.guide?.trim() && l.homework?.trim()).length
    return Math.round(filled / lessons.length * 100)
  }, [lessons])

  const existingNumbers = lessons.map(l => l.lesson_number)

  return (
    <div className="lessons-page">
      {confirmUI}
      <div className="lessons-header">
        <div>
          <p className="eyebrow">O'quv metodikasi</p>
          <h1>Dars rejalari</h1>
          <p className="page-subtitle">Dasturlar, dars qo‘llanmalari va uy vazifalari</p>
        </div>
        <div className="header-right">
          {isMetodist && (
            <button className="button secondary icon-btn" onClick={() => setShowAudit(true)}>
              <FontAwesomeIcon icon={faClockRotateLeft} /> Tarix
            </button>
          )}
          <div className="lesson-completion"><span>Reja tayyorligi <strong>{progress}%</strong></span><ProgressBar value={progress} /></div>
        </div>
      </div>

      <div className="lesson-tracks" aria-label="O‘quv dasturi">
        {Object.entries(CATEGORY_LABELS).map(([key, label], i) => (
          <button key={key} type="button" className={`lesson-track${key === category ? ' is-active' : ''}`}
            aria-pressed={key === category} onClick={() => onSelectCategory?.(key)}>
            <span className="lesson-track-icon"><FontAwesomeIcon icon={[faLayerGroup, faCode, faServer][i]} /></span>
            <span><strong>{label}</strong><small>{['Dasturlash asoslari', 'Veb interfeyslar', 'Server va ma’lumotlar'][i]}</small></span>
            <span className="lesson-track-index">0{i + 1}</span>
          </button>
        ))}
      </div>

      <div className="lessons-body">
        <section className="lesson-panel">
          <div className="panel-head">
            <h2>{CATEGORY_LABELS[category]} <span className="lesson-count">{lessons.length} dars</span></h2>
            <div className="panel-head-actions">
              {loading && <span className="tag">Yuklanmoqda...</span>}
              {isMetodist && (
                <button className="button small" onClick={() => setShowAdd(true)}>
                  <FontAwesomeIcon icon={faPlus} /> Dars
                </button>
              )}
            </div>
          </div>
          <LessonList
            lessons={lessons}
            selectedLessonId={selectedId}
            onSelectLesson={setSelectedId}
            canEdit={isMetodist}
            onReorder={handleReorder}
            onDelete={handleDelete}
          />
        </section>

        <section className="lesson-panel">
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
            <div className="muted center py-8">
              {lessons.length === 0 ? 'Hali dars yo\'q' : 'Dars tanlang'}
            </div>
          )}
        </section>
      </div>

      {showAdd && (
        <AddLessonModal
          category={category}
          onSave={handleAdd}
          onClose={() => setShowAdd(false)}
          existingNumbers={existingNumbers}
        />
      )}
      {showAudit && <AuditLogPanel onClose={() => setShowAudit(false)} />}
    </div>
  )
}
