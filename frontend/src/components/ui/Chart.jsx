/**
 * Yengil grafik primitivlari — SVG, hech qanday kutubxonasiz.
 *
 * Nima uchun: ilovada 3 ta alohida "qo'lda yasalgan" bar chart bor edi
 * (Dashboard + Leads Analytics'da 2 ta), har biri o'z markup'i, o'z raqam
 * formati va o'z rang mantig'i bilan. package.json'da grafik kutubxonasi yo'q
 * va uni qo'shish bundle'ni sezilarli kattalashtiradi — shuning uchun SVG.
 *
 * Ranglar CSS token'lardan (`currentColor` / var(--...)) olinadi, ya'ni 3 ta
 * mavzuda ham to'g'ri ishlaydi.
 */

const fmtNum = (n) => Number(n || 0).toLocaleString('uz-UZ')

/** Katta raqamni qisqartiradi: 1 250 000 → "1.3M", 45 000 → "45k" */
export function short(n) {
  const v = Number(n || 0)
  if (Math.abs(v) >= 1e9) return (v / 1e9).toFixed(1).replace(/\.0$/, '') + 'B'
  if (Math.abs(v) >= 1e6) return (v / 1e6).toFixed(1).replace(/\.0$/, '') + 'M'
  if (Math.abs(v) >= 1e3) return Math.round(v / 1e3) + 'k'
  return String(Math.round(v))
}

/**
 * Ustunli diagramma. Bitta yoki ikkita qator (taqqoslash uchun).
 *
 *   <BarChart
 *     data={[{ label: 'Yan', value: 1200000, compare: 800000 }, ...]}
 *     seriesLabel="Tushum" compareLabel="Chiqim"
 *     highlightIndex={currentMonthIdx}
 *     onBarClick={(d, i) => ...}
 *   />
 */
export function BarChart({
  data = [],
  height = 200,
  seriesLabel = '',
  compareLabel = '',
  lineLabel = '',
  highlightIndex = -1,
  valueFormat = short,
  tooltipFormat = fmtNum,
  onBarClick,
  emptyText = "Ma'lumot yo'q",
}) {
  const hasCompare = data.some(d => d.compare != null)
  // Uchinchi qator — chiziq (sof foyda kabi manfiy bo'la oladigan ko'rsatkich).
  // Ustunlar 0 dan yuqoriga o'sadi, shuning uchun manfiy qiymatni ustun bilan
  // ko'rsatib bo'lmaydi; chiziq o'z shkalasida chiziladi va 0 chizig'i
  // ko'rsatiladi.
  const hasLine = data.some(d => d.line != null)
  const max = Math.max(
    ...data.map(d => Math.max(Number(d.value) || 0, Number(d.compare) || 0)),
    1,
  )

  if (!data.length) return <div className="muted center py-8">{emptyText}</div>

  // Chiziq geometriyasi: 0..100 foizli koordinatalar (SVG preserveAspectRatio=none)
  let linePts = null, lineZeroY = null
  if (hasLine) {
    // null — ma'lumot yo'q (masalan hali kelmagan oylar): chiziq u yerda uzilади,
    // nolga tushgandek ko'rinmaydi.
    const known = data
      .map((d, i) => ({ i, v: d.line == null ? null : Number(d.line) || 0 }))
      .filter(p => p.v != null)
    const vals = known.map(p => p.v)
    const lo = Math.min(0, ...vals)
    const hi = Math.max(0, ...vals)
    const span = hi - lo || 1
    const toY = v => 100 - ((v - lo) / span) * 100
    const stepX = data.length > 1 ? 100 / (data.length - 1) : 0
    linePts = known.map(p => `${(p.i * stepX).toFixed(2)},${toY(p.v).toFixed(2)}`).join(' ')
    lineZeroY = toY(0)
  }

  return (
    <div className="chart">
      {(seriesLabel || compareLabel) && (
        <div className="chart-legend">
          {seriesLabel && (
            <span className="chart-legend-item">
              <span className="chart-swatch is-primary" /> {seriesLabel}
            </span>
          )}
          {hasCompare && compareLabel && (
            <span className="chart-legend-item">
              <span className="chart-swatch is-compare" /> {compareLabel}
            </span>
          )}
          {hasLine && lineLabel && (
            <span className="chart-legend-item">
              <span className="chart-swatch is-line" /> {lineLabel}
              {/* Foyda manfiy bo'la oladi, ustunlar esa faqat 0 dan yuqoriga
                  o'sadi — shuning uchun chiziq o'z shkalasida chiziladi va
                  nol darajasi punktir bilan belgilanadi. Bu yerda muhimi
                  qiymat emas, shakl: tushum o'sib foyda tushayotganini
                  ko'rsatish. */}
              <span className="chart-legend-note">(shakl · o'z shkalasi)</span>
            </span>
          )}
        </div>
      )}

      <div className="chart-plot" style={{ height }}>
        {/* gorizontal to'r chiziqlari */}
        <div className="chart-grid" aria-hidden="true">
          {[1, 0.75, 0.5, 0.25, 0].map(f => (
            <div key={f} className="chart-grid-line">
              <span className="chart-grid-label">{valueFormat(max * f)}</span>
            </div>
          ))}
        </div>

        {hasLine && (
          <svg className="chart-line-layer" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
            <line x1="0" x2="100" y1={lineZeroY} y2={lineZeroY} className="chart-line-zero" />
            <polyline points={linePts} className="chart-line-path" />
          </svg>
        )}

        <div className="chart-bars">
          {data.map((d, i) => {
            const v = Number(d.value) || 0
            const c = Number(d.compare) || 0
            const isHi = i === highlightIndex
            let title = hasCompare
              ? `${d.label}: ${seriesLabel} ${tooltipFormat(v)} · ${compareLabel} ${tooltipFormat(c)}`
              : `${d.label}: ${tooltipFormat(v)}`
            if (hasLine && d.line != null) title += ` · ${lineLabel || 'Foyda'} ${tooltipFormat(d.line)}`
            return (
              <div
                key={i}
                className={`chart-col ${isHi ? 'is-current' : ''} ${onBarClick ? 'is-clickable' : ''}`.trim()}
                title={title}
                onClick={onBarClick ? () => onBarClick(d, i) : undefined}
              >
                <div className="chart-col-value">{v > 0 ? valueFormat(v) : ''}</div>
                <div className="chart-col-bars">
                  <div
                    className="chart-bar is-primary"
                    style={{ height: `${Math.max((v / max) * 100, v > 0 ? 2 : 0)}%` }}
                  />
                  {hasCompare && (
                    <div
                      className="chart-bar is-compare"
                      style={{ height: `${Math.max((c / max) * 100, c > 0 ? 2 : 0)}%` }}
                    />
                  )}
                </div>
                <div className="chart-col-label">{d.label}</div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

/**
 * Sparkline — KPI kartasi ichidagi kichik trend chizig'i (SVG polyline).
 * Qiymatlar 0 bo'lsa ham chiziq ko'rinadi (tekis chiziq sifatida).
 */
export function Sparkline({ values = [], width = 96, height = 28, tone = 'primary' }) {
  const nums = values.map(v => Number(v) || 0)
  if (nums.length < 2) return null

  const max = Math.max(...nums), min = Math.min(...nums)
  const span = max - min || 1
  const stepX = width / (nums.length - 1)
  const pts = nums.map((v, i) => {
    const x = i * stepX
    const y = height - ((v - min) / span) * (height - 4) - 2
    return `${x.toFixed(1)},${y.toFixed(1)}`
  })

  return (
    <svg
      className={`ui-sparkline is-${tone}`}
      width={width} height={height}
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <polyline points={pts.join(' ')} fill="none" strokeWidth="1.75" />
      <polygon points={`0,${height} ${pts.join(' ')} ${width},${height}`} className="spark-fill" />
    </svg>
  )
}

/**
 * Trend ko'rsatkichi — o'tgan davrga nisbatan o'zgarish.
 * `invert` — kamayish yaxshi bo'lgan holatlar uchun (masalan xarajat).
 */
export function TrendIndicator({ value, suffix = '%', invert = false, label }) {
  const v = Number(value) || 0
  const flat = Math.abs(v) < 0.05
  const good = invert ? v < 0 : v > 0
  const tone = flat ? 'flat' : good ? 'up' : 'down'
  const arrow = flat ? '→' : v > 0 ? '▲' : '▼'

  return (
    <span className={`ui-trend is-${tone}`}>
      <span aria-hidden="true">{arrow}</span>
      {Math.abs(v).toFixed(1)}{suffix}
      {label && <span className="ui-trend-label">{label}</span>}
    </span>
  )
}

/**
 * Waterfall — P&L parchalanishi: tushumdan boshlab har bir chiqim qanchani
 * "yeb" ketishini va oxirida nima qolishini bitta qatorda ko'rsatadi.
 *
 * Nima uchun: Dashboard'da bu ma'lumot 4 ta alohida KPI kartasi edi (tushum,
 * o'qituvchi maoshi, tashqi xarajat, umumiy chiqim) — foydalanuvchi ularning
 * o'zaro nisbatini boshida hisoblashi kerak edi. Waterfall nisbatni ko'rsatadi:
 * maosh tushumning yarmini yeyayotgani bir qarashda ko'rinadi.
 *
 *   <Waterfall
 *     start={{ label: 'Tushum', value: 40000000 }}
 *     steps={[{ label: "O'qituvchi maoshi", value: -12000000 }, ...]}
 *     result={{ label: 'Sof foyda', value: 21000000 }} />
 */
export function Waterfall({ start, steps = [], result, format = fmtNum, onStepClick }) {
  const base = Math.abs(Number(start?.value) || 0) || 1
  const pct = v => Math.min(100, (Math.abs(Number(v) || 0) / base) * 100)
  const negative = Number(result?.value) < 0

  return (
    <div className="ui-waterfall">
      <div className="ui-wf-row is-start">
        <span className="ui-wf-label">{start.label}</span>
        <div className="ui-wf-track">
          <div className="ui-wf-fill is-income" style={{ width: '100%' }} />
        </div>
        <span className="ui-wf-value num">{format(start.value)}</span>
      </div>

      {steps.map((s, i) => {
        const Tag = s.onClick || onStepClick ? 'button' : 'div'
        return (
          <Tag
            key={i}
            className={`ui-wf-row is-step${s.onClick || onStepClick ? ' is-clickable' : ''}`}
            onClick={s.onClick || (onStepClick ? () => onStepClick(s, i) : undefined)}
            type={s.onClick || onStepClick ? 'button' : undefined}
          >
            <span className="ui-wf-label">{s.label}</span>
            <div className="ui-wf-track">
              <div
                className={`ui-wf-fill is-cost${Math.abs(s.value) > base ? ' is-over' : ''}`}
                style={{ width: `${pct(s.value)}%` }}
              />
              <span className="ui-wf-share num">{Math.round((Math.abs(Number(s.value) || 0) / base) * 100)}%</span>
            </div>
            <span className="ui-wf-value num is-cost">−{format(Math.abs(s.value))}</span>
          </Tag>
        )
      })}

      <div className={`ui-wf-row is-result${negative ? ' is-negative' : ''}`}>
        <span className="ui-wf-label">{result.label}</span>
        <div className="ui-wf-track">
          <div
            className={`ui-wf-fill ${negative ? 'is-loss' : 'is-profit'}`}
            style={{ width: `${pct(result.value)}%` }}
          />
          {/* Zarar bo'lganda "tushumning necha foizi" degan ulush ma'nosiz
              (17% zarar — nimadan 17%?), shuning uchun o'rniga yorliq. */}
          <span className="ui-wf-share num">
            {negative ? 'zarar' : `${Math.round(pct(result.value))}%`}
          </span>
        </div>
        <span className={`ui-wf-value num ${negative ? 'is-loss' : 'is-profit'}`}>
          {negative ? '−' : ''}{format(Math.abs(result.value))}
        </span>
      </div>
    </div>
  )
}

/**
 * MiniBars — KPI plitkasi ichidagi kichik ustunli trend (6-12 nuqta).
 *
 * Nima uchun Sparkline emas: oylik yig'ilish foizi — uzluksiz emas, diskret
 * o'lchov. Chiziq oraliq qiymatlar bordek ko'rsatadi; ustunlar esa "har oy
 * alohida o'lchov" degan to'g'ri o'qishni beradi va oxirgi ustunni ajratib
 * ko'rsatish mumkin.
 */
export function MiniBars({ values = [], labels = [], height = 34, tone = 'primary', format = short, max: maxProp }) {
  const nums = values.map(v => (v == null ? null : Number(v) || 0))
  const known = nums.filter(v => v != null)
  if (!known.length) return null
  const max = maxProp ?? Math.max(...known, 1)
  const last = nums.length - 1

  return (
    <div className={`ui-minibars is-${tone}`} style={{ height }}>
      {nums.map((v, i) => (
        <div
          key={i}
          className={`ui-minibar${i === last ? ' is-last' : ''}${v == null ? ' is-empty' : ''}`}
          title={labels[i] ? `${labels[i]}: ${v == null ? "ma'lumot yo'q" : format(v)}` : undefined}
        >
          <div
            className="ui-minibar-fill"
            style={{ height: v == null ? '0%' : `${Math.max((v / max) * 100, v > 0 ? 6 : 0)}%` }}
          />
        </div>
      ))}
    </div>
  )
}

/**
 * StackedBar — bitta 100% chiziqda tarkib (yig'ilgan / qolgan).
 *
 * Nima uchun oddiy progress bar emas: progress bar faqat "qanchasi bajarildi"
 * ni ko'rsatadi. Bu yerda ikkala qismning ham o'z summasi bor va menejerga
 * ikkalasi ham kerak — segment ichidagi yorliq raqamni izlashni yo'q qiladi.
 *
 * segments: [{ label, value, tone }]
 */
export function StackedBar({ segments = [], format = fmtNum, height = 34 }) {
  const total = segments.reduce((s, x) => s + (Number(x.value) || 0), 0) || 1
  return (
    <div className="ui-stack">
      <div className="ui-stack-bar" style={{ height }}>
        {segments.map((s, i) => {
          const pct = (Number(s.value) || 0) / total * 100
          if (pct <= 0) return null
          return (
            <div
              key={i}
              className={`ui-stack-seg tone-${s.tone || 'primary'}`}
              style={{ width: `${pct}%` }}
              title={`${s.label}: ${format(s.value)} (${pct.toFixed(1)}%)`}
            >
              {pct >= 12 && <span className="ui-stack-seg-pct num">{Math.round(pct)}%</span>}
            </div>
          )
        })}
      </div>
      <div className="ui-stack-legend">
        {segments.map((s, i) => (
          <span key={i} className="ui-stack-legend-item">
            <span className={`ui-stack-dot tone-${s.tone || 'primary'}`} />
            <span className="ui-stack-legend-label">{s.label}</span>
            <strong className="num">{format(s.value)}</strong>
          </span>
        ))}
      </div>
    </div>
  )
}
