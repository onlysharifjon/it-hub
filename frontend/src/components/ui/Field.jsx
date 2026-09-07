import { useId } from 'react'

/**
 * Forma maydonlari — yagona ko'rinish: label + nazorat + yordam matni + xato.
 *
 * Ilgari har bir maydon qo'lda yig'ilardi: <label>matn</label> + <input
 * className="field"> yonma-yon, `.modal-body`ning `gap:12px`iga tayanib. Xato
 * holati esa umuman yo'q edi — validatsiya faqat toast orqali ko'rsatilardi va
 * foydalanuvchi qaysi maydon xato ekanini formadan qidirishi kerak edi.
 *
 * <Field> bitta flex-bola sifatida chiqadi, shuning uchun `.modal-body`dagi
 * mavjud vertikal ritm buzilmaydi.
 *
 *   <Input label="Tarif nomi" required value={v} onChange={...} error={err.name} />
 *   <Select label="Rol" value={role} onChange={...}>{options}</Select>
 *   <Textarea label="Tavsif" rows={2} hint="Ixtiyoriy" />
 */
export function Field({ label, required, hint, error, htmlFor, children, className = '' }) {
  return (
    <div className={`ui-field ${error ? 'has-error' : ''} ${className}`.trim()}>
      {label && (
        <label className="ui-field-label" htmlFor={htmlFor}>
          {label}{required && <span className="ui-field-req" aria-hidden="true"> *</span>}
        </label>
      )}
      {children}
      {error
        ? <div className="ui-field-error" role="alert">{error}</div>
        : hint ? <div className="ui-field-hint">{hint}</div> : null}
    </div>
  )
}

export function Input({ label, required, hint, error, className = '', ...rest }) {
  const id = useId()
  return (
    <Field label={label} required={required} hint={hint} error={error} htmlFor={id}>
      <input
        id={id}
        className={`field ${error ? 'is-invalid' : ''} ${className}`.trim()}
        aria-invalid={error ? 'true' : undefined}
        {...rest}
      />
    </Field>
  )
}

export function Textarea({ label, required, hint, error, rows = 3, className = '', ...rest }) {
  const id = useId()
  return (
    <Field label={label} required={required} hint={hint} error={error} htmlFor={id}>
      <textarea
        id={id}
        rows={rows}
        className={`field ${error ? 'is-invalid' : ''} ${className}`.trim()}
        aria-invalid={error ? 'true' : undefined}
        {...rest}
      />
    </Field>
  )
}

export function Select({ label, required, hint, error, children, className = '', ...rest }) {
  const id = useId()
  return (
    <Field label={label} required={required} hint={hint} error={error} htmlFor={id}>
      <select
        id={id}
        className={`field ${error ? 'is-invalid' : ''} ${className}`.trim()}
        aria-invalid={error ? 'true' : undefined}
        {...rest}
      >
        {children}
      </select>
    </Field>
  )
}

export function Checkbox({ label, hint, error, className = '', ...rest }) {
  const id = useId()
  return (
    <div className={`ui-field ui-field-inline ${className}`.trim()}>
      <label className="ui-check" htmlFor={id}>
        <input id={id} type="checkbox" {...rest} />
        <span>{label}</span>
      </label>
      {error
        ? <div className="ui-field-error" role="alert">{error}</div>
        : hint ? <div className="ui-field-hint">{hint}</div> : null}
    </div>
  )
}

export function Switch({ label, hint, checked, onChange, disabled, className = '' }) {
  const id = useId()
  return (
    <div className={`ui-field ui-field-inline ${className}`.trim()}>
      <label className="ui-switch" htmlFor={id}>
        <input
          id={id}
          type="checkbox"
          role="switch"
          checked={!!checked}
          onChange={onChange}
          disabled={disabled}
        />
        <span className="ui-switch-track" aria-hidden="true"><span className="ui-switch-thumb" /></span>
        {label && <span className="ui-switch-label">{label}</span>}
      </label>
      {hint && <div className="ui-field-hint">{hint}</div>}
    </div>
  )
}
