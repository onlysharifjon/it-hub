import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faArrowTrendUp, faArrowTrendDown, faMinus } from '@fortawesome/free-solid-svg-icons'

const fmtPct = (n) => `${n > 0 ? '+' : n < 0 ? '−' : ''}${Math.abs(n).toFixed(1)}%`

/**
 * Zich metrika chizig'i — KpiCard'ning "karta" og'irligisiz varianti.
 *
 * Nima uchun: Dashboard'da 10 ta bir xil og'irlikdagi KPI kartasi bor edi —
 * "Talabalar: 47" ham, "Sof foyda: −2.4M" ham bir xil o'lchamda. Kartalar
 * ierarxiya bermaydi, faqat ekranni to'ldiradi. `<MetricStrip>` ikkinchi
 * darajali ko'rsatkichlarni bitta zich qatorda beradi, shunda asosiy raqam
 * (bitta katta KpiCard) haqiqatan ajralib turadi.
 */
export function Metric({
  label, value, unit, delta, deltaInvert = false, sub, tone, onClick, hint,
  chart,          // kichik trend grafigi (MiniBars/Sparkline)
  deltaText,      // tayyor matn — foizdan boshqa birlik uchun (masalan "p.p.")
  deltaGood,      // deltaText bilan birga: yashilmi/qizilmi
}) {
  const Tag = onClick ? 'button' : 'div'
  const dir = delta == null ? null : delta > 0.05 ? 'up' : delta < -0.05 ? 'down' : 'flat'
  const good = dir === 'flat' ? null : deltaInvert ? dir === 'down' : dir === 'up'
  return (
    <Tag
      className={`ui-metric${onClick ? ' is-clickable' : ''}${tone ? ` tone-${tone}` : ''}`}
      onClick={onClick}
      type={onClick ? 'button' : undefined}
      title={hint}
    >
      <span className="ui-metric-label">{label}</span>
      <span className="ui-metric-value">
        {value}
        {unit && <span className="ui-metric-unit">{unit}</span>}
      </span>
      {(dir || sub || deltaText) && (
        <span className="ui-metric-foot">
          {dir && (
            <span className={`ui-metric-delta${good == null ? '' : good ? ' is-good' : ' is-bad'}`}>
              <FontAwesomeIcon icon={dir === 'up' ? faArrowTrendUp : dir === 'down' ? faArrowTrendDown : faMinus} />
              {fmtPct(delta)}
            </span>
          )}
          {deltaText && (
            <span className={`ui-metric-delta${deltaGood == null ? '' : deltaGood ? ' is-good' : ' is-bad'}`}>
              <FontAwesomeIcon icon={deltaGood == null ? faMinus : deltaGood ? faArrowTrendUp : faArrowTrendDown} />
              {deltaText}
            </span>
          )}
          {sub && <span className="ui-metric-sub">{sub}</span>}
        </span>
      )}

      {chart && <span className="ui-metric-chart">{chart}</span>}
    </Tag>
  )
}

export function MetricStrip({ children, columns }) {
  return (
    <div
      className="ui-metric-strip"
      style={columns ? { '--metric-cols': columns } : undefined}
    >
      {children}
    </div>
  )
}
