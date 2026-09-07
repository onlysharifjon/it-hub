import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faInbox, faTriangleExclamation, faRotateRight } from '@fortawesome/free-solid-svg-icons'
import { BRAND_ASSETS } from '../../constants/brand'

/**
 * Bo'sh holat — "hali ma'lumot yo'q" uchun.
 * Ilgari har sahifa o'zicha qilardi: kimdir ikonka+matn, kimdir emoji, kimdir
 * shunchaki bo'sh qator. Endi bitta ko'rinish.
 *
 *   <EmptyState title="Tariflar yo'q" description="Birinchi tarifni qo'shing"
 *               action={<button className="button primary">Qo'shish</button>} />
 */
export function EmptyState({ icon = faInbox, title, description, action, compact = false, brand = true }) {
  return (
    <div className={`ui-state ${compact ? 'ui-state-compact' : ''}`}>
      <div className="ui-state-figure">
        {/* Brend belgisi — ikonka ORTIDA, juda past shaffoflikda.
            Bu yerda logotip "nima yo'q"ligini tushuntirmaydi (buni kontekst
            ikonkasi qiladi), shuning uchun u yetakchi element emas: bo'sh
            ekranga brend nafasini beradi, xolos. Zich (compact) holatda
            umuman chizilmaydi. */}
        {brand && !compact && (
          <img
            className="ui-state-brand"
            src={BRAND_ASSETS.mark.brand.src}
            alt=""
            aria-hidden="true"
            draggable="false"
          />
        )}
        <div className="ui-state-icon"><FontAwesomeIcon icon={icon} /></div>
      </div>
      {title && <div className="ui-state-title">{title}</div>}
      {description && <div className="ui-state-desc">{description}</div>}
      {action && <div className="ui-state-action">{action}</div>}
    </div>
  )
}

/**
 * Xatolik holati — qayta urinish tugmasi bilan.
 * Ilgari xatolik faqat toast'da ko'rinardi va sahifa bo'sh qolardi: foydalanuvchi
 * nima bo'lganini ham, nima qilishni ham bilmasdi.
 *
 *   <ErrorState message={err.message} onRetry={load} />
 */
export function ErrorState({
  title = 'Ma\'lumotni yuklab bo\'lmadi',
  message,
  onRetry,
  compact = false,
}) {
  return (
    <div className={`ui-state ui-state-error ${compact ? 'ui-state-compact' : ''}`}>
      <div className="ui-state-icon"><FontAwesomeIcon icon={faTriangleExclamation} /></div>
      <div className="ui-state-title">{title}</div>
      {message && <div className="ui-state-desc">{message}</div>}
      {onRetry && (
        <div className="ui-state-action">
          <button className="button secondary" onClick={onRetry}>
            <FontAwesomeIcon icon={faRotateRight} /> Qayta urinish
          </button>
        </div>
      )}
    </div>
  )
}

/** Bitta skeleton chizig'i (kenglik/balandlik sozlanadi). */
export function Skeleton({ width = '100%', height = 14, radius, style }) {
  return (
    <span
      className="ui-skeleton"
      style={{ width, height, borderRadius: radius ?? 'var(--radius-sm)', ...style }}
    />
  )
}

/** Jadval skeleton'i — yuklanayotganda jadval shaklini saqlab turadi. */
export function TableSkeleton({ rows = 6, cols = 5 }) {
  return (
    <div className="table-wrap" aria-hidden="true">
      <table className="data-table">
        <tbody>
          {Array.from({ length: rows }).map((_, r) => (
            <tr key={r}>
              {Array.from({ length: cols }).map((_, c) => (
                <td key={c}>
                  <Skeleton width={c === 0 ? '40%' : `${60 + ((r + c) % 3) * 12}%`} />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/** Karta skeleton'i — KPI/karta setkalari uchun. */
export function CardSkeleton({ count = 1, height = 92 }) {
  return (
    <>
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="ui-skeleton-card" style={{ height }} aria-hidden="true">
          <Skeleton width="45%" height={11} />
          <Skeleton width="70%" height={22} />
          <Skeleton width="35%" height={11} />
        </div>
      ))}
    </>
  )
}

/** Forma skeleton'i — modal ichida ma'lumot yuklanayotganda. */
export function FormSkeleton({ fields = 3 }) {
  return (
    <div className="ui-skeleton-form" aria-hidden="true">
      {Array.from({ length: fields }).map((_, i) => (
        <div key={i} className="ui-skeleton-field">
          <Skeleton width="30%" height={11} />
          <Skeleton height={36} radius="var(--radius)" />
        </div>
      ))}
    </div>
  )
}
