import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
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
import { PageIntro, ViewTabs, Initials, ProgressRing } from './ui/Workspace'
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
  const [workView, setWorkView] = useState('queue')
  const [focusedKey, setFocusedKey] = useState(null)

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

  const focusPanelRef = useRef(null)

  if (err) {
    return (
      <div className="page">
        <div className="page-header"><h1><FontAwesomeIcon icon={faListCheck} className="page-icon" /> Ishlarim</h1></div>
        <ErrorState title="Ish ro'yxatini yuklab bo'lmadi" onRetry={load} />
      </div>
    )
  }

  const kpi = data?.kpi
  const daily = data?.daily
  const selectedTask = filtered.find(t => t.source_key === focusedKey) || PRIORITY_ORDER.flatMap(p => byPriority[p])[0]
  function focusTask(key) {
    setFocusedKey(key)
    if (window.matchMedia('(max-width: 900px)').matches) requestAnimationFrame(() => {
      focusPanelRef.current?.focus({ preventScroll: true })
      focusPanelRef.current?.scrollIntoView({ block: 'start', behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' })
    })
  }
  const completion = kpi?.total ? kpi.completed / kpi.total * 100 : 0

  return (
    <div className="page work-studio">
      {confirmUI}
      <PageIntro title="Ishlarim" eyebrow="Kundalik ish maydoni" description="Bir vazifaga e’tibor. Har bir aloqa — keyingi qadam." actions={<>
        {isAdmin && users.length > 0 && <select className="field-sm" value={scopeUser} aria-label="Xodim" onChange={e => { setLoading(true); setScopeUser(e.target.value) }}><option value="">Mening navbatim</option>{users.map(u => <option key={u.id} value={u.id}>{u.full_name || u.username}</option>)}</select>}
        <button className="button secondary" onClick={load} aria-label="Yangilash"><FontAwesomeIcon icon={faRotate} /></button>
        <button className="button" onClick={() => setNewTask({ title: '', reason: '', priority: 'normal', due_at: '' })}><FontAwesomeIcon icon={faPlus} /> Yangi vazifa</button>
      </>} />
      <div className="work-overview">
        <div className="work-progress"><ProgressRing value={completion} label="Vazifalar bajarilishi" /><div><span className="studio-eyebrow">Bugungi reja</span><h2>{kpi?.completed ?? '—'} <span>/ {kpi?.total ?? '—'} bajarildi</span></h2><p>{kpi?.remaining ?? '—'} ta vazifa navbatda</p></div></div>
        <div className="work-pulse"><span><FontAwesomeIcon icon={faPhone} /> Qo‘ng‘iroqlar</span><strong>{daily?.calls ?? '—'}</strong><small>{daily?.connected ?? 0} ta bog‘lanildi</small></div>
        <div className="work-pulse"><span><FontAwesomeIcon icon={faClock} /> Qayta aloqa</span><strong>{daily?.callbacks ?? '—'}</strong><small>{daily?.no_answer ?? 0} ta javobsiz</small></div>
        <button className={'work-urgent' + (prioFilter === 'critical' ? ' is-active' : '')} onClick={() => { setPrioFilter(prioFilter === 'critical' ? '' : 'critical'); setWorkView('queue') }}><span><FontAwesomeIcon icon={faTriangleExclamation} /> E’tibor talab qiladi</span><strong>{kpi?.critical ?? '—'}</strong><small>{overdue.length} ta kechikkan vazifa →</small></button>
      </div>
      <ViewTabs value={workView} onChange={setWorkView} items={[{ key: 'queue', label: 'Ish navbati', count: tasks.length }, { key: 'done', label: 'Bajarilgan', count: data?.completed?.length || 0 }]} />
      {loading ? <div className="work-loading"><Skeleton height={460} radius="16px" /></div> : workView === 'done' ? (
        <section className="studio-section"><div className="studio-section-head"><h2>Bugun bajarilgan vazifalar</h2><FontAwesomeIcon icon={faCircleCheck} /></div>
          {data?.completed?.length ? <ul className="work-completed">{data.completed.map(t => <li key={t.source_key}><span className="work-done-check"><FontAwesomeIcon icon={faCheck} /></span><div><strong>{t.title}</strong><p>{t.task_label}{t.last_note && ' · ' + t.last_note}</p></div><time>{fmtRelative(t.completed_at)}</time></li>)}</ul> : <EmptyState title="Bajarilgan vazifalar shu yerda ko‘rinadi" icon={faCircleCheck} compact />}
        </section>
      ) : <div className="work-desk">
        <section className="work-queue">
          <div className="work-queue-head"><h2>Vazifalar <span>{filtered.length}</span></h2><select className="field-sm" value={prioFilter} aria-label="Muhimlik" onChange={e => setPrioFilter(e.target.value)}><option value="">Barcha muhimliklar</option>{PRIORITY_ORDER.map(p => <option key={p} value={p}>{PRIORITY_LABEL[p]}</option>)}</select></div>
          <div className="work-types"><button className={!typeFilter ? 'is-active' : ''} onClick={() => setTypeFilter('')}>Hammasi</button>{typeCounts.map(([type, n]) => <button key={type} className={typeFilter === type ? 'is-active' : ''} onClick={() => setTypeFilter(typeFilter === type ? '' : type)} title={tasks.find(t => t.task_type === type)?.task_label}><FontAwesomeIcon icon={TYPE_ICON[type] || faListCheck} />{tasks.find(t => t.task_type === type)?.task_label}<span>{n}</span></button>)}</div>
          {filtered.length ? <div className="work-queue-list">{PRIORITY_ORDER.map(p => byPriority[p].length > 0 && <div key={p}><div className="work-priority-label"><i className={'prio-' + p} />{PRIORITY_LABEL[p]}<span>{byPriority[p].length}</span></div>{byPriority[p].map(t => <button key={t.source_key} type="button" className={'work-row' + (selectedTask?.source_key === t.source_key ? ' is-selected' : '')} aria-pressed={selectedTask?.source_key === t.source_key} onClick={() => focusTask(t.source_key)}><span className="work-row-icon"><FontAwesomeIcon icon={TYPE_ICON[t.task_type] || faListCheck} /></span><span className="work-row-copy"><strong>{t.title}</strong><span>{t.reason || t.task_label}</span></span><span className="work-row-end">{t.overdue ? <small className="tone-danger">Kechikkan</small> : <small>{t.due_at ? fmtRelative(t.due_at) : t.task_label}</small>}<span>→</span></span></button>)}</div>)}</div> : <EmptyState icon={faCircleCheck} title={tasks.length ? 'Bu filtrda vazifa yo‘q' : 'Bugun hammasi bajarilgan'} description={tasks.length ? 'Boshqa filtrni tanlang.' : 'Yangi vazifalar shu yerda ko‘rinadi.'} compact />}
        </section>
        <aside className="work-focus" ref={focusPanelRef} tabIndex={-1} aria-label="Vazifa tafsilotlari">{selectedTask ? <TaskCard key={selectedTask.source_key} task={selectedTask} onCall={() => setCallFor(selectedTask)} onDone={() => markDone(selectedTask)} onSkip={() => skip(selectedTask)} onPostpone={() => setPostponeFor({ task: selectedTask, when: '' })} /> : <div className="work-focus-empty"><FontAwesomeIcon icon={faListCheck} /><h3>Ish navbati tayyor</h3><p>Tafsilotlarni ko‘rish uchun vazifani tanlang.</p></div>}</aside>
      </div>}
      {!loading && daily && <div className="work-day-footer"><span>Bugungi natija</span><span><strong>{daily.payment_calls}</strong> to‘lov bo‘yicha aloqa</span><span><strong>{daily.absence_calls}</strong> davomat bo‘yicha aloqa</span><span><strong>{daily.completed_tasks}</strong> yopilgan vazifa</span></div>}

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
    <article className="task-focus-card">
      <header><span className="studio-eyebrow">Vazifa tafsilotlari</span><span className={'task-priority prio-' + task.priority}>{PRIORITY_LABEL[task.priority]}</span></header>
      <div className="task-person"><Initials name={task.title} /><h2>{task.title}</h2><p>{task.task_label}</p></div>
      <div className="task-reason"><span>Sabab</span><p>{task.reason || 'Vazifani ko‘rib chiqing va natijani belgilang.'}</p></div>
      <dl className="task-facts">{(m.groups?.length > 0 || m.group) && <div><dt>Guruh</dt><dd>{m.groups?.join(', ') || m.group}</dd></div>}{m.stage && <div><dt>Bosqich</dt><dd>{m.stage}</dd></div>}{task.due_at && <div><dt>Muddat</dt><dd className={task.overdue ? 'tone-danger' : ''}>{fmtDateTime(task.due_at)}</dd></div>}{phones.map((p, i) => <div key={p}><dt>{i ? 'Qo‘shimcha telefon' : 'Telefon'}</dt><dd><a href={'tel:' + p}>{p}</a></dd></div>)}</dl>
      <div className="task-primary-actions">{task.entity_id && task.phone && <a className="button" href={'tel:' + task.phone} onClick={() => setTimeout(onCall, 400)}><FontAwesomeIcon icon={faPhone} /> Qo‘ng‘iroq qilish</a>}{task.entity_id && <button className="button secondary" onClick={onCall}>Natijani yozish</button>}<button className="button secondary" onClick={onDone}><FontAwesomeIcon icon={faCheck} /> Bajarildi</button></div>
      <footer><button onClick={onPostpone}><FontAwesomeIcon icon={faClock} /> Keyinga surish</button><button onClick={onSkip}><FontAwesomeIcon icon={faForward} /> O‘tkazib yuborish</button></footer>
    </article>
  )
}
