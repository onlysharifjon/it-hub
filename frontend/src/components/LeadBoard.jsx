import { useMemo, useState } from 'react'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faPhone, faClock, faArrowUpRightFromSquare, faCommentDots, faPlus, faInbox } from '@fortawesome/free-solid-svg-icons'
import { Initials } from './ui/Workspace'
import { EmptyState } from './ui/States'
import { fmtDateTime, fmtRelative } from '../utils/datetime'

const stageTone = stage => stage.kind === 'won' ? 'won' : stage.kind === 'lost' ? 'lost' : 'open'

export default function LeadBoard({ leads, stages, canMove, canSeeOwner, currentUser, onOpen, onDragStart, onDrop, onClaim, claimingId, onAdd }) {
  const [stageId, setStageId] = useState('all')
  const [sort, setSort] = useState('newest')
  const [dragOver, setDragOver] = useState(null)
  const [limit, setLimit] = useState(30)
  const currentStage = stages.find(s => s.id === stageId)
  const items = useMemo(() => leads.filter(l => stageId === 'all' || l.stage_id === stageId).sort((a, b) => sort === 'name' ? a.full_name.localeCompare(b.full_name) : (String(b.created_at || '').localeCompare(String(a.created_at || '')) * (sort === 'oldest' ? -1 : 1))), [leads, stageId, sort])
  const pickStage = id => { setStageId(id); setLimit(30) }
  return <div className="lead-workspace">
    <aside className="lead-stages" aria-label="Lid bosqichlari">
      <span className="studio-eyebrow">Bosqichlar</span>
      <button className={`lead-stage${stageId === 'all' ? ' is-active' : ''}`} aria-pressed={stageId === 'all'} onClick={() => pickStage('all')}><span className="lead-stage-dot all" /><span>Barcha lidlar</span><strong>{leads.length}</strong></button>
      <div className="lead-stage-divider" />
      {stages.map((s, i) => {
        const count = leads.filter(l => l.stage_id === s.id).length
        return <button key={s.id} aria-pressed={stageId === s.id} className={`lead-stage${stageId === s.id ? ' is-active' : ''}${dragOver === s.id ? ' is-drop-target' : ''}`} onClick={() => pickStage(s.id)}
          onDragOver={e => { if (canMove) { e.preventDefault(); setDragOver(s.id) } }} onDragLeave={() => setDragOver(null)} onDrop={e => { if (canMove) { e.preventDefault(); setDragOver(null); onDrop(s.id) } }}>
          <span className={`lead-stage-dot ${stageTone(s)}`} /><span>{s.name}</span><strong>{count}</strong>
        </button>
      })}
      <div className="lead-stage-note"><FontAwesomeIcon icon={faInbox} /><span>{canMove ? 'Lidni kerakli bosqichga surib o‘tkazishingiz mumkin.' : 'Bosqichni tanlab, lidlarni ko‘ring.'}</span></div>
    </aside>
    <section className="lead-inbox">
      <header className="lead-inbox-head"><div><h2>{currentStage?.name || 'Barcha lidlar'} <span>{items.length}</span></h2><p>{stageId === 'all' ? 'Yangi aloqalar va davom etayotgan suhbatlar.' : 'Ushbu bosqichdagi aloqalar.'}</p></div><select className="field-sm" aria-label="Lidlarni tartiblash" value={sort} onChange={e => setSort(e.target.value)}><option value="newest">Avval yangilari</option><option value="oldest">Avval eskilari</option><option value="name">Ism bo‘yicha</option></select></header>
      {items.length ? <div className="lead-contact-grid">{items.slice(0, limit).map((lead, index) => {
        const stage = stages.find(s => s.id === lead.stage_id)
        const owner = lead.claimed_by_name || lead.created_by_name
        return <article key={lead.id} className="lead-contact" draggable={canMove} onDragStart={() => onDragStart(lead.id)} style={{ '--item-index': Math.min(index, 8) }}>
          <button className="lead-contact-open" onClick={() => onOpen(lead)} aria-label={`${lead.full_name} — lidni ochish`}>
            <header><Initials name={lead.full_name} /><div><h3>{lead.full_name}</h3><span>{lead.course_interest || lead.interested_group_name || 'Kurs tanlanmagan'}</span></div><FontAwesomeIcon icon={faArrowUpRightFromSquare} /></header>
            <div className="lead-contact-phone"><FontAwesomeIcon icon={faPhone} />{lead.phone_display || lead.phone || 'Telefon kiritilmagan'}</div>
            <p className="lead-contact-note">{lead.next_reminder_body || lead.notes || 'Hozircha izoh qoldirilmagan.'}</p>
            <div className="lead-contact-tags"><span className={`lead-status ${stageTone(stage || {})}`}><i />{stage?.name || lead.stage_name || 'Bosqich'}</span>{lead.source_name && <span className="lead-source">{lead.source_name}</span>}</div>
            <footer><span className={lead.is_overdue ? 'tone-danger' : ''}><FontAwesomeIcon icon={faClock} />{lead.callback_at ? fmtDateTime(lead.callback_at) : fmtRelative(lead.created_at)}</span><span>{lead.comments_count > 0 && <><FontAwesomeIcon icon={faCommentDots} />{lead.comments_count}</>}</span></footer>
          </button>
          {canSeeOwner && owner && <div className="lead-owner"><Initials name={owner} /><span>{owner}</span>{lead.claimed_by_id === currentUser?.id && <small>meniki</small>}</div>}
          {lead.is_shared && !lead.claimed_by_id && canMove && <button className="lead-claim" disabled={claimingId === lead.id} onClick={() => onClaim(lead)}>{claimingId === lead.id ? 'Band qilinmoqda...' : 'Band qilish'}</button>}
        </article>
      })}{onAdd && <button className="lead-add-tile" onClick={onAdd}><span><FontAwesomeIcon icon={faPlus} /></span><strong>Yangi lid</strong><small>Yangi aloqa qo‘shish</small></button>}</div> : <EmptyState icon={faInbox} title="Bu bosqichda lidlar yo‘q" description="Boshqa bosqichni tanlang yoki yangi lid qo‘shing." />}
      {items.length > limit && <button className="button secondary lead-more" onClick={() => setLimit(n => n + 30)}>Yana {Math.min(items.length - limit, 30)} ta ko‘rsatish</button>}
    </section>
  </div>
}
