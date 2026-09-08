import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faChevronUp, faChevronDown, faXmark, faCheck } from '@fortawesome/free-solid-svg-icons'

function LessonList({ lessons, selectedLessonId, onSelectLesson, canEdit, onReorder, onDelete }) {
  if (!lessons.length) {
    return <div className="muted">Bu hafta uchun darslar yo'q</div>
  }

  function moveLesson(index, direction) {
    const newLessons = [...lessons]
    const swapIndex = index + direction
    if (swapIndex < 0 || swapIndex >= newLessons.length) return
    const items = newLessons.map((l, i) => {
      if (i === index) return { id: l.id, lesson_number: newLessons[swapIndex].lesson_number }
      if (i === swapIndex) return { id: l.id, lesson_number: newLessons[index].lesson_number }
      return { id: l.id, lesson_number: l.lesson_number }
    })
    onReorder(items)
  }

  return (
    <ul className="lesson-list">
      {lessons.map((lesson, index) => (
        <li key={lesson.id} className={`lesson-list-item${lesson.id === selectedLessonId ? ' is-selected' : ''}`}>
          <button
            className={`lesson-card ${lesson.id === selectedLessonId ? 'selected' : ''}`}
            onClick={() => onSelectLesson(lesson.id)}
            aria-pressed={lesson.id === selectedLessonId}
          >
            <span className="lesson-number">{String(lesson.lesson_number).padStart(2, '0')}</span>
            <span className="lesson-row-copy"><span className="lesson-title">{lesson.title}</span><span className="lesson-section">{lesson.section || 'Bo‘lim kiritilmagan'}</span></span>
            {lesson.guide?.trim() && lesson.homework?.trim() && <span className="lesson-ready" title="Qo‘llanma va uy vazifasi tayyor"><FontAwesomeIcon icon={faCheck} /></span>}
          </button>

          {canEdit && (
            <div className="lesson-actions">
              <button
                className="icon-action"
                onClick={(e) => { e.stopPropagation(); moveLesson(index, -1) }}
                disabled={index === 0}
                title="Yuqoriga"
                aria-label={`${lesson.title}: yuqoriga`}
              ><FontAwesomeIcon icon={faChevronUp} /></button>
              <button
                className="icon-action"
                onClick={(e) => { e.stopPropagation(); moveLesson(index, 1) }}
                disabled={index === lessons.length - 1}
                title="Pastga"
                aria-label={`${lesson.title}: pastga`}
              ><FontAwesomeIcon icon={faChevronDown} /></button>
              <button
                className="icon-action danger"
                onClick={(e) => { e.stopPropagation(); onDelete(lesson) }}
                title="O'chirish"
                aria-label={`${lesson.title}: o‘chirish`}
              ><FontAwesomeIcon icon={faXmark} /></button>
            </div>
          )}
        </li>
      ))}
    </ul>
  )
}

export default LessonList
