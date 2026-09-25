import { useEffect, useMemo, useState } from 'react'
import { toast } from 'react-hot-toast'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faCashRegister, faCalendarDays, faArrowDown, faArrowUp,
  faReceipt, faCreditCard, faCircleInfo,
} from '@fortawesome/free-solid-svg-icons'
import { fetchCashbox, fetchCashboxDay } from '../api'
import { PageIntro, SummaryRow } from './ui/Workspace'
import InsightChart from './ui/InsightChart'
import DataTable from './ui/DataTable'
import Modal from './ui/Modal'
import Badge from './ui/Badge'
import SectionHead from './ui/SectionHead'
import { TableSkeleton } from './ui/States'
import { tashkentNow, fmtTime } from '../utils/datetime'

const MONTHS = ['Yanvar','Fevral','Mart','Aprel','May','Iyun','Iyul','Avgust','Sentyabr','Oktyabr','Noyabr','Dekabr']
const WEEKDAYS = ['Dushanba','Seshanba','Chorshanba','Payshanba','Juma','Shanba','Yakshanba']
const NOW = tashkentNow()
const YEARS = Array.from({ length: 5 }, (_, i) => NOW.getFullYear() - 2 + i)

const fmt = n => Number(n || 0).toLocaleString('uz-UZ')
const money = n => `${fmt(n)} so'm`
/** Sof qiymat — ishorasi bilan ("+1 200 000" / "−300 000"). */
const signed = n => (Number(n) < 0 ? '−' : '+') + fmt(Math.abs(Number(n) || 0))
const netTone = n => (Number(n) > 0 ? 'success' : Number(n) < 0 ? 'danger' : undefined)

/** "2026-09-14" → "14.09.2026" (serverdan sof sana keladi, vaqt zonasisiz). */
function dayLabel(iso) {
  if (!iso) return '—'
  const [y, m, d] = iso.split('-')
  return `${d}.${m}.${y}`
}

/** Kartalardagi sarlavha — "Bugun, 16.09" ko'rinishida. */
function shortDay(iso) {
  if (!iso) return ''
  const [, m, d] = iso.split('-')
  return `${d}.${m}`
}

export default function Cashbox() {
  const [month, setMonth] = useState(NOW.getMonth() + 1)
  const [year, setYear] = useState(NOW.getFullYear())
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  // Harakatsiz kunlar jadvalni cho'zadi — lekin "o'sha kuni umuman pul
  // tushmagan" ham hisobot uchun javob, shuning uchun o'chirish emas, filtr.
  const [onlyActive, setOnlyActive] = useState(false)
  const [dayModal, setDayModal] = useState(null)      // {date} — tanlangan kun
  const [dayData, setDayData] = useState(null)
  const [dayLoading, setDayLoading] = useState(false)

  useEffect(() => { load() }, [month, year])

  async function load() {
    setLoading(true)
    try { setData(await fetchCashbox(month, year)) }
    catch (err) { toast.error(err.message || "Yuklab bo'lmadi") }
    finally { setLoading(false) }
  }

  async function openDay(iso) {
    setDayModal({ date: iso })
    setDayData(null)
    setDayLoading(true)
    try { setDayData(await fetchCashboxDay(iso)) }
    catch (err) { toast.error(err.message || "Yuklab bo'lmadi"); setDayModal(null) }
    finally { setDayLoading(false) }
  }

  const days = data?.days || []
  const rows = useMemo(
    () => (onlyActive ? days.filter(d => d.income || d.expense) : days),
    [days, onlyActive],
  )

  // Eng ko'p pul tushgan kun — "oyning eng yaxshi kuni" degan javob.
  const bestDay = useMemo(
    () => days.reduce((best, d) => (d.income > (best?.income || 0) ? d : best), null),
    [days],
  )
  const activeDays = days.filter(d => d.income > 0).length
  const avgIncome = activeDays ? (data?.month_income || 0) / activeDays : 0

  const columns = [
    {
      key: 'date', header: 'Sana', sortable: true,
      render: d => (
        <div className="kassa-day-cell">
          <strong>{dayLabel(d.date)}</strong>
          <small>{WEEKDAYS[d.weekday]}</small>
        </div>
      ),
    },
    {
      key: 'income', header: 'Kirim', align: 'right', sortable: true, sortValue: d => d.income,
      render: d => d.income
        ? <span className="amount tone-success">{fmt(d.income)}</span>
        : <span className="muted-sm">—</span>,
    },
    {
      key: 'payment_count', header: "To'lov", align: 'right', sortable: true,
      render: d => <span className="muted-sm">{d.payment_count || '—'}</span>,
    },
    {
      key: 'expense', header: 'Chiqim', align: 'right', sortable: true, sortValue: d => d.expense,
      render: d => d.expense
        ? <span className="amount tone-danger">{fmt(d.expense)}</span>
        : <span className="muted-sm">—</span>,
    },
    {
      key: 'net', header: 'Sof', align: 'right', sortable: true, sortValue: d => d.net,
      render: d => (d.income || d.expense)
        ? <span className={`amount${netTone(d.net) ? ' tone-' + netTone(d.net) : ''}`}>{signed(d.net)}</span>
        : <span className="muted-sm">—</span>,
    },
    {
      key: 'balance', header: 'Kun oxiridagi kassa', align: 'right', sortable: true, sortValue: d => d.balance,
      render: d => <span className="amount">{fmt(d.balance)}</span>,
    },
  ]

  const isCurrentMonth = month === NOW.getMonth() + 1 && year === NOW.getFullYear()

  return (
    <div className="page kassa-studio">
      <PageIntro
        title={<>Kassa</>}
        description={<>{MONTHS[month - 1]} {year} · kunlik naqd oqim · kassada hozir{' '}
          <strong className={netTone(data?.balance) ? 'tone-' + netTone(data?.balance) : undefined}>
            {fmt(data?.balance)} so'm
          </strong></>}
        actions={
          <div className="header-actions">
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
          </div>
        }
      />

      {loading ? <TableSkeleton /> : data ? (
        <>
          {/* ── 1. Kassadagi qoldiq + bugun/kecha ─────────────────────────── */}
          <section className="ledger-overview kassa-overview" aria-label="Kassa qoldig'i">
            <div className="ledger-balance">
              <span className="studio-eyebrow">Kassadagi qoldiq</span>
              <strong className={netTone(data.balance) ? 'tone-' + netTone(data.balance) : undefined}>
                {fmt(data.balance)}<small>so‘m</small>
              </strong>
              <div>
                <span className="icon-tile tone-success" aria-hidden="true"><FontAwesomeIcon icon={faCashRegister} /></span>
                <p>Oy kirimi {fmt(data.month_income)} so‘m
                  <span>Oy chiqimi {fmt(data.month_expense)} so‘m · {MONTHS[month - 1].toLowerCase()} {year}</span>
                </p>
              </div>
            </div>
            <div className="ledger-balance-details">
              <button onClick={() => openDay(data.today.date)}>
                <span>Bugun <small>{shortDay(data.today.date)} · {data.today.payment_count} to‘lov →</small></span>
                <strong className={data.today.income ? 'tone-success' : undefined}>
                  {fmt(data.today.income)} <small>so‘m</small>
                </strong>
              </button>
              <button onClick={() => openDay(data.yesterday.date)}>
                <span>Kecha <small>{shortDay(data.yesterday.date)} · {data.yesterday.payment_count} to‘lov →</small></span>
                <strong className={data.yesterday.income ? 'tone-success' : undefined}>
                  {fmt(data.yesterday.income)} <small>so‘m</small>
                </strong>
              </button>
              <div>
                <span>Bugungi chiqim <small>{data.today.expense_count} yozuv</small></span>
                <strong className={data.today.expense ? 'tone-danger' : undefined}>
                  {fmt(data.today.expense)} <small>so‘m</small>
                </strong>
              </div>
            </div>
          </section>

          {/* ── 2. Oy kesimi: kirim − chiqim = qoldiq ─────────────────────── */}
          <SummaryRow
            label="Oy ko‘rsatkichlari"
            items={[
              {
                label: 'Oy boshidagi qoldiq', value: fmt(data.opening_balance), unit: 'so‘m',
                sub: `1-${MONTHS[month - 1].toLowerCase()} holatiga`,
              },
              {
                label: 'Oy kirimi', value: fmt(data.month_income), unit: 'so‘m', tone: 'success',
                icon: faArrowDown,
                sub: `${activeDays} kunda tushum · o‘rtacha ${fmt(Math.round(avgIncome))}`,
              },
              {
                label: 'Oy chiqimi', value: fmt(data.month_expense), unit: 'so‘m', tone: 'danger',
                icon: faArrowUp,
                sub: `oylik ${fmt(data.month_salary_expense)} · boshqa ${fmt(data.month_other_expense)}`,
              },
              {
                label: 'Oylik sof', value: signed(data.month_net), unit: 'so‘m',
                tone: netTone(data.month_net),
                sub: 'kirim − chiqim',
              },
              {
                label: isCurrentMonth ? 'Hozirgi qoldiq' : 'Oy oxiridagi qoldiq',
                value: fmt(data.closing_balance), unit: 'so‘m',
                sub: 'oy boshi + sof',
              },
            ]}
          />

          {/* ── 3. Kunlar grafigi ─────────────────────────────────────────── */}
          <section className="kassa-chart" aria-label="Kunlik oqim">
            <InsightChart
              title="Kunlik naqd oqim"
              subtitle={`${MONTHS[month - 1]} ${year} · har bir kun alohida`}
              unit="so‘m"
              data={days.map(d => ({
                label: String(Number(d.date.slice(8, 10))),
                value: d.income,
                compare: d.expense,
                line: d.balance,
              }))}
              series={[
                { key: 'value', label: 'Kirim', color: 'var(--viz-1)' },
                { key: 'compare', label: 'Chiqim', color: 'var(--viz-3)' },
                { key: 'line', label: 'Kassa qoldig‘i', color: 'var(--viz-2)' },
              ]}
              aggregate="last"
              footnote={bestDay && bestDay.income > 0
                ? <>Eng ko‘p tushum: <strong>{dayLabel(bestDay.date)}</strong> — {money(bestDay.income)}</>
                : <>Bu oyda hali tushum yo‘q</>}
            />
          </section>

          {/* ── 4. Kunlar jadvali ─────────────────────────────────────────── */}
          <div className="studio-section kassa-table">
            <div className="studio-section-head">
              <div>
                <h2>Kun kesimida</h2>
                <p>Qatorni bosing — o‘sha kunning har bir to‘lovi va xarajati ko‘rinadi.</p>
              </div>
              <label className="kassa-toggle">
                <input type="checkbox" checked={onlyActive} onChange={e => setOnlyActive(e.target.checked)} />
                Faqat harakat bo‘lgan kunlar
              </label>
            </div>
            <DataTable
              columns={columns}
              rows={rows}
              rowKey={d => d.date}
              onRowClick={d => openDay(d.date)}
              rowClassName={d => (d.income || d.expense ? undefined : 'kassa-row-idle')}
              empty={{
                icon: faCashRegister,
                title: `${MONTHS[month - 1]} ${year} uchun harakat yo‘q`,
                description: 'Bu oyda hali to‘lov ham, xarajat ham yozilmagan.',
              }}
            />
            {rows.length > 0 && (
              <div className="kassa-table-foot">
                <span>Jami {rows.length} kun</span>
                <div>
                  <span>Kirim <strong className="tone-success">{fmt(data.month_income)}</strong></span>
                  <span>Chiqim <strong className="tone-danger">{fmt(data.month_expense)}</strong></span>
                  <span>Sof <strong className={netTone(data.month_net) ? 'tone-' + netTone(data.month_net) : undefined}>{signed(data.month_net)}</strong></span>
                </div>
              </div>
            )}
          </div>

          <p className="kassa-note">
            <FontAwesomeIcon icon={faCircleInfo} />
            Kassa pul HAQIQATDA qabul qilingan/chiqarilgan kunga qarab hisoblanadi.
            Shuning uchun, masalan, avgust oyi uchun sentyabrda kelgan to‘lov
            «Moliya hisoboti»da avgustda, bu yerda esa to‘langan kunida ko‘rinadi.
            Kassa qoldig‘i har oy 0 so‘mdan boshlanadi — oldingi oyning
            qoldig‘i keyingi oyga ko‘chirilmaydi.
          </p>
        </>
      ) : null}

      <Modal
        open={!!dayModal}
        title={dayModal ? `${dayLabel(dayModal.date)} — kassa` : ''}
        onClose={() => setDayModal(null)}
        size="xl"
        footer={<button className="button secondary" onClick={() => setDayModal(null)}>Yopish</button>}
      >
        {dayLoading ? <TableSkeleton /> : dayData ? (
          <div className="kassa-day">
            <div className="kassa-day-totals">
              <div>
                <span>Kirim</span>
                <strong className="tone-success">{money(dayData.income)}</strong>
              </div>
              <div>
                <span>Chiqim</span>
                <strong className="tone-danger">{money(dayData.expense)}</strong>
              </div>
              <div>
                <span>Sof</span>
                <strong className={netTone(dayData.net) ? 'tone-' + netTone(dayData.net) : undefined}>
                  {signed(dayData.net)} so‘m
                </strong>
              </div>
            </div>

            <SectionHead title="Kirimlar" description={`${dayData.payments.length} ta to‘lov`} />
            {dayData.payments.length ? (
              <table className="data-table kassa-day-table">
                <thead>
                  <tr>
                    <th>Vaqt</th><th>Talaba</th><th>Guruh</th><th>Qaysi oy uchun</th>
                    <th>Qabul qilgan</th><th className="right">Summa</th>
                  </tr>
                </thead>
                <tbody>
                  {dayData.payments.map(p => (
                    <tr key={p.id}>
                      <td className="muted-sm">{fmtTime(p.paid_at)}</td>
                      <td><strong>{p.student_name || '—'}</strong></td>
                      <td className="muted-sm">{p.group_name || '—'}</td>
                      <td className="muted-sm">{MONTHS[p.for_month - 1]} {p.for_year}</td>
                      <td className="muted-sm">{p.recorded_by || '—'}</td>
                      <td className="right amount tone-success">{fmt(p.amount)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : <p className="muted-sm kassa-day-empty">Bu kuni to‘lov qabul qilinmagan.</p>}

            <SectionHead title="Chiqimlar" description={`${dayData.expenses.length} ta xarajat`} />
            {dayData.expenses.length ? (
              <table className="data-table kassa-day-table">
                <thead>
                  <tr>
                    <th>Vaqt</th><th>Nomi / Sabab</th><th>Turi</th>
                    <th>Qaysi oy uchun</th><th className="right">Summa</th>
                  </tr>
                </thead>
                <tbody>
                  {dayData.expenses.map(e => (
                    <tr key={e.id}>
                      <td className="muted-sm">{fmtTime(e.created_at)}</td>
                      <td><strong>{e.name}</strong></td>
                      <td>
                        {e.category === 'salary'
                          ? <Badge variant="info" size="sm">Oylik — {e.staff_name || '—'}</Badge>
                          : <span className="muted-sm">Oddiy</span>}
                      </td>
                      <td className="muted-sm">{MONTHS[e.for_month - 1]} {e.for_year}</td>
                      <td className="right amount tone-danger">{fmt(e.amount)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : <p className="muted-sm kassa-day-empty">Bu kuni xarajat yozilmagan.</p>}

            <div className="kassa-day-links">
              <span><FontAwesomeIcon icon={faCreditCard} /> To‘lovlar «To‘lovlar» bo‘limida kiritiladi</span>
              <span><FontAwesomeIcon icon={faReceipt} /> Xarajatlar «Xarajatlar» bo‘limida kiritiladi</span>
            </div>
          </div>
        ) : null}
      </Modal>
    </div>
  )
}
