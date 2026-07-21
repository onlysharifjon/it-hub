import { useEffect, useState } from 'react'
import { toast } from 'react-hot-toast'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faPlus, faMagnifyingGlass, faPhone, faCircle,
  faPen, faTrash, faTableColumns, faList, faSliders, faXmark,
  faArrowUp, faArrowDown, faClockRotateLeft, faChartPie,
  faBell, faCheck, faClock, faTriangleExclamation,
  faInbox, faHandHolding, faShareNodes, faLink, faCopy, faClipboardList,
} from '@fortawesome/free-solid-svg-icons'
import {
  fetchLeads, createLead, moveLeadStage, deleteLead,
  fetchLeadStages, createLeadStage, updateLeadStage, reorderLeadStages, deleteLeadStage,
  fetchLeadSources, fetchLeadActivities, fetchLeadAnalytics,
  fetchReminders, createReminder, updateReminder,
  fetchNotifications, fetchUnreadCount, markNotificationRead, markAllNotificationsRead,
  claimLead, releaseLead, shareLead, fetchGroups,
  fetchIntakeForms, createIntakeForm, updateIntakeForm, deleteIntakeForm,
} from '../api'

// Bosqich rangi kaliti → hex
const COLORS = {
  sky: '#0ea5e9', indigo: '#6366f1', amber: '#d97706', violet: '#7c3aed',
  emerald: '#059669', red: '#dc2626', slate: '#64748b', purple: '#9333ea',
  teal: '#0d9488', rose: '#e11d48', blue: '#2563eb', green: '#16a34a',
  orange: '#ea580c', cyan: '#0891b2',
}
const COLOR_KEYS = Object.keys(COLORS)
const hex = (c) => COLORS[c] || COLORS.slate

const KIND_LABEL = { lead: 'Jarayon', won: 'Yutuq', lost: 'Yo‘qotish' }

const COURSES = [
  { key: '',           label: 'Kurs tanlang' },
  { key: 'foundation', label: 'Foundation' },
  { key: 'frontend',   label: 'Frontend' },
  { key: 'backend',    label: 'Backend' },
]

const EMPTY_FORM = {
  full_name: '', phone: '', course_interest: '', source_id: '', notes: '',
  date_of_birth: '', parent_phone: '', parent2_phone: '', interested_group_id: '',
}
const fmtDate = (s) => s ? new Date(s).toLocaleString('uz-UZ', { dateStyle: 'short', timeStyle: 'short' }) : ''

export default function Leads({ currentUser }) {
  const role = currentUser?.role
  const isAdmin = role === 'admin'
  // Hunter va Sales — faqat o'z lidlari doirasida ishlaydi (backend ham shunday filtrlaydi)
  const isHunter = role === 'hunter' || role === 'sales'
  const canAddLead = isHunter || role === 'call_center' || isAdmin
  const canMove    = isHunter || role === 'call_center' || isAdmin
  const canDelete  = isHunter || isAdmin

  const [view, setView]     = useState('kanban')     // 'kanban' | 'list'
  const [leads, setLeads]   = useState([])
  const [stages, setStages] = useState([])
  const [sources, setSources] = useState([])
  const [loading, setLoading] = useState(false)
  const [search, setSearch]   = useState('')
  const [filterSource, setFilterSource] = useState('')

  const [addModal, setAddModal] = useState(false)
  const [form, setForm]   = useState(EMPTY_FORM)
  const [saving, setSaving] = useState(false)

  const [drawer, setDrawer]         = useState(null)   // lead object
  const [activities, setActivities] = useState([])
  const [stageModal, setStageModal] = useState(false)
  const [formModal, setFormModal]   = useState(false)
  const [poolMode, setPoolMode]     = useState(false)
  const [groups, setGroups]         = useState([])

  const [dragId, setDragId]       = useState(null)
  const [dragOver, setDragOver]   = useState(null)

  useEffect(() => { boot() }, [])

  async function boot() {
    setLoading(true)
    try {
      const [st, src] = await Promise.all([fetchLeadStages(), fetchLeadSources()])
      setStages(st)
      setSources(src)
      fetchGroups({ is_active: true }).then(g => setGroups(g.items || g || [])).catch(() => {})
      await load(false)
    } catch { toast.error("Yuklab bo'lmadi") }
    finally { setLoading(false) }
  }

  async function load(pool = poolMode) {
    const data = await fetchLeads({
      search: search || undefined,
      source_id: filterSource || undefined,
      pool: pool || undefined,
    })
    setLeads(data)
  }
  function togglePool() {
    const next = !poolMode
    setPoolMode(next)
    setLoading(true)
    load(next).catch(() => toast.error("Yuklab bo'lmadi")).finally(() => setLoading(false))
  }
  async function reload() {
    setLoading(true)
    try { await load() } catch { toast.error("Yuklab bo'lmadi") } finally { setLoading(false) }
  }
  async function refreshStages() { try { setStages(await fetchLeadStages()) } catch {} }

  // ── Add lead ──
  async function handleAdd() {
    if (!form.full_name.trim() || !form.phone.trim()) return toast.error('Ism va telefon majburiy')
    setSaving(true)
    try {
      await createLead({
        full_name: form.full_name.trim(),
        phone: form.phone.trim(),
        course_interest: form.course_interest || null,
        source_id: form.source_id ? Number(form.source_id) : null,
        notes: form.notes || null,
        date_of_birth: form.date_of_birth || null,
        parent_phone: form.parent_phone || null,
        parent2_phone: form.parent2_phone || null,
        interested_group_id: form.interested_group_id ? Number(form.interested_group_id) : null,
      })
      toast.success("Lid qo'shildi")
      setAddModal(false); setForm(EMPTY_FORM); reload()
    } catch (e) { toast.error(e.message) } finally { setSaving(false) }
  }

  // ── Claim / release ──
  async function handleClaim(lead) {
    try {
      const updated = await claimLead(lead.id)
      toast.success('Lid band qilindi')
      if (poolMode) setLeads(ls => ls.filter(l => l.id !== lead.id))
      else setLeads(ls => ls.map(l => l.id === updated.id ? updated : l))
      if (drawer?.id === lead.id) setDrawer(updated)
    } catch (e) { toast.error(e.message) }
  }
  async function handleRelease(lead) {
    try {
      const updated = await releaseLead(lead.id)
      toast.success('Havzaga qaytarildi')
      setLeads(ls => ls.map(l => l.id === updated.id ? updated : l))
      if (drawer?.id === lead.id) setDrawer(updated)
    } catch (e) { toast.error(e.message) }
  }

  async function handleDelete(lead) {
    if (!confirm(`"${lead.full_name}" lidini o'chirish?`)) return
    try { await deleteLead(lead.id); toast.success("O'chirildi"); setDrawer(null); reload() }
    catch (e) { toast.error(e.message) }
  }

  // ── Move stage (drag or button) ──
  async function moveTo(lead, stageId, extra = {}) {
    if (lead.stage_id === stageId && !Object.keys(extra).length) return
    const prev = leads
    setLeads(ls => ls.map(l => l.id === lead.id ? { ...l, stage_id: stageId } : l))
    try {
      const updated = await moveLeadStage(lead.id, { stage_id: stageId, ...extra })
      setLeads(ls => ls.map(l => l.id === updated.id ? updated : l))
      if (drawer?.id === lead.id) { setDrawer(updated); openActivities(updated.id) }
    } catch (e) { setLeads(prev); toast.error(e.message) }
  }

  function onDrop(stageId) {
    setDragOver(null)
    const lead = leads.find(l => l.id === dragId)
    setDragId(null)
    if (lead) moveTo(lead, stageId)
  }

  // ── Drawer / timeline ──
  async function openDrawer(lead) {
    setDrawer(lead)
    openActivities(lead.id)
  }
  async function openActivities(id) {
    setActivities([])
    try { setActivities(await fetchLeadActivities(id)) } catch {}
  }

  const visibleStages = stages.filter(s => !s.is_archived)
  const byStage = (sid) => leads.filter(l => l.stage_id === sid)

  return (
    <div className="page">
      <div className="page-header">
        <h1>Lidlar</h1>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <NotificationBell />
          {isAdmin && (
            <button className="button secondary" onClick={() => setFormModal(true)}>
              <FontAwesomeIcon icon={faClipboardList} /> Formalar
            </button>
          )}
          {isAdmin && (
            <button className="button secondary" onClick={() => setStageModal(true)}>
              <FontAwesomeIcon icon={faSliders} /> Bosqichlar
            </button>
          )}
          {canAddLead && (
            <button className="button primary" onClick={() => setAddModal(true)}>
              <FontAwesomeIcon icon={faPlus} /> Lid qo'shish
            </button>
          )}
        </div>
      </div>

      {/* Toolbar */}
      <div className="toolbar">
        <div className="search-wrap">
          <FontAwesomeIcon icon={faMagnifyingGlass} className="search-icon" />
          <input className="search-input" placeholder="Ism yoki telefon..."
            value={search} onChange={e => setSearch(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && reload()} />
        </div>
        <select className="field" style={{ maxWidth: 180 }} value={filterSource}
          onChange={e => { setFilterSource(e.target.value); setTimeout(reload, 0) }}>
          <option value="">Barcha manbalar</option>
          {sources.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
        </select>
        <button className={`df-preset${poolMode ? ' active' : ''}`} onClick={togglePool} title="Band qilinmagan umumiy lidlar">
          <FontAwesomeIcon icon={faInbox} /> Umumiy havza
        </button>
        <span style={{ flex: 1 }} />
        <div className="view-toggle">
          <button className={view === 'kanban' ? 'active' : ''} onClick={() => setView('kanban')}>
            <FontAwesomeIcon icon={faTableColumns} /> Board
          </button>
          <button className={view === 'list' ? 'active' : ''} onClick={() => setView('list')}>
            <FontAwesomeIcon icon={faList} /> Ro'yxat
          </button>
          <button className={view === 'analytics' ? 'active' : ''} onClick={() => setView('analytics')}>
            <FontAwesomeIcon icon={faChartPie} /> Analitika
          </button>
        </div>
        <span className="toolbar-count">Jami: <strong>{leads.length}</strong></span>
      </div>

      {view === 'analytics' ? (
        <Analytics />
      ) : loading ? (
        <div className="muted center py-8">Yuklanmoqda...</div>
      ) : view === 'kanban' ? (
        <div className="kanban">
          {visibleStages.map(stage => {
            const items = byStage(stage.id)
            return (
              <div key={stage.id}
                className={`kanban-col${dragOver === stage.id ? ' drag-over' : ''}`}
                onDragOver={e => { if (canMove) { e.preventDefault(); setDragOver(stage.id) } }}
                onDragLeave={() => setDragOver(o => o === stage.id ? null : o)}
                onDrop={() => canMove && onDrop(stage.id)}>
                <div className="kanban-col-head">
                  <span className="dot" style={{ background: hex(stage.color) }} />
                  <span className="title">{stage.name}</span>
                  <span className="count">{items.length}</span>
                </div>
                <div className="kanban-col-body">
                  {items.map(lead => (
                    <div key={lead.id}
                      className={`kanban-card${dragId === lead.id ? ' dragging' : ''}`}
                      style={{ '--card-accent': hex(stage.color) }}
                      draggable={canMove}
                      onDragStart={() => setDragId(lead.id)}
                      onDragEnd={() => { setDragId(null); setDragOver(null) }}
                      onClick={() => openDrawer(lead)}>
                      <div className="kc-name">
                        {lead.full_name}
                        {lead.is_shared && !lead.claimed_by_id && <span className="kc-badge pool" style={{ marginLeft: 6 }}>havza</span>}
                        {lead.claimed_by_id === currentUser?.id && <span className="kc-badge mine" style={{ marginLeft: 6 }}>meniki</span>}
                      </div>
                      <div className="kc-row"><FontAwesomeIcon icon={faPhone} /> {lead.phone}</div>
                      <div className="kc-meta">
                        {lead.course_interest && <span className="kc-tag">{lead.course_interest}</span>}
                        {lead.source_name && <span className="kc-tag">{lead.source_name}</span>}
                        {lead.interested_group_name && <span className="kc-tag">{lead.interested_group_name}</span>}
                        {!isHunter && lead.claimed_by_name && <span className="kc-tag">👤 {lead.claimed_by_name}</span>}
                        {!isHunter && !lead.claimed_by_name && lead.created_by_name && <span className="kc-tag">{lead.created_by_name}</span>}
                      </div>
                      {lead.callback_at && (
                        <div className="kc-row kc-callback" style={{ marginTop: 6 }}>
                          <FontAwesomeIcon icon={faClockRotateLeft} /> {fmtDate(lead.callback_at)}
                        </div>
                      )}
                      {lead.is_shared && !lead.claimed_by_id && canMove && (
                        <button className="kc-claim" onClick={e => { e.stopPropagation(); handleClaim(lead) }}>
                          <FontAwesomeIcon icon={faHandHolding} /> Band qilish
                        </button>
                      )}
                    </div>
                  ))}
                  {items.length === 0 && <div className="kanban-empty">— bo'sh —</div>}
                </div>
              </div>
            )
          })}
        </div>
      ) : (
        <ListView leads={leads} stages={stages} isHunter={isHunter}
          canDelete={canDelete} onOpen={openDrawer} onDelete={handleDelete} />
      )}

      {/* Add Lead Modal */}
      {addModal && (
        <div className="modal-overlay" onClick={() => setAddModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Yangi lid</h3>
              <button className="modal-close" onClick={() => setAddModal(false)}>✕</button>
            </div>
            <div className="modal-body">
              <label>Ism Familiya *</label>
              <input className="field" value={form.full_name}
                onChange={e => setForm(p => ({ ...p, full_name: e.target.value }))} placeholder="To'liq ism" />
              <label><FontAwesomeIcon icon={faPhone} /> Telefon *</label>
              <input className="field" value={form.phone}
                onChange={e => setForm(p => ({ ...p, phone: e.target.value }))} placeholder="+998901234567" />
              <label>Qiziqayotgan kurs</label>
              <select className="field" value={form.course_interest}
                onChange={e => setForm(p => ({ ...p, course_interest: e.target.value }))}>
                {COURSES.map(c => <option key={c.key} value={c.key}>{c.label}</option>)}
              </select>
              <label>Manba</label>
              <select className="field" value={form.source_id}
                onChange={e => setForm(p => ({ ...p, source_id: e.target.value }))}>
                <option value="">Manba tanlang</option>
                {sources.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
              <div style={{ display: 'flex', gap: 10 }}>
                <div style={{ flex: 1 }}>
                  <label>Tug'ilgan sana</label>
                  <input className="field" type="date" value={form.date_of_birth}
                    onChange={e => setForm(p => ({ ...p, date_of_birth: e.target.value }))} />
                </div>
                <div style={{ flex: 1 }}>
                  <label>Qiziqqan guruh</label>
                  <select className="field" value={form.interested_group_id}
                    onChange={e => setForm(p => ({ ...p, interested_group_id: e.target.value }))}>
                    <option value="">—</option>
                    {groups.map(g => <option key={g.id} value={g.id}>{g.name}</option>)}
                  </select>
                </div>
              </div>
              <div style={{ display: 'flex', gap: 10 }}>
                <div style={{ flex: 1 }}>
                  <label>Ota-ona telefoni</label>
                  <input className="field" value={form.parent_phone}
                    onChange={e => setForm(p => ({ ...p, parent_phone: e.target.value }))} placeholder="+998..." />
                </div>
                <div style={{ flex: 1 }}>
                  <label>2-telefon</label>
                  <input className="field" value={form.parent2_phone}
                    onChange={e => setForm(p => ({ ...p, parent2_phone: e.target.value }))} placeholder="+998..." />
                </div>
              </div>
              <label>Izoh</label>
              <textarea className="field" rows={2} value={form.notes}
                onChange={e => setForm(p => ({ ...p, notes: e.target.value }))} placeholder="Qo'shimcha ma'lumot..." />
            </div>
            <div className="modal-footer">
              <button className="button secondary" onClick={() => setAddModal(false)}>Bekor</button>
              <button className="button primary" onClick={handleAdd} disabled={saving}>
                {saving ? 'Saqlanmoqda...' : "Qo'shish"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Lead drawer */}
      {drawer && (
        <LeadDrawer
          lead={drawer} stages={visibleStages} activities={activities}
          canMove={canMove} canDelete={canDelete} currentUser={currentUser}
          onClose={() => setDrawer(null)}
          onMove={(sid, extra) => moveTo(drawer, sid, extra)}
          onClaim={() => handleClaim(drawer)}
          onRelease={() => handleRelease(drawer)}
          onDelete={() => handleDelete(drawer)} />
      )}

      {/* Stage management */}
      {stageModal && (
        <StageManager stages={stages} onClose={() => setStageModal(false)}
          onChanged={refreshStages} />
      )}

      {/* Intake form management */}
      {formModal && (
        <IntakeFormManager sources={sources} onClose={() => setFormModal(false)} />
      )}
    </div>
  )
}

// ── List (table) view ──────────────────────────────────────────────────────
function ListView({ leads, stages, isHunter, canDelete, onOpen, onDelete }) {
  const stageOf = (id) => stages.find(s => s.id === id)
  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            <th>#</th><th>Ism Familiya</th><th><FontAwesomeIcon icon={faPhone} /> Telefon</th>
            <th>Manba</th><th>Bosqich</th><th>Vaqt / Izoh</th>
            {!isHunter && <th>Hunter</th>}<th>Amallar</th>
          </tr>
        </thead>
        <tbody>
          {leads.map((lead, i) => {
            const st = stageOf(lead.stage_id)
            const c = hex(st?.color)
            return (
              <tr key={lead.id} style={{ cursor: 'pointer' }} onClick={() => onOpen(lead)}>
                <td className="text-muted">{i + 1}</td>
                <td><strong>{lead.full_name}</strong></td>
                <td>{lead.phone}</td>
                <td>{lead.source_name ? <span className="badge">{lead.source_name}</span> : <span className="text-muted">—</span>}</td>
                <td>
                  <span className="lead-status-badge" style={{ background: c + '22', color: c }}>
                    {st?.name || lead.status}
                  </span>
                </td>
                <td style={{ fontSize: 12, maxWidth: 200 }}>
                  {lead.callback_at && <div style={{ color: 'var(--warning)', fontWeight: 600 }}>{fmtDate(lead.callback_at)}</div>}
                  {lead.notes && <div className="text-muted" style={{ marginTop: 2 }}>{lead.notes}</div>}
                </td>
                {!isHunter && <td className="text-muted" style={{ fontSize: 12 }}>{lead.created_by_name || '—'}</td>}
                <td className="actions" onClick={e => e.stopPropagation()}>
                  <button className="btn-icon" title="Ochish" onClick={() => onOpen(lead)}><FontAwesomeIcon icon={faPen} /></button>
                  {canDelete && <button className="btn-icon danger" title="O'chirish" onClick={() => onDelete(lead)}><FontAwesomeIcon icon={faTrash} /></button>}
                </td>
              </tr>
            )
          })}
          {leads.length === 0 && (
            <tr><td colSpan={isHunter ? 7 : 8} className="muted center py-4">Lidlar topilmadi</td></tr>
          )}
        </tbody>
      </table>
    </div>
  )
}

// ── Lead detail drawer with timeline ───────────────────────────────────────
function LeadDrawer({ lead, stages, activities, canMove, canDelete, currentUser, onClose, onMove, onClaim, onRelease, onDelete }) {
  const [cb, setCb] = useState(lead.callback_at ? lead.callback_at.slice(0, 16) : '')
  const [reminders, setReminders] = useState([])
  const [remDue, setRemDue] = useState('')
  const [remBody, setRemBody] = useState('')
  const [remBusy, setRemBusy] = useState(false)

  useEffect(() => { loadReminders() }, [lead.id])
  async function loadReminders() {
    try { setReminders(await fetchReminders({ lead_id: lead.id })) } catch {}
  }
  async function addReminder() {
    if (!remDue) return toast.error('Vaqtni tanlang')
    setRemBusy(true)
    try {
      await createReminder({ lead_id: lead.id, due_at: new Date(remDue).toISOString(), body: remBody || null, kind: 'call' })
      setRemDue(''); setRemBody(''); loadReminders(); toast.success("Eslatma qo'shildi")
    } catch (e) { toast.error(e.message) } finally { setRemBusy(false) }
  }
  async function doneReminder(r) {
    try { await updateReminder(r.id, { status: 'done' }); loadReminders() } catch (e) { toast.error(e.message) }
  }

  return (
    <div className="drawer-overlay" onClick={onClose}>
      <div className="drawer" onClick={e => e.stopPropagation()}>
        <div className="drawer-head">
          <h3>{lead.full_name}</h3>
          <span style={{ flex: 1 }} />
          {canDelete && <button className="btn-icon danger" title="O'chirish" onClick={onDelete}><FontAwesomeIcon icon={faTrash} /></button>}
          <button className="modal-close" onClick={onClose}><FontAwesomeIcon icon={faXmark} /></button>
        </div>
        <div className="drawer-body">
          <div className="kc-row" style={{ marginBottom: 6 }}><FontAwesomeIcon icon={faPhone} /> {lead.phone}</div>
          <div className="kc-meta" style={{ marginBottom: 12 }}>
            {lead.course_interest && <span className="kc-tag">{lead.course_interest}</span>}
            {lead.source_name && <span className="kc-tag">Manba: {lead.source_name}</span>}
            {lead.interested_group_name && <span className="kc-tag">Guruh: {lead.interested_group_name}</span>}
            {lead.claimed_by_name && <span className="kc-tag">👤 {lead.claimed_by_name}</span>}
            {lead.created_by_name && <span className="kc-tag">Yaratdi: {lead.created_by_name}</span>}
          </div>

          {/* Rich fields */}
          {(lead.parent_phone || lead.parent2_phone || lead.date_of_birth) && (
            <div className="kc-meta" style={{ marginBottom: 14, flexDirection: 'column', alignItems: 'flex-start', gap: 3 }}>
              {lead.date_of_birth && <span className="text-muted" style={{ fontSize: 12.5 }}>🎂 {lead.date_of_birth}</span>}
              {lead.parent_phone && <span className="text-muted" style={{ fontSize: 12.5 }}>👪 {lead.parent_phone}</span>}
              {lead.parent2_phone && <span className="text-muted" style={{ fontSize: 12.5 }}>📞 {lead.parent2_phone}</span>}
            </div>
          )}

          {/* Claim / release */}
          {canMove && (
            <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
              {lead.is_shared && !lead.claimed_by_id && (
                <button className="button primary" style={{ flex: 1, justifyContent: 'center' }} onClick={onClaim}>
                  <FontAwesomeIcon icon={faHandHolding} /> Band qilish
                </button>
              )}
              {lead.claimed_by_id && (lead.claimed_by_id === currentUser?.id || currentUser?.role === 'admin') && (
                <button className="button secondary" style={{ flex: 1, justifyContent: 'center' }} onClick={onRelease}>
                  <FontAwesomeIcon icon={faShareNodes} /> Havzaga qaytarish
                </button>
              )}
            </div>
          )}

          {canMove && (
            <>
              <label>Bosqich</label>
              <div className="leads-status-grid" style={{ marginBottom: 14 }}>
                {stages.map(s => {
                  const on = s.id === lead.stage_id
                  const c = hex(s.color)
                  return (
                    <button key={s.id}
                      className={`leads-status-opt${on ? ' selected' : ''}`}
                      style={on ? { background: c + '18', borderColor: c, color: c } : {}}
                      onClick={() => onMove(s.id, cb ? { callback_at: new Date(cb).toISOString() } : {})}>
                      <FontAwesomeIcon icon={faCircle} style={{ color: c, fontSize: 8 }} />
                      {s.name}
                    </button>
                  )
                })}
              </div>
              <label>Kelish / qayta ring vaqti</label>
              <input className="field" type="datetime-local" value={cb}
                onChange={e => setCb(e.target.value)}
                onBlur={() => cb && onMove(lead.stage_id, { callback_at: new Date(cb).toISOString() })} />
            </>
          )}

          {lead.notes && (
            <div style={{ marginTop: 14 }}>
              <label>Izoh</label>
              <div className="text-muted" style={{ fontSize: 13 }}>{lead.notes}</div>
            </div>
          )}

          {/* Reminders */}
          <h4 style={{ margin: '22px 0 10px' }}><FontAwesomeIcon icon={faClock} /> Eslatmalar</h4>
          {reminders.map(r => (
            <div key={r.id} className={`rem-item${r.is_overdue ? ' overdue' : ''}${r.status !== 'pending' ? ' done' : ''}`}>
              <FontAwesomeIcon icon={r.is_overdue ? faTriangleExclamation : faClock} style={{ marginTop: 3 }} />
              <div style={{ flex: 1 }}>
                <div className="rem-when">{fmtDate(r.snoozed_until || r.due_at)}</div>
                {r.body && <div className="text-muted" style={{ fontSize: 12 }}>{r.body}</div>}
              </div>
              {r.status === 'pending' && (
                <button className="btn-icon" title="Bajarildi" onClick={() => doneReminder(r)}>
                  <FontAwesomeIcon icon={faCheck} />
                </button>
              )}
            </div>
          ))}
          {reminders.length === 0 && <div className="muted" style={{ fontSize: 13 }}>Eslatma yo'q</div>}
          {canMove && (
            <div style={{ display: 'flex', gap: 6, marginTop: 10, flexWrap: 'wrap' }}>
              <input className="field" type="datetime-local" style={{ flex: 1, minWidth: 150 }}
                value={remDue} onChange={e => setRemDue(e.target.value)} />
              <input className="field" style={{ flex: 1, minWidth: 120 }} placeholder="Izoh"
                value={remBody} onChange={e => setRemBody(e.target.value)} />
              <button className="button primary" onClick={addReminder} disabled={remBusy}>
                <FontAwesomeIcon icon={faPlus} />
              </button>
            </div>
          )}

          <h4 style={{ margin: '22px 0 12px' }}><FontAwesomeIcon icon={faClockRotateLeft} /> Tarix</h4>
          {activities.length === 0 ? (
            <div className="muted" style={{ fontSize: 13 }}>Hozircha yozuv yo'q</div>
          ) : (
            <ul className="timeline">
              {activities.map(a => (
                <li key={a.id}>
                  <div className="tl-desc">{a.description}</div>
                  <div className="tl-meta">{a.author_name || 'Tizim'} · {fmtDate(a.created_at)}</div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Stage management (admin) ───────────────────────────────────────────────
function StageManager({ stages, onClose, onChanged }) {
  const [list, setList] = useState(stages)
  const [name, setName] = useState('')
  const [color, setColor] = useState('sky')
  const [kind, setKind] = useState('lead')
  const [busy, setBusy] = useState(false)

  async function refresh() { const s = await fetchLeadStages(); setList(s); onChanged?.() }

  async function add() {
    if (!name.trim()) return toast.error('Nom kiriting')
    setBusy(true)
    try { await createLeadStage({ name: name.trim(), color, kind, icon: 'circle' }); setName(''); await refresh(); toast.success("Qo'shildi") }
    catch (e) { toast.error(e.message) } finally { setBusy(false) }
  }
  async function patch(s, data) {
    try { await updateLeadStage(s.id, data); await refresh() } catch (e) { toast.error(e.message) }
  }
  async function remove(s) {
    if (!confirm(`"${s.name}" bosqichini o'chirish?`)) return
    try { await deleteLeadStage(s.id); await refresh() } catch (e) { toast.error(e.message) }
  }
  async function move(idx, dir) {
    const arr = [...list]
    const j = idx + dir
    if (j < 0 || j >= arr.length) return
    ;[arr[idx], arr[j]] = [arr[j], arr[idx]]
    setList(arr)
    try { await reorderLeadStages(arr.map(s => s.id)); onChanged?.() } catch (e) { toast.error(e.message); refresh() }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: 560 }}>
        <div className="modal-header">
          <h3>Pipeline bosqichlari</h3>
          <button className="modal-close" onClick={onClose}>✕</button>
        </div>
        <div className="modal-body">
          {list.map((s, i) => (
            <div key={s.id} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
              <span className="dot" style={{ width: 12, height: 12, borderRadius: '50%', background: hex(s.color), flex: 'none' }} />
              <strong style={{ flex: 1 }}>{s.name}</strong>
              <span className="kc-tag">{KIND_LABEL[s.kind]}</span>
              <span className="text-muted" style={{ fontSize: 12 }}>{s.lead_count} lid</span>
              <button className="btn-icon" disabled={i === 0} onClick={() => move(i, -1)}><FontAwesomeIcon icon={faArrowUp} /></button>
              <button className="btn-icon" disabled={i === list.length - 1} onClick={() => move(i, 1)}><FontAwesomeIcon icon={faArrowDown} /></button>
              <button className="btn-icon danger" onClick={() => remove(s)}><FontAwesomeIcon icon={faTrash} /></button>
            </div>
          ))}

          <div style={{ marginTop: 16 }}>
            <label>Yangi bosqich</label>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
              <input className="field" style={{ flex: 1, minWidth: 140 }} value={name}
                onChange={e => setName(e.target.value)} placeholder="Bosqich nomi" />
              <select className="field" style={{ width: 130 }} value={kind} onChange={e => setKind(e.target.value)}>
                <option value="lead">Jarayon</option>
                <option value="won">Yutuq</option>
                <option value="lost">Yo'qotish</option>
              </select>
            </div>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', margin: '10px 0' }}>
              {COLOR_KEYS.map(c => (
                <button key={c} onClick={() => setColor(c)}
                  title={c}
                  style={{
                    width: 24, height: 24, borderRadius: '50%', background: hex(c),
                    border: color === c ? '3px solid var(--text)' : '2px solid var(--border)',
                    cursor: 'pointer',
                  }} />
              ))}
            </div>
            <button className="button primary" onClick={add} disabled={busy}>
              <FontAwesomeIcon icon={faPlus} /> Bosqich qo'shish
            </button>
          </div>
        </div>
        <div className="modal-footer">
          <button className="button secondary" onClick={onClose}>Yopish</button>
        </div>
      </div>
    </div>
  )
}

// ── Notifications bell ──────────────────────────────────────────────────────
function NotificationBell() {
  const [open, setOpen] = useState(false)
  const [items, setItems] = useState([])
  const [count, setCount] = useState(0)

  useEffect(() => {
    refreshCount()
    const t = setInterval(refreshCount, 30000)
    return () => clearInterval(t)
  }, [])

  async function refreshCount() {
    try { const r = await fetchUnreadCount(); setCount(r.count || 0) } catch {}
  }
  async function toggle() {
    const next = !open
    setOpen(next)
    if (next) {
      try { setItems(await fetchNotifications()) } catch {}
    }
  }
  async function openItem(n) {
    if (!n.is_read) {
      try { await markNotificationRead(n.id); refreshCount() } catch {}
    }
    setItems(list => list.map(x => x.id === n.id ? { ...x, is_read: true } : x))
  }
  async function readAll() {
    try { await markAllNotificationsRead(); setItems(list => list.map(x => ({ ...x, is_read: true }))); setCount(0) } catch {}
  }

  return (
    <div className="bell-wrap">
      <button className="bell-btn" onClick={toggle} title="Bildirishnomalar">
        <FontAwesomeIcon icon={faBell} />
        {count > 0 && <span className="bell-badge">{count > 99 ? '99+' : count}</span>}
      </button>
      {open && (
        <>
          <div style={{ position: 'fixed', inset: 0, zIndex: 40 }} onClick={() => setOpen(false)} />
          <div className="notif-dropdown">
            <div className="notif-head">
              <h4>Bildirishnomalar</h4>
              <button className="df-preset" onClick={readAll}>Hammasini o'qildi</button>
            </div>
            {items.length === 0 && <div className="muted center py-4" style={{ fontSize: 13 }}>Bo'sh</div>}
            {items.map(n => (
              <div key={n.id} className={`notif-item${n.is_read ? '' : ' unread'}`} onClick={() => openItem(n)}>
                <div className="ni-title">{n.title}</div>
                {n.body && <div className="ni-body">{n.body}</div>}
                <div className="ni-time">{fmtDate(n.created_at)}</div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}

// ── Analytics view ──────────────────────────────────────────────────────────
function Analytics() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => { (async () => {
    try { setData(await fetchLeadAnalytics()) } catch { toast.error("Yuklab bo'lmadi") } finally { setLoading(false) }
  })() }, [])

  if (loading) return <div className="muted center py-8">Yuklanmoqda...</div>
  if (!data) return null
  const maxCount = Math.max(1, ...data.distribution.map(d => d.count))

  return (
    <div>
      <div className="analytics-tiles">
        <div className="a-tile"><div className="a-label">Jami lidlar</div><div className="a-value">{data.total}</div></div>
        <div className="a-tile"><div className="a-label">Ro'yxatdan o'tgan</div><div className="a-value" style={{ color: COLORS.emerald }}>{data.won}</div></div>
        <div className="a-tile"><div className="a-label">Yo'qotilgan</div><div className="a-value" style={{ color: COLORS.red }}>{data.lost}</div></div>
        <div className="a-tile"><div className="a-label">Konversiya</div><div className="a-value" style={{ color: COLORS.indigo }}>{data.conversion}%</div></div>
      </div>

      <div className="analytics-grid">
        <div className="panel-card">
          <h4>Bosqichlar bo'yicha taqsimot</h4>
          {data.distribution.map(d => (
            <div key={d.slug} className="funnel-row">
              <div className="fr-top">
                <span>{d.name}</span>
                <span className="text-muted">{d.count} · {d.percentage}%</span>
              </div>
              <div className="funnel-bar">
                <span style={{ width: `${(d.count / maxCount) * 100}%`, background: hex(d.color) }} />
              </div>
            </div>
          ))}
        </div>

        <div className="panel-card">
          <h4>Manba bo'yicha konversiya</h4>
          {data.sources.length === 0 ? (
            <div className="muted" style={{ fontSize: 13 }}>Ma'lumot yo'q</div>
          ) : (
            <table className="src-table">
              <thead><tr><th>Manba</th><th className="num">Lidlar</th><th className="num">Ro'yxat</th><th className="num">Konv.</th></tr></thead>
              <tbody>
                {data.sources.map(s => {
                  const good = s.conversion_rate >= 30
                  return (
                    <tr key={s.source}>
                      <td>{s.source}</td>
                      <td className="num">{s.total}</td>
                      <td className="num">{s.enrolled}</td>
                      <td className="num">
                        <span className="conv-pill" style={{
                          background: (good ? COLORS.emerald : COLORS.amber) + '22',
                          color: good ? COLORS.emerald : COLORS.amber,
                        }}>{s.conversion_rate}%</span>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Intake form manager (admin) ─────────────────────────────────────────────
function IntakeFormManager({ sources, onClose }) {
  const [list, setList] = useState([])
  const [name, setName] = useState('')
  const [title, setTitle] = useState('')
  const [desc, setDesc] = useState('')
  const [sourceId, setSourceId] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => { refresh() }, [])
  async function refresh() { try { setList(await fetchIntakeForms()) } catch {} }

  const linkFor = (slug) => `${window.location.origin}/#intake/${slug}`

  async function add() {
    if (!name.trim()) return toast.error('Nom kiriting')
    setBusy(true)
    try {
      await createIntakeForm({
        name: name.trim(), title: title.trim() || null,
        description: desc.trim() || null, source_id: sourceId ? Number(sourceId) : null,
      })
      setName(''); setTitle(''); setDesc(''); setSourceId(''); await refresh(); toast.success("Forma yaratildi")
    } catch (e) { toast.error(e.message) } finally { setBusy(false) }
  }
  async function toggle(f) {
    try { await updateIntakeForm(f.id, { is_active: !f.is_active }); refresh() } catch (e) { toast.error(e.message) }
  }
  async function remove(f) {
    if (!confirm(`"${f.name}" formasini o'chirish?`)) return
    try { await deleteIntakeForm(f.id); refresh() } catch (e) { toast.error(e.message) }
  }
  async function copy(slug) {
    try { await navigator.clipboard.writeText(linkFor(slug)); toast.success('Havola nusxalandi') }
    catch { toast.error('Nusxalab bo\'lmadi') }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: 600 }}>
        <div className="modal-header">
          <h3>Ommaviy qabul formalari</h3>
          <button className="modal-close" onClick={onClose}>✕</button>
        </div>
        <div className="modal-body">
          {list.length === 0 && <div className="muted" style={{ fontSize: 13 }}>Hozircha forma yo'q</div>}
          {list.map(f => (
            <div key={f.id} className={`intake-row${f.is_active ? '' : ' ir-off'}`}>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div className="ir-name">{f.name} {!f.is_active && <span className="text-muted">(o'chiq)</span>}</div>
                <div className="ir-link"><FontAwesomeIcon icon={faLink} /> {linkFor(f.slug)}</div>
                <div className="text-muted" style={{ fontSize: 11.5 }}>{f.submissions} ta ariza · manba: {f.source_name || '—'}</div>
              </div>
              <button className="btn-icon" title="Havolani nusxalash" onClick={() => copy(f.slug)}><FontAwesomeIcon icon={faCopy} /></button>
              <button className="df-preset" onClick={() => toggle(f)}>{f.is_active ? "O'chirish" : 'Yoqish'}</button>
              <button className="btn-icon danger" onClick={() => remove(f)}><FontAwesomeIcon icon={faTrash} /></button>
            </div>
          ))}

          <div style={{ marginTop: 18 }}>
            <label>Yangi forma</label>
            <input className="field" value={name} onChange={e => setName(e.target.value)} placeholder="Forma nomi (ichki)" />
            <label>Sarlavha (formada ko'rinadi)</label>
            <input className="field" value={title} onChange={e => setTitle(e.target.value)} placeholder="Masalan: Minar Academy — Qabul" />
            <label>Tavsif</label>
            <textarea className="field" rows={2} value={desc} onChange={e => setDesc(e.target.value)} placeholder="Ariza qoldiring, biz bog'lanamiz" />
            <label>Manba</label>
            <select className="field" value={sourceId} onChange={e => setSourceId(e.target.value)}>
              <option value="">Manba tanlang</option>
              {sources.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
            <button className="button primary" style={{ marginTop: 12 }} onClick={add} disabled={busy}>
              <FontAwesomeIcon icon={faPlus} /> Forma yaratish
            </button>
          </div>
        </div>
        <div className="modal-footer">
          <button className="button secondary" onClick={onClose}>Yopish</button>
        </div>
      </div>
    </div>
  )
}
