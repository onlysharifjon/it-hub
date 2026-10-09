import { useEffect, useState } from 'react'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faMagnifyingGlass, faFileInvoiceDollar, faPlus } from '@fortawesome/free-solid-svg-icons'
import { finance } from '../../api'
import { PageIntro, SummaryRow, ViewTabs } from '../ui/Workspace'
import DataTable from '../ui/DataTable'
import Badge from '../ui/Badge'
import { Drawer } from '../ui/Modal'
import { FormSkeleton, ErrorState } from '../ui/States'
import { IncomeForm } from './FinIncome'
import { money, fmt, fmtDate, periodLabel, useDebounced, useRefData, can, NoAccess, StatusBadge, KindBadge, signedMoney, TxDrawer } from './shared'

const SCHED = {
  paid: ['success', "To'langan"], partial: ['warning', 'Qisman'], due: ['info', 'Muddati kelmagan'],
  overdue: ['danger', "Muddati o'tgan"], upcoming: ['neutral', 'Kelgusi'], free: ['neutral', 'Bepul'],
}

function StudentDrawer({ studentId, onClose, currentUser, onPaid }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [pay, setPay] = useState(null)
  const [txId, setTxId] = useState(null)
  async function load() {
    setError(null)
    try { setData(await finance.student(studentId)) } catch (e) { setError(e.message) }
  }
  useEffect(() => { if (studentId) { setData(null); load() } }, [studentId])
  const t = data?.totals
  return (
    <Drawer open={!!studentId} onClose={onClose} width={720} title={data?.student?.name || 'Mijoz'}
      footer={can(currentUser, 'finance.income') && data && (
        <button className="button" onClick={() => setPay({ id: data.student.id, name: data.student.name, phone: data.student.phone,
          contracts: data.contracts.map(c => ({ ...c, active: !c.left_at && c.group_active })) })}>
          <FontAwesomeIcon icon={faPlus} /> To'lov qabul qilish
        </button>)}>
      {error && <ErrorState message={error} onRetry={load} />}
      {!data && !error && <FormSkeleton fields={6} />}
      {data && (
        <div className="fin-drawer">
          <SummaryRow items={[
            { label: 'Shartnoma summasi', value: fmt(t.contract_total), unit: "so'm" },
            { label: 'Chegirmalar', value: fmt(t.discounts), unit: "so'm", sub: "ta'til + Special" },
            { label: "To'langan", value: fmt(t.paid_total), unit: "so'm", tone: 'success' },
            { label: 'Qolgan qarz', value: fmt(t.debt), unit: "so'm", tone: Number(t.debt) > 0 ? 'danger' : undefined,
              sub: Number(t.overdue_debt) > 0 ? `muddati o'tgan: ${fmt(t.overdue_debt)} · ${t.overdue_days} kun` : 'muddati o‘tgan yo‘q' },
            ...(Number(t.advance) > 0 ? [{ label: 'Avans (ortiqcha to‘lov)', value: fmt(t.advance), unit: "so'm", tone: 'success' }] : []),
          ]} />
          <section className="fin-drawer-section">
            <h3>Shartnomalar (guruhlar)</h3>
            <ul className="fin-list">
              {data.contracts.map(c => (
                <li key={`${c.group_id}-${c.joined_at}`}><div><strong>{c.group_name}</strong>
                  <small>{c.tariff ? `${c.tariff} · ` : ''}{fmtDate(c.joined_at)} — {c.left_at ? fmtDate(c.left_at) : 'hozirgacha'}</small></div>
                  <span className="amount">{money(c.monthly_price)}/oy</span></li>
              ))}
            </ul>
          </section>
          {data.discounts.length > 0 && (
            <section className="fin-drawer-section">
              <h3>Tasdiqlangan chegirmalar</h3>
              <ul className="fin-list">{data.discounts.map(d => (
                <li key={d.id}><div><strong>{{ free_month: 'Bepul oy', monthly: 'Har oy', one_time: 'Bir martalik' }[d.kind] || d.kind}</strong>
                  <small>{d.month ? periodLabel(d.month, d.year) : 'butun kurs'}{d.reason ? ` · ${d.reason}` : ''}</small></div>
                  <span className="amount">{d.kind === 'free_month' ? '100%' : money(d.amount)}</span></li>))}</ul>
            </section>
          )}
          <section className="fin-drawer-section">
            <h3>To'lov jadvali (bosqichlar)</h3>
            <DataTable
              rows={data.installments}
              rowKey={(r) => `${r.group_id}-${r.year}-${r.month}`}
              columns={[
                { key: 'period', header: 'Davr', render: r => <><strong>{periodLabel(r.month, r.year)}</strong><span className="fin-sub">{r.group_name}</span></> },
                { key: 'due', header: 'Muddat', render: r => <>{fmtDate(r.due_date)}{r.overdue_days > 0 && <span className="fin-sub tone-danger">{r.overdue_days} kun kechikdi</span>}</> },
                { key: 'net', header: 'Hisoblangan', align: 'right', render: r => <>{money(r.net)}{Number(r.discount) + Number(r.vacation) > 0 && <span className="fin-sub">chegirma: {fmt(Number(r.discount) + Number(r.vacation))}</span>}</> },
                { key: 'paid', header: "To'langan", align: 'right', render: r => money(r.paid) },
                { key: 'remaining', header: 'Qoldiq', align: 'right', render: r => <strong className={Number(r.remaining) > 0 ? 'tone-danger' : ''}>{money(r.remaining)}</strong> },
                { key: 'status', header: 'Holat', render: r => <Badge size="sm" variant={SCHED[r.status]?.[0]}>{SCHED[r.status]?.[1] || r.status}</Badge> },
              ]}
              empty={{ title: "To'lov bosqichlari yo'q", description: 'Mijoz guruhga biriktirilmagan yoki guruh hali boshlanmagan.' }}
            />
            <p className="muted-sm">To'lovlar bosqichlarga muddat tartibida taqsimlanadi (CRM qoidasi: bir oyda ortiqcha to'langan summa keyingi qarzni yopadi).</p>
          </section>
          {can(currentUser, 'finance.clients') && (
            <section className="fin-drawer-section">
              <h3>To'lov tarixi</h3>
              {data.transactions.length === 0 ? <p className="muted-sm">Operatsiya yo'q</p> : (
                <ul className="fin-list">{data.transactions.map(x => (
                  <li key={x.id} role="button" tabIndex={0} style={{ cursor: 'pointer' }} onClick={() => setTxId(x.id)} onKeyDown={e => e.key === 'Enter' && setTxId(x.id)}>
                    <div><strong><KindBadge kind={x.kind} /> {x.number}</strong><small>{fmtDate(x.op_date)} · {x.group?.name} · {periodLabel(x.period_month, x.period_year)}</small></div>
                    <div style={{ textAlign: 'right', display: 'grid', gap: 4, justifyItems: 'end' }}>
                      <span className="amount">{signedMoney(x.signed_amount, x.currency)}</span><StatusBadge status={x.status} /></div>
                  </li>))}</ul>
              )}
            </section>
          )}
        </div>
      )}
      <IncomeForm open={!!pay} onClose={() => setPay(null)} student={pay} currentUser={currentUser} onSaved={() => { load(); onPaid?.() }} />
      <TxDrawer txId={txId} currentUser={currentUser} onClose={() => setTxId(null)} onChanged={() => { load(); onPaid?.() }} />
    </Drawer>
  )
}

export default function FinDebts({ currentUser }) {
  const [{ groups }] = useRefData(['groups'])
  const [status, setStatus] = useState('debtor')
  const [search, setSearch] = useState('')
  const [groupId, setGroupId] = useState('')
  const [sort, setSort] = useState({ key: 'debt', dir: 'desc' })
  const [page, setPage] = useState(1)
  const [data, setData] = useState({ items: [], meta: null, totals: {} })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [openId, setOpenId] = useState(null)
  const q = useDebounced(search)

  async function load() {
    setLoading(true); setError(null)
    try { setData(await finance.debts({ status, search: q, group_id: groupId, sort: sort.key, dir: sort.dir, page, page_size: 25 })) }
    catch (e) { setError(e.message) } finally { setLoading(false) }
  }
  useEffect(() => { load() }, [status, q, groupId, sort, page])
  useEffect(() => { setPage(1) }, [status, q, groupId])
  if (!can(currentUser, 'finance.debts')) return <div className="page fin-page"><NoAccess /></div>
  const T = data.totals || {}

  return (
    <div className="page fin-page">
      <PageIntro eyebrow="Moliya" title="Qarzdorlik" description="Shartnoma, chegirma, to'lov va qarz — mavjud CRM qoidalari (tarif, ta'til, Special chegirma) asosida." />
      <SummaryRow items={[
        { label: 'Umumiy qarz', value: fmt(T.debt), unit: "so'm", tone: 'danger' },
        { label: "Muddati o'tgan", value: fmt(T.overdue_debt), unit: "so'm", tone: 'danger' },
        { label: 'Muddati kelmagan', value: fmt(T.not_due_debt), unit: "so'm" },
        { label: 'Avanslar', value: fmt(T.advance), unit: "so'm", tone: 'success' },
      ]} />
      <div className="fin-toolbar" role="search">
        <ViewTabs value={status} onChange={setStatus} label="Holat" items={[
          { key: 'debtor', label: 'Qarzdorlar' }, { key: 'overdue', label: "Muddati o'tgan" },
          { key: 'advance', label: 'Avansdagilar' }, { key: 'all', label: 'Hammasi' }]} />
        <div className="search-wrap">
          <FontAwesomeIcon icon={faMagnifyingGlass} />
          <input className="search-input" value={search} onChange={e => setSearch(e.target.value)} placeholder="Ism yoki telefon" aria-label="Qidiruv" />
        </div>
        <select className="field-sm" value={groupId} onChange={e => setGroupId(e.target.value)} aria-label="Guruh">
          <option value="">Barcha guruhlar</option>
          {groups.map(g => <option key={g.id} value={g.id}>{g.name}</option>)}
        </select>
      </div>
      <section className="studio-section">
        <div className="studio-section-head"><div><h2>Mijozlar</h2><p>Qatorni bosing — to'lov jadvali va tarixi ochiladi.</p></div><span>{data.meta?.total ?? 0} ta</span></div>
        <DataTable
          rows={data.items}
          rowKey={r => r.student_id}
          loading={loading && !data.items.length}
          error={error} onRetry={load}
          meta={data.meta} onPageChange={setPage}
          sort={sort} onSortChange={setSort}
          onRowClick={r => setOpenId(r.student_id)}
          columns={[
            { key: 'student', header: 'Mijoz', sortable: true, render: r => <><strong>{r.student}</strong><span className="fin-sub">{r.phone} · {r.groups}{r.is_archived ? ' · arxivda' : ''}</span></> },
            { key: 'contract_total', header: 'Shartnoma', align: 'right', render: r => <>{money(r.contract_total)}{Number(r.discounts) > 0 && <span className="fin-sub">chegirma: {fmt(r.discounts)}</span>}</> },
            { key: 'paid_total', header: "To'langan", align: 'right', sortable: true, render: r => money(r.paid_total) },
            { key: 'debt', header: 'Qarz', align: 'right', sortable: true, render: r => <strong className={Number(r.debt) > 0 ? 'tone-danger' : ''}>{money(r.debt)}</strong> },
            { key: 'overdue_debt', header: "Muddati o'tgan", align: 'right', sortable: true, render: r => Number(r.overdue_debt) > 0 ? <span className="tone-danger">{money(r.overdue_debt)}</span> : <span className="muted-sm">—</span> },
            { key: 'overdue_days', header: 'Kechikish', align: 'right', sortable: true, render: r => r.overdue_days > 0 ? `${r.overdue_days} kun` : '—' },
            { key: 'next_due_date', header: 'Keyingi muddat', sortable: true, render: r => r.next_due_date ? <>{fmtDate(r.next_due_date)}<span className="fin-sub">{money(r.next_due_amount)}</span></> : '—' },
            { key: 'advance', header: 'Avans', align: 'right', sortable: true, render: r => Number(r.advance) > 0 ? <span className="tone-success">{money(r.advance)}</span> : '—' },
          ]}
          empty={{ icon: faFileInvoiceDollar, title: status === 'debtor' ? "Qarzdor mijoz yo'q" : "Mos mijoz topilmadi", description: 'Filtrlarni o‘zgartirib ko‘ring.' }}
          densityKey="fin-debts"
        />
      </section>
      <StudentDrawer studentId={openId} onClose={() => setOpenId(null)} currentUser={currentUser} onPaid={load} />
    </div>
  )
}
