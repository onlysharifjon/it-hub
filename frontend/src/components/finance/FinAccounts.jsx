import { useEffect, useState } from 'react'
import { toast } from 'react-hot-toast'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faPlus, faRightLeft, faPen, faGear, faCircleCheck, faTriangleExclamation } from '@fortawesome/free-solid-svg-icons'
import { finance, tashkentToday } from '../../api'
import { PageIntro } from '../ui/Workspace'
import Badge from '../ui/Badge'
import DataTable from '../ui/DataTable'
import { CardSkeleton, ErrorState } from '../ui/States'
import {
  Modal, Input, Select, Textarea, DateRange, presetRange, money, fmtDate, can, newKey, ACCOUNT_KINDS, CURRENCIES, signedMoney,
} from './shared'

function AccountModal({ open, account, onClose, onSaved }) {
  const [f, setF] = useState({})
  const [busy, setBusy] = useState(false)
  useEffect(() => {
    if (open) setF(account ? { name: account.name, note: account.note || '', is_active: account.is_active, opening_balance: String(account.opening_balance), reason: '' }
      : { name: '', kind: 'cash', currency: 'UZS', opening_balance: '0', note: '' })
  }, [open])
  async function save() {
    if ((f.name || '').trim().length < 2) { toast.error('Hisob nomini kiriting'); return }
    const openingChanged = account && Number(f.opening_balance) !== Number(account.opening_balance)
    if (openingChanged && (f.reason || '').trim().length < 3) { toast.error("Boshlang'ich qoldiqni o'zgartirish sababini yozing"); return }
    setBusy(true)
    try {
      if (account) {
        await finance.updateAccount(account.id, { name: f.name, note: f.note, is_active: f.is_active,
          ...(openingChanged ? { opening_balance: f.opening_balance, reason: f.reason } : {}) })
      } else {
        await finance.createAccount({ name: f.name, kind: f.kind, currency: f.currency, opening_balance: f.opening_balance || 0, note: f.note })
      }
      toast.success('Saqlandi'); onSaved(); onClose()
    } catch (e) { toast.error(e.message) } finally { setBusy(false) }
  }
  return (
    <Modal open={open} onClose={onClose} title={account ? 'Hisobni tahrirlash' : "Yangi kassa / hisob"} size="md"
      footer={<><button className="button secondary" onClick={onClose}>Bekor</button><button className="button" disabled={busy} onClick={save}>Saqlash</button></>}>
      <div className="fin-form">
        <div className="is-wide"><Input label="Nomi" required value={f.name || ''} maxLength={120} onChange={e => setF({ ...f, name: e.target.value })} placeholder="Masalan: Kapitalbank hisob raqami" /></div>
        {!account && <>
          <Select label="Turi" value={f.kind} onChange={e => setF({ ...f, kind: e.target.value })}>
            {Object.entries(ACCOUNT_KINDS).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
          </Select>
          <Select label="Valyuta" value={f.currency} onChange={e => setF({ ...f, currency: e.target.value })}>
            {CURRENCIES.map(c => <option key={c} value={c}>{c}</option>)}
          </Select>
        </>}
        <Input label="Boshlang'ich qoldiq" type="number" step="0.01" value={f.opening_balance ?? ''} onChange={e => setF({ ...f, opening_balance: e.target.value })}
          hint="Modul ishga tushgan kundagi haqiqiy qoldiq (kassadagi naqd / bank ko'chirmasi)" />
        {account && <Select label="Holat" value={f.is_active ? '1' : '0'} onChange={e => setF({ ...f, is_active: e.target.value === '1' })}>
          <option value="1">Faol</option><option value="0">Nofaol</option></Select>}
        {account && Number(f.opening_balance) !== Number(account.opening_balance) && (
          <div className="is-wide"><Textarea label="O'zgartirish sababi" required rows={2} value={f.reason || ''} onChange={e => setF({ ...f, reason: e.target.value })} /></div>
        )}
        <div className="is-wide"><Textarea label="Izoh" rows={2} value={f.note || ''} onChange={e => setF({ ...f, note: e.target.value })} /></div>
      </div>
    </Modal>
  )
}

function TransferModal({ open, accounts, onClose, onSaved }) {
  const [f, setF] = useState({})
  const [errors, setErrors] = useState({})
  const [busy, setBusy] = useState(false)
  const [key, setKey] = useState(newKey)
  const active = accounts.filter(a => a.is_active)
  useEffect(() => { if (open) { setF({ account_id: '', to_account_id: '', amount: '', op_date: tashkentToday(), notes: '' }); setErrors({}); setKey(newKey()) } }, [open])
  const src = accounts.find(a => String(a.id) === String(f.account_id))
  async function save() {
    const e = {}
    if (!f.account_id) e.account_id = 'Qaysi hisobdan'
    if (!f.to_account_id) e.to_account_id = 'Qaysi hisobga'
    if (f.account_id && f.account_id === f.to_account_id) e.to_account_id = 'Boshqa hisobni tanlang'
    const dst = accounts.find(a => String(a.id) === String(f.to_account_id))
    if (src && dst && src.currency !== dst.currency) e.to_account_id = 'Valyutalar bir xil bo‘lishi kerak'
    if (!(Number(f.amount) > 0)) e.amount = "Summa 0 dan katta bo'lishi kerak"
    setErrors(e)
    if (Object.keys(e).length) return
    setBusy(true)
    try {
      const r = await finance.transfer({ account_id: Number(f.account_id), to_account_id: Number(f.to_account_id), amount: f.amount, op_date: f.op_date, notes: f.notes, idempotency_key: key })
      toast.success(`${r.number} — o'tkazma bajarildi`); onSaved(); onClose()
    } catch (err) { toast.error(err.message) } finally { setBusy(false) }
  }
  return (
    <Modal open={open} onClose={onClose} title="Hisoblar orasida o'tkazma" size="md"
      footer={<><button className="button secondary" onClick={onClose}>Bekor</button><button className="button" disabled={busy} onClick={save}>{busy ? 'Bajarilmoqda…' : "O'tkazish"}</button></>}>
      <div className="fin-form">
        <Select label="Qaysi hisobdan" required value={f.account_id || ''} error={errors.account_id} onChange={e => setF({ ...f, account_id: e.target.value })}>
          <option value="">— Tanlang —</option>{active.map(a => <option key={a.id} value={a.id}>{a.name} · {money(a.balance, a.currency)}</option>)}
        </Select>
        <Select label="Qaysi hisobga" required value={f.to_account_id || ''} error={errors.to_account_id} onChange={e => setF({ ...f, to_account_id: e.target.value })}>
          <option value="">— Tanlang —</option>{active.filter(a => String(a.id) !== String(f.account_id)).map(a => <option key={a.id} value={a.id}>{a.name} ({a.currency})</option>)}
        </Select>
        <Input label={`Summa${src ? ` (${src.currency})` : ''}`} required type="number" step="0.01" value={f.amount || ''} error={errors.amount} onChange={e => setF({ ...f, amount: e.target.value })} />
        <Input label="Sana" type="date" value={f.op_date || ''} max={tashkentToday()} onChange={e => setF({ ...f, op_date: e.target.value })} />
        <div className="is-wide"><Textarea label="Izoh" rows={2} value={f.notes || ''} onChange={e => setF({ ...f, notes: e.target.value })} placeholder="Masalan: kassadagi naqdni bankka topshirish" /></div>
        <p className="fin-note is-wide">Ichki o'tkazma tushum yoki xarajat hisoblanmaydi — faqat hisoblar qoldig'i o'zgaradi.</p>
      </div>
    </Modal>
  )
}

function SettingsModal({ open, onClose }) {
  const [f, setF] = useState({ due_day: 10, upcoming_days: 7 })
  const [busy, setBusy] = useState(false)
  useEffect(() => { if (open) finance.me().then(m => setF(m.settings)).catch(() => {}) }, [open])
  async function save() {
    setBusy(true)
    try { await finance.updateSettings({ due_day: Number(f.due_day), upcoming_days: Number(f.upcoming_days) }); toast.success('Saqlandi'); onClose() }
    catch (e) { toast.error(e.message) } finally { setBusy(false) }
  }
  return (
    <Modal open={open} onClose={onClose} title="Moliya sozlamalari" size="sm"
      footer={<><button className="button secondary" onClick={onClose}>Bekor</button><button className="button" disabled={busy} onClick={save}>Saqlash</button></>}>
      <Input label="Oylik to'lov muddati (oyning nechanchi kuni)" type="number" min={1} max={28} value={f.due_day} onChange={e => setF({ ...f, due_day: e.target.value })}
        hint="Shu kundan keyin to'lanmagan oy “muddati o'tgan” hisoblanadi" />
      <Input label="Yaqinlashayotgan to'lovlar oynasi (kun)" type="number" min={1} max={60} value={f.upcoming_days} onChange={e => setF({ ...f, upcoming_days: e.target.value })} />
    </Modal>
  )
}

export default function FinAccounts({ currentUser }) {
  const isAdmin = currentUser?.role === 'admin'
  const [accounts, setAccounts] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selected, setSelected] = useState(null)
  const [range, setRange] = useState(() => presetRange('month'))
  const [moves, setMoves] = useState(null)
  const [movesLoading, setMovesLoading] = useState(false)
  const [modal, setModal] = useState(null)   // {type:'account', account} | 'transfer' | 'settings'
  const [recon, setRecon] = useState(null)
  const canReports = can(currentUser, 'finance.reports')

  async function load() {
    setLoading(true); setError(null)
    try { setAccounts(await finance.accounts()) } catch (e) { setError(e.message) } finally { setLoading(false) }
    if (canReports) finance.reconcile().then(setRecon).catch(() => {})
  }
  useEffect(() => { load() }, [])
  useEffect(() => {
    if (!selected || !canReports) return
    setMovesLoading(true)
    finance.report('accounts', { ...range, account_id: selected }).then(setMoves).catch(e => toast.error(e.message)).finally(() => setMovesLoading(false))
  }, [selected, range])

  const totals = accounts.filter(a => a.is_active).reduce((m, a) => ({ ...m, [a.currency]: (m[a.currency] || 0) + Number(a.balance) }), {})
  const allOk = recon && recon.payments.in_sync && recon.expenses.in_sync && recon.accounts.every(a => a.in_sync)
  const sel = accounts.find(a => a.id === selected)
  const summary = moves?.rows?.[0]

  return (
    <div className="page fin-page">
      <PageIntro eyebrow="Moliya" title="Kassa va hisoblar"
        description={<>Jami: {Object.entries(totals).map(([c, v]) => <strong key={c} style={{ marginRight: 12 }}>{money(v, c)}</strong>)}</>}
        actions={<div className="header-actions">
          {isAdmin && <button className="button secondary" onClick={() => setModal('settings')}><FontAwesomeIcon icon={faGear} /> Sozlamalar</button>}
          {can(currentUser, 'finance.transfer') && <button className="button secondary" onClick={() => setModal('transfer')}><FontAwesomeIcon icon={faRightLeft} /> O'tkazma</button>}
          {isAdmin && <button className="button" onClick={() => setModal({ type: 'account' })}><FontAwesomeIcon icon={faPlus} /> Hisob qo'shish</button>}
        </div>} />

      {recon && (
        <div className={`fin-callout`} style={allOk ? { borderColor: 'var(--success)', background: 'color-mix(in srgb, var(--success) 8%, var(--surface))' } : undefined} role="status">
          <span><FontAwesomeIcon icon={allOk ? faCircleCheck : faTriangleExclamation} />{' '}
            {allOk ? "Moslik tekshiruvi: jurnal, mijoz to'lovlari, xarajatlar va hisob qoldiqlari bir-biriga mos."
              : "Moslik tekshiruvida farq bor — administratorga xabar bering."}</span>
          {!allOk && <span className="muted-sm">To'lovlar: {money(recon.payments.ledger)} / {money(recon.payments.journal)} · Xarajatlar: {money(recon.expenses.ledger)} / {money(recon.expenses.journal)}</span>}
        </div>
      )}

      {error && <ErrorState message={error} onRetry={load} />}
      {loading && !accounts.length && <CardSkeleton count={3} />}
      <div className="fin-accounts">
        {accounts.map(a => (
          <article key={a.id} className={`fin-account${selected === a.id ? ' is-selected' : ''}${a.is_active ? '' : ' is-inactive'}`}>
            {canReports && <button className="fin-account-btn" aria-label={`${a.name} harakatlari`} onClick={() => setSelected(a.id === selected ? null : a.id)} />}
            <header><h3>{a.name}</h3>
              {isAdmin && <button className="btn-icon" aria-label="Tahrirlash" onClick={() => setModal({ type: 'account', account: a })}><FontAwesomeIcon icon={faPen} /></button>}</header>
            <div className={`fin-balance${Number(a.balance) < 0 ? ' tone-danger' : ''}`}>{money(a.balance, a.currency)}</div>
            <footer>
              <Badge size="sm">{ACCOUNT_KINDS[a.kind] || a.kind}</Badge>
              {!a.is_active && <Badge size="sm" variant="warning">Nofaol</Badge>}
              {!a.in_sync && <Badge size="sm" variant="danger">Qoldiq mos emas</Badge>}
              <span>boshlang'ich: {money(a.opening_balance, a.currency)}</span>
            </footer>
          </article>
        ))}
      </div>

      {canReports && sel && (
        <section className="studio-section">
          <div className="studio-section-head"><div><h2>{sel.name} — harakatlar</h2>
            <p>{summary ? <>Boshida: {money(summary.opening, sel.currency)} · kirim: {money(summary.inflow, sel.currency)} · chiqim: {money(summary.outflow, sel.currency)} · oxirida: <strong>{money(summary.closing, sel.currency)}</strong></> : '…'}</p></div></div>
          <div className="fin-toolbar" style={{ border: 0, borderRadius: 0, borderBottom: '1px solid var(--border)' }}><DateRange value={range} onChange={setRange} /></div>
          <DataTable rows={moves?.lines || []} loading={movesLoading} clientPageSize={25} rowKey={(r, i) => `${r.number}-${i}`}
            columns={[
              { key: 'date', header: 'Sana', render: r => <>{fmtDate(r.date)}<span className="fin-sub">{r.number}</span></> },
              { key: 'kind', header: 'Turi' },
              { key: 'who', header: 'Mijoz / kategoriya', render: r => r.student || r.category || r.notes || '—' },
              { key: 'amount', header: 'Harakat', align: 'right', render: r => <span className={`fin-amount ${Number(r.amount) >= 0 ? 'is-in' : 'is-out'}`}>{signedMoney(r.amount, sel.currency)}</span> },
              { key: 'balance', header: 'Qoldiq', align: 'right', render: r => money(r.balance, sel.currency) },
            ]}
            empty={{ title: "Bu davrda harakat yo'q" }} />
        </section>
      )}
      {canReports && !sel && accounts.length > 0 && <p className="muted-sm">Harakatlar (kirim/chiqim va qoldiq) ro'yxatini ko'rish uchun hisob kartasini bosing.</p>}

      <AccountModal open={modal?.type === 'account'} account={modal?.account} onClose={() => setModal(null)} onSaved={load} />
      <TransferModal open={modal === 'transfer'} accounts={accounts} onClose={() => setModal(null)} onSaved={load} />
      <SettingsModal open={modal === 'settings'} onClose={() => setModal(null)} />
    </div>
  )
}
