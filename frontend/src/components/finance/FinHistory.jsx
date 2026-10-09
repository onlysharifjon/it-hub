import { useEffect, useState } from 'react'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faMagnifyingGlass, faClockRotateLeft, faLock } from '@fortawesome/free-solid-svg-icons'
import { finance } from '../../api'
import { PageIntro } from '../ui/Workspace'
import DataTable from '../ui/DataTable'
import Badge from '../ui/Badge'
import { Drawer } from '../ui/Modal'
import { DateRange, presetRange, fmtDateTime, useDebounced, useRefData, can, NoAccess, JsonDiff, TxDrawer } from './shared'

const ENTITIES = {
  finance_tx: 'Operatsiya', finance_account: 'Kassa/hisob', finance_category: 'Kategoriya', finance_setting: 'Sozlama',
  finance_export: 'Eksport', user_permissions: 'Huquqlar', payment: "To'lov (CRM)", expense: 'Xarajat (CRM)',
}
const ACTIONS = { create: 'Yaratildi', confirm: 'Tasdiqlandi', cancel: 'Bekor qilindi', refund: 'Qaytarim', adjust: 'Tuzatish',
  transfer: "O'tkazma", update: "O'zgartirildi", export: 'Eksport', delete: "O'chirildi" }
const ACTION_TONE = { confirm: 'success', cancel: 'neutral', refund: 'warning', adjust: 'info', delete: 'danger', update: 'info' }

export default function FinHistory({ currentUser }) {
  const [{ staff }] = useRefData(['staff'])
  const [range, setRange] = useState(() => presetRange('month'))
  const [f, setF] = useState({ entity_type: '', action: '', actor_id: '' })
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [data, setData] = useState({ items: [], meta: null })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [open, setOpen] = useState(null)
  const [txId, setTxId] = useState(null)
  const q = useDebounced(search)

  async function load() {
    setLoading(true); setError(null)
    try { setData(await finance.audit({ ...f, ...range, search: q, page, page_size: 25 })) }
    catch (e) { setError(e.message) } finally { setLoading(false) }
  }
  useEffect(() => { load() }, [f, range, q, page])
  useEffect(() => { setPage(1) }, [f, range, q])
  if (!can(currentUser, 'finance.audit')) return <div className="page fin-page"><NoAccess /></div>

  return (
    <div className="page fin-page">
      <PageIntro eyebrow="Moliya" title="Operatsiyalar tarixi"
        description={<><FontAwesomeIcon icon={faLock} /> Kim, qachon, nima qilgani, oldingi va yangi qiymatlar hamda sabab. Tarixni hech kim o'zgartira olmaydi.</>} />
      <div className="fin-toolbar" role="search">
        <div className="search-wrap"><FontAwesomeIcon icon={faMagnifyingGlass} />
          <input className="search-input" value={search} onChange={e => setSearch(e.target.value)} placeholder="Raqam, summa yoki sabab" aria-label="Qidiruv" /></div>
        <DateRange value={range} onChange={setRange} />
        <select className="field-sm" value={f.entity_type} onChange={e => setF({ ...f, entity_type: e.target.value })} aria-label="Obyekt">
          <option value="">Barcha obyektlar</option>{Object.entries(ENTITIES).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select>
        <select className="field-sm" value={f.action} onChange={e => setF({ ...f, action: e.target.value })} aria-label="Amal">
          <option value="">Barcha amallar</option>{Object.entries(ACTIONS).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select>
        <select className="field-sm" value={f.actor_id} onChange={e => setF({ ...f, actor_id: e.target.value })} aria-label="Xodim">
          <option value="">Barcha xodimlar</option>{staff.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select>
      </div>
      <section className="studio-section">
        <div className="studio-section-head"><div><h2>Audit jurnali</h2><p>Qatorni bosing — o'zgarishlar tafsiloti.</p></div><span>{data.meta?.total ?? 0} yozuv</span></div>
        <DataTable
          rows={data.items} loading={loading && !data.items.length} error={error} onRetry={load}
          meta={data.meta} onPageChange={setPage} onRowClick={setOpen}
          columns={[
            { key: 'changed_at', header: 'Vaqt', render: l => fmtDateTime(l.changed_at) },
            { key: 'changed_by', header: 'Xodim', render: l => <strong>{l.changed_by || '—'}</strong> },
            { key: 'action', header: 'Amal', render: l => <Badge size="sm" variant={ACTION_TONE[l.action] || 'neutral'}>{l.action_label}</Badge> },
            { key: 'entity', header: 'Obyekt', render: l => <>{ENTITIES[l.entity_type] || l.entity_type}<span className="fin-sub">{l.new_value?.number || l.old_value?.origin || (l.entity_id ? `#${l.entity_id}` : '')}</span></> },
            { key: 'reason', header: 'Sabab', render: l => <span className="muted-sm">{l.reason || '—'}</span> },
          ]}
          empty={{ icon: faClockRotateLeft, title: "Bu davrda yozuv yo'q" }}
          densityKey="fin-audit"
        />
      </section>
      <Drawer open={!!open} onClose={() => setOpen(null)} title={open ? `${open.action_label} · ${ENTITIES[open.entity_type] || open.entity_type}` : ''} width={560}
        footer={open?.entity_type === 'finance_tx' && open.entity_id && <button className="button secondary" onClick={() => setTxId(open.entity_id)}>Operatsiyani ochish</button>}>
        {open && (
          <div className="fin-drawer">
            <div className="fin-kv"><span>Vaqt</span><div>{fmtDateTime(open.changed_at)}</div></div>
            <div className="fin-kv"><span>Xodim</span><div>{open.changed_by}</div></div>
            {open.reason && <div className="fin-kv"><span>Sabab</span><div>{open.reason}</div></div>}
            <section className="fin-drawer-section"><h3>O'zgarishlar (oldingi → yangi)</h3>
              {(typeof open.old_value === 'object' || typeof open.new_value === 'object')
                ? <JsonDiff oldV={Array.isArray(open.old_value) ? { qiymat: open.old_value } : open.old_value} newV={Array.isArray(open.new_value) ? { qiymat: open.new_value } : open.new_value} />
                : <p className="muted-sm">{String(open.old_value ?? '—')} → {String(open.new_value ?? '—')}</p>}
            </section>
          </div>
        )}
      </Drawer>
      <TxDrawer txId={txId} currentUser={currentUser} onClose={() => setTxId(null)} />
    </div>
  )
}
