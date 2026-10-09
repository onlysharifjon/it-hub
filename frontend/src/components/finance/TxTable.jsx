import { useEffect, useState } from 'react'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faMagnifyingGlass, faXmark } from '@fortawesome/free-solid-svg-icons'
import { finance } from '../../api'
import DataTable from '../ui/DataTable'
import {
  DateRange, presetRange, METHOD_LABELS, StatusBadge, KindBadge, money, signedMoney, fmtDate, periodLabel,
  useDebounced, TxDrawer, CurrencyLines,
} from './shared'

/**
 * Operatsiyalar jadvali (server sahifalash + saralash + filtrlar).
 * `fixed` — doimiy filtr ({flow: 'income'} kabi), `extraFilters` — qo'shimcha select'lar.
 */
export default function TxTable({ fixed, currentUser, accounts = [], extraFilters = [], columns, empty, reloadKey, toolbarEnd }) {
  const [range, setRange] = useState(() => presetRange('month'))
  const [search, setSearch] = useState('')
  const [filters, setFilters] = useState({ status: '', method: '', account_id: '' })
  const [sort, setSort] = useState({ key: 'date', dir: 'desc' })
  const [page, setPage] = useState(1)
  const [data, setData] = useState({ items: [], meta: null })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [openId, setOpenId] = useState(null)
  const q = useDebounced(search)

  async function load() {
    setLoading(true); setError(null)
    try {
      setData(await finance.transactions({
        ...fixed, ...filters, ...range, search: q, sort: sort.key, dir: sort.dir, page, page_size: 25,
      }))
    } catch (e) { setError(e.message) } finally { setLoading(false) }
  }
  useEffect(() => { load() }, [range, q, filters, sort, page, reloadKey])
  useEffect(() => { setPage(1) }, [range, q, filters])

  const setF = patch => setFilters(f => ({ ...f, ...patch }))
  const hasFilters = search || filters.status || filters.method || filters.account_id || extraFilters.some(x => filters[x.key])

  const defaultCols = [
    { key: 'date', header: 'Sana', sortable: true, render: t => <><span>{fmtDate(t.op_date)}</span><span className="fin-sub">{t.number}</span></> },
    { key: 'kind', header: 'Turi', render: t => <KindBadge kind={t.kind} /> },
    ...columns,
    { key: 'method', header: "Usul / hisob", render: t => <><span>{METHOD_LABELS[t.method] || '—'}</span><span className="fin-sub">{t.account?.name || 'Belgilanmagan'}</span></> },
    { key: 'amount', header: 'Summa', align: 'right', sortable: true,
      render: t => <span className={`fin-amount ${t.signed_amount > 0 ? 'is-in' : t.signed_amount < 0 ? 'is-out' : ''}`}>
        {t.kind === 'transfer' ? money(t.amount, t.currency) : signedMoney(t.signed_amount, t.currency)}</span> },
    { key: 'status', header: 'Holat', render: t => <StatusBadge status={t.status} /> },
  ]

  return (
    <>
      <div className="fin-toolbar" role="search" aria-label="Filtrlar">
        <div className="search-wrap">
          <FontAwesomeIcon icon={faMagnifyingGlass} />
          <input className="search-input" value={search} onChange={e => setSearch(e.target.value)} placeholder="Raqam, mijoz, oluvchi yoki izoh" aria-label="Qidiruv" />
        </div>
        <DateRange value={range} onChange={setRange} />
        <select className="field-sm" value={filters.status} onChange={e => setF({ status: e.target.value })} aria-label="Holat">
          <option value="">Barcha holatlar</option>
          <option value="draft">Qoralama</option>
          <option value="confirmed">Tasdiqlangan</option>
          <option value="cancelled">Bekor qilingan</option>
        </select>
        <select className="field-sm" value={filters.method} onChange={e => setF({ method: e.target.value })} aria-label="To'lov usuli">
          <option value="">Barcha usullar</option>
          {Object.entries(METHOD_LABELS).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
        </select>
        <select className="field-sm" value={filters.account_id} onChange={e => setF({ account_id: e.target.value })} aria-label="Kassa yoki hisob">
          <option value="">Barcha hisoblar</option>
          {accounts.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}
        </select>
        {extraFilters.map(x => (
          <select key={x.key} className="field-sm" value={filters[x.key] || ''} onChange={e => setF({ [x.key]: e.target.value })} aria-label={x.label}>
            <option value="">{x.all}</option>
            {x.options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        ))}
        {hasFilters && (
          <button className="button small secondary" onClick={() => { setSearch(''); setFilters({ status: '', method: '', account_id: '' }) }}>
            <FontAwesomeIcon icon={faXmark} /> Tozalash
          </button>
        )}
        {toolbarEnd && <div className="fin-toolbar-end">{toolbarEnd}</div>}
      </div>

      <section className="studio-section">
        <div className="studio-section-head">
          <div><h2>Operatsiyalar</h2><p>Tasdiqlangan jami: <CurrencyLines values={data.confirmed_net_by_currency} signed empty="0" /></p></div>
          <span>{data.meta?.total ?? 0} yozuv</span>
        </div>
        <DataTable
          columns={defaultCols}
          rows={data.items}
          loading={loading && !data.items.length}
          error={error}
          onRetry={load}
          meta={data.meta}
          onPageChange={setPage}
          sort={sort}
          onSortChange={setSort}
          onRowClick={t => setOpenId(t.id)}
          empty={hasFilters ? { title: "Filtrlarga mos operatsiya topilmadi", description: "Filtrlarni o'zgartiring yoki tozalang." } : empty}
          densityKey="fin-tx"
        />
      </section>

      <TxDrawer txId={openId} currentUser={currentUser} onClose={() => setOpenId(null)} onChanged={load} />
    </>
  )
}

export const studentCols = [
  { key: 'student', header: 'Mijoz / shartnoma', render: t => <><strong>{t.student?.name || '—'}</strong><span className="fin-sub">{t.group?.name || ''}{t.period_month ? ` · ${periodLabel(t.period_month, t.period_year)}` : ''}</span></> },
]
