import { useState } from 'react'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faTableCellsLarge, faList } from '@fortawesome/free-solid-svg-icons'

export default function Catalog({ rows, loading, error, renderCard, label, children }) {
  const [view, setView] = useState('cards')
  return <>
    <div className="catalog-toolbar">
      <span>{loading ? 'Yuklanmoqda...' : <><strong>{rows.length}</strong> {label}</>}</span>
      <div className="segmented" aria-label="Ko‘rinish">
        <button type="button" className={view === 'cards' ? 'active' : ''} aria-pressed={view === 'cards'} onClick={() => setView('cards')}><FontAwesomeIcon icon={faTableCellsLarge} /> Kartalar</button>
        <button type="button" className={view === 'table' ? 'active' : ''} aria-pressed={view === 'table'} onClick={() => setView('table')}><FontAwesomeIcon icon={faList} /> Jadval</button>
      </div>
    </div>
    {view === 'cards' && !loading && !error && rows.length > 0
      ? <div className="catalog-grid">{rows.map((row, i) => renderCard(row, i))}</div>
      : children}
  </>
}
