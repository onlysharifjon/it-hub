import { useEffect, useMemo, useState } from 'react'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faChevronLeft, faChevronRight, faArrowUp, faArrowDown, faMinus,
  faMoneyBillWave, faChalkboardUser, faUserGraduate, faCalendarCheck, faWallet,
} from '@fortawesome/free-solid-svg-icons'
import { fetchMySalaryAnalytics, fetchSalaryBreakdown } from '../api'
import Modal from './ui/Modal'
import DataTable from './ui/DataTable'
import { EmptyState, CardSkeleton, ErrorState } from './ui/States'
import { tashkentNow } from '../utils/datetime'

const MONTHS = ['Yanvar','Fevral','Mart','Aprel','May','Iyun',
                 'Iyul','Avgust','Sentyabr','Oktyabr','Noyabr','Dekabr']
const SHORT = ['Yan','Fev','Mar','Apr','May','Iyn','Iyl','Avg','Sen','Okt','Noy','Dek']

const num = n => Number(n || 0)
function fmt(n) { return num(n).toLocaleString('uz-UZ', { maximumFractionDigits: 0 }) + ' so‘m' }
function fmtShort(n) {
  const v = num(n)
  if (Math.abs(v) >= 1e6) return (v / 1e6).toLocaleString('uz-UZ', { maximumFractionDigits: 1 }) + ' mln'
  if (Math.abs(v) >= 1e3) return Math.round(v / 1e3).toLocaleString('uz-UZ') + ' ming'
  return v.toLocaleString('uz-UZ')
}

/** O'tgan davrga nisbatan o'zgarish: +/− qiymat va foiz. */
function Delta({ cur, prev, money = false, suffix = '' }) {
  const d = num(cur) - num(prev)
  const pct = num(prev) ? (d / Math.abs(num(prev))) * 100 : null
  const tone = d > 0 ? 'up' : d < 0 ? 'down' : 'flat'
  const icon = d > 0 ? faArrowUp : d < 0 ? faArrowDown : faMinus
  const abs = money ? fmt(Math.abs(d)) : Math.abs(d).toLocaleString('uz-UZ') + suffix
  return (
    <span className={`sal-delta is-${tone}`}>
      <FontAwesomeIcon icon={icon} />
      {d === 0 ? 'o‘zgarishsiz' : `${d > 0 ? '+' : '−'}${abs}`}
      {pct != null && d !== 0 && <em>{d > 0 ? '+' : '−'}{Math.abs(pct).toFixed(1)}%</em>}
    </span>
  )
}

function Kpi({ icon, label, value, cur, prev, money, suffix, hint }) {
  return (
    <div className="sal-kpi">
      <span className="sal-kpi-icon"><FontAwesomeIcon icon={icon} /></span>
      <span className="sal-kpi-label">{label}</span>
      <strong className="sal-kpi-value">{value}</strong>
      {prev !== undefined && <Delta cur={cur} prev={prev} money={money} suffix={suffix} />}
      {hint && <span className="sal-kpi-hint">{hint}</span>}
    </div>
  )
}

/** 6 oylik oylik: FIX + ulush ustunlari, to'langan — nuqtali chiziq. */
function SalaryTrendChart({ trend, selectedIdx }) {
  const W = 640, H = 260, P = { l: 52, r: 12, t: 16, b: 34 }
  const max = Math.max(1, ...trend.map(t => Math.max(num(t.salary), num(t.paid)))) * 1.1
  const iw = W - P.l - P.r, ih = H - P.t - P.b
  const step = iw / trend.length, bw = Math.min(46, step * 0.55)
  const y = v => P.t + ih - (num(v) / max) * ih
  const ticks = [0, .25, .5, .75, 1].map(f => max * f)
  const paidPts = trend.map((t, i) => `${P.l + step * i + step / 2},${y(t.paid)}`).join(' ')
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="sal-chart" role="img" aria-label="Oxirgi oylar bo‘yicha oylik grafigi">
      {ticks.map((v, i) => (
        <g key={i}>
          <line x1={P.l} x2={W - P.r} y1={y(v)} y2={y(v)} className="sal-grid" />
          <text x={P.l - 8} y={y(v) + 4} textAnchor="end" className="sal-axis">{fmtShort(v)}</text>
        </g>
      ))}
      {trend.map((t, i) => {
        const x = P.l + step * i + (step - bw) / 2
        const other = Math.max(0, num(t.salary) - num(t.bonus))   // FIX yoki qo'lda belgilangan qism
        const bonus = Math.min(num(t.bonus), num(t.salary))
        const sel = i === selectedIdx
        return (
          <g key={i} className={sel ? 'is-selected' : ''}>
            <title>{`${MONTHS[t.month - 1]} ${t.year}\nOylik: ${fmt(t.salary)}\nUlush: ${fmt(t.bonus)}\nTo‘langan: ${fmt(t.paid)}`}</title>
            <rect x={x} y={y(other)} width={bw} height={Math.max(0, P.t + ih - y(other))} rx="4" className="sal-bar-base" />
            <rect x={x} y={y(other + bonus)} width={bw} height={Math.max(0, y(other) - y(other + bonus))} rx="4" className="sal-bar-bonus" />
            {num(t.salary) > 0 && <text x={x + bw / 2} y={y(t.salary) - 6} textAnchor="middle" className="sal-bar-label">{fmtShort(t.salary)}</text>}
            <text x={x + bw / 2} y={H - 12} textAnchor="middle" className={'sal-axis' + (sel ? ' is-strong' : '')}>{SHORT[t.month - 1]}</text>
          </g>
        )
      })}
      <polyline points={paidPts} className="sal-line-paid" />
      {trend.map((t, i) => <circle key={i} cx={P.l + step * i + step / 2} cy={y(t.paid)} r="3.5" className="sal-dot-paid" />)}
    </svg>
  )
}

/** Oy ichida jamlanma qatnashuv: shu oy va o'tgan oy (kun bo'yicha). */
function CumulativeChart({ daily, prevDaily, days, prevDays, uptoDay }) {
  const W = 640, H = 240, P = { l: 40, r: 12, t: 14, b: 28 }
  const cum = (rows, n, upto) => {
    const byDay = {}
    rows.forEach(r => { byDay[+r.date.slice(8, 10)] = num(r.attendances) })
    let acc = 0
    return Array.from({ length: Math.min(n, upto ?? n) }, (_, i) => (acc += byDay[i + 1] || 0))
  }
  const cur = cum(daily, days, uptoDay), prev = cum(prevDaily, prevDays)
  const maxDays = Math.max(days, prevDays)
  const max = Math.max(1, ...cur, ...prev) * 1.1
  const iw = W - P.l - P.r, ih = H - P.t - P.b
  const x = d => P.l + ((d - 1) / Math.max(1, maxDays - 1)) * iw
  const y = v => P.t + ih - (v / max) * ih
  const line = arr => arr.map((v, i) => `${x(i + 1)},${y(v)}`).join(' ')
  const area = cur.length ? `${x(1)},${y(0)} ${line(cur)} ${x(cur.length)},${y(0)}` : ''
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="sal-chart" role="img" aria-label="Oy davomidagi qatnashuvlar grafigi">
      {[0, .5, 1].map((f, i) => (
        <g key={i}>
          <line x1={P.l} x2={W - P.r} y1={y(max * f)} y2={y(max * f)} className="sal-grid" />
          <text x={P.l - 8} y={y(max * f) + 4} textAnchor="end" className="sal-axis">{Math.round(max * f)}</text>
        </g>
      ))}
      {[1, 5, 10, 15, 20, 25, maxDays].map(d => (
        <text key={d} x={x(d)} y={H - 8} textAnchor="middle" className="sal-axis">{d}</text>
      ))}
      <polyline points={line(prev)} className="sal-line-prev" />
      {area && <polygon points={area} className="sal-area-cur" />}
      <polyline points={line(cur)} className="sal-line-cur" />
      {cur.length > 0 && <circle cx={x(cur.length)} cy={y(cur[cur.length - 1])} r="4" className="sal-dot-cur" />}
    </svg>
  )
}

/** Guruhlar bo'yicha ulush: shu oy va o'tgan oy yonma-yon gorizontal ustunlar. */
function GroupBars({ groups }) {
  const max = Math.max(1, ...groups.flatMap(g => [num(g.bonus), num(g.prev_bonus)]))
  return (
    <div className="sal-hbars">
      {groups.map(g => (
        <div key={g.group_id} className="sal-hbar">
          <span className="sal-hbar-name">{g.group_name}</span>
          <div className="sal-hbar-tracks">
            <div className="sal-hbar-track"><i className="is-cur" style={{ width: `${(num(g.bonus) / max) * 100}%` }} /><b>{fmtShort(g.bonus)}</b></div>
            <div className="sal-hbar-track"><i className="is-prev" style={{ width: `${(num(g.prev_bonus) / max) * 100}%` }} /><b>{fmtShort(g.prev_bonus)}</b></div>
          </div>
        </div>
      ))}
    </div>
  )
}

/** O'qituvchining shaxsiy oylik maoshi — profil menyusidan to'liq ekranda ochiladi. */
export default function TeacherSalaryModal({ open, onClose, currentUser }) {
  const now = tashkentNow()
  const [month, setMonth] = useState(now.getMonth() + 1)
  const [year,  setYear]  = useState(now.getFullYear())
  const [data, setData] = useState(null)
  const [breakdown, setBreakdown] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => { if (open) load() }, [open, month, year])

  async function load() {
    setLoading(true); setError(null)
    try {
      const [a, b] = await Promise.all([
        fetchMySalaryAnalytics(month, year, 6),
        currentUser?.id ? fetchSalaryBreakdown(currentUser.id, month, year).catch(() => null) : null,
      ])
      setData(a); setBreakdown(b)
    } catch (e) { setError(e.message) } finally { setLoading(false) }
  }

  function prevMonth() { if (month === 1) { setMonth(12); setYear(y => y - 1) } else setMonth(m => m - 1) }
  function nextMonth() { if (month === 12) { setMonth(1); setYear(y => y + 1) } else setMonth(m => m + 1) }

  const isCurrentMonth = month === now.getMonth() + 1 && year === now.getFullYear()
  const isFuture = year > now.getFullYear() || (year === now.getFullYear() && month > now.getMonth() + 1)

  const view = useMemo(() => {
    if (!data?.trend?.length) return null
    const trend = data.trend
    const cur = trend[trend.length - 1]
    const prev = trend[trend.length - 2]
    const days = new Date(year, month, 0).getDate()
    const prevDays = new Date(prev.year, prev.month, 0).getDate()
    const today = now.getDate()
    // Joriy oy tugamagan — o'tgan oyning SHU KUNIGACHA bo'lgan qismi bilan ham solishtiramiz
    const upto = (rows, d) => rows.filter(r => +r.date.slice(8, 10) <= d)
      .reduce((a, r) => ({ lessons: a.lessons + num(r.lessons), attendances: a.attendances + num(r.attendances) }), { lessons: 0, attendances: 0 })
    const prevSamePeriod = isCurrentMonth ? upto(data.prev_daily || [], today) : null
    const perLessonAvg = cur.lessons ? cur.attendances / cur.lessons : 0
    const prevPerLessonAvg = prev.lessons ? prev.attendances / prev.lessons : 0
    const projected = isCurrentMonth && today > 0
      ? num(cur.base) + (num(cur.bonus) / today) * days : null
    return { trend, cur, prev, days, prevDays, today, prevSamePeriod, perLessonAvg, prevPerLessonAvg, projected }
  }, [data, month, year])

  const prevLabel = view ? `${MONTHS[view.prev.month - 1]}` : ''

  return (
    <Modal open={open} title="Oylik maoshim" onClose={onClose} size="full">
      <div className="sal-toolbar">
        <div className="td-monthnav">
          <button className="btn-icon" onClick={prevMonth} aria-label="Oldingi oy"><FontAwesomeIcon icon={faChevronLeft} /></button>
          <span className="td-monthnav-label">{MONTHS[month - 1]} {year}</span>
          <button className="btn-icon" onClick={nextMonth} aria-label="Keyingi oy"><FontAwesomeIcon icon={faChevronRight} /></button>
        </div>
        {view && <span className="muted-sm">Solishtirish: {MONTHS[view.prev.month - 1]} {view.prev.year}{isCurrentMonth && ` · oy davom etmoqda (${view.today}/${view.days} kun)`}</span>}
      </div>

      {error && <ErrorState title="Maosh ma’lumotlarini yuklab bo‘lmadi" onRetry={load} />}
      {loading && !data && <CardSkeleton count={3} height={120} />}

      {!error && view && (
        <div className={'sal-page' + (loading ? ' is-loading' : '')}>
          <section className="sal-hero">
            <div className="sal-hero-main">
              <span className="sal-hero-label">{MONTHS[month - 1]} {year} — hisoblangan oylik</span>
              <strong className="sal-hero-value">{fmt(view.cur.salary)}</strong>
              <Delta cur={view.cur.salary} prev={view.prev.salary} money />
              <span className="sal-hero-note">
                {view.cur.is_internship
                  ? 'Stajirovka — shu oy uchun oylik 0'
                  : view.cur.auto
                    ? `FIX ${fmt(view.cur.base)} + talaba ulushi ${fmt(view.cur.bonus)}`
                    : 'Qo‘lda belgilangan oylik'}
              </span>
              {view.projected != null && view.cur.auto && !view.cur.is_internship && (
                <span className="sal-hero-forecast">Oy oxirigacha shu sur’atda: <b>≈ {fmt(view.projected)}</b></span>
              )}
            </div>
            <dl className="sal-hero-facts">
              <div><dt>{prevLabel} oyligi</dt><dd>{fmt(view.prev.salary)}</dd></div>
              <div><dt>To‘langan</dt><dd className="tone-success">{fmt(view.cur.paid)}</dd></div>
              <div><dt>Qolgan</dt><dd className={num(view.cur.remaining) > 0 ? 'tone-warning' : 'tone-success'}>{fmt(view.cur.remaining)}</dd></div>
              <div>
                <dt>To‘lov holati</dt>
                <dd>
                  <span className="sal-progress"><i style={{ width: `${Math.min(100, num(view.cur.salary) ? (num(view.cur.paid) / num(view.cur.salary)) * 100 : 0)}%` }} /></span>
                  {num(view.cur.salary) ? Math.round((num(view.cur.paid) / num(view.cur.salary)) * 100) : 0}%
                </dd>
              </div>
            </dl>
          </section>

          <section className="sal-kpis">
            <Kpi icon={faMoneyBillWave} label="Talaba ulushi" value={fmt(view.cur.bonus)} cur={view.cur.bonus} prev={view.prev.bonus} money />
            <Kpi icon={faChalkboardUser} label="O‘tilgan darslar" value={view.cur.lessons} cur={view.cur.lessons} prev={view.prev.lessons} suffix=" dars"
              hint={view.prevSamePeriod && `${prevLabel}ning shu kunigacha: ${view.prevSamePeriod.lessons} dars`} />
            <Kpi icon={faUserGraduate} label="O‘qitilgan talabalar" value={view.cur.students} cur={view.cur.students} prev={view.prev.students} suffix=" talaba"
              hint={`${view.cur.groups} ta guruhda`} />
            <Kpi icon={faCalendarCheck} label="Qatnashuvlar" value={view.cur.attendances} cur={view.cur.attendances} prev={view.prev.attendances}
              hint={view.prevSamePeriod && `${prevLabel}ning shu kunigacha: ${view.prevSamePeriod.attendances}`} />
            <Kpi icon={faWallet} label="1 darsdagi o‘rtacha talaba" value={view.perLessonAvg.toFixed(1)}
              cur={Math.round(view.perLessonAvg * 10) / 10} prev={Math.round(view.prevPerLessonAvg * 10) / 10}
              hint={`1 dars × 1 talaba = ${fmt(data.per_lesson)}`} />
          </section>

          <section className="sal-charts">
            <article className="card sal-card">
              <header>
                <h4>Oxirgi 6 oy dinamikasi</h4>
                <div className="sal-legend">
                  <span><i className="is-base" />FIX / belgilangan</span>
                  <span><i className="is-bonus" />Talaba ulushi</span>
                  <span><i className="is-paid" />To‘langan</span>
                </div>
              </header>
              <SalaryTrendChart trend={view.trend} selectedIdx={view.trend.length - 1} />
            </article>
            <article className="card sal-card">
              <header>
                <h4>Oy davomida qatnashuvlar (jamlanma)</h4>
                <div className="sal-legend">
                  <span><i className="is-cur" />{MONTHS[month - 1]}</span>
                  <span><i className="is-prev" />{prevLabel}</span>
                </div>
              </header>
              {isFuture
                ? <EmptyState title="Bu oy hali boshlanmagan" compact />
                : <CumulativeChart daily={data.daily} prevDaily={data.prev_daily || []} days={view.days}
                    prevDays={view.prevDays} uptoDay={isCurrentMonth ? view.today : undefined} />}
            </article>
          </section>

          <section className="card sal-card">
            <header>
              <h4>Guruhlar bo‘yicha — {MONTHS[month - 1]} va {prevLabel}</h4>
              <div className="sal-legend">
                <span><i className="is-cur" />{MONTHS[month - 1]}</span>
                <span><i className="is-prev" />{prevLabel}</span>
              </div>
            </header>
            {data.groups.length === 0 ? (
              <EmptyState icon={faMoneyBillWave} title="Bu ikki oyda dars o‘tilmagan" compact />
            ) : (
              <div className="sal-groups">
                <GroupBars groups={data.groups} />
                <DataTable
                  columns={[
                    { key: 'group_name', header: 'Guruh', sortable: true },
                    { key: 'lessons', header: 'Dars', align: 'right', sortable: true,
                      render: g => <span>{g.lessons} <Delta cur={g.lessons} prev={g.prev_lessons} /></span> },
                    { key: 'students', header: 'Talaba', align: 'right', sortable: true,
                      render: g => <span>{g.students} <Delta cur={g.students} prev={g.prev_students} /></span> },
                    { key: 'attendances', header: 'Qatnashuv', align: 'right', sortable: true,
                      render: g => <span>{g.attendances} <Delta cur={g.attendances} prev={g.prev_attendances} /></span> },
                    { key: 'bonus', header: 'Ulush', align: 'right', sortable: true, sortValue: g => num(g.bonus),
                      render: g => <span><strong className="tone-success">{fmt(g.bonus)}</strong> <Delta cur={g.bonus} prev={g.prev_bonus} money /></span> },
                  ]}
                  rows={data.groups}
                  rowKey={g => g.group_id}
                />
              </div>
            )}
          </section>

          {breakdown?.items?.length > 0 && (
            <section className="card sal-card">
              <header>
                <h4>Talabalar bo‘yicha hisob</h4>
                <span className="muted-sm">50 000 so‘m 12 darsga to‘g‘ri keladi (1 dars = {fmt(data.per_lesson)}) × talaba qatnashgan darslar</span>
              </header>
              <DataTable
                columns={[
                  { key: 'group_name', header: 'Guruh', sortable: true },
                  { key: 'student_name', header: 'Talaba', sortable: true },
                  { key: 'lessons_held', header: 'Oydagi darslar', align: 'right', sortable: true },
                  { key: 'attended', header: 'Qatnashgan', align: 'right', sortable: true },
                  { key: 'share', header: 'Ulush', align: 'right', sortable: true, sortValue: it => num(it.share),
                    render: it => <strong className="tone-success">{fmt(it.share)}</strong> },
                ]}
                rows={breakdown.items}
                rowKey={(it, i) => i}
                clientPageSize={20}
                empty={{ title: 'Davomat yozuvi yo‘q' }}
              />
            </section>
          )}
        </div>
      )}
    </Modal>
  )
}
