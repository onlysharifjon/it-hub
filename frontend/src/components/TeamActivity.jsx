import { useCallback, useEffect, useMemo, useState } from 'react'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faUsersGear, faPhone, faCircleCheck, faPhoneSlash, faPercent,
  faMagnifyingGlass, faXmark, faArrowRight, faClock,
} from '@fortawesome/free-solid-svg-icons'
import {
  fetchTeamActivity, fetchOperatorActivity, fetchCallActivities,
} from '../api'
import { PageIntro, SummaryRow, ViewTabs, Initials, ProgressRing } from './ui/Workspace'
import DataTable from './ui/DataTable'
import OperatorRoster, { TEAM_ROLE_LABEL } from './team/OperatorRoster'
import { Drawer } from './ui/Modal'
import { EmptyState, ErrorState, CardSkeleton, TableSkeleton } from './ui/States'
import { ConversionInsights } from './tree/ConversionPanels'
import { fmtDateTime, fmtTime, fmtRelative, tashkentToday, shiftDay } from '../utils/datetime'

const RANGES = [
  { v: 'today',     label: 'Bugun' },
  { v: 'yesterday', label: 'Kecha' },
  { v: 'week',      label: 'Bu hafta' },
  { v: 'month',     label: 'Bu oy' },
  { v: 'custom',    label: 'Oraliq' },
]

const OUTCOME_TONE = {
  connected: 'success', resolved: 'success', will_pay: 'success',
  returns: 'success', interested: 'success',
  no_answer: 'muted', phone_off: 'muted', wrong_number: 'muted',
  callback: 'info',
  wont_pay: 'danger', not_returns: 'danger', rejected: 'danger',
}

/**
 * Davr chegaralari — DOIM Toshkent kalendari bo'yicha.
 * Backend sana filtrlarini shu tarzda tushunadi, shuning uchun qurilma
 * mintaqasi boshqa bo'lsa ham ikkala tomon bir xil kunni ko'radi.
 */
function rangeDates(kind) {
  const today = tashkentToday()
  if (kind === 'yesterday') {
    const y = shiftDay(today, -1)
    return [y, y]
  }
  if (kind === 'week') {
    // Dushanbadan boshlanadi (mahalliy odat)
    const [yy, mm, dd] = today.split('-').map(Number)
    const dow = (new Date(Date.UTC(yy, mm - 1, dd)).getUTCDay() + 6) % 7
    return [shiftDay(today, -dow), today]
  }
  if (kind === 'month') {
    return [today.slice(0, 8) + '01', today]
  }
  return [today, today]
}

/**
 * Jamoa faoliyati — admin uchun monitoring maydoni.
 *
 * Savol: "Call center bugun nima qildi?" Javob bir ekranda bo'lishi kerak:
 * nechta qo'ng'iroq, nechtasi bog'landi, kim ko'proq ishladi, nima gaplashildi.
 *
 * Barcha filtr va sahifalash SERVERDA — faoliyat jurnali vaqt o'tishi bilan
 * o'n minglab qatorga yetadi, uni brauzerga tashish mumkin emas.
 */
export default function TeamActivity() {
  const [range, setRange] = useState('today')
  const [activityView, setActivityView] = useState('overview')
  const [operatorView, setOperatorView] = useState('performance')
  const [operatorQuery, setOperatorQuery] = useState('')
  const [operatorSort, setOperatorSort] = useState('calls')
  const [from, setFrom] = useState(() => rangeDates('today')[0])
  const [to, setTo] = useState(() => rangeDates('today')[1])
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState(null)
  const [openOp, setOpenOp] = useState(null)
  const [opDetail, setOpDetail] = useState(null)

  // Jurnal (pastdagi jadval)
  const [log, setLog] = useState(null)
  const [logPage, setLogPage] = useState(1)
  const [logLoading, setLogLoading] = useState(true)
  const [fOperator, setFOperator] = useState('')
  const [fOutcome, setFOutcome] = useState('')
  const [fType, setFType] = useState('')
  const [q, setQ] = useState('')
  const [dq, setDq] = useState('')

  useEffect(() => {
    const t = setTimeout(() => { setDq(q.trim()); setLogPage(1) }, 300)
    return () => clearTimeout(t)
  }, [q])

  function pickRange(kind) {
    setRange(kind)
    if (kind !== 'custom') {
      const [a, b] = rangeDates(kind)
      setFrom(a); setTo(b)
    }
  }

  const load = useCallback(async () => {
    setLoading(true); setErr(null)
    try { setData(await fetchTeamActivity(from, to)) }
    catch (e) { setErr(e.message); setData(null) }
    finally { setLoading(false) }
  }, [from, to])

  const loadLog = useCallback(async () => {
    setLogLoading(true)
    try {
      setLog(await fetchCallActivities({
        date_from: from, date_to: to, page: logPage, per_page: 50,
        user_id: fOperator || undefined,
        outcome: fOutcome || undefined,
        task_type: fType || undefined,
        q: dq || undefined,
      }))
    } catch { setLog(null) } finally { setLogLoading(false) }
  }, [from, to, logPage, fOperator, fOutcome, fType, dq])

  useEffect(() => { load() }, [load])
  useEffect(() => { loadLog() }, [loadLog])

  async function openOperator(op) {
    setOpenOp(op); setOpDetail(null)
    try { setOpDetail(await fetchOperatorActivity(op.id, from, to)) } catch {}
  }

  const opColumns = useMemo(() => [
    { key: 'name', header: 'Operator', render: r => (
      <span className="ta-op"><strong>{r.name}</strong><span className="muted">{r.role}</span></span>
    ) },
    { key: 'calls', header: "Qo'ng'iroq", align: 'right', sortable: true, render: r => r.calls },
    { key: 'connected', header: "Bog'landi", align: 'right', sortable: true, render: r => r.connected },
    { key: 'no_answer', header: 'Javobsiz', align: 'right', sortable: true, render: r => r.no_answer },
    { key: 'connect_rate', header: 'Bog\'lanish %', align: 'right', sortable: true,
      render: r => <span className={r.connect_rate >= 50 ? 'num-pos' : ''}>{r.connect_rate}%</span> },
    { key: 'completed_tasks', header: 'Bajarilgan', align: 'right', sortable: true, render: r => r.completed_tasks },
    { key: 'callbacks', header: 'Callback', align: 'right', sortable: true, render: r => r.callbacks },
    { key: 'payment_calls', header: "To'lov", align: 'right', sortable: true, render: r => r.payment_calls },
    { key: 'absence_calls', header: 'Davomat', align: 'right', sortable: true, render: r => r.absence_calls },
    { key: 'leads_handled', header: 'Lidlar', align: 'right', sortable: true, render: r => r.leads_handled },
  ], [])

  const logColumns = useMemo(() => [
    { key: 'created_at', header: 'Vaqt', width: 130,
      render: r => <span title={fmtDateTime(r.created_at)}>{fmtDateTime(r.created_at)}</span> },
    { key: 'user_name', header: 'Operator', render: r => r.user_name },
    { key: 'entity_name', header: 'Kim', render: r => (
      <span className="ta-who">
        <strong>{r.entity_name}</strong>
        <span className="muted">{r.phone}</span>
      </span>
    ) },
    { key: 'task_type', header: 'Turi', render: r => r.task_type || '—' },
    { key: 'outcome', header: 'Natija', render: r => (
      <span className={`ta-outcome tone-${OUTCOME_TONE[r.outcome] || 'muted'}`}>
        {r.outcome_label}
      </span>
    ) },
    { key: 'note', header: 'Izoh', className: 'cell-wrap',
      render: r => r.note ? <span className="ta-note">{r.note}</span> : <span className="muted">—</span> },
    { key: 'next_action_at', header: 'Keyingi qadam', render: r => (
      r.next_action_at
        ? <span>{fmtDateTime(r.next_action_at)}</span>
        : <span className="muted">{r.next_action || '—'}</span>
    ) },
  ], [])

  if (err) {
    return (
      <div className="page">
        <div className="page-header"><h1><FontAwesomeIcon icon={faUsersGear} className="page-icon" /> Jamoa faoliyati</h1></div>
        <ErrorState title="Faoliyat ma'lumotini yuklab bo'lmadi" onRetry={load} />
      </div>
    )
  }

  const operators = data?.operators || []

  return (
    <div className="page team-hub">
      <PageIntro title="Jamoa faoliyati" description="Aloqalar, natijalar va jamoaning kundalik ritmi." actions={<div className="team-period">{RANGES.map(r => <button key={r.v} type="button" className={range === r.v ? 'is-active' : ''} onClick={() => pickRange(r.v)}>{r.label}</button>)}</div>} />
      {range === 'custom' && <div className="team-custom-period"><span>Hisobot davri</span><input className="field" type="date" value={from} aria-label="Boshlanish" onChange={e => setFrom(e.target.value)} /><span>—</span><input className="field" type="date" value={to} aria-label="Tugash" onChange={e => setTo(e.target.value)} /></div>}
      {loading ? <CardSkeleton count={4} /> : <div className="team-pulse-band">
        <div className="team-pulse-total"><span className="team-pulse-icon"><FontAwesomeIcon icon={faPhone} /></span><div><span>Jami qo‘ng‘iroqlar</span><strong>{data.total_calls}</strong></div><small>O‘rtacha {data.avg_calls_per_operator} / operator</small></div>
        <div><span><i className="pulse-dot blue" />Bog‘lanildi</span><strong>{data.connected}<small>{data.connect_rate}%</small></strong></div>
        <div><span><i className="pulse-dot rose" />Javobsiz</span><strong>{data.no_answer}</strong></div>
        <div><span><i className="pulse-dot violet" />Vazifalar bajarildi</span><strong>{data.completed_tasks}<small>{data.callbacks} qayta aloqa</small></strong></div>
      </div>}
      <div className="team-view-line"><ViewTabs value={activityView} onChange={setActivityView} items={[{ key: 'overview', label: 'Jamoa ko‘rinishi', count: operators.length }, { key: 'journal', label: 'Qo‘ng‘iroqlar jurnali', count: log?.total }]} />{activityView === 'overview' && <div className="segmented"><button onClick={() => setOperatorView('performance')} className={operatorView === 'performance' ? 'active' : ''}>Natijalar</button><button onClick={() => setOperatorView('table')} className={operatorView === 'table' ? 'active' : ''}>Batafsil jadval</button></div>}</div>
      {activityView === 'overview' && (loading ? <TableSkeleton rows={5} cols={6} /> : operatorView === 'table' ? <div className="team-full-table"><DataTable columns={opColumns} rows={operators} rowKey={r => r.id} onRowClick={openOperator} scroll /></div> : <OperatorRoster operators={operators} onOpen={openOperator} query={operatorQuery} setQuery={setOperatorQuery} sort={operatorSort} setSort={setOperatorSort} />)}
      {activityView === 'overview' && !loading && data?.insights?.length > 0 && <ConversionInsights insights={data.insights} onFocus={() => {}} />}

      {activityView === 'journal' && <section className="studio-section team-journal">
        <div className="studio-section-head"><div><h2>Qo‘ng‘iroqlar jurnali</h2><p>Natijalar, izohlar va keyingi qadamlar.</p></div><span>{log?.total || 0} ta yozuv</span></div>
        <div className="ta-filters">
          <div className="ta-search">
            <FontAwesomeIcon icon={faMagnifyingGlass} />
            <input className="field" value={q} onChange={e => setQ(e.target.value)}
              placeholder="Ism, telefon yoki izoh" aria-label="Jurnalda qidirish" />
          </div>
          <select className="field" value={fOperator} aria-label="Operator"
            onChange={e => { setFOperator(e.target.value); setLogPage(1) }}>
            <option value="">Barcha operatorlar</option>
            {operators.map(o => <option key={o.id} value={o.id}>{o.name}</option>)}
          </select>
          <select className="field" value={fType} aria-label="Vazifa turi"
            onChange={e => { setFType(e.target.value); setLogPage(1) }}>
            <option value="">Barcha turlar</option>
            <option value="CALLBACK">Qayta qo'ng'iroq</option>
            <option value="PAYMENT_REMINDER">To'lov eslatmasi</option>
            <option value="ABSENCE_FOLLOWUP">Davomat</option>
            <option value="LEAD_CALL">Yangi lid</option>
          </select>
          <select className="field" value={fOutcome} aria-label="Natija"
            onChange={e => { setFOutcome(e.target.value); setLogPage(1) }}>
            <option value="">Barcha natijalar</option>
            {Object.keys(OUTCOME_TONE).map(o => <option key={o} value={o}>{o}</option>)}
          </select>
          {(fOperator || fOutcome || fType || dq) && (
            <button className="button secondary sm"
              onClick={() => { setFOperator(''); setFOutcome(''); setFType(''); setQ('') }}>
              <FontAwesomeIcon icon={faXmark} /> Tozalash
            </button>
          )}
        </div>
        <DataTable
          columns={logColumns}
          rows={log?.items || []}
          loading={logLoading}
          rowKey={r => r.id}
          empty={{ title: "Qo'ng'iroq topilmadi",
                   description: 'Tanlangan filtrga mos yozuv yo\'q' }}
          meta={log ? { page: log.page, pages: log.pages, total: log.total } : null}
          onPageChange={setLogPage}
          scroll
        />
      </section>}

      <Drawer open={!!openOp} title={openOp?.name} onClose={() => setOpenOp(null)} width={560}>
        {openOp && <OperatorDetail op={openOp} detail={opDetail} />}
      </Drawer>
    </div>
  )
}

/** Bitta operatorning davr ichidagi to'liq faoliyati. */
function OperatorDetail({ op, detail }) {
  if (!detail) {
    return <div className="tp-list">{Array.from({ length: 6 }).map((_, i) =>
      <div key={i} className="tp-lead" />)}</div>
  }
  const s = detail.operator
  return (
    <div className="ta-detail operator-dossier"><header className="operator-dossier-head"><Initials name={op.name} /><div><span>Operator tafsilotlari</span><h2>{op.name}</h2><p>{TEAM_ROLE_LABEL[op.role] || op.role}</p></div></header>
      <div className="ta-detail-stats">
        <Stat n={s.calls} label="qo'ng'iroq" />
        <Stat n={s.connected} label="bog'landi" />
        <Stat n={s.no_answer} label="javobsiz" />
        <Stat n={`${s.connect_rate}%`} label="bog'lanish" />
        <Stat n={s.completed_tasks} label="bajarildi" />
        <Stat n={s.leads_handled} label="lid" />
      </div>

      <h5>Qo'ng'iroqlar ({detail.calls.length})</h5>
      {detail.calls.length === 0 ? (
        <p className="muted">Bu davrda qo'ng'iroq yozilmagan.</p>
      ) : (
        <ul className="ta-timeline">
          {detail.calls.map(c => (
            <li key={c.id}>
              <span className="ta-tl-time">{fmtTime(c.created_at)}</span>
              <div className="ta-tl-body">
                <div className="ta-tl-head">
                  <strong>{c.entity_name}</strong>
                  <span className={`ta-outcome tone-${OUTCOME_TONE[c.outcome] || 'muted'}`}>
                    {c.outcome_label}
                  </span>
                </div>
                {c.note && <div className="ta-tl-note">{c.note}</div>}
                <div className="ta-tl-meta">
                  {c.task_type && <span>{c.task_type}</span>}
                  {c.payment_promise && <span>va'da: {c.payment_promise}</span>}
                  {c.promised_at && <span>sana: {c.promised_at}</span>}
                  {c.next_action_at && (
                    <span><FontAwesomeIcon icon={faClock} /> {fmtDateTime(c.next_action_at)}</span>
                  )}
                  {c.edited_at && <span className="ta-edited">tahrirlangan</span>}
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}

      <h5>Bajarilgan vazifalar ({detail.tasks.length})</h5>
      {detail.tasks.length === 0 ? (
        <p className="muted">Bu davrda vazifa yopilmagan.</p>
      ) : (
        <ul className="wc-done">
          {detail.tasks.map(t => (
            <li key={t.source_key}>
              <span className="wc-done-title">{t.title}</span>
              <span className="muted">{t.task_label}</span>
              <span className="muted wc-done-when">{fmtRelative(t.completed_at)}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function Stat({ n, label }) {
  return <div className="wc-stat"><strong>{n}</strong><span>{label}</span></div>
}
