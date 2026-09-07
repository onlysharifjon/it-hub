import { useState } from 'react'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faTriangleExclamation } from '@fortawesome/free-solid-svg-icons'
import Modal from './Modal'

/**
 * Tasdiqlash oynasi — brauzerning `window.confirm()` o'rniga.
 *
 * Ilgari ilovadagi HAR BIR o'chirish/arxivlash amali brauzerning bezaksiz
 * confirm'idan foydalanardi: ta'til yozuvini o'chirish ham, xodim akkountini
 * BUTUNLAY o'chirish ham bir xil darajada "arzon" ko'rinardi. `requireText`
 * bilan qaytarib bo'lmaydigan amallar uchun qo'shimcha to'siq qo'yiladi —
 * foydalanuvchi tasdiq matnini (masalan, xodim ismini) yozishi kerak.
 *
 *   <ConfirmDialog open={!!target} title="Tarifni o'chirish"
 *     message={`"${target.name}" o'chirilsinmi?`}
 *     onConfirm={doDelete} onClose={() => setTarget(null)} />
 *
 *   // qaytarib bo'lmaydigan amal uchun:
 *   <ConfirmDialog ... requireText={user.username} danger />
 */
export default function ConfirmDialog({
  open,
  title = 'Tasdiqlaysizmi?',
  message,
  detail,
  confirmLabel = 'Ha, davom etish',
  cancelLabel = 'Bekor',
  onConfirm,
  onClose,
  danger = true,
  loading = false,
  requireText = null,
}) {
  const [typed, setTyped] = useState('')
  const blocked = requireText ? typed.trim() !== requireText : false

  function handleClose() {
    setTyped('')
    onClose?.()
  }

  return (
    <Modal
      open={open}
      title={title}
      onClose={handleClose}
      size="sm"
      footer={
        <>
          <button className="button secondary" onClick={handleClose} disabled={loading}>
            {cancelLabel}
          </button>
          <button
            className={`button ${danger ? 'danger' : 'primary'}`}
            onClick={onConfirm}
            disabled={loading || blocked}
          >
            {loading ? 'Bajarilmoqda...' : confirmLabel}
          </button>
        </>
      }
    >
      <div className="ui-confirm">
        <div className={`ui-confirm-icon ${danger ? 'is-danger' : ''}`.trim()}>
          <FontAwesomeIcon icon={faTriangleExclamation} />
        </div>
        <div>
          {message && <div className="ui-confirm-msg">{message}</div>}
          {detail && <div className="ui-confirm-detail">{detail}</div>}
        </div>
      </div>

      {requireText && (
        <div className="ui-field">
          <label className="ui-field-label">
            Tasdiqlash uchun <code>{requireText}</code> deb yozing
          </label>
          <input
            className="field"
            value={typed}
            onChange={e => setTyped(e.target.value)}
            placeholder={requireText}
            autoComplete="off"
          />
        </div>
      )}
    </Modal>
  )
}
