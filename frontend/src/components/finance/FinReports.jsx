import { useEffect, useState } from 'react'
import { toast } from 'react-hot-toast'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faFileExcel, faFileCsv, faMagnifyingGlass } from '@fortawesome/free-solid-svg-icons'
import { finance } from '../../api'
import { PageIntro, ViewTabs } from '../ui/Workspace'
import DataTable from '../ui/DataTable'
import { EmptyState } from '../ui/States'
import { DateRange, presetRange, money, fmt, fmtDate, METHOD_LABELS, useRefData, can, NoAccess, StudentPicker, useDebounced } from './shared'

const REPORTS = [
  { key: 'income', label: 'Kirimlar', filters: ['date', 'method', 'account', 'group', 'responsible'] },
  { key: 'expenses', label: 'Xarajatlar', filters: ['date', 'category', 'method', 'account', 'responsible'] },
  { key: 'cashflow', label: 'Pul oqimi', filters: ['date', 'method', 'account', 'granularity'] },
  { key: 'accounts', label: 'Kassa va hisoblar', filters: ['date', 'account'] },
  { key: 'debts', label: 'Qarzdorlik', filters: ['search', 'group', 'status'], perm: 'finance.debts' },
  { key: 'overdue', label: "Muddati o'tgan", filters: ['search', 'group'], perm: 'finance.debts' },
  { key: 'history', label: "To'lov tarixi", filters: ['date', 'student', 'group'] },
]
const TOTAL_LABELS = {
  income: 'Tushum', refunds: 'Qaytarimlar', net: 'Sof pul oqimi', expense: 'Xarajatlar', opening: 'Boshida',
  inflow: 'Kirim', outflow: 'Chiqim', closing: 'Oxirida', contract_total: 'Shartnoma', discounts: 'Chegirmalar',
  paid_total: "To'langan", debt: 'Qarz', overdue_debt: "Muddati o'tgan", not_due_debt: 'Muddati kelmagan',
  advance: 'Avans', remaining: 'Qoldiq qarz',
}

function cell(col, row) {
  const v = row[col.key]
  if (col.type === 'money') return <span className="fin-amount">{v == null ? '—' : money(v, row.currency || 'UZS')}</span>
  if (col.type === 'date') return fmtDate(v)
  if (col.type === 'int') return v ?? '—'
  return v ?? '—'
}

export default function FinReports({ currentUser }) {
  const [{ accounts, categories, staff, groups }] = useRefData(['accounts', 'categories', 'staff', 'groups'])
  const visible = REPORTS.filter(r => !r.perm || can(currentUser, r.perm))
  const [kind, setKind] = useState('income')
  const [range, setRange] = useState(() => presetRange('month'))
  const [f, setF] = useState({ method: '', account_id: '', category_id: '', responsible_id: '', group_id: '', status: 'debtor', granularity: '' })
  const [student, setStudent] = useState(null)
  const [search, setSearch] = useState('')
  const [rep, setRep] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [exporting, setExporting] = useState(null)
  const q = useDebounced(search)
  const def = REPORTS.find(r => r.key === kind)
  const has = k => def.filters.includes(k)

  function params() {
    const p = {}
    if (has('date')) Object.assign(p, range)
    if (has('method')) p.method = f.method
    if (has('account')) p.account_id = f.account_id
    if (has('category')) p.category_id = f.category_id
    if (has('responsible')) p.responsible_id = f.responsible_id
    if (has('group')) p.group_id = f.group_id
    if (has('status')) p.status = f.status
    if (has('granularity')) p.granularity = f.granularity
    if (has('search')) p.search = q
    if (has('student')) p.student_id = student?.id
    return p
  }
  const needsTarget = kind === 'history' && !student && !f.group_id

  async function load() {
    if (needsTarget) { setRep(null); return }
    setLoading(true); setError(null)
    try { setRep(await finance.report(kind, params())) } catch (e) { setError(e.message); setRep(null) } finally { setLoading(false) }
  }
  useEffect(() => { load() }, [kind, range, f, q, student])

  async function doExport(format) {
    setExporting(format)
    try { await finance.exportReport(kind, params(), format); toast.success('Fayl yuklab olindi') }
    catch (e) { toast.error(e.message) } finally { setExporting(null) }
  }

  if (!can(currentUser, 'finance.reports')) return <div className="page fin-page"><NoAccess /></div>
  const canExport = can(currentUser, 'finance.export')
  const maxCat = Math.max(1, ...(rep?.breakdown || []).map(b => Number(b.by_currency.UZS?.amount || 0)))

  return (
    <div className="page fin-page">
      <PageIntro eyebrow="Moliya" title="Hisobotlar" description="Filtrlangan natijani Excel yoki CSV formatida yuklab olish mumkin. Faqat tasdiqlangan operatsiyalar hisoblanadi."
        actions={canExport && <div className="header-actions">
          <button className="button secondary" disabled={!!exporting || needsTarget} onClick={() => doExport('csv')}><FontAwesomeIcon icon={faFileCsv} /> {exporting === 'csv' ? '…' : 'CSV'}</button>
          <button className="button" disabled={!!exporting || needsTarget} onClick={() => doExport('xlsx')}><FontAwesomeIcon icon={faFileExcel} /> {exporting === 'xlsx' ? 'Tayyorlanmoqda…' : 'Excel'}</button>
        </div>} />

      <ViewTabs items={visible.map(r => ({ key: r.key, label: r.label }))} value={kind} onChange={k => { setKind(k); setRep(null) }} label="Hisobot turi" />

      <div className="fin-toolbar" role="search" aria-label="Hisobot filtrlari">
        {has('date') && <DateRange value={range} onChange={setRange} />}
        {has('search') && <div className="search-wrap"><FontAwesomeIcon icon={faMagnifyingGlass} />
          <input className="search-input" value={search} onChange={e => setSearch(e.target.value)} placeholder="Ism yoki telefon" aria-label="Qidiruv" /></div>}
        {has('student') && <div style={{ flex: '1 1 260px', minWidth: 0 }}><StudentPicker label="Mijoz" value={student} onChange={setStudent} /></div>}
        {has('method') && <select className="field-sm" value={f.method} onChange={e => setF({ ...f, method: e.target.value })} aria-label="To'lov usuli">
          <option value="">Barcha usullar</option>{Object.entries(METHOD_LABELS).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select>}
        {has('account') && <select className="field-sm" value={f.account_id} onChange={e => setF({ ...f, account_id: e.target.value })} aria-label="Hisob">
          <option value="">Barcha hisoblar</option>{accounts.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}</select>}
        {has('category') && <select className="field-sm" value={f.category_id} onChange={e => setF({ ...f, category_id: e.target.value })} aria-label="Kategoriya">
          <option value="">Barcha kategoriyalar</option>{categories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select>}
        {has('responsible') && <select className="field-sm" value={f.responsible_id} onChange={e => setF({ ...f, responsible_id: e.target.value })} aria-label="Mas'ul">
          <option value="">Barcha mas'ullar</option>{staff.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select>}
        {has('group') && <select className="field-sm" value={f.group_id} onChange={e => setF({ ...f, group_id: e.target.value })} aria-label="Guruh (shartnoma)">
          <option value="">Barcha guruhlar</option>{groups.map(g => <option key={g.id} value={g.id}>{g.name}</option>)}</select>}
        {has('status') && <select className="field-sm" value={f.status} onChange={e => setF({ ...f, status: e.target.value })} aria-label="Holat">
          <option value="debtor">Qarzdorlar</option><option value="overdue">Muddati o'tgan</option><option value="advance">Avansdagilar</option><option value="all">Hammasi</option></select>}
        {has('granularity') && <select className="field-sm" value={f.granularity} onChange={e => setF({ ...f, granularity: e.target.value })} aria-label="Guruhlash">
          <option value="">Avtomatik</option><option value="day">Kunlik</option><option value="month">Oylik</option></select>}
      </div>

      {needsTarget ? (
        <EmptyState title="Mijoz yoki guruhni tanlang" description="To'lov tarixi hisobotini ko'rish uchun mijozni qidiring yoki guruh (shartnoma)ni tanlang." />
      ) : (
        <section className="studio-section">
          <div className="studio-section-head"><div><h2>{rep?.title || def.label}</h2>
            <p>{has('date') ? `${fmtDate(range.date_from)} — ${fmtDate(range.date_to)}` : 'Bugungi holat bo‘yicha'}{rep?.truncated ? ` · ekranda dastlabki ${rep.rows.length} ta (eksportda hammasi)` : ''}</p></div>
            <span>{rep?.row_count ?? 0} qator</span></div>
          <DataTable
            columns={(rep?.columns || []).map(c => ({ key: c.key, header: c.label, align: ['money', 'int'].includes(c.type) ? 'right' : undefined,
              sortable: true, sortValue: r => (c.type === 'money' || c.type === 'int' ? Number(r[c.key] || 0) : r[c.key]), render: r => cell(c, r) }))}
            rows={rep?.rows || []}
            loading={loading} error={error} onRetry={load} clientPageSize={50}
            rowKey={(r, i) => i}
            empty={{ title: "Tanlangan filtrlar bo'yicha ma'lumot yo'q" }}
            densityKey="fin-report"
          />
          {rep && Object.keys(rep.totals || {}).length > 0 && (
            <div className="fin-totals">
              {Object.entries(rep.totals).map(([cur, t]) => Object.entries(t).map(([k, v]) => (
                <div key={`${cur}-${k}`}><span>{TOTAL_LABELS[k] || k}{Object.keys(rep.totals).length > 1 ? ` (${cur})` : ''}:</span><strong>{money(v, cur)}</strong></div>
              )))}
            </div>
          )}
        </section>
      )}

      {kind === 'expenses' && rep?.breakdown?.length > 0 && (
        <section className="fin-card">
          <div className="fin-card-head"><div><h2>Kategoriyalar bo'yicha taqsimot</h2><p>So'mdagi xarajatlar</p></div></div>
          <div className="fin-bars">
            {rep.breakdown.map(b => {
              const v = Number(b.by_currency.UZS?.amount || 0)
              const others = Object.entries(b.by_currency).filter(([c]) => c !== 'UZS').map(([c, x]) => money(x.amount, c)).join(' · ')
              return (
                <div key={b.category} className="fin-bar">
                  <span title={b.category}>{b.category}</span>
                  <div className="fin-bar-track" aria-hidden="true"><div className="fin-bar-fill" style={{ width: `${(v / maxCat) * 100}%` }} /></div>
                  <strong>{fmt(v)} so'm{others ? ` · ${others}` : ''}</strong>
                </div>
              )
            })}
          </div>
        </section>
      )}
    </div>
  )
}
