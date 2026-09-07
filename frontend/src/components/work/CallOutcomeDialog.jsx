import { useState } from 'react'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faPhone, faSpinner } from '@fortawesome/free-solid-svg-icons'
import Modal from '../ui/Modal'
import { Textarea } from '../ui/Field'
import { inputToIso } from '../../utils/datetime'

/**
 * Qo'ng'iroqdan keyingi natija oynasi.
 *
 * Talab: tez bo'lsin. Xodim kuniga 40+ qo'ng'iroq qiladi — har biriga uzun
 * forma to'ldirsa, hech kim yozmaydi (aynan shu sabab ilgari izohlar deyarli
 * bo'sh edi). Shuning uchun bu yerda majburiy maydon bitta: NATIJA.
 * Qolgani ixtiyoriy.
 */

const OUTCOMES = [
  { v: 'connected',    label: "Bog'landim",           tone: 'success' },
  { v: 'no_answer',    label: 'Javob bermadi',        tone: 'muted' },
  { v: 'phone_off',    label: "Telefon o'chiq",       tone: 'muted' },
  { v: 'callback',     label: "Qayta qo'ng'iroq kerak", tone: 'info' },
  { v: 'resolved',     label: 'Muammo hal qilindi',   tone: 'success' },
  { v: 'will_pay',     label: "To'lov qiladi",        tone: 'success' },
  { v: 'wont_pay',     label: "To'lov qilmaydi",      tone: 'danger' },
  { v: 'returns',      label: 'Darsga qaytadi',       tone: 'success' },
  { v: 'not_returns',  label: 'Darsga qaytmaydi',     tone: 'danger' },
  { v: 'interested',   label: 'Qiziqdi',              tone: 'success' },
  { v: 'rejected',     label: 'Rad etdi',             tone: 'danger' },
  { v: 'wrong_number', label: "Noto'g'ri raqam",      tone: 'muted' },
]

const NEXT_ACTIONS = [
  { v: 'callback', label: "Qayta qo'ng'iroq" },
  { v: 'watch',    label: 'Kuzatish' },
  { v: 'close',    label: 'Yopish' },
  { v: 'other',    label: 'Boshqa' },
]

const PROMISES = [
  { v: 'yes',     label: 'Ha' },
  { v: 'no',      label: "Yo'q" },
  { v: 'partial', label: 'Qisman' },
  { v: 'unknown', label: "Noma'lum" },
]

export default function CallOutcomeDialog({ task, saving, onClose, onSubmit }) {
  const [outcome, setOutcome] = useState('')
  const [note, setNote] = useState('')
  const [nextAction, setNextAction] = useState('')
  const [nextAt, setNextAt] = useState('')
  const [promise, setPromise] = useState('')
  const [promisedAt, setPromisedAt] = useState('')

  const isPayment = task?.task_type === 'PAYMENT_REMINDER'
  const needsDate = nextAction === 'callback'

  function submit() {
    if (!outcome) return
    onSubmit({
      entity_type: task.entity_type,
      entity_id: task.entity_id,
      outcome,
      note: note.trim() || null,
      next_action: nextAction || null,
      next_action_at: needsDate ? inputToIso(nextAt) : null,
      payment_promise: isPayment ? (promise || null) : null,
      promised_at: isPayment && promisedAt ? promisedAt : null,
      source_key: task.source_key,
      task_type: task.task_type,
      complete_task: true,
    })
  }

  return (
    <Modal
      open
      title="Qo'ng'iroq natijasi"
      onClose={onClose}
      footer={
        <>
          <button className="button secondary" onClick={onClose}>Bekor</button>
          <button className="button" onClick={submit} disabled={saving || !outcome}>
            {saving
              ? <><FontAwesomeIcon icon={faSpinner} className="kc-spin" /> Saqlanmoqda</>
              : 'Saqlash'}
          </button>
        </>
      }
    >
      <div className="co-who">
        <FontAwesomeIcon icon={faPhone} />
        <div>
          <strong>{task.title}</strong>
          <span className="muted"> · {task.task_label}</span>
          {task.phone && <div className="muted" style={{ fontSize: 12 }}>{task.phone}</div>}
        </div>
      </div>

      <label className="co-label">Natija <span className="req">*</span></label>
      <div className="co-opts" role="radiogroup" aria-label="Qo'ng'iroq natijasi">
        {OUTCOMES.map(o => (
          <button
            key={o.v} type="button" role="radio" aria-checked={outcome === o.v}
            className={`co-opt tone-${o.tone}${outcome === o.v ? ' is-on' : ''}`}
            onClick={() => setOutcome(o.v)}
          >
            {o.label}
          </button>
        ))}
      </div>

      {isPayment && (
        <>
          <label className="co-label">To'lov va'da qilindimi?</label>
          <div className="co-opts" role="radiogroup" aria-label="To'lov va'dasi">
            {PROMISES.map(o => (
              <button
                key={o.v} type="button" role="radio" aria-checked={promise === o.v}
                className={`co-opt${promise === o.v ? ' is-on' : ''}`}
                onClick={() => setPromise(o.v)}
              >
                {o.label}
              </button>
            ))}
          </div>
          {(promise === 'yes' || promise === 'partial') && (
            <>
              <label className="co-label">Va'da qilingan sana</label>
              <input className="field" type="date" value={promisedAt}
                onChange={e => setPromisedAt(e.target.value)} />
            </>
          )}
        </>
      )}

      <Textarea label="Izoh" rows={3} value={note}
        onChange={e => setNote(e.target.value)}
        placeholder="Nima gaplashildi? Nima va'da qilindi?" />

      <label className="co-label">Keyingi qadam</label>
      <div className="co-opts" role="radiogroup" aria-label="Keyingi qadam">
        {NEXT_ACTIONS.map(o => (
          <button
            key={o.v} type="button" role="radio" aria-checked={nextAction === o.v}
            className={`co-opt${nextAction === o.v ? ' is-on' : ''}`}
            onClick={() => setNextAction(nextAction === o.v ? '' : o.v)}
          >
            {o.label}
          </button>
        ))}
      </div>
      {needsDate && (
        <>
          <label className="co-label">Qachon</label>
          <input className="field" type="datetime-local" value={nextAt}
            onChange={e => setNextAt(e.target.value)} />
          {task.entity_type === 'lead' && (
            <p className="co-hint">
              Lid uchun shu vaqtga eslatma yaratiladi. Bosqich o'zgarmaydi —
              uni lid kartasidan o'zingiz o'zgartirasiz.
            </p>
          )}
        </>
      )}
    </Modal>
  )
}

export { OUTCOMES }
