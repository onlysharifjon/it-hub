import { useEffect, useState } from 'react'
import {
  faArrowDownLong, faHandHoldingDollar, faScaleBalanced, faBuildingColumns, faFileInvoiceDollar,
  faTriangleExclamation, faCalendarDays, faSun,
} from '@fortawesome/free-solid-svg-icons'
import { finance } from '../../api'
import { PageIntro } from '../ui/Workspace'
import KpiCard from '../ui/KpiCard'
import { BarChart } from '../ui/Chart'
import { CardSkeleton, ErrorState, EmptyState } from '../ui/States'
import {
  DateRange, presetRange, money, fmt, fmtDate, METHOD_LABELS, useRefData, can, NoAccess, CurrencyLines,
} from './shared'

const pct = (a, b) => (Number(b) ? Math.round((Number(a) - Number(b)) / Math.abs(Number(b)) * 1000) / 10 : null)
const short = n => new Intl.NumberFormat('en', { notation: 'compact', maximumFractionDigits: 1 }).format(n)

function otherCurrencies(obj, field) {
  const rows = Object.entries(obj || {}).filter(([cur, v]) => cur !== 'UZS' && Number(v?.[field] ?? v))
  if (!rows.length) return null
  return rows.map(([cur, v]) => money(v?.[field] ?? v, cur)).join(' · ')
}

export default function FinOverview({ currentUser, onNavigate }) {
  const [range, setRange] = useState(() => presetRange('month'))
  const [method, setMethod] = useState('')
  const [accountId, setAccountId] = useState('')
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const [{ accounts }] = useRefData(['accounts'])

  async function load() {
    setLoading(true); setError(null)
    try { setData(await finance.dashboard({ ...range, method, account_id: accountId })) }
    catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }
  useEffect(() => { if (range.date_from && range.date_to) load() }, [range, method, accountId])

  if (!can(currentUser, 'finance.dashboard')) return <div className="page fin-page"><NoAccess /></div>

  const P = data?.period?.UZS || {}
  const prev = data?.previous?.UZS || {}
  const today = data?.today_totals?.UZS || {}
  const chart = (data?.chart || []).filter(c => c.currency === 'UZS').map(c => ({
    label: data.chart_granularity === 'day' ? fmtDate(c.label).slice(0, 5) : c.label.slice(0, 3) + c.label.slice(-5),
    value: Number(c.income), compare: Number(c.expense), line: Number(c.net),
  }))
  const drafts = Object.values(data?.drafts || {}).reduce((a, b) => a + b, 0)

  return (
    <div className="page fin-page">
      <PageIntro eyebrow="Moliya" title="Umumiy ko'rinish"
        description="Tushum, xarajat, pul oqimi, hisob qoldiqlari va qarzdorlik — faqat tasdiqlangan operatsiyalar asosida." />

      <div className="fin-toolbar" role="search" aria-label="Filtrlar">
        <DateRange value={range} onChange={setRange} />
        <select className="field-sm" value={method} onChange={e => setMethod(e.target.value)} aria-label="To'lov usuli">
          <option value="">Barcha usullar</option>
          {Object.entries(METHOD_LABELS).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
        </select>
        <select className="field-sm" value={accountId} onChange={e => setAccountId(e.target.value)} aria-label="Kassa yoki hisob">
          <option value="">Barcha hisoblar</option>
          {accounts.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}
        </select>
      </div>

      {error && <ErrorState message={error} onRetry={load} />}
      {!error && loading && !data && <CardSkeleton count={8} />}

      {data && !error && (
        <>
          {drafts > 0 && (
            <div className="fin-callout" role="status">
              <span><strong>{drafts}</strong> ta operatsiya tasdiqlanishini kutmoqda (qoralama) — ular yakuniy summalarga kirmaydi.</span>
              {can(currentUser, 'finance.approve') && (
                <button className="button small secondary" onClick={() => onNavigate(data.drafts.expense ? 'fin_expenses' : 'fin_income')}>Ko'rish</button>
              )}
            </div>
          )}

          <div className="fin-kpis" aria-busy={loading}>
            <KpiCard label="Bugungi tushum" value={fmt(Number(today.income || 0) - Number(today.refunds || 0))} unit="so'm" icon={faSun}
              tone="success" sub={otherCurrencies(data.today_totals, 'income') || fmtDate(data.today)} />
            <KpiCard label="Davr tushumi" value={fmt(Number(P.income || 0) - Number(P.refunds || 0))} unit="so'm" icon={faArrowDownLong}
              tone="success" trend={pct(Number(P.income || 0) - Number(P.refunds || 0), Number(prev.income || 0) - Number(prev.refunds || 0))}
              trendLabel="oldingi davrga nisbatan"
              sub={[Number(P.refunds) ? `qaytarim: ${fmt(P.refunds)}` : null, otherCurrencies(data.period, 'income')].filter(Boolean).join(' · ') || undefined}
              onClick={can(currentUser, 'finance.clients') ? () => onNavigate('fin_income') : undefined} />
            <KpiCard label="Davr xarajatlari" value={fmt(P.expense)} unit="so'm" icon={faHandHoldingDollar} tone="danger"
              trend={pct(P.expense, prev.expense)} trendInvert trendLabel="oldingi davrga nisbatan"
              sub={otherCurrencies(data.period, 'expense') || undefined}
              onClick={can(currentUser, 'finance.expense') ? () => onNavigate('fin_expenses') : undefined} />
            <KpiCard label="Sof pul oqimi" value={(Number(P.net) < 0 ? '−' : '') + fmt(Math.abs(Number(P.net || 0)))} unit="so'm"
              icon={faScaleBalanced} tone={Number(P.net) < 0 ? 'danger' : 'primary'}
              hint="Tushum − qaytarimlar − xarajatlar. Ichki o'tkazmalar kirmaydi. Bu sof foyda emas."
              sub={otherCurrencies(data.period, 'net') || 'tushum − xarajat'} />
            <KpiCard label="Kassa va bank qoldig'i" value={fmt(data.balances?.UZS)} unit="so'm" icon={faBuildingColumns} tone="info"
              sub={otherCurrencies(data.balances) || `${data.accounts.length} ta faol hisob`} onClick={() => onNavigate('fin_accounts')} />
            <KpiCard label="Umumiy qarzdorlik" value={fmt(data.debt.total)} unit="so'm" icon={faFileInvoiceDollar} tone="warning"
              sub={`${data.debt.debtors} ta mijoz · avans: ${fmt(data.debt.advance)}`}
              onClick={can(currentUser, 'finance.debts') ? () => onNavigate('fin_debts') : undefined} />
            <KpiCard label="Muddati o'tgan qarz" value={fmt(data.debt.overdue)} unit="so'm" icon={faTriangleExclamation} tone="danger"
              sub={`${data.debt.overdue_students} ta mijoz · muddati kelmagan: ${fmt(data.debt.not_due)}`}
              onClick={can(currentUser, 'finance.debts') ? () => onNavigate('fin_debts') : undefined} />
            <KpiCard label="Yaqinlashayotgan to'lovlar" value={fmt(data.upcoming.total)} unit="so'm" icon={faCalendarDays} tone="accent"
              sub={`${data.upcoming.count} ta to'lov · ${data.upcoming.days} kun ichida`} />
          </div>

          <div className="fin-grid-2">
            <section className="fin-card" aria-labelledby="fin-chart-h">
              <div className="fin-card-head">
                <div><h2 id="fin-chart-h">Tushum va xarajatlar dinamikasi</h2>
                  <p>{data.chart_granularity === 'day' ? 'Kunlik' : 'Oylik'} · {fmtDate(data.date_from)} — {fmtDate(data.date_to)} · so'm</p></div>
              </div>
              <div className="fin-card-body">
                <BarChart data={chart} seriesLabel="Tushum (qaytarimsiz)" compareLabel="Xarajat" lineLabel="Sof pul oqimi"
                  valueFormat={short} tooltipFormat={v => `${fmt(v)} so'm`} height={240} emptyText="Bu davrda tasdiqlangan operatsiya yo'q" />
              </div>
              {Object.keys(data.period).some(c => c !== 'UZS') && (
                <p className="fin-chart-note">Grafik faqat so'mdagi operatsiyalarni ko'rsatadi. Boshqa valyutalar alohida hisoblanadi va so'mga qo'shilmaydi.</p>
              )}
            </section>

            <section className="fin-card" aria-labelledby="fin-acc-h">
              <div className="fin-card-head"><div><h2 id="fin-acc-h">Kassa va hisoblar</h2><p>Joriy qoldiq</p></div></div>
              {data.accounts.length === 0
                ? <EmptyState compact title="Faol hisob yo'q" />
                : <ul className="fin-list">
                  {data.accounts.map(a => (
                    <li key={a.id}><div><strong>{a.name}</strong><small>{a.currency}</small></div>
                      <span className={`amount${Number(a.balance) < 0 ? ' tone-danger' : ''}`}>{money(a.balance, a.currency)}</span></li>
                  ))}
                </ul>}
            </section>
          </div>

          <section className="fin-card" aria-labelledby="fin-up-h">
            <div className="fin-card-head">
              <div><h2 id="fin-up-h">Yaqinlashayotgan to'lovlar</h2><p>Keyingi {data.upcoming.days} kun ichida muddati keladigan, hali to'lanmagan bosqichlar</p></div>
              <span className="muted-sm">{data.upcoming.count} ta</span>
            </div>
            {data.upcoming.items.length === 0
              ? <EmptyState compact title="Yaqin kunlarda to'lov muddati yo'q" />
              : <ul className="fin-list">
                {data.upcoming.items.slice(0, 12).map((u, i) => (
                  <li key={`${u.student_id}-${u.period}-${i}`}>
                    <div><strong>{u.student}</strong><small>{u.group} · {u.period} · {u.phone}</small></div>
                    <div style={{ textAlign: 'right' }}><span className="amount">{money(u.amount)}</span><small>{fmtDate(u.due_date)} gacha</small></div>
                  </li>
                ))}
              </ul>}
          </section>

          {Object.keys(data.period).some(c => c !== 'UZS') && (
            <p className="muted-sm">Boshqa valyutadagi davr natijalari: <CurrencyLines values={Object.fromEntries(Object.entries(data.period).filter(([c]) => c !== 'UZS'))} field="net" signed /></p>
          )}
        </>
      )}
    </div>
  )
}
