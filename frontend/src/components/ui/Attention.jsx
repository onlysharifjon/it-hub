import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faTriangleExclamation, faCircleInfo, faCircleCheck, faArrowRight,
} from '@fortawesome/free-solid-svg-icons'

const LEVEL_ICON = {
  critical: faTriangleExclamation,
  warning:  faTriangleExclamation,
  info:     faCircleInfo,
}

/**
 * "E'tibor talab qiladi" paneli.
 *
 * Nima uchun: ilovada birorta ham ogohlantirish bloki yo'q edi — davomat 58%
 * ga tushsa ham u boshqa o'nlab raqam orasida kulrang matn bo'lib turardi.
 * Hisobot foydalanuvchidan muammoni o'zi topishni talab qiladi; bu panel
 * muammoni oldiga qo'yadi va darhol harakat havolasini beradi.
 *
 * items: [{ id, level, title, detail, value, actionLabel, onAction }]
 */
export default function AttentionPanel({ title = "E'tibor talab qiladi", items = [], emptyText = "Hammasi joyida — hozircha e'tibor talab qiladigan narsa yo'q" }) {
  const sorted = [...items].sort((a, b) => {
    const rank = { critical: 0, warning: 1, info: 2 }
    return (rank[a.level] ?? 3) - (rank[b.level] ?? 3)
  })
  const critical = sorted.filter(i => i.level === 'critical').length

  return (
    <section className="ui-attention" aria-label={title}>
      <header className="ui-attention-head">
        <h2>{title}</h2>
        {sorted.length > 0 && (
          <span className={`ui-attention-count${critical ? ' is-critical' : ''}`}>
            {sorted.length}
          </span>
        )}
      </header>

      {sorted.length === 0 ? (
        <div className="ui-attention-empty">
          <FontAwesomeIcon icon={faCircleCheck} />
          <span>{emptyText}</span>
        </div>
      ) : (
        <ul className="ui-attention-list">
          {sorted.map(item => (
            <li key={item.id} className={`ui-attention-item level-${item.level || 'info'}`}>
              <span className="ui-attention-icon">
                <FontAwesomeIcon icon={LEVEL_ICON[item.level] || faCircleInfo} />
              </span>
              <span className="ui-attention-body">
                <span className="ui-attention-title">{item.title}</span>
                {item.detail && <span className="ui-attention-detail">{item.detail}</span>}
              </span>
              {item.value != null && <span className="ui-attention-value">{item.value}</span>}
              {item.onAction && (
                <button className="ui-attention-action" onClick={item.onAction} type="button">
                  {item.actionLabel || "Ko'rish"}
                  <FontAwesomeIcon icon={faArrowRight} />
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
