import { useRef } from 'react'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faXmark } from '@fortawesome/free-solid-svg-icons'
import useFocusTrap from './useFocusTrap'

/**
 * Umumiy modal oynasi — mavjud `.modal-overlay/.modal/.modal-header/.modal-body/
 * .modal-footer` klasslari ustiga qurilgan (ya'ni ko'rinishi o'zgarmaydi), lekin
 * qo'shimcha: Escape bilan yopish, Tab fokus tutqichi, role="dialog"/aria-modal
 * va sahifa scroll'ini bloklash.
 *
 * O'lchamlar: sm (400px) · md (480px, standart) · lg (640px) · xl (820px).
 * Yon paneli uchun — pastdagi <Drawer>.
 *
 *   <Modal open={!!modal} title="Yangi tarif" onClose={close}
 *          footer={<><button className="button secondary" onClick={close}>Bekor</button>
 *                    <button className="button primary" onClick={save}>Saqlash</button></>}>
 *     ...maydonlar...
 *   </Modal>
 */
export default function Modal({
  open,
  title,
  onClose,
  children,
  footer,
  size = 'md',
  closeOnOverlay = true,
  labelledBy,
}) {
  const ref = useRef(null)
  useFocusTrap(open, ref, () => onClose?.())

  if (!open) return null

  const titleId = labelledBy || 'modal-title'

  return (
    <div
      className="modal-overlay"
      onClick={closeOnOverlay ? onClose : undefined}
    >
      <div
        ref={ref}
        className={`modal modal-${size}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby={title ? titleId : undefined}
        onClick={e => e.stopPropagation()}
      >
        {title && (
          <div className="modal-header">
            <h3 id={titleId}>{title}</h3>
            <button className="modal-close" onClick={onClose} aria-label="Yopish">
              <FontAwesomeIcon icon={faXmark} />
            </button>
          </div>
        )}
        <div className="modal-body">{children}</div>
        {footer && <div className="modal-footer">{footer}</div>}
      </div>
    </div>
  )
}

/**
 * Yon panel (drawer) — o'ngdan chiqadigan variant. Modal bilan bir xil
 * klaviatura xulqi (Escape + fokus tutqichi), lekin boshqa joylashuv.
 */
export function Drawer({ open, title, onClose, children, footer, width = 460, labelledBy }) {
  const ref = useRef(null)
  useFocusTrap(open, ref, () => onClose?.())

  if (!open) return null

  const titleId = labelledBy || 'drawer-title'

  return (
    <div className="drawer-overlay" onClick={onClose}>
      <aside
        ref={ref}
        className="drawer"
        style={{ width: `min(${width}px, 100%)` }}
        role="dialog"
        aria-modal="true"
        aria-labelledby={title ? titleId : undefined}
        onClick={e => e.stopPropagation()}
      >
        {title && (
          <div className="modal-header">
            <h3 id={titleId}>{title}</h3>
            <button className="modal-close" onClick={onClose} aria-label="Yopish">
              <FontAwesomeIcon icon={faXmark} />
            </button>
          </div>
        )}
        <div className="drawer-body">{children}</div>
        {footer && <div className="modal-footer">{footer}</div>}
      </aside>
    </div>
  )
}
