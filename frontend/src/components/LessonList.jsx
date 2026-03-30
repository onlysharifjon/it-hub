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
        <li key={lesson.id} className="lesson-list-item">
          <button
            className={`lesson-card ${lesson.id === selectedLessonId ? 'selected' : ''}`}
            onClick={() => onSelectLesson(lesson.id)}
          >
            <div className="lesson-number">Dars {lesson.lesson_number}</div>
            <div className="lesson-title">{lesson.title}</div>
            <div className="lesson-section">Bo'lim: {lesson.section || 'kiritilmagan'}</div>
          </button>

          {canEdit && (
            <div className="lesson-actions">
              <button
                className="icon-action"
                onClick={(e) => { e.stopPropagation(); moveLesson(index, -1) }}
                disabled={index === 0}
                title="Yuqoriga"
              >▲</button>
              <button
                className="icon-action"
                onClick={(e) => { e.stopPropagation(); moveLesson(index, 1) }}
                disabled={index === lessons.length - 1}
                title="Pastga"
              >▼</button>
              <button
                className="icon-action danger"
                onClick={(e) => {
                  e.stopPropagation()
                  if (confirm(`"${lesson.title}" darsini o'chirasizmi?`)) {
                    onDelete(lesson.id)
                  }
                }}
                title="O'chirish"
              >✕</button>
            </div>
          )}
        </li>
      ))}
    </ul>
  )
}

export default LessonList
