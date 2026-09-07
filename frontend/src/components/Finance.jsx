import { useEffect, useMemo, useState } from 'react'
import { toast } from 'react-hot-toast'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faWallet, faChevronDown, faChevronRight, faCircleCheck, faFileExcel,
  faPhone, faArrowRight, faLayerGroup, faUserGroup, faTriangleExclamation,
  faLightbulb, faUsers, faCircleExclamation, faCircleInfo, faArrowTrendUp,
  faArrowTrendDown, faCalendarDays,
} from '@fortawesome/free-solid-svg-icons'
import { fetchFinanceMonthly, fetchFinanceTrend, exportExcelUrl, openDownload } from '../api'
import { TableSkeleton, EmptyState } from './ui/States'
import DataTable from './ui/DataTable'
import Meter from './ui/Meter'
import { Metric } from './ui/Metric'
import SectionHead from './ui/SectionHead'
import { MiniBars, StackedBar, short } from './ui/Chart'
import { tashkentNow } from '../utils/datetime'

const MONTHS = ['Yanvar','Fevral','Mart','Aprel','May','Iyun','Iyul','Avgust','Sentyabr','Oktyabr','Noyabr','Dekabr']
const MONTHS_SHORT = ['Yan','Fev','Mar','Apr','May','Iyu','Iyl','Avg','Sen','Okt','Noy','Dek']
const NOW = tashkentNow()
const YEARS = Array.from({ length: 5 }, (_, i) => NOW.getFullYear() - 2 + i)

const fmt = n => Number(n || 0).toLocaleString('uz-UZ')
const money = n => `${fmt(n)} so'm`
const pctChange = (cur, prev) => (!prev ? null : ((cur - prev) / prev) * 100)

// Bazadagi raqamlar aralash formatda saqlangan ("+998914158889", "914422900",
// "99 455 99 89") — ro'yxatda ular ustma-ust turganda o'qish qiyin.
const phoneDisplay = (raw) => {
  const d = String(raw || '').replace(/\D/g, '')
  const uz = d.length === 9 || (d.length === 12 && d.startsWith('998'))
  if (!uz) return raw
  const n = d.slice(-9)
  return `+998 ${n.slice(0, 2)} ${n.slice(2, 5)} ${n.slice(5, 7)} ${n.slice(7)}`
}

/** Guruh xavf darajasi: qoldiq qanchalik katta VA yig'ilish qanchalik past. */
function riskOf(g) {
  if (!g.expected) return { level: 'none', score: 0 }
  const collected = g.actual / g.expected
  const score = g.deficit * (1 - Math.min(1, collected))
  if (collected === 0 && g.deficit > 0) return { level: 'critical', score }
  if (collected < 0.5) return { level: 'high', score }
  if (collected < 0.85) return { level: 'medium', score }
  return { level: 'ok', score }
}
const RISK_LABEL = { critical: 'Hech kim to‘lamagan', high: 'Past', medium: 'O‘rtacha', ok: 'Yaxshi', none: '—' }

/** Xulosa qatorining og'irligi — ikonka + yorliq faqat ko'rinish uchun. */
const SEVERITY = {
  danger:  { icon: faTriangleExclamation, label: 'Yuqori' },
  warning: { icon: faCircleExclamation,   label: "O'rtacha" },
  info:    { icon: faCircleInfo,          label: "Ma'lumot" },
  success: { icon: faArrowTrendUp,        label: 'Ijobiy' },
}

// Xulosa matnidagi raqamlar ko'zga tashlanishi uchun ajratiladi — matn
// o'zgarmaydi, faqat son qismi <b> ichiga o'raladi. Guruh nomi ichidagi
// raqam ("Frontend Pro S-004") ajratilmasligi uchun oldingi belgi harf,
// raqam yoki chiziqcha bo'lmasligi tekshiriladi.
const NUM_RE = /\d{1,3}(?:[\s\u00A0]\d{3})*(?:[.,]\d+)?(?:\s?%|\s?p\.p\.)?/g
const GLUED = /[\p{L}\d_-]/u
function highlight(text) {
  const str = String(text)
  const out = []
  let at = 0
  for (const m of str.matchAll(NUM_RE)) {
    const i = m.index
    if (i > 0 && GLUED.test(str[i - 1])) continue
    const end = i + m[0].length
    if (end < str.length && GLUED.test(str[end])) continue
    if (i > at) out.push(str.slice(at, i))
    out.push(<b key={i} className="fin-hl">{m[0]}</b>)
    at = end
  }
  if (at < str.length) out.push(str.slice(at))
  return out
}

export default function Finance({ onNavigate }) {
  const [month, setMonth] = useState(NOW.getMonth() + 1)
  const [year, setYear] = useState(NOW.getFullYear())
  const [data, setData] = useState(null)
  const [trend, setTrend] = useState(null)
  const [loading, setLoading] = useState(false)
  const [expanded, setExpanded] = useState(null)
  const [debtorLimit, setDebtorLimit] = useState(8)

  useEffect(() => { load() }, [month, year])

  async function load() {
    setLoading(true)
    setExpanded(null)
    setDebtorLimit(8)
    setTrend(null)
    try {
      setData(await fetchFinanceMonthly(month, year))
    } catch { toast.error("Yuklab bo'lmadi") }
    finally { setLoading(false) }
    // Trend asosiy ko'rinishni to'smaydi — kelgach plitkalarga qo'shiladi.
    fetchFinanceTrend(month, year, 6).then(setTrend).catch(() => {})
  }

  const groups = data?.groups || []
  const isCurrentMonth = month === NOW.getMonth() + 1 && year === NOW.getFullYear()

  // ── Trend qatorlari ────────────────────────────────────────────────────────
  const series = trend?.months || []
  const prev = series.length > 1 ? series[series.length - 2] : null
  const trendLabels = series.map(m => `${MONTHS_SHORT[m.month - 1]} ${m.year}`)
  const collectionSeries = series.map(m => m.collection_pct)
  const avgCollection = (() => {
    const known = collectionSeries.filter(v => v != null)
    return known.length ? known.reduce((a, b) => a + b, 0) / known.length : null
  })()

  const collectionPct = data?.total_expected > 0
    ? Math.min(100, (data.total_actual / data.total_expected) * 100)
    : 0
  const ppChange = prev?.collection_pct != null ? collectionPct - prev.collection_pct : null
  const collectionTone = collectionPct >= 80 ? 'success' : collectionPct >= 50 ? 'warning' : 'danger'
  const worstMonth = series.reduce(
    (w, m) => (m.collection_pct == null ? w : !w || m.collection_pct < w.collection_pct ? m : w),
    null,
  )

  // Har bir guruhning o'z trendi — jadvaldagi mini ustunlar uchun
  const groupTrend = useMemo(() => {
    const map = {}
    for (const g of (trend?.groups || [])) map[g.group_id] = g.points.map(p => p.collection_pct)
    return map
  }, [trend])

  // ── Qarzdorlar (guruhlar bo'ylab birlashgan) ──────────────────────────────
  const debtors = useMemo(() => {
    const out = []
    for (const g of groups) {
      for (const s of (g.unpaid_students || [])) {
        out.push({ ...s, group_id: g.group_id, group_name: g.group_name })
      }
    }
    return out.sort((a, b) => b.owed - a.owed)
  }, [groups])

  const totalDebt = debtors.reduce((s, d) => s + Number(d.owed || 0), 0)
  const chronic = debtors.filter(d => (d.months_without_payment || 0) >= 3)

  const groupRows = useMemo(() => groups.map(g => {
    const risk = riskOf(g)
    return {
      ...g,
      collection: g.expected > 0 ? (g.actual / g.expected) * 100 : null,
      risk: risk.level,
      riskScore: risk.score,
      debtShare: totalDebt > 0 ? (g.deficit / totalDebt) * 100 : 0,
    }
  }), [groups, totalDebt])

  const watchList = useMemo(
    () => groupRows.filter(g => g.deficit > 0).sort((a, b) => b.riskScore - a.riskScore).slice(0, 3),
    [groupRows],
  )

  // ── Hisoblangan xulosalar ─────────────────────────────────────────────────
  const insights = useMemo(() => {
    const out = []
    if (!data) return out

    if (ppChange != null && Math.abs(ppChange) >= 1) {
      const down = ppChange < 0
      out.push({
        id: 'trend', tone: down ? 'danger' : 'success',
        text: `Yig'ilish o'tgan oyga nisbatan ${Math.abs(ppChange).toFixed(1)} p.p. ${down ? 'tushdi' : 'oshdi'}`,
        sub: avgCollection != null ? `6 oylik o'rtacha ${avgCollection.toFixed(1)}%` : null,
      })
    }
    const top5 = debtors.slice(0, 5).reduce((s, d) => s + d.owed, 0)
    if (debtors.length > 5 && totalDebt > 0) {
      out.push({
        id: 'concentration', tone: 'info',
        text: `Eng katta 5 qarzdor jami qoldiqning ${Math.round(top5 / totalDebt * 100)}% ini tashkil qiladi`,
        sub: `${money(top5)} / ${money(totalDebt)}`,
      })
    }
    const worst = watchList[0]
    if (worst && worst.debtShare >= 15) {
      out.push({
        id: 'worst-group', tone: 'warning',
        text: `${worst.group_name} guruhi qoldiqning ${Math.round(worst.debtShare)}% ini beryapti`,
        sub: `${money(worst.deficit)} · ${worst.unpaid_count} o'quvchi to'lamagan`,
        action: () => setExpanded(worst.group_id),
        actionLabel: "O'quvchilarni ko'rish",
      })
    }
    const zeroGroups = groupRows.filter(g => g.risk === 'critical')
    if (zeroGroups.length) {
      out.push({
        id: 'zero', tone: 'danger',
        text: `${zeroGroups.length} guruhda bu oy hech kim to'lamagan`,
        sub: zeroGroups.map(g => g.group_name).join(', '),
      })
    }
    if (chronic.length) {
      out.push({
        id: 'chronic', tone: 'danger',
        text: `${chronic.length} o'quvchi 3+ oydan beri to'lov qilmagan`,
        sub: `Jami ${money(chronic.reduce((s, d) => s + d.owed, 0))}`,
      })
    }
    return out
  }, [data, ppChange, avgCollection, debtors, totalDebt, watchList, groupRows, chronic])

  const groupColumns = [
    {
      key: 'group_name', header: 'Guruh', sortable: true, width: '100%',
      render: g => (
        <span className="fin-group-cell">
          <FontAwesomeIcon
            icon={expanded === g.group_id ? faChevronDown : faChevronRight}
            className="fin-group-caret"
          />
          <strong>{g.group_name}</strong>
          {g.risk === 'critical' && <span className="fin-risk-dot critical" title="Hech kim to'lamagan" />}
          {g.risk === 'high' && <span className="fin-risk-dot high" title="Yig'ilish 50% dan past" />}
        </span>
      ),
    },
    {
      key: 'student_count', header: "O'quvchi", sortable: true, align: 'right', width: 76,
      render: g => <span className="num">{g.student_count}</span>,
    },
    {
      key: 'expected', header: 'Kutilgan', sortable: true, align: 'right', width: 124,
      sortValue: g => Number(g.expected),
      render: g => <span className="num">{fmt(g.expected)}</span>,
    },
    {
      key: 'actual', header: "Yig'ilgan", sortable: true, align: 'right', width: 124,
      sortValue: g => Number(g.actual),
      render: g => <span className="num tone-success">{fmt(g.actual)}</span>,
    },
    {
      key: 'deficit', header: 'Qoldiq', sortable: true, align: 'right', width: 152,
      sortValue: g => Number(g.deficit),
      render: g => g.deficit > 0
        ? (
          <span className="fin-deficit-cell">
            <span className="num tone-danger">{fmt(g.deficit)}</span>
            {g.debtShare >= 8 && <span className="fin-share num">{Math.round(g.debtShare)}%</span>}
          </span>
        )
        : <span className="num text-muted">—</span>,
    },
    {
      key: 'collection', header: "Yig'ilish", sortable: true, width: 112,
      sortValue: g => g.collection ?? -1,
      render: g => g.collection == null
        ? <span className="text-muted">—</span>
        : <Meter value={g.collection} size="sm" showValue />,
    },
    {
      key: 'spark', header: '6 oy', width: 84,
      render: g => {
        const pts = groupTrend[g.group_id]
        if (!pts?.some(v => v != null)) return <span className="text-muted fin-spark-empty">—</span>
        return <MiniBars values={pts} labels={trendLabels} height={24} max={100} tone="primary" format={v => `${v}%`} />
      },
    },
    {
      key: 'unpaid_count', header: "To'lamagan", sortable: true, align: 'center', width: 96,
      render: g => g.unpaid_count > 0
        ? <span className="fin-unpaid-pill">{g.unpaid_count}</span>
        : <FontAwesomeIcon icon={faCircleCheck} className="tone-success" />,
    },
    {
      key: 'row_actions', header: '', align: 'right', width: 92, className: 'fin-row-actions',
      render: g => (
        <span className="fin-actions" onClick={e => e.stopPropagation()}>
          <button
            className="fin-action"
            onClick={() => setExpanded(id => (id === g.group_id ? null : g.group_id))}
            title="O'quvchilar ro'yxati"
          >
            <FontAwesomeIcon icon={faUsers} />
          </button>
          {onNavigate && g.deficit > 0 && (
            <button className="fin-action is-primary" onClick={() => onNavigate('payments')} title="To'lov kiritish">
              <FontAwesomeIcon icon={faWallet} />
            </button>
          )}
        </span>
      ),
    },
  ]

  const totals = groupRows.reduce((a, g) => ({
    students: a.students + g.student_count,
    expected: a.expected + g.expected,
    actual: a.actual + g.actual,
    deficit: a.deficit + g.deficit,
    unpaid: a.unpaid + g.unpaid_count,
  }), { students: 0, expected: 0, actual: 0, deficit: 0, unpaid: 0 })

  return (
    <div className="page page-dense fin-page">
      {/* ── 1. Sarlavha: davr tanlagichi sahifa bo'ylab yopishib turadi ── */}
      <div className="page-header fin-header">
        <div className="fin-header-text">
          <h1><FontAwesomeIcon icon={faWallet} className="page-icon" /> Moliya</h1>
          <p className="fin-header-sub">
            {MONTHS[month - 1]} {year} · {isCurrentMonth ? 'oy davom etmoqda' : 'oy yakunlangan'}
          </p>
        </div>
        <div className="header-actions fin-header-actions">
          <div className="fin-period" role="group" aria-label="Davr">
            <FontAwesomeIcon icon={faCalendarDays} className="fin-period-icon" />
            <select className="field-sm" value={month} onChange={e => setMonth(Number(e.target.value))} aria-label="Oy">
              {MONTHS.map((m, i) => <option key={i} value={i + 1}>{m}</option>)}
            </select>
            <span className="fin-period-sep" aria-hidden="true" />
            <select className="field-sm" value={year} onChange={e => setYear(Number(e.target.value))} aria-label="Yil">
              {YEARS.map(y => <option key={y} value={y}>{y}</option>)}
            </select>
          </div>
          <button className="button secondary" onClick={() => openDownload(exportExcelUrl(month, year)).catch(e => toast.error(e.message || "Yuklab bo'lmadi"))}>
            <FontAwesomeIcon icon={faFileExcel} /> Excel
          </button>
        </div>
      </div>

      {loading ? (
        <TableSkeleton />
      ) : data ? (
        <>
          {/* ── 2. KPI: bitta yetakchi raqam + uchta yordamchi ── */}
          <section className="fin-kpi" aria-label="Asosiy ko'rsatkichlar">
            <div className={`fin-kpi-primary tone-${collectionTone}`}>
              <span className="fin-kpi-label">Yig'ilish darajasi</span>
              <span className="fin-kpi-figure">
                <span className="fin-kpi-value num">{collectionPct.toFixed(1)}</span>
                <span className="fin-kpi-suffix">%</span>
                {ppChange != null && (
                  <span className={`fin-kpi-delta${ppChange >= 0 ? ' is-good' : ' is-bad'}`}>
                    <FontAwesomeIcon icon={ppChange >= 0 ? faArrowTrendUp : faArrowTrendDown} />
                    {`${ppChange >= 0 ? '+' : '−'}${Math.abs(ppChange).toFixed(1)} p.p.`}
                  </span>
                )}
              </span>
              <Meter value={collectionPct} tone={collectionTone} size="md" />
              <dl className="fin-kpi-facts">
                <div>
                  <dt>O'tgan oy</dt>
                  <dd className="num">{prev?.collection_pct == null ? '—' : `${prev.collection_pct.toFixed(1)}%`}</dd>
                </div>
                <div>
                  <dt>6 oy o'rtachasi</dt>
                  <dd className="num">{avgCollection == null ? '—' : `${avgCollection.toFixed(1)}%`}</dd>
                </div>
                <div>
                  <dt>Eng past oy</dt>
                  <dd className="num">{worstMonth ? `${Math.round(worstMonth.collection_pct)}% · ${MONTHS_SHORT[worstMonth.month - 1]}` : '—'}</dd>
                </div>
              </dl>
            </div>

            <div className="fin-kpi-secondary">
              <Metric
                label="Kutilgan" value={fmt(data.total_expected)} unit="so'm"
                delta={isCurrentMonth || !prev ? null : pctChange(data.total_expected, prev.expected)}
                sub={`${groups.length} guruh · ${totals.students} o'quvchi`}
                chart={<MiniBars values={series.map(m => m.expected)} labels={trendLabels} height="100%" tone="neutral" format={short} />}
              />
              <Metric
                label="Yig'ilgan" value={fmt(data.total_actual)} unit="so'm" tone="success"
                delta={isCurrentMonth || !prev ? null : pctChange(data.total_actual, prev.actual)}
                sub={prev ? `O'tgan oy: ${fmt(prev.actual)}` : '—'}
                chart={<MiniBars values={series.map(m => m.actual)} labels={trendLabels} height="100%" tone="success" format={short} />}
              />
              <Metric
                label="Qoldiq" value={fmt(data.total_deficit)} unit="so'm" tone="danger"
                sub={`${debtors.length} o'quvchi · kutilganning ${data.total_expected > 0 ? Math.round(data.total_deficit / data.total_expected * 100) : 0}%`}
                chart={<MiniBars values={series.map(m => m.deficit)} labels={trendLabels} height="100%" tone="danger" format={short} />}
              />
            </div>
          </section>

          {/* ── 3. Trend va tahlil: trend — sahifaning asosiy grafigi ── */}
          <section className="fin-analytics" aria-label="Trend va tahlil">
            <div className="fin-card fin-card-trend">
              <SectionHead
                title="Yig'ilish trendi"
                description="Oxirgi 6 oy · har bir ustun — o'sha oyda yig'ilgan ulush"
                actions={avgCollection != null && (
                  <span className="fin-legend">
                    <span className="fin-legend-item"><i className="fin-legend-dash" /> O'rtacha {avgCollection.toFixed(1)}%</span>
                  </span>
                )}
              />
              {series.length ? (
                <>
                  <div className="fin-trend">
                    <div className="fin-trend-plot">
                      <div className="fin-trend-grid" aria-hidden="true">
                        {[100, 75, 50, 25, 0].map(v => (
                          <span key={v} className="fin-trend-gridline" style={{ bottom: `${v}%` }}>
                            <i className="fin-trend-gridlabel">{v}</i>
                          </span>
                        ))}
                        {avgCollection != null && (
                          <span className="fin-trend-avg" style={{ bottom: `${Math.min(100, avgCollection)}%` }} />
                        )}
                      </div>
                      <div className="fin-trend-cols">
                        {series.map((m, i) => {
                          const v = m.collection_pct
                          const isLast = i === series.length - 1
                          const band = v == null ? 'is-empty' : v >= 80 ? 'is-good' : v >= 50 ? 'is-mid' : 'is-bad'
                          return (
                            <div
                              key={`${m.year}-${m.month}`}
                              className={`fin-trend-col${isLast ? ' is-current' : ''}`}
                              title={`${MONTHS[m.month - 1]} ${m.year}: ${v == null ? '—' : v + '%'} · ${money(m.actual)} / ${money(m.expected)}`}
                            >
                              <div className={`fin-trend-fill ${band}`} style={{ height: v == null ? '0%' : `${Math.max(v, v > 0 ? 1.5 : 0)}%` }}>
                                <span className="fin-trend-val num">{v == null ? '—' : `${Math.round(v)}%`}</span>
                              </div>
                            </div>
                          )
                        })}
                      </div>
                    </div>
                    <div className="fin-trend-axis" aria-hidden="true">
                      {series.map((m, i) => (
                        <span key={`${m.year}-${m.month}`} className={`fin-trend-label${i === series.length - 1 ? ' is-current' : ''}`}>
                          {MONTHS_SHORT[m.month - 1]}
                        </span>
                      ))}
                    </div>
                  </div>
                  <p className="fin-note">
                    Oxirgi ustun — {MONTHS[month - 1]} {year}. Kutilgan summa har bir o'quvchining
                    to'liq oylik tarifidan hisoblanadi (davomatga bog'liq emas).
                  </p>
                </>
              ) : (
                <div className="fin-trend-loading">Trend yuklanmoqda…</div>
              )}
            </div>

            <div className="fin-card fin-card-split">
              <SectionHead title="Oy tarkibi" description={`${MONTHS[month - 1]} ${year}`} />
              <StackedBar
                segments={[
                  { label: "Yig'ilgan", value: data.total_actual, tone: 'success' },
                  { label: 'Qoldiq', value: data.total_deficit, tone: 'danger' },
                ]}
                format={money}
              />
              <dl className="fin-split-facts">
                <div>
                  <dt>Qarzdor o'quvchi</dt>
                  <dd className="num">{debtors.length}</dd>
                </div>
                <div>
                  <dt>3+ oy to'lamagan</dt>
                  <dd className={`num${chronic.length ? ' tone-danger' : ''}`}>{chronic.length}</dd>
                </div>
                <div>
                  <dt>Xavfli guruh</dt>
                  <dd className={`num${watchList.length ? ' tone-warning' : ''}`}>{watchList.length}</dd>
                </div>
              </dl>
            </div>
          </section>

          {/* ── 4. Muhim xulosalar ── */}
          {insights.length > 0 && (
            <section className="fin-card fin-insights" aria-label="Muhim xulosalar">
              <SectionHead
                title="Muhim xulosalar"
                description="Joriy oy ma'lumotidan avtomatik hisoblangan"
              />
              <ul className="fin-insight-list">
                {insights.map(i => {
                  const sev = SEVERITY[i.tone] || SEVERITY.info
                  return (
                    <li key={i.id} className={`fin-insight sev-${i.tone}`}>
                      <span className="fin-insight-icon"><FontAwesomeIcon icon={sev.icon} /></span>
                      <span className="fin-insight-sev">{sev.label}</span>
                      <span className="fin-insight-body">
                        <span className="fin-insight-text">{highlight(i.text)}</span>
                        {i.sub && <span className="fin-insight-sub">{i.sub}</span>}
                      </span>
                      <span className="fin-insight-meta">
                        {i.action && (
                          <button className="fin-insight-action" onClick={i.action}>
                            {i.actionLabel} <FontAwesomeIcon icon={faArrowRight} />
                          </button>
                        )}
                      </span>
                    </li>
                  )
                })}
              </ul>
            </section>
          )}

          {/* ── 5. Diqqat talab qiladigan guruhlar ── */}
          {watchList.length > 0 && (
            <section aria-label="Diqqat talab qiladigan guruhlar">
              <SectionHead
                title="Diqqat talab qiladigan guruhlar"
                description="Qoldiq hajmi va yig'ilish darajasi bo'yicha eng xavflisi"
              />
              <div className="fin-watch">
                {watchList.map(g => (
                  <button key={g.group_id} className={`fin-watch-card risk-${g.risk}`}
                    onClick={() => setExpanded(id => (id === g.group_id ? null : g.group_id))}>
                    <span className="fin-watch-head">
                      <strong className="fin-watch-name">{g.group_name}</strong>
                      <span className={`fin-risk-badge risk-${g.risk}`}>{RISK_LABEL[g.risk]}</span>
                    </span>

                    <span className="fin-watch-amount">
                      <span className="fin-watch-amount-label">Qoldiq</span>
                      <span className="fin-watch-value num">{fmt(g.deficit)}<em>so'm</em></span>
                    </span>

                    <span className="fin-watch-stats">
                      <span className="fin-watch-stat">
                        <em>To'lamagan</em>
                        <b className="num">{g.unpaid_count}<span>/{g.student_count}</span></b>
                      </span>
                      <span className="fin-watch-stat">
                        <em>Qoldiq ulushi</em>
                        <b className="num">{Math.round(g.debtShare)}%</b>
                      </span>
                    </span>

                    <Meter value={g.collection || 0} size="sm" showValue label="Yig'ilish" />

                    <span className="fin-watch-cta">
                      O'quvchilarni ko'rish <FontAwesomeIcon icon={faArrowRight} />
                    </span>
                  </button>
                ))}
              </div>
            </section>
          )}

          {/* ── 6. To'lov kutilmoqda ── */}
          {debtors.length > 0 && (
            <section className="fin-card fin-debtors" aria-label="Qarzdorlar">
              <SectionHead
                title="To'lov kutilmoqda"
                description={`${debtors.length} o'quvchi · jami ${money(totalDebt)}`}
                actions={onNavigate && (
                  <button className="button secondary" onClick={() => onNavigate('payments')}>
                    To'lov kiritish <FontAwesomeIcon icon={faArrowRight} />
                  </button>
                )}
              />
              <ol className="fin-debtor-list">
                {debtors.slice(0, debtorLimit).map((d, i) => {
                  const mo = d.months_without_payment || 0
                  return (
                    <li key={`${d.group_id}-${d.student_id}`} className={`fin-debtor${i < 3 ? ' is-top' : ''}`}>
                      <span className="fin-debtor-rank num">{i + 1}</span>
                      <span className="fin-debtor-name">
                        {d.student_name}
                        {mo >= 3 && (
                          <span className="fin-chronic" title="Uzoq vaqtdan beri to'lov yozuvi yo'q">
                            <FontAwesomeIcon icon={faCircleExclamation} /> {mo} oy
                          </span>
                        )}
                      </span>
                      <span className="fin-debtor-meta">
                        <FontAwesomeIcon icon={faUserGroup} /> {d.group_name}
                        {d.tariff_name && <> · {d.tariff_name}</>}
                        {d.total_lessons_held > 0 && <> · {d.attended}/{d.total_lessons_held} dars</>}
                      </span>
                      <span className="fin-debtor-owed num">
                        {fmt(d.owed)}<em>so'm</em>
                      </span>
                      <span className="fin-debtor-act">
                        {d.phone ? (
                          <a className="fin-debtor-call" href={`tel:${d.phone}`} title={`Qo'ng'iroq: ${d.phone}`}>
                            <FontAwesomeIcon icon={faPhone} />
                            <span className="fin-debtor-phone num">{phoneDisplay(d.phone)}</span>
                          </a>
                        ) : (
                          <span className="fin-debtor-nophone">telefon yo'q</span>
                        )}
                      </span>
                    </li>
                  )
                })}
              </ol>
              {debtors.length > debtorLimit && (
                <div className="fin-debtor-more-wrap">
                  <button className="fin-debtor-more" onClick={() => setDebtorLimit(n => n + 20)}>
                    Yana {Math.min(20, debtors.length - debtorLimit)} ta ko'rsatish
                    <span className="text-muted"> ({debtorLimit}/{debtors.length})</span>
                  </button>
                </div>
              )}
            </section>
          )}

          {/* ── 7. Guruhlar kesimi ── */}
          <section className="fin-table-section" aria-label="Guruhlar kesimi">
            <SectionHead
              title="Guruhlar kesimi"
              description="Ustun sarlavhasini bosib saralang · qatorni bosib o'quvchilarni oching"
            />
            <div className="fin-table-shell">
              <DataTable
                className="fin-table-wrap"
                columns={groupColumns}
                rows={groupRows}
                rowKey={g => g.group_id}
                onRowClick={g => setExpanded(id => (id === g.group_id ? null : g.group_id))}
                rowClassName={g => `fin-row risk-${g.risk}${expanded === g.group_id ? ' is-expanded' : ''}`}
                empty={<EmptyState icon={faLayerGroup} title="Faol guruhlar yo'q"
                  description="Guruh yaratilgach shu yerda oylik moliyaviy kesimi ko'rinadi" />}
                stickyHeader
                scroll
              />
              {groupRows.length > 0 && (
                <div className="fin-totals">
                  <span className="fin-totals-label">Jami · {groupRows.length} guruh</span>
                  <span className="fin-totals-cell"><em>O'quvchi</em><b className="num">{totals.students}</b></span>
                  <span className="fin-totals-cell"><em>Kutilgan</em><b className="num">{fmt(totals.expected)}</b></span>
                  <span className="fin-totals-cell"><em>Yig'ilgan</em><b className="num tone-success">{fmt(totals.actual)}</b></span>
                  <span className="fin-totals-cell"><em>Qoldiq</em><b className="num tone-danger">{fmt(totals.deficit)}</b></span>
                  <span className="fin-totals-cell"><em>To'lamagan</em><b className="num">{totals.unpaid}</b></span>
                </div>
              )}
            </div>

            {expanded != null && (() => {
              const g = groups.find(x => x.group_id === expanded)
              if (!g) return null
              const list = g.all_students || []
              return (
                <div className="fin-detail" role="region" aria-label={`${g.group_name} o'quvchilari`}>
                  <div className="fin-detail-head">
                    <strong>{g.group_name}</strong>
                    <span className="text-muted">
                      {list.length} o'quvchi · {g.unpaid_count} to'lamagan · qoldiq {money(g.deficit)}
                    </span>
                    <button className="btn-icon" onClick={() => setExpanded(null)} aria-label="Yopish">
                      <FontAwesomeIcon icon={faChevronDown} />
                    </button>
                  </div>
                  <div className="fin-detail-scroll">
                    <table className="data-table fin-detail-table">
                      <thead>
                        <tr>
                          <th>O'quvchi</th>
                          <th>Telefon</th>
                          <th>Tarif</th>
                          <th style={{ textAlign: 'center' }}>Davomat</th>
                          <th style={{ textAlign: 'right' }}>To'lashi kerak</th>
                          <th style={{ textAlign: 'center' }}>Holat</th>
                        </tr>
                      </thead>
                      <tbody>
                        {list.map(s => (
                          <tr key={s.student_id} className={s.is_paid === false ? 'row-danger' : ''}>
                            <td className="cell-strong">{s.student_name}</td>
                            <td><a className="num" href={`tel:${s.phone}`}>{phoneDisplay(s.phone)}</a></td>
                            <td>
                              {s.tariff_name
                                ? <>{s.tariff_name} <span className="text-muted num">({fmt(s.tariff_price)})</span></>
                                : <span className="text-muted">Tarif yo'q</span>}
                            </td>
                            <td style={{ textAlign: 'center' }}>
                              <span className="num">{s.attended}</span>
                              <span className="text-muted num">/{s.total_lessons_held || '–'}</span>
                            </td>
                            <td style={{ textAlign: 'right' }} className="num">
                              {s.owed > 0 ? money(s.owed) : <span className="text-muted">—</span>}
                            </td>
                            <td style={{ textAlign: 'center' }}>
                              {s.is_paid === null
                                ? <span className="text-muted">—</span>
                                : s.is_paid
                                  ? <span className="fin-status paid">To'landi</span>
                                  : <span className="fin-status unpaid">Kutilmoqda</span>}
                            </td>
                          </tr>
                        ))}
                        {list.length === 0 && (
                          <tr><td colSpan={6} className="muted center py-4">O'quvchilar yo'q</td></tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              )
            })()}
          </section>
        </>
      ) : null}
    </div>
  )
}
