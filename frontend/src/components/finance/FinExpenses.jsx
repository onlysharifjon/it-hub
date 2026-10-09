import { useEffect, useState } from 'react'
import { toast } from 'react-hot-toast'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faPlus, faTags, faHandHoldingDollar, faPen, faCheck } from '@fortawesome/free-solid-svg-icons'
import { finance, tashkentToday } from '../../api'
import { PageIntro } from '../ui/Workspace'
import Badge from '../ui/Badge'
import TxTable from './TxTable'
import { Modal, Input, Select, Textarea, DocumentField, money, useRefData, can, newKey, NoAccess, METHOD_LABELS } from './shared'

const MANUAL_METHODS = { cash: METHOD_LABELS.cash, card: METHOD_LABELS.card, bank_transfer: METHOD_LABELS.bank_transfer }
const blank = () => ({ category_id: '', amount: '', account_id: '', fx_rate: '', method: 'cash', op_date: tashkentToday(),
  counterparty: '', responsible_id: '', staff_id: '', notes: '', document: null })

function ExpenseForm({ open, onClose, onSaved, currentUser, refs }) {
  const { accounts, categories, staff } = refs
  const [form, setForm] = useState(blank)
  const [errors, setErrors] = useState({})
  const [busy, setBusy] = useState(false)
  const [key, setKey] = useState(newKey)
  const active = accounts.filter(a => a.is_active && a.kind !== 'online')
  const account = accounts.find(a => String(a.id) === String(form.account_id))
  const currency = account?.currency || 'UZS'
  const cat = categories.find(c => String(c.id) === String(form.category_id))
  const isSalary = cat?.code === 'salary'
  const isAdmin = currentUser?.role === 'admin'

  useEffect(() => {
    if (!open) return
    const main = active.find(a => a.code === 'main_cash') || active[0]
    setForm({ ...blank(), account_id: main ? String(main.id) : '', responsible_id: String(currentUser?.id || '') })
    setErrors({}); setKey(newKey())
  }, [open])

  const set = patch => { setForm(f => ({ ...f, ...patch })); setErrors(e => ({ ...e, ...Object.fromEntries(Object.keys(patch).map(k => [k, undefined])) })) }

  function validate() {
    const e = {}
    if (!form.category_id) e.category_id = 'Kategoriyani tanlang'
    const a = Number(form.amount)
    if (!form.amount) e.amount = 'Summani kiriting'
    else if (Number.isNaN(a) || a <= 0) e.amount = "Summa 0 dan katta bo'lishi kerak"
    else if (!/^\d+(\.\d{1,2})?$/.test(String(form.amount))) e.amount = "Ko'pi bilan 2 xona kasr"
    if (!form.account_id) e.account_id = 'Pul yechiladigan kassa/hisobni tanlang'
    if (currency !== 'UZS' && !(Number(form.fx_rate) > 0)) e.fx_rate = `1 ${currency} necha so'm ekanini kiriting`
    if (isSalary && !form.staff_id) e.staff_id = 'Ish haqi kimga berilganini tanlang'
    if (!form.op_date) e.op_date = 'Sanani kiriting'
    else if (form.op_date > tashkentToday()) e.op_date = "Kelajakdagi sana bo'lishi mumkin emas"
    setErrors(e)
    return !Object.keys(e).length
  }

  async function save(confirm) {
    if (!validate()) return
    setBusy(true)
    try {
      const res = await finance.createExpense({
        category_id: Number(form.category_id), amount: form.amount, currency, fx_rate: currency !== 'UZS' ? form.fx_rate : null,
        op_date: form.op_date, method: form.method, account_id: Number(form.account_id), counterparty: form.counterparty,
        responsible_id: form.responsible_id ? Number(form.responsible_id) : null, staff_id: isSalary ? Number(form.staff_id) : null,
        notes: form.notes, document_path: form.document?.path || null, idempotency_key: key, confirm,
      })
      toast.success(res.duplicate ? `Bu xarajat allaqachon saqlangan: ${res.number}` : `${res.number} ${confirm ? 'tasdiqlandi' : 'tasdiqlashga yuborildi'}`)
      onSaved?.(); onClose()
    } catch (err) { toast.error(err.message || "Saqlab bo'lmadi") } finally { setBusy(false) }
  }

  return (
    <Modal open={open} onClose={onClose} title="Xarajat kiritish" size="lg"
      footer={<>
        <button className="button secondary" onClick={onClose} disabled={busy}>Bekor</button>
        <button className={`button${isAdmin ? ' secondary' : ''}`} onClick={() => save(false)} disabled={busy}>{busy && !isAdmin ? 'Saqlanmoqda…' : 'Tasdiqlashga yuborish'}</button>
        {isAdmin && <button className="button" onClick={() => save(true)} disabled={busy}>{busy ? 'Saqlanmoqda…' : 'Saqlash va tasdiqlash'}</button>}
      </>}>
      <div className="fin-form">
        <Select label="Kategoriya" required value={form.category_id} onChange={e => set({ category_id: e.target.value })} error={errors.category_id}>
          <option value="">— Tanlang —</option>
          {categories.filter(c => c.is_active).map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
        </Select>
        <Select label="Pul yechilgan kassa / hisob" required value={form.account_id} onChange={e => set({ account_id: e.target.value })} error={errors.account_id}>
          <option value="">— Tanlang —</option>
          {active.map(a => <option key={a.id} value={a.id}>{a.name} ({a.currency}) · {money(a.balance, a.currency)}</option>)}
        </Select>
        <Input label={`Summa (${currency})`} required type="number" inputMode="decimal" min="0" step="0.01" value={form.amount}
          onChange={e => set({ amount: e.target.value })} error={errors.amount} />
        {currency !== 'UZS'
          ? <Input label={`Kurs: 1 ${currency} = ? so'm`} required type="number" step="0.0001" value={form.fx_rate} onChange={e => set({ fx_rate: e.target.value })} error={errors.fx_rate} />
          : <Input label="Sana" required type="date" value={form.op_date} max={tashkentToday()} onChange={e => set({ op_date: e.target.value })} error={errors.op_date} />}
        {currency !== 'UZS' && <Input label="Sana" required type="date" value={form.op_date} max={tashkentToday()} onChange={e => set({ op_date: e.target.value })} error={errors.op_date} />}
        <Select label="To'lov usuli" value={form.method} onChange={e => set({ method: e.target.value })}>
          {Object.entries(MANUAL_METHODS).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
        </Select>
        {isSalary
          ? <Select label="Kimga (xodim)" required value={form.staff_id} onChange={e => set({ staff_id: e.target.value })} error={errors.staff_id}>
              <option value="">— Tanlang —</option>
              {staff.map(s => <option key={s.id} value={s.id}>{s.name}{s.is_active ? '' : ' (bloklangan)'}</option>)}
            </Select>
          : <Input label="Oluvchi / kontragent" value={form.counterparty} maxLength={200} onChange={e => set({ counterparty: e.target.value })} placeholder="Masalan: Uy egasi, Elektr tarmoqlari" />}
        <Select label="Mas'ul xodim" value={form.responsible_id} onChange={e => set({ responsible_id: e.target.value })}>
          <option value="">— Belgilanmagan —</option>
          {staff.filter(s => s.is_active).map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
        </Select>
        <div className="is-wide"><Textarea label="Izoh" rows={2} maxLength={2000} value={form.notes} onChange={e => set({ notes: e.target.value })} /></div>
        <div className="is-wide"><DocumentField value={form.document} onChange={d => set({ document: d })} /></div>
        <p className="fin-note is-wide">
          Tasdiqlash holati: {isAdmin ? "admin sifatida darhol tasdiqlashingiz mumkin." : "xarajat qoralama sifatida saqlanadi va boshqa vakolatli xodim (yoki admin) tasdiqlagandan keyin kassa qoldig'idan yechiladi."}
        </p>
      </div>
    </Modal>
  )
}

function CategoriesModal({ open, onClose, categories, onChanged }) {
  const [name, setName] = useState('')
  const [edit, setEdit] = useState(null)
  const [busy, setBusy] = useState(false)
  async function run(fn, ok) {
    setBusy(true)
    try { await fn(); toast.success(ok); onChanged(); return true } catch (e) { toast.error(e.message); return false } finally { setBusy(false) }
  }
  return (
    <Modal open={open} onClose={onClose} title="Xarajat kategoriyalari" size="md"
      footer={<button className="button secondary" onClick={onClose}>Yopish</button>}>
      <form className="fin-form" onSubmit={e => { e.preventDefault(); if (name.trim().length < 2) { toast.error('Nom kamida 2 belgi'); return } run(() => finance.createCategory({ name: name.trim() }), "Qo'shildi").then(ok => ok && setName('')) }}>
        <Input label="Yangi kategoriya" value={name} maxLength={120} onChange={e => setName(e.target.value)} placeholder="Masalan: Internet" />
        <div style={{ alignSelf: 'end' }}><button className="button" disabled={busy} type="submit"><FontAwesomeIcon icon={faPlus} /> Qo'shish</button></div>
      </form>
      <ul className="fin-list" style={{ marginTop: 12 }}>
        {categories.map(c => (
          <li key={c.id}>
            {edit?.id === c.id
              ? <input className="field-sm" value={edit.name} autoFocus onChange={e => setEdit({ ...edit, name: e.target.value })} aria-label="Kategoriya nomi" />
              : <div><strong>{c.name}</strong>{c.code && <small>tizim kategoriyasi</small>}</div>}
            <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
              {!c.is_active && <Badge size="sm">Nofaol</Badge>}
              {edit?.id === c.id
                ? <button className="btn-icon" aria-label="Saqlash" onClick={() => run(() => finance.updateCategory(c.id, { name: edit.name }), 'Saqlandi').then(ok => ok && setEdit(null))}><FontAwesomeIcon icon={faCheck} /></button>
                : <button className="btn-icon" aria-label="Nomini o'zgartirish" onClick={() => setEdit({ id: c.id, name: c.name })}><FontAwesomeIcon icon={faPen} /></button>}
              {!c.code && <button className="button small secondary" disabled={busy} onClick={() => run(() => finance.updateCategory(c.id, { is_active: !c.is_active }), 'Saqlandi')}>{c.is_active ? 'Nofaol qilish' : 'Faollashtirish'}</button>}
            </div>
          </li>
        ))}
      </ul>
    </Modal>
  )
}

export default function FinExpenses({ currentUser }) {
  const [refs, reload] = useRefData(['accounts', 'categories', 'staff'])
  const [open, setOpen] = useState(false)
  const [catsOpen, setCatsOpen] = useState(false)
  const [reloadKey, setReloadKey] = useState(0)
  if (!can(currentUser, 'finance.expense')) return <div className="page fin-page"><NoAccess /></div>
  const addBtn = <button className="button" onClick={() => setOpen(true)}><FontAwesomeIcon icon={faPlus} /> Xarajat kiritish</button>

  return (
    <div className="page fin-page">
      <PageIntro eyebrow="Moliya" title="Xarajatlar" description="Barcha chiqimlar, kategoriyalar va tasdiqlash holati."
        actions={<div className="header-actions">
          {can(currentUser, 'finance.categories') && <button className="button secondary" onClick={() => setCatsOpen(true)}><FontAwesomeIcon icon={faTags} /> Kategoriyalar</button>}
          {addBtn}
        </div>} />
      <TxTable
        fixed={{ flow: 'expense' }}
        currentUser={currentUser}
        accounts={refs.accounts}
        reloadKey={reloadKey}
        extraFilters={[
          { key: 'category_id', label: 'Kategoriya', all: 'Barcha kategoriyalar', options: refs.categories.map(c => ({ value: c.id, label: c.name })) },
          { key: 'responsible_id', label: "Mas'ul", all: "Barcha mas'ullar", options: refs.staff.map(s => ({ value: s.id, label: s.name })) },
        ]}
        columns={[{ key: 'category', header: 'Kategoriya / oluvchi', render: t => <><strong>{t.category?.name || '—'}</strong><span className="fin-sub">{t.staff?.name || t.counterparty || t.notes || ''}</span></> },
          { key: 'responsible', header: "Mas'ul", render: t => <span className="muted-sm">{t.responsible?.name || t.created_by || '—'}</span> }]}
        empty={{ icon: faHandHoldingDollar, title: "Bu davrda xarajat yo'q", description: 'Ijara, kommunal, ish haqi kabi chiqimlarni shu yerda yuriting.', action: addBtn }}
      />
      <ExpenseForm open={open} onClose={() => setOpen(false)} onSaved={() => { setReloadKey(k => k + 1); reload('accounts') }} currentUser={currentUser} refs={refs} />
      <CategoriesModal open={catsOpen} onClose={() => setCatsOpen(false)} categories={refs.categories} onChanged={() => reload('categories')} />
    </div>
  )
}
