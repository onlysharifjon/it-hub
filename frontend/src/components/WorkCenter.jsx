import { useCallback, useEffect, useMemo, useState } from 'react'
import { toast } from 'react-hot-toast'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faListCheck, faPhone, faCheck, faClock, faTriangleExclamation,
  faCircleCheck, faForward, faPlus, faSpinner, faUser, faFilter,
  faMoneyBillWave, faCalendarXmark, faBullseye, faRotate,
} from '@fortawesome/free-solid-svg-icons'
import {
  fetchWorkCenter, createWorkTask, updateWorkTask, logCall, fetchUsers,
} from '../api'
import KpiCard from './ui/KpiCard'
import Modal from './ui/Modal'
import { Input, Textarea, Select } from './ui/Field'
import { EmptyState, ErrorState, CardSkeleton, Skeleton } from './ui/States'
import useConfirm from './ui/useConfirm'
import CallOutcomeDialog from './work/CallOutcomeDialog'
import { fmtDateTime, fmtRelative, inputToIso } from '../utils/datetime'

const PRIORITY_LABEL = { critical: 'Shoshilinch', high: 'Muhim', normal: 'Oddiy', low: 'Past' }
const PRIORITY_ORDER = ['critical', 'high', 'normal', 'low']

const TYPE_ICON = {
  PAYMENT_REMINDER: faMoneyBillWave,
  ABSENCE_FOLLOWUP: faCalendarXmark,
  CALLBACK: faPhone,
  LEAD_CALL: faBullseye,
  GENERAL_TASK: faListCheck,
}

/**
 * Ishlarim — hunter va call center uchun kunlik boshqaruv paneli.
 *
 * Maqsad: xodim "bugun kimga qo'ng'iroq qilaman?" deb o'ylamasin. Ro'yxat
 * CRM ma'lumotidan avtomatik yig'iladi va muhimligi bo'yicha tartiblanadi —
 * eng tepada bugun hal qilinishi kerak bo'lgan ishlar turadi.
 */
export default function WorkCenter({ currentUser }) {
  const [confirmUI, ask] = useConfirm()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState(null)
  const [saving, setSaving] = useState(false)
  const [callFor, setCallFor] = useState(null)
  const [typeFilter, setTypeFilter] = useState('')
  const [prioFilter, setPrioFilter] = useState('')
  const [newTask, setNewTask] = useState(null)
  const [postponeFor, setPostponeFor] = useState(null)
  const [users, setUsers] = useState([])
  const [scopeUser, setScopeUser] = useState('')

  const isAdmin = currentUser?.role === 'admin'

  const load = useCallback(async () => {
    setErr(null)
    try {
      setData(await fetchWorkCenter(scopeUser || undefined))
    } catch (e) {
      setErr(e.message)
    } finally {
      setLoading(false)
    }
  }, [scopeUser])

  useEffect(() => { load() }, [load])
  useEffect(() => {
    if (!isAdmin) return
    fetchUsers().then(u => setUsers(u.filter(x =>
      ['hunter', 'call_center', 'admin'].includes(x.role) && x.is_active))).catch(() => {})
  }, [isAdmin])

  const tasks = data?.tasks || []

  const filtered = useMemo(() => tasks.filter(t =>
    (!typeFilter || t.task_type === typeFilter) &&
    (!prioFilter || t.priority === prioFilter)), [tasks, typeFilter, prioFilter])

  const byPriority = useMemo(() => {
    const g = {}
    for (const p of PRIORITY_ORDER) g[p] = filtered.filter(t => t.priority === p)
    return g
  }, [filtered])

  const overdue = useMemo(() => tasks.filter(t => t.overdue), [tasks])
  // Ro'yxat muhimlik bo'yicha tartiblangan, shuning uchun "eng eskisi"ni
  // alohida topamiz — oxirgi element eng eski degani emas.
  const oldestOverdue = useMemo(() => overdue.reduce(
    (a, b) => (!a || (b.due_at && b.due_at < a.due_at) ? b : a), null), [overdue])

  const typeCounts = useMemo(() => {
    const m = new Map()
    for (const t of tasks) m.set(t.task_type, (m.get(t.task_type) || 0) + 1)
    return [...m.entries()].sort((a, b) => b[1] - a[1])
  }, [tasks])

  async function submitCall(payload) {
    setSaving(true)
    try {
      await logCall(payload)
      toast.success("Qo'ng'iroq yozildi")
      setCallFor(null)
      await load()
    } catch (e) { toast.error(e.message) } finally { setSaving(false) }
  }

  async function markDone(task) {
    try {
      await updateWorkTask(task.source_key, {
        status: 'completed', task_type: task.task_type, title: task.title,
        entity_type: task.entity_type, entity_id: task.entity_id, priority: task.priority,
      })
      toast.success('Bajarildi')
      load()
    } catch (e) { toast.error(e.message) }
  }

  async function skip(task) {
    const ok = await ask({
      title: "Vazifani o'tkazib yuborish",
      message: `"${task.title}" vazifasi bugungi ro'yxatdan olib tashlansinmi?`,
      confirmLabel: 'Ha',
    })
    if (!ok) return
    try {
      await updateWorkTask(task.source_key, {
        status: 'skipped', task_type: task.task_type, title: task.title,
        entity_type: task.entity_type, entity_id: task.entity_id, priority: task.priority,
      })
      load()
    } catch (e) { toast.error(e.message) }
  }

  /* Keyinga surish uchun YANGI VAQT majburiy (§17) — shuning uchun bu
     alohida oyna, `prompt()` emas: brauzer oynasi mobil qurilmada
     ishonchsiz va uni mavzuga moslab bo'lmaydi. */
  async function savePostpone() {
    const t = postponeFor
    if (!t?.when) return toast.error('Vaqtni tanlang')
    const postponedTo = inputToIso(t.when)
    if (!postponedTo) return toast.error("Vaqt noto'g'ri")
    setSaving(true)
    try {
      await updateWorkTask(t.task.source_key, {
        status: 'postponed', postponed_to: postponedTo,
        task_type: t.task.task_type, title: t.task.title,
        entity_type: t.task.entity_type, entity_id: t.task.entity_id,
        priority: t.task.priority,
      })
      toast.success('Keyinga surildi')
      setPostponeFor(null)
      load()
    } catch (e) { toast.error(e.message) } finally { setSaving(false) }
  }

  async function saveNewTask() {
    if (!newTask.title.trim()) return toast.error('Sarlavha kerak')
    setSaving(true)
    try {
      await createWorkTask({
        title: newTask.title.trim(),
        reason: newTask.reason || null,
        priority: newTask.priority,
        due_at: inputToIso(newTask.due_at),
      })
      toast.success("Vazifa qo'shildi")
      setNewTask(null)
      load()
    } catch (e) { toast.error(e.message) } finally { setSaving(false) }
  }

  if (err) {
    return (
      <div className="page">
        <div className="page-head"><h2><FontAwesomeIcon icon={faListCheck} /> Ishlarim</h2></div>
        <ErrorState title="Ish ro'yxatini yuklab bo'lmadi" onRetry={load} />
      </div>
    )
  }

  const kpi = data?.kpi
  const daily = data?.daily

  return (
    <div className="page">
      {confirmUI}
      <div className="page-head">
        <div>
          <h2><FontAwesomeIcon icon={faListCheck} /> Ishlarim</h2>
          <p className="page-sub">Bugun kim bilan bog'lanish kerakligi — avtomatik ro'yxat</p>
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {isAdmin && users.length > 0 && (
            <select className="field wc-user-pick" value={scopeUser} aria-label="Xodim"
              onChange={e => { setLoading(true); setScopeUser(e.target.value) }}>
              <option value="">Mening navbatim</option>
              {users.map(u => <option key={u.id} value={u.id}>{u.full_name || u.username}</option>)}
            </select>
          )}
          <button className="button secondary" onClick={load} aria-label="Yangilash">
            <FontAwesomeIcon icon={faRotate} /> Yangilash
          </button>
          <button className="button" onClick={() => setNewTask({ title: '', reason: '', priority: 'normal', due_at: '' })}>
            <FontAwesomeIcon icon={faPlus} /> Vazifa
          </button>
        </div>
      </div>

      <div className="kpi-grid">
        {loading ? <CardSkeleton count={4} /> : (
          <>
            <KpiCard label="Bugungi vazifalar" value={kpi.total} icon={faListCheck} tone="primary" />
            <KpiCard label="Bajarildi" value={kpi.completed} icon={faCircleCheck} tone="success" />
            <KpiCard label="Qoldi" value={kpi.remaining} icon={faClock} tone="info" />
            <KpiCard label="Shoshilinch" value={kpi.critical} icon={faTriangleExclamation}
              tone={kpi.critical > 0 ? 'danger' : 'default'}
              sub={kpi.overdue ? `${kpi.overdue} ta kechikkan` : undefined} />
          </>
        )}
      </div>

      {!loading && overdue.length > 0 && (
        <div className="wc-overdue">
          <FontAwesomeIcon icon={faTriangleExclamation} />
          <div>
            <strong>Kechikkan ishlar: {overdue.length} ta</strong>
            {oldestOverdue?.due_at && (
              <span> — eng eskisi {fmtDateTime(oldestOverdue.due_at)} ({fmtRelative(oldestOverdue.due_at)})</span>
            )}
          </div>
        </div>
      )}

      {!loading && (
        <div className="wc-filters">
          <FontAwesomeIcon icon={faFilter} className="muted" />
          <button className={`chip${!typeFilter ? ' is-on' : ''}`} onClick={() => setTypeFilter('')}>
            Hammasi <span>{tasks.length}</span>
          </button>
          {typeCounts.map(([type, n]) => (
            <button key={type} className={`chip${typeFilter === type ? ' is-on' : ''}`}
              onClick={() => setTypeFilter(typeFilter === type ? '' : type)}>
              <FontAwesomeIcon icon={TYPE_ICON[type] || faListCheck} />
              {' '}{tasks.find(t => t.task_type === type)?.task_label} <span>{n}</span>
            </button>
          ))}
          <span style={{ flex: 1 }} />
          {PRIORITY_ORDER.map(p => {
            const n = tasks.filter(t => t.priority === p).length
            if (!n) return null
            return (
              <button key={p} className={`chip prio-${p}${prioFilter === p ? ' is-on' : ''}`}
                onClick={() => setPrioFilter(prioFilter === p ? '' : p)}>
                {PRIORITY_LABEL[p]} <span>{n}</span>
              </button>
            )
          })}
        </div>
      )}

      {loading ? (
        <div className="wc-grid">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} height={150} radius="var(--radius-lg)" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={faCircleCheck}
          title={tasks.length ? 'Bu filtrda vazifa yo\'q' : 'Bugun hammasi bajarilgan'}
          description={tasks.length
            ? 'Filterni o\'zgartiring'
            : "Yangi callback, qarz yoki davomat muammosi paydo bo'lsa, shu yerda ko'rinadi."}
        />
      ) : (
        PRIORITY_ORDER.map(p => byPriority[p].length > 0 && (
          <section key={p} className="wc-section">
            <h4 className={`wc-section-head prio-${p}`}>
              <span className="wc-dot" /> {PRIORITY_LABEL[p]}
              <span className="wc-count">{byPriority[p].length}</span>
            </h4>
            <div className="wc-grid">
              {byPriority[p].map(t => (
                <TaskCard key={t.source_key} task={t}
                  onCall={() => setCallFor(t)}
                  onDone={() => markDone(t)}
                  onSkip={() => skip(t)}
                  onPostpone={() => setPostponeFor({ task: t, when: '' })} />
              ))}
            </div>
          </section>
        ))
      )}

      {!loading && daily && (
        <section className="wc-section">
          <h4 className="wc-section-head"><FontAwesomeIcon icon={faPhone} /> Bugungi natija</h4>
          <div className="wc-daily">
            <Stat n={daily.calls} label="qo'ng'iroq" />
            <Stat n={daily.connected} label="bog'landi" tone="success" />
            <Stat n={daily.no_answer} label="javobsiz" tone="muted" />
            <Stat n={daily.callbacks} label="callback" />
            <Stat n={daily.payment_calls} label="to'lov" />
            <Stat n={daily.absence_calls} label="davomat" />
            <Stat n={daily.completed_tasks} label="bajarilgan vazifa" tone="success" />
          </div>
        </section>
      )}

      {!loading && data?.completed?.length > 0 && (
        <section className="wc-section">
          <h4 className="wc-section-head">
            <FontAwesomeIcon icon={faCircleCheck} /> Bugun bajarilgan
            <span className="wc-count">{data.completed.length}</span>
          </h4>
          <ul className="wc-done">
            {data.completed.map(t => (
              <li key={t.source_key}>
                <FontAwesomeIcon icon={faCheck} className="wc-done-icon" />
                <span className="wc-done-title">{t.title}</span>
                <span className="muted">{t.task_label}</span>
                {t.last_note && <span className="wc-done-note">{t.last_note}</span>}
                <span className="muted wc-done-when">{fmtRelative(t.completed_at)}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {callFor && (
        <CallOutcomeDialog task={callFor} saving={saving}
          onClose={() => setCallFor(null)} onSubmit={submitCall} />
      )}

      {postponeFor && (
        <Modal open title="Keyinga surish" onClose={() => setPostponeFor(null)}
          footer={<>
            <button className="button secondary" onClick={() => setPostponeFor(null)}>Bekor</button>
            <button className="button" onClick={savePostpone} disabled={saving || !postponeFor.when}>
              {saving ? <FontAwesomeIcon icon={faSpinner} className="kc-spin" /> : 'Surish'}
            </button>
          </>}>
          <p className="muted" style={{ marginTop: 0, fontSize: 13 }}>
            <strong>{postponeFor.task.title}</strong> — bu vazifa tanlangan vaqtgacha
            ro'yxatda ko'rinmaydi.
          </p>
          <label>Yangi vaqt</label>
          <input className="field" type="datetime-local" autoFocus
            value={postponeFor.when}
            onChange={e => setPostponeFor(p => ({ ...p, when: e.target.value }))} />
        </Modal>
      )}

      {newTask && (
        <Modal open title="Yangi vazifa" onClose={() => setNewTask(null)}
          footer={<>
            <button className="button secondary" onClick={() => setNewTask(null)}>Bekor</button>
            <button className="button" onClick={saveNewTask} disabled={saving}>
              {saving ? <FontAwesomeIcon icon={faSpinner} className="kc-spin" /> : 'Saqlash'}
            </button>
          </>}>
          <Input label="Sarlavha" required value={newTask.title}
            onChange={e => setNewTask(p => ({ ...p, title: e.target.value }))} />
          <Textarea label="Izoh" rows={2} value={newTask.reason}
            onChange={e => setNewTask(p => ({ ...p, reason: e.target.value }))} />
          <Select label="Muhimlik" value={newTask.priority}
            onChange={e => setNewTask(p => ({ ...p, priority: e.target.value }))}>
            {PRIORITY_ORDER.map(p => <option key={p} value={p}>{PRIORITY_LABEL[p]}</option>)}
          </Select>
          <label>Muddat</label>
          <input className="field" type="datetime-local" value={newTask.due_at}
            onChange={e => setNewTask(p => ({ ...p, due_at: e.target.value }))} />
        </Modal>
      )}
    </div>
  )
}

function Stat({ n, label, tone }) {
  return (
    <div className={`wc-stat${tone ? ' tone-' + tone : ''}`}>
      <strong>{n}</strong>
      <span>{label}</span>
    </div>
  )
}

/** Bitta vazifa kartasi — nima, kim, nega, va bitta bosishda qo'ng'iroq. */
function TaskCard({ task, onCall, onDone, onSkip, onPostpone }) {
  const m = task.meta || {}
  const phones = [task.phone, task.phone2].filter(Boolean)
  return (
    <article className={`wc-card prio-${task.priority}${task.overdue ? ' is-overdue' : ''}`}>
      <header className="wc-card-head">
        <span className="wc-type">
          <FontAwesomeIcon icon={TYPE_ICON[task.task_type] || faListCheck} />
          {' '}{task.task_label}
        </span>
        {task.overdue && <span className="wc-badge-late">kechikkan</span>}
      </header>

      <div className="wc-name">{task.title}</div>
      {m.groups?.length > 0 && <div className="wc-sub">{m.groups.join(', ')}</div>}
      {m.group && <div className="wc-sub">{m.group}</div>}
      {m.stage && <div className="wc-sub">Bosqich: {m.stage}</div>}

      {task.reason && <div className="wc-reason">{task.reason}</div>}

      {task.due_at && (
        <div className="wc-due">
          <FontAwesomeIcon icon={faClock} /> {fmtDateTime(task.due_at)}
          <span className="muted"> · {fmtRelative(task.due_at)}</span>
        </div>
      )}

      {phones.length > 0 && (
        <div className="wc-phones">
          {phones.map(p => (
            <a key={p} className="wc-phone" href={`tel:${p}`}>
              <FontAwesomeIcon icon={faPhone} /> {p}
            </a>
          ))}
        </div>
      )}

      <footer className="wc-actions">
        {task.entity_id && task.phone ? (
          <a className="button" href={`tel:${task.phone}`} onClick={() => setTimeout(onCall, 400)}>
            <FontAwesomeIcon icon={faPhone} /> Qo'ng'iroq
          </a>
        ) : null}
        {task.entity_id && (
          <button className="button secondary" onClick={onCall}>Natijani yozish</button>
        )}
        <button className="btn-icon" onClick={onDone} title="Bajarildi" aria-label="Bajarildi">
          <FontAwesomeIcon icon={faCheck} />
        </button>
        <button className="btn-icon" onClick={onPostpone} title="Keyinga surish" aria-label="Keyinga surish">
          <FontAwesomeIcon icon={faClock} />
        </button>
        <button className="btn-icon" onClick={onSkip} title="O'tkazib yuborish" aria-label="O'tkazib yuborish">
          <FontAwesomeIcon icon={faForward} />
        </button>
      </footer>
    </article>
  )
}
