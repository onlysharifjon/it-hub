import { useEffect, useMemo, useRef, useState } from 'react'
import { toast } from 'react-hot-toast'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faCircleCheck, faBan, faRotateLeft, faScaleBalanced, faPaperclip, faMagnifyingGlass, faXmark,
  faShieldHalved,
} from '@fortawesome/free-solid-svg-icons'
import { finance, tashkentToday, API_BASE } from '../../api'
import { Drawer } from '../ui/Modal'
import Modal from '../ui/Modal'
import Badge from '../ui/Badge'
import { Input, Select, Textarea } from '../ui/Field'
import { FormSkeleton } from '../ui/States'
import './finance.css'

export const MONTHS = ['Yanvar', 'Fevral', 'Mart', 'Aprel', 'May', 'Iyun', 'Iyul', 'Avgust', 'Sentyabr', 'Oktyabr', 'Noyabr', 'Dekabr']
export const METHOD_LABELS = { cash: 'Naqd', card: 'Karta', bank_transfer: "Bank o'tkazmasi", online: 'Onlayn (Payme/Click/Uzum)', unknown: 'Belgilanmagan' }
export const KIND_LABELS = { income: 'Kirim', expense: 'Xarajat', refund: 'Qaytarim', adjustment: 'Tuzatish', transfer: "O'tkazma" }
export const ACCOUNT_KINDS = { cash: 'Kassa (naqd)', bank: 'Bank hisobi', card: 'Karta', online: 'Onlayn' }
export const CURRENCIES = ['UZS', 'USD', 'EUR', 'RUB']
const STATUS = {
  draft: { label: 'Qoralama', variant: 'warning' },
  confirmed: { label: 'Tasdiqlangan', variant: 'success' },
  cancelled: { label: 'Bekor qilingan', variant: 'neutral' },
}

export const can = (user, perm) => (user?.finance_permissions || []).includes(perm)

const num = n => Number(n || 0)
export const fmt = n => num(n).toLocaleString('uz-UZ', { maximumFractionDigits: 2 })
export function money(n, cur = 'UZS') {
  return cur === 'UZS' ? `${fmt(n)} so'm` : `${fmt(n)} ${cur}`
}
export const signedMoney = (n, cur) => (num(n) > 0 ? '+' : num(n) < 0 ? '−' : '') + money(Math.abs(num(n)), cur)

export function fmtDate(v) {
  if (!v) return '—'
  const s = String(v).slice(0, 10)
  const [y, m, d] = s.split('-')
  return d ? `${d}.${m}.${y}` : s
}
export function fmtDateTime(v) {
  if (!v) return '—'
  const d = new Date(String(v).endsWith('Z') || String(v).includes('+') ? v : `${v}Z`)
  return d.toLocaleString('uz-UZ', { timeZone: 'Asia/Tashkent', day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}
export const periodLabel = (m, y) => (m && y ? `${MONTHS[m - 1]} ${y}` : '—')

/** Takroriy yuborishdan himoya: har bir forma ochilganda yangi kalit. */
export function newKey() {
  if (window.crypto?.randomUUID) return window.crypto.randomUUID()
  return `k-${Date.now()}-${Math.random().toString(36).slice(2, 12)}`
}

export function StatusBadge({ status }) {
  const s = STATUS[status] || { label: status, variant: 'neutral' }
  return <Badge size="sm" variant={s.variant}>{s.label}</Badge>
}

export function KindBadge({ kind }) {
  const v = { income: 'success', expense: 'danger', refund: 'warning', adjustment: 'info', transfer: 'neutral' }[kind]
  return <Badge size="sm" variant={v || 'neutral'}>{KIND_LABELS[kind] || kind}</Badge>
}

/** Valyuta bo'yicha alohida summalar ({UZS: 100, USD: 5}) — hech qachon qo'shilmaydi. */
export function CurrencyLines({ values, field, empty = '—', signed = false }) {
  const rows = Object.entries(values || {}).map(([cur, v]) => [cur, field ? v?.[field] : v]).filter(([, v]) => num(v) !== 0)
  if (!rows.length) return <span className="muted-sm">{empty}</span>
  return <span className="fin-cur-lines">{rows.map(([cur, v]) => <span key={cur}>{signed ? signedMoney(v, cur) : money(v, cur)}</span>)}</span>
}

// ── Sana oralig'i ────────────────────────────────────────────────────────────

function shift(iso, days) {
  const d = new Date(`${iso}T00:00:00Z`)
  d.setUTCDate(d.getUTCDate() + days)
  return d.toISOString().slice(0, 10)
}
export function presetRange(key) {
  const t = tashkentToday()
  const [y, m] = t.split('-').map(Number)
  const first = `${t.slice(0, 7)}-01`
  if (key === 'today') return { date_from: t, date_to: t }
  if (key === 'week') return { date_from: shift(t, -6), date_to: t }
  if (key === 'month') return { date_from: first, date_to: t }
  if (key === 'prev') {
    const py = m === 1 ? y - 1 : y, pm = m === 1 ? 12 : m - 1
    const last = new Date(Date.UTC(py, pm, 0)).getUTCDate()
    return { date_from: `${py}-${String(pm).padStart(2, '0')}-01`, date_to: `${py}-${String(pm).padStart(2, '0')}-${last}` }
  }
  if (key === 'year') return { date_from: `${y}-01-01`, date_to: t }
  return null
}
const PRESETS = [['today', 'Bugun'], ['week', '7 kun'], ['month', 'Bu oy'], ['prev', "O'tgan oy"], ['year', 'Bu yil']]

export function DateRange({ value, onChange }) {
  const active = PRESETS.find(([k]) => {
    const r = presetRange(k)
    return r.date_from === value.date_from && r.date_to === value.date_to
  })?.[0]
  return (
    <div className="fin-range">
      <div className="fin-presets" role="group" aria-label="Davr">
        {PRESETS.map(([k, l]) => (
          <button key={k} type="button" className={active === k ? 'is-active' : ''} onClick={() => onChange(presetRange(k))}>{l}</button>
        ))}
      </div>
      <div className="fin-dates">
        <input type="date" className="field-sm" aria-label="Boshlanish sanasi" value={value.date_from || ''} max={value.date_to || undefined}
          onChange={e => onChange({ ...value, date_from: e.target.value })} />
        <span aria-hidden="true">—</span>
        <input type="date" className="field-sm" aria-label="Tugash sanasi" value={value.date_to || ''} min={value.date_from || undefined}
          onChange={e => onChange({ ...value, date_to: e.target.value })} />
      </div>
    </div>
  )
}

// ── Ma'lumotnomalar ──────────────────────────────────────────────────────────

const cache = {}
export function useRefData(keys) {
  const [data, setData] = useState(() => Object.fromEntries(keys.map(k => [k, cache[k] || []])))
  const keyStr = keys.join(',')
  async function reload(only) {
    const list = only ? [only] : keys
    const loaders = { accounts: finance.accounts, categories: finance.categories, staff: finance.staff, groups: finance.groups }
    const res = await Promise.all(list.map(k => loaders[k]().catch(() => [])))
    list.forEach((k, i) => { cache[k] = res[i] })
    setData(d => ({ ...d, ...Object.fromEntries(list.map((k, i) => [k, res[i]])) }))
  }
  useEffect(() => { reload() }, [keyStr])
  return [data, reload]
}

// ── Talaba (mijoz) tanlagich ─────────────────────────────────────────────────

export function StudentPicker({ value, onChange, error, label = 'Mijoz (talaba)', required }) {
  const [q, setQ] = useState('')
  const [items, setItems] = useState([])
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const timer = useRef(null)
  useEffect(() => {
    if (!open) return
    clearTimeout(timer.current)
    timer.current = setTimeout(async () => {
      setLoading(true)
      try { setItems(await finance.students(q)) } catch (e) { toast.error(e.message) } finally { setLoading(false) }
    }, 250)
    return () => clearTimeout(timer.current)
  }, [q, open])

  if (value) {
    return (
      <div className="ui-field">
        <span className="ui-field-label">{label}{required && <span className="ui-field-req"> *</span>}</span>
        <div className="fin-picked">
          <div><strong>{value.name}</strong><span>{value.phone}</span></div>
          <button type="button" className="btn-icon" aria-label="Boshqa mijoz tanlash" onClick={() => { onChange(null); setOpen(true) }}>
            <FontAwesomeIcon icon={faXmark} />
          </button>
        </div>
      </div>
    )
  }
  return (
    <div className="ui-field fin-picker">
      <label className="ui-field-label" htmlFor="fin-student-search">{label}{required && <span className="ui-field-req"> *</span>}</label>
      <div className="search-wrap">
        <FontAwesomeIcon icon={faMagnifyingGlass} className="fin-picker-icon" />
        <input id="fin-student-search" className="search-input" placeholder="Ism yoki telefon raqami" value={q}
          onFocus={() => setOpen(true)} onChange={e => { setQ(e.target.value); setOpen(true) }} autoComplete="off" />
      </div>
      {error && <span className="ui-field-error" role="alert">{error}</span>}
      {open && (
        <div className="fin-picker-list" role="listbox">
          {loading && <div className="fin-picker-empty">Qidirilmoqda…</div>}
          {!loading && items.length === 0 && <div className="fin-picker-empty">Mijoz topilmadi</div>}
          {!loading && items.map(s => (
            <button key={s.id} type="button" role="option" aria-selected="false" onClick={() => { onChange(s); setOpen(false); setQ('') }}>
              <strong>{s.name}</strong>
              <span>{s.phone}{s.is_archived ? ' · arxivda' : ''} · {s.contracts.map(c => c.group_name).join(', ') || "guruhsiz"}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

export function DocumentField({ value, onChange }) {
  const [busy, setBusy] = useState(false)
  async function pick(e) {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    if (file.size > 10 * 1024 * 1024) { toast.error('Fayl hajmi 10 MB dan oshmasligi kerak'); return }
    setBusy(true)
    try { onChange(await finance.uploadDocument(file)) } catch (err) { toast.error(err.message) } finally { setBusy(false) }
  }
  return (
    <div className="ui-field">
      <span className="ui-field-label">Tasdiqlovchi hujjat <span className="muted-sm">(ixtiyoriy)</span></span>
      {value ? (
        <div className="fin-picked">
          <div><strong><FontAwesomeIcon icon={faPaperclip} /> {value.name}</strong></div>
          <button type="button" className="btn-icon" aria-label="Hujjatni olib tashlash" onClick={() => onChange(null)}><FontAwesomeIcon icon={faXmark} /></button>
        </div>
      ) : (
        <label className="fin-upload">
          <input type="file" accept=".pdf,.jpg,.jpeg,.png,.webp,.heic,.xlsx,.xls,.doc,.docx" onChange={pick} disabled={busy} />
          <FontAwesomeIcon icon={faPaperclip} /> {busy ? 'Yuklanmoqda…' : 'Chek, kvitansiya yoki shartnoma (PDF/rasm, 10 MB gacha)'}
        </label>
      )}
    </div>
  )
}

// ── Operatsiya paneli (tafsilot + amallar) ──────────────────────────────────

function Row({ label, children }) {
  return <div className="fin-kv"><span>{label}</span><div>{children ?? '—'}</div></div>
}

function JsonDiff({ oldV, newV }) {
  const keys = [...new Set([...Object.keys(oldV || {}), ...Object.keys(newV || {})])]
  if (!keys.length) return null
  const show = v => (v == null || v === '' ? '—' : typeof v === 'object' ? JSON.stringify(v) : String(v))
  return (
    <div className="fin-diff">
      {keys.map(k => (
        <div key={k}><code>{k}</code><span className="fin-diff-old">{show(oldV?.[k])}</span><span aria-hidden="true">→</span><span>{show(newV?.[k])}</span></div>
      ))}
    </div>
  )
}
export { JsonDiff }

export function TxDrawer({ txId, onClose, onChanged, currentUser }) {
  const [tx, setTx] = useState(null)
  const [error, setError] = useState(null)
  const [action, setAction] = useState(null)   // cancel | refund | adjust
  const [form, setForm] = useState({})
  const [busy, setBusy] = useState(false)
  const [key, setKey] = useState(newKey)

  async function load() {
    setError(null)
    try { setTx(await finance.transaction(txId)) } catch (e) { setError(e.message) }
  }
  useEffect(() => { if (txId) { setTx(null); load() } }, [txId])

  const canApprove = can(currentUser, 'finance.approve')
  const canRefund = can(currentUser, 'finance.refund')
  const isOwnDraft = tx && tx.created_by_id === currentUser?.id
  const selfExpense = tx && tx.kind === 'expense' && isOwnDraft && currentUser?.role !== 'admin'

  async function run(fn, ok) {
    setBusy(true)
    try {
      await fn()
      toast.success(ok)
      setAction(null); setForm({}); setKey(newKey())
      await load(); onChanged?.()
    } catch (e) { toast.error(e.message) } finally { setBusy(false) }
  }

  function submitAction() {
    const reason = (form.reason || '').trim()
    if (reason.length < 3) { toast.error('Sababni yozing (kamida 3 belgi)'); return }
    if (action === 'cancel') return run(() => finance.cancel(tx.id, reason), 'Qoralama bekor qilindi')
    const amount = Number(form.amount)
    if (!form.amount || Number.isNaN(amount) || amount === 0 || (action === 'refund' && amount <= 0)) {
      toast.error(action === 'refund' ? "Qaytarim summasini kiriting" : "Tuzatish summasini kiriting (+ yoki −)"); return
    }
    if (action === 'refund' && tx.net_amount != null && amount > Number(tx.net_amount)) {
      toast.error(`Qaytarim ${money(tx.net_amount, tx.currency)} dan oshmasligi kerak`); return
    }
    const body = { amount: form.amount, reason, idempotency_key: key, ...(form.account_id ? { account_id: Number(form.account_id) } : {}) }
    return run(() => (action === 'refund' ? finance.refund(tx.id, body) : finance.adjust(tx.id, body)),
      action === 'refund' ? 'Qaytarim rasmiylashtirildi' : 'Tuzatish yozildi')
  }

  const footer = tx && !action && (
    <div className="fin-drawer-actions">
      {tx.status === 'draft' && canApprove && !selfExpense && (
        <button className="button" disabled={busy} onClick={() => run(() => finance.confirm(tx.id), 'Tasdiqlandi')}>
          <FontAwesomeIcon icon={faCircleCheck} /> Tasdiqlash
        </button>
      )}
      {tx.status === 'draft' && (canApprove || isOwnDraft) && (
        <button className="button secondary" onClick={() => setAction('cancel')}><FontAwesomeIcon icon={faBan} /> Bekor qilish</button>
      )}
      {tx.status === 'confirmed' && tx.kind === 'income' && canRefund && Number(tx.net_amount) > 0 && (
        <button className="button secondary" onClick={() => setAction('refund')}><FontAwesomeIcon icon={faRotateLeft} /> Qaytarim</button>
      )}
      {tx.status === 'confirmed' && ['income', 'expense'].includes(tx.kind) && canRefund && (
        <button className="button secondary" onClick={() => setAction('adjust')}><FontAwesomeIcon icon={faScaleBalanced} /> Tuzatish</button>
      )}
    </div>
  )

  return (
    <Drawer open={!!txId} title={tx ? `${KIND_LABELS[tx.kind]} ${tx.number}` : 'Operatsiya'} onClose={onClose} width={520} footer={footer}>
      {error && <p className="ui-field-error">{error}</p>}
      {!tx && !error && <FormSkeleton fields={6} />}
      {tx && (
        <div className="fin-drawer">
          <div className="fin-drawer-amount">
            <strong className={tx.signed_amount < 0 ? 'tone-danger' : tx.signed_amount > 0 ? 'tone-success' : ''}>
              {tx.kind === 'transfer' ? money(tx.amount, tx.currency) : signedMoney(tx.signed_amount, tx.currency)}
            </strong>
            <StatusBadge status={tx.status} />
          </div>
          {tx.status === 'draft' && selfExpense && canApprove && (
            <p className="fin-note"><FontAwesomeIcon icon={faShieldHalved} /> O'zingiz kiritgan xarajatni boshqa vakolatli xodim yoki admin tasdiqlaydi.</p>
          )}
          {tx.status === 'draft' && !canApprove && (
            <p className="fin-note">Qoralama hisob qoldig'i va qarzdorlikka ta'sir qilmaydi — tasdiqlash huquqi bor xodim tasdiqlashi kerak.</p>
          )}
          <Row label="Sana">{fmtDate(tx.op_date)}</Row>
          {tx.student && <Row label="Mijoz">{tx.student.name} <span className="muted-sm">{tx.student.phone}</span></Row>}
          {tx.group && <Row label="Shartnoma (guruh)">{tx.group.name}</Row>}
          {tx.period_month && <Row label="Qaysi oy uchun">{periodLabel(tx.period_month, tx.period_year)}</Row>}
          {tx.category && <Row label="Kategoriya">{tx.category.name}</Row>}
          {tx.counterparty && <Row label="Oluvchi / kontragent">{tx.counterparty}</Row>}
          {tx.staff && <Row label="Xodim (ish haqi)">{tx.staff.name}</Row>}
          {tx.method && <Row label="To'lov usuli">{METHOD_LABELS[tx.method] || tx.method}</Row>}
          <Row label={tx.kind === 'transfer' ? 'Qaysi hisobdan' : 'Kassa / hisob'}>{tx.account?.name || 'Belgilanmagan (tarixiy yozuv)'}</Row>
          {tx.to_account && <Row label="Qaysi hisobga">{tx.to_account.name}</Row>}
          {tx.currency !== 'UZS' && <Row label="Kurs">1 {tx.currency} = {fmt(tx.fx_rate)} so'm · {money(tx.amount_uzs)}</Row>}
          <Row label="Bank tasdig'i">
            {tx.external_verified
              ? <Badge size="sm" variant="success">Provayder tasdiqlagan</Badge>
              : <span className="muted-sm">Qo'lda qayd etilgan{tx.external_ref ? '' : ''}</span>}
            {tx.external_ref && <div className="muted-sm">Tranzaksiya: {tx.external_ref}</div>}
          </Row>
          {tx.origin && <Row label="Asl operatsiya">{tx.origin.number}</Row>}
          {tx.reason && <Row label="Sabab">{tx.reason}</Row>}
          {tx.notes && <Row label="Izoh">{tx.notes}</Row>}
          {tx.responsible && <Row label="Mas'ul">{tx.responsible.name}</Row>}
          {tx.document_url && <Row label="Hujjat"><a href={`${API_BASE}${tx.document_url}`} target="_blank" rel="noreferrer"><FontAwesomeIcon icon={faPaperclip} /> Ochish</a></Row>}
          <Row label="Kiritdi">{tx.created_by || 'Tizim'} · {fmtDateTime(tx.created_at)}</Row>
          {tx.confirmed_at && <Row label="Tasdiqladi">{tx.confirmed_by || 'Tizim'} · {fmtDateTime(tx.confirmed_at)}</Row>}
          {tx.cancelled_at && <Row label="Bekor qildi">{tx.cancelled_by} · {fmtDateTime(tx.cancelled_at)}</Row>}
          {tx.net_amount != null && tx.children?.length > 0 && <Row label="Sof summa">{money(tx.net_amount, tx.currency)}</Row>}

          {tx.children?.length > 0 && (
            <section className="fin-drawer-section">
              <h3>Bog'langan qaytarim va tuzatishlar</h3>
              {tx.children.map(c => (
                <div key={c.id} className="fin-child">
                  <div><KindBadge kind={c.kind} /> <strong>{c.number}</strong> <span className="muted-sm">{fmtDate(c.op_date)}</span></div>
                  <div className="fin-child-amt">{c.kind === 'refund' ? '−' : Number(c.amount) > 0 ? '+' : ''}{money(Math.abs(c.amount), tx.currency)}</div>
                  <p className="muted-sm">{c.reason} · {c.created_by || 'Tizim'}</p>
                </div>
              ))}
            </section>
          )}

          {action && (
            <section className="fin-drawer-section fin-action">
              <h3>{{ cancel: 'Qoralamani bekor qilish', refund: 'Qaytarim rasmiylashtirish', adjust: 'Tuzatish yozuvi' }[action]}</h3>
              {action === 'refund' && <p className="muted-sm">Qaytarilishi mumkin: <strong>{money(tx.net_amount, tx.currency)}</strong>. Asl to'lov o'zgarmaydi — alohida yozuv yaratiladi.</p>}
              {action === 'adjust' && <p className="muted-sm">Musbat summa asl operatsiyani oshiradi, manfiy (−) — kamaytiradi. Hozirgi sof summa: <strong>{money(tx.net_amount, tx.currency)}</strong>.</p>}
              {action !== 'cancel' && (
                <Input label={`Summa (${tx.currency})`} required type="number" step="0.01" inputMode="decimal" value={form.amount || ''}
                  onChange={e => setForm(f => ({ ...f, amount: e.target.value }))} placeholder={action === 'adjust' ? '-50000' : ''} />
              )}
              <Textarea label="Sabab" required rows={2} value={form.reason || ''} onChange={e => setForm(f => ({ ...f, reason: e.target.value }))}
                hint="Audit tarixida saqlanadi" />
              <div className="fin-drawer-actions">
                <button className="button secondary" onClick={() => { setAction(null); setForm({}) }} disabled={busy}>Orqaga</button>
                <button className={`button${action === 'cancel' ? ' danger' : ''}`} onClick={submitAction} disabled={busy}>{busy ? 'Saqlanmoqda…' : 'Tasdiqlash'}</button>
              </div>
            </section>
          )}

          {tx.history?.length > 0 && (
            <section className="fin-drawer-section">
              <h3>Audit tarixi</h3>
              <ol className="fin-timeline">
                {tx.history.map(h => (
                  <li key={h.id}>
                    <strong>{h.action_label}</strong> · {h.changed_by} · <span className="muted-sm">{fmtDateTime(h.changed_at)}</span>
                    {h.reason && <p>Sabab: {h.reason}</p>}
                  </li>
                ))}
              </ol>
            </section>
          )}
        </div>
      )}
    </Drawer>
  )
}

export function NoAccess({ text = "Bu bo'lim uchun ruxsatingiz yo'q. Administratorga murojaat qiling." }) {
  return <div className="fin-noaccess" role="alert">{text}</div>
}

export function useDebounced(value, ms = 300) {
  const [v, setV] = useState(value)
  useEffect(() => { const t = setTimeout(() => setV(value), ms); return () => clearTimeout(t) }, [value, ms])
  return v
}

export function useFilterState(initial) {
  const [f, setF] = useState(initial)
  const set = useMemo(() => (patch) => setF(prev => ({ ...prev, ...patch, page: patch.page ?? 1 })), [])
  return [f, set]
}

export { Modal, Select, Input, Textarea }
