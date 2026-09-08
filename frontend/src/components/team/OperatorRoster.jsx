import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faArrowRight, faPhone, faMagnifyingGlass } from '@fortawesome/free-solid-svg-icons'
import { Initials } from '../ui/Workspace'
import { EmptyState } from '../ui/States'

export const TEAM_ROLE_LABEL = { admin: 'Administrator', hunter: 'Menejer', call_center: 'Call-markaz', sales: 'Sotuv', teacher: 'O‘qituvchi', support_teacher: 'Yordamchi o‘qituvchi' }

export default function OperatorRoster({ operators, onOpen, query, setQuery, sort, setSort }) {
  const rows = operators.filter(op => `${op.name} ${TEAM_ROLE_LABEL[op.role] || op.role}`.toLowerCase().includes(query.toLowerCase()))
    .sort((a,b) => Number(b[sort] || 0) - Number(a[sort] || 0) || (a.name || '').localeCompare(b.name || ''))

  return <section className="operator-roster">
    <header className="operator-roster-tools">
      <div><h2>Jamoa natijalari <span>{rows.length}</span></h2><p>Har bir operatorning tanlangan davrdagi faoliyati.</p></div>
      <div className="operator-roster-filters">
        <label className="operator-search"><FontAwesomeIcon icon={faMagnifyingGlass} /><input type="search" aria-label="Operatorni qidirish" value={query} onChange={e => setQuery(e.target.value)} placeholder="Operatorni qidirish" /></label>
        <select value={sort} onChange={e => setSort(e.target.value)} aria-label="Operatorlarni saralash"><option value="calls">Qo‘ng‘iroqlar bo‘yicha</option><option value="connect_rate">Bog‘lanish bo‘yicha</option><option value="completed_tasks">Vazifalar bo‘yicha</option></select>
      </div>
    </header>
    <div className="operator-table-head" aria-hidden="true"><span>#</span><span>Operator</span><span>Bog‘lanish darajasi</span><span>Qo‘ng‘iroqlar</span><span>Bajarilgan</span><span>Lidlar</span><span /></div>
    {rows.length ? <div className="operator-rows">{rows.map((op,i) => <button type="button" className="operator-row" key={op.id} onClick={() => onOpen(op)}>
      <span className="operator-rank">{String(i + 1).padStart(2,'0')}</span>
      <span className="operator-identity"><Initials name={op.name} /><span><strong>{op.name}</strong><small>{TEAM_ROLE_LABEL[op.role] || op.role}</small></span></span>
      <span className="operator-quality"><span><b>{op.connect_rate}%</b><small>{op.connected} ta bog‘lanildi</small></span><i><i style={{ width: `${Math.max(0, Math.min(100, Number(op.connect_rate) || 0))}%` }} /></i></span>
      <span className="operator-cell"><small>Qo‘ng‘iroqlar</small><strong>{op.calls}</strong><span>{op.no_answer} javobsiz</span></span>
      <span className="operator-cell"><small>Bajarilgan</small><strong>{op.completed_tasks}</strong><span>{op.callbacks} qayta aloqa</span></span>
      <span className="operator-cell"><small>Lidlar</small><strong>{op.leads_handled}</strong><span>ta aloqa</span></span>
      <FontAwesomeIcon icon={faArrowRight} className="operator-open" />
    </button>)}</div> : <EmptyState compact icon={faPhone} title="Operator topilmadi" description="Qidiruv yoki tanlangan davrni o‘zgartiring." />}
    <footer className="operator-roster-foot"><i />Operatorni tanlab, qo‘ng‘iroqlar va bajarilgan vazifalarni ko‘ring.</footer>
  </section>
}
