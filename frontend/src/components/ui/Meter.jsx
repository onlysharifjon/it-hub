/**
 * Inline progress meter — jadval katakchasi yoki metrika ostiga sig'adigan
 * yupqa chiziq.
 *
 * Nima uchun: ilovada foizlar faqat matn sifatida ko'rsatilardi ("67%"), yoki
 * har safar qo'lda inline-styled `div` yasalardi (Finance yig'ilish chizig'i,
 * guruh progressi, maosh to'langanligi — uchtasi uch xil markup). Raqamlar
 * ustunini ko'z bilan solishtirish sekin; chiziq uzunligini solishtirish esa
 * bir qarashda bo'ladi.
 *
 * `tone="auto"` — qiymatga qarab rang: yashil/sariq/qizil. `invert` — kam
 * bo'lgani yaxshi ko'rsatkichlar uchun (masalan qarzdorlik ulushi).
 */
export default function Meter({
  value,                  // 0..100
  tone = 'auto',          // auto | primary | success | warning | danger | neutral
  invert = false,
  size = 'md',            // sm | md
  showValue = false,
  label,
  className = '',
}) {
  const pct = Math.max(0, Math.min(100, Number(value) || 0))
  let resolved = tone
  if (tone === 'auto') {
    const good = invert ? 100 - pct : pct
    resolved = good >= 80 ? 'success' : good >= 50 ? 'warning' : 'danger'
  }
  return (
    <div className={`ui-meter ui-meter-${size} ${className}`.trim()}>
      {(label || showValue) && (
        <div className="ui-meter-head">
          {label && <span className="ui-meter-label">{label}</span>}
          {showValue && <span className={`ui-meter-pct tone-${resolved}`}>{Math.round(pct)}%</span>}
        </div>
      )}
      <div
        className="ui-meter-track"
        role="progressbar"
        aria-valuenow={Math.round(pct)}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={label || undefined}
      >
        <div className={`ui-meter-fill fill-${resolved}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}
