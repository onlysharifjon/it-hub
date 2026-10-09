import { useEffect, useMemo, useState } from 'react'
import { toast } from 'react-hot-toast'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faPlus, faArrowDownLong } from '@fortawesome/free-solid-svg-icons'
import { finance, tashkentToday } from '../../api'
import { PageIntro } from '../ui/Workspace'
import TxTable, { studentCols } from './TxTable'
import {
  Modal, Input, Select, Textarea, StudentPicker, DocumentField, MONTHS, money, fmt, useRefData, can, newKey, NoAccess,
} from './shared'

const MANUAL_METHODS = { cash: 'Naqd', card: 'Karta', bank_transfer: "Bank o'tkazmasi" }

function emptyForm(student, contract) {
  const t = tashkentToday()
  return {
    student: student || null, group_id: contract ? String(contract) : '', period_month: Number(t.slice(5, 7)),
    period_year: Number(t.slice(0, 4)), amount: '', account_id: '', fx_rate: '', method: 'cash',
    op_date: t, external_ref: '', notes: '', document: null,
  }
}

/** To'lov qabul qilish formasi — Kirimlar va Qarzdorlik sahifalaridan. */
export function IncomeForm({ open, onClose, onSaved, currentUser, student, contract }) {
  const [{ accounts }] = useRefData(['accounts'])
  const [form, setForm] = useState(() => emptyForm(student, contract))
  const [errors, setErrors] = useState({})
  const [hint, setHint] = useState(null)
  const [busy, setBusy] = useState(false)
  const [key, setKey] = useState(newKey)
  const active = accounts.filter(a => a.is_active && a.kind !== 'online')
  const account = accounts.find(a => String(a.id) === String(form.account_id))
  const currency = account?.currency || 'UZS'
  const canConfirm = can(currentUser, 'finance.approve')

  useEffect(() => { if (open) { setForm(emptyForm(student, contract)); setErrors({}); setKey(newKey()); setHint(null) } }, [open])
  useEffect(() => {
    if (!form.account_id && active.length) {
      const main = active.find(a => a.code === 'main_cash') || active[0]
      setForm(f => ({ ...f, account_id: String(main.id) }))
    }
  }, [accounts, open])
  useEffect(() => {
    const contracts = form.student?.contracts || []
    if (form.student && !form.group_id && contracts.length) {
      const c = contracts.find(x => x.active) || contracts[0]
      setForm(f => ({ ...f, group_id: String(c.group_id) }))
    }
  }, [form.student])
  useEffect(() => {
    if (!form.student || !form.group_id) { setHint(null); return }
    let alive = true
    finance.expected({ student_id: form.student.id, group_id: form.group_id, month: form.period_month, year: form.period_year })
      .then(h => alive && setHint(h)).catch(() => alive && setHint(null))
    return () => { alive = false }
  }, [form.student, form.group_id, form.period_month, form.period_year])

  const set = patch => { setForm(f => ({ ...f, ...patch })); setErrors(e => ({ ...e, ...Object.fromEntries(Object.keys(patch).map(k => [k, undefined])) })) }
  const amountUzs = currency === 'UZS' ? Number(form.amount || 0) : Number(form.amount || 0) * Number(form.fx_rate || 0)
  const payKind = useMemo(() => {
    if (!hint || !amountUzs) return null
    const rem = Number(hint.remaining)
    if (Number(hint.expected) <= 0) return { tone: 'info', text: "Bu oy uchun to'lov hisoblanmagan — summa avans sifatida qoladi" }
    if (amountUzs === rem) return { tone: 'success', text: "To'liq to'lov — shu oy yopiladi" }
    if (amountUzs < rem) return { tone: 'warning', text: `Qisman to'lov — shu oy uchun ${money(rem - amountUzs)} qoladi` }
    return { tone: 'info', text: `Ortiqcha to'lov — ${money(amountUzs - rem)} boshqa oy qarzini yopadi yoki avans bo'ladi` }
  }, [hint, amountUzs])

  function validate() {
    const e = {}
    if (!form.student) e.student = 'Mijozni tanlang'
    if (!form.group_id) e.group_id = 'Shartnoma (guruh)ni tanlang'
    const a = Number(form.amount)
    if (!form.amount) e.amount = 'Summani kiriting'
    else if (Number.isNaN(a) || a <= 0) e.amount = "Summa 0 dan katta bo'lishi kerak"
    else if (!/^\d+(\.\d{1,2})?$/.test(String(form.amount))) e.amount = "Ko'pi bilan 2 xona kasr"
    if (!form.account_id) e.account_id = 'Kassa yoki hisobni tanlang'
    if (currency !== 'UZS' && !(Number(form.fx_rate) > 0)) e.fx_rate = `1 ${currency} necha so'm ekanini kiriting`
    if (!form.op_date) e.op_date = 'Sanani kiriting'
    else if (form.op_date > tashkentToday()) e.op_date = "Kelajakdagi sana bo'lishi mumkin emas"
    setErrors(e)
    return !Object.keys(e).length
  }

  async function save(confirm) {
    if (!validate()) return
    setBusy(true)
    try {
      const res = await finance.createIncome({
        student_id: form.student.id, group_id: Number(form.group_id), amount: form.amount, currency,
        fx_rate: currency !== 'UZS' ? form.fx_rate : null, op_date: form.op_date, method: form.method,
        account_id: Number(form.account_id), period_month: Number(form.period_month), period_year: Number(form.period_year),
        external_ref: form.external_ref, notes: form.notes, document_path: form.document?.path || null,
        idempotency_key: key, confirm,
      })
      toast.success(res.duplicate ? `Bu to'lov allaqachon saqlangan: ${res.number}` : `${res.number} ${confirm ? 'tasdiqlandi' : 'qoralama sifatida saqlandi'}`)
      onSaved?.(res)
      onClose()
    } catch (err) {
      toast.error(err.message || "Saqlab bo'lmadi")
    } finally { setBusy(false) }
  }

  const years = [Number(tashkentToday().slice(0, 4)) - 1, Number(tashkentToday().slice(0, 4)), Number(tashkentToday().slice(0, 4)) + 1]

  return (
    <Modal open={open} onClose={onClose} title="To'lov qabul qilish" size="lg"
      footer={<>
        <button className="button secondary" onClick={onClose} disabled={busy}>Bekor</button>
        <button className={`button${canConfirm ? ' secondary' : ''}`} onClick={() => save(false)} disabled={busy}>Qoralama saqlash</button>
        {canConfirm && <button className="button" onClick={() => save(true)} disabled={busy}>{busy ? 'Saqlanmoqda…' : 'Saqlash va tasdiqlash'}</button>}
      </>}>
      <div className="fin-form">
        <div className="is-wide"><StudentPicker required value={form.student} onChange={s => set({ student: s, group_id: '' })} error={errors.student} /></div>
        <Select label="Shartnoma (guruh)" required value={form.group_id} onChange={e => set({ group_id: e.target.value })} error={errors.group_id} disabled={!form.student}>
          <option value="">— Tanlang —</option>
          {(form.student?.contracts || []).map(c => (
            <option key={c.group_id} value={c.group_id}>{c.group_name}{c.tariff ? ` · ${c.tariff}` : ''} · {fmt(c.monthly_price)} so'm/oy{c.active ? '' : ' (yakunlangan)'}</option>
          ))}
        </Select>
        <div className="fin-form" style={{ gap: 8 }}>
          <Select label="Qaysi oy uchun" required value={form.period_month} onChange={e => set({ period_month: Number(e.target.value) })}>
            {MONTHS.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}
          </Select>
          <Select label="Yil" required value={form.period_year} onChange={e => set({ period_year: Number(e.target.value) })}>
            {years.map(y => <option key={y} value={y}>{y}</option>)}
          </Select>
        </div>
        {hint && (
          <div className="fin-hint-box" aria-live="polite">
            <div><span>Shu oy hisoblangan</span><strong>{money(hint.expected)}</strong></div>
            <div><span>Shu oy to'langan</span><strong>{money(hint.paid)}</strong></div>
            <div><span>Shu oy qolgan</span><strong>{money(hint.remaining)}</strong></div>
            <div><span>Umumiy qarz</span><strong className={Number(hint.debt) > 0 ? 'tone-danger' : ''}>{money(hint.debt)}</strong></div>
            {Number(hint.advance) > 0 && <div><span>Avans</span><strong className="tone-success">{money(hint.advance)}</strong></div>}
            {hint.remaining > 0 && !form.amount && (
              <div><button type="button" className="button small secondary" onClick={() => set({ amount: String(Number(hint.remaining)) })}>Qolganini kiritish</button></div>
            )}
          </div>
        )}
        <Select label="Kassa / hisob" required value={form.account_id} onChange={e => set({ account_id: e.target.value })} error={errors.account_id}>
          <option value="">— Tanlang —</option>
          {active.map(a => <option key={a.id} value={a.id}>{a.name} ({a.currency})</option>)}
        </Select>
        <Input label={`Summa (${currency})`} required type="number" inputMode="decimal" min="0" step="0.01" value={form.amount}
          onChange={e => set({ amount: e.target.value })} error={errors.amount} placeholder="500000" />
        {currency !== 'UZS' && (
          <Input label={`Kurs: 1 ${currency} = ? so'm`} required type="number" step="0.0001" value={form.fx_rate}
            onChange={e => set({ fx_rate: e.target.value })} error={errors.fx_rate}
            hint={amountUzs ? `Talaba hisobiga ${money(amountUzs)} yoziladi` : 'Qarz so\'mda yuritiladi'} />
        )}
        {payKind && <p className={`fin-pay-kind tone-${payKind.tone}`} role="status">{payKind.text}</p>}
        <Select label="To'lov usuli" required value={form.method} onChange={e => set({ method: e.target.value })}>
          {Object.entries(MANUAL_METHODS).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
        </Select>
        <Input label="To'lov sanasi" required type="date" value={form.op_date} max={tashkentToday()} onChange={e => set({ op_date: e.target.value })} error={errors.op_date} />
        {form.method !== 'cash' && (
          <Input label="Bank/terminal tranzaksiya raqami" value={form.external_ref} maxLength={120} onChange={e => set({ external_ref: e.target.value })}
            hint="Ixtiyoriy. Bu faqat qayd — bank tasdig'i hisoblanmaydi" />
        )}
        <div className="is-wide"><Textarea label="Izoh" rows={2} value={form.notes} maxLength={2000} onChange={e => set({ notes: e.target.value })} /></div>
        <div className="is-wide"><DocumentField value={form.document} onChange={d => set({ document: d })} /></div>
        {!canConfirm && <p className="fin-note is-wide">Sizda tasdiqlash huquqi yo'q: to'lov qoralama sifatida saqlanadi va vakolatli xodim tasdiqlagandan keyin qarzdorlik va kassa qoldig'iga ta'sir qiladi.</p>}
      </div>
    </Modal>
  )
}

export default function FinIncome({ currentUser }) {
  const [{ accounts, groups }] = useRefData(['accounts', 'groups'])
  const [open, setOpen] = useState(false)
  const [reloadKey, setReloadKey] = useState(0)
  const canSee = can(currentUser, 'finance.clients') || can(currentUser, 'finance.income')
  const canAdd = can(currentUser, 'finance.income')
  if (!canSee) return <div className="page fin-page"><NoAccess /></div>

  const addBtn = canAdd && <button className="button" onClick={() => setOpen(true)}><FontAwesomeIcon icon={faPlus} /> To'lov qabul qilish</button>
  return (
    <div className="page fin-page">
      <PageIntro eyebrow="Moliya" title="Kirimlar" description="Mijoz to'lovlari, qaytarimlar va tuzatishlar. Qatorni bosib tafsilot va amallarni oching." actions={addBtn} />
      <TxTable
        fixed={{ flows: 'income,refund' }}
        currentUser={currentUser}
        accounts={accounts}
        reloadKey={reloadKey}
        extraFilters={[
          { key: 'kind', label: 'Turi', all: 'Kirim + qaytarim + tuzatish', options: [
            { value: 'income', label: 'Faqat kirim' }, { value: 'refund', label: 'Qaytarimlar' }, { value: 'adjustment', label: 'Tuzatishlar' }] },
          { key: 'group_id', label: 'Guruh', all: 'Barcha guruhlar', options: groups.map(g => ({ value: g.id, label: g.name })) },
        ]}
        columns={studentCols}
        empty={{ icon: faArrowDownLong, title: "Bu davrda kirim yo'q", description: "To'lov qabul qilinganda shu yerda ko'rinadi.", action: addBtn }}
      />
      <IncomeForm open={open} onClose={() => setOpen(false)} onSaved={() => setReloadKey(k => k + 1)} currentUser={currentUser} />
    </div>
  )
}
