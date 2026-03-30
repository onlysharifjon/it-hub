import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faChevronLeft, faChevronRight, faAnglesLeft, faAnglesRight } from '@fortawesome/free-solid-svg-icons'

export default function Pagination({ meta, onPageChange }) {
  if (!meta || meta.total_pages <= 1) return null

  const { page, total_pages, total, page_size } = meta
  const from = (page - 1) * page_size + 1
  const to = Math.min(page * page_size, total)

  const pages = []
  const delta = 2
  for (let i = Math.max(1, page - delta); i <= Math.min(total_pages, page + delta); i++) {
    pages.push(i)
  }

  return (
    <div className="pagination">
      <span className="pagination-info">
        {from}–{to} / {total} ta
      </span>
      <div className="pagination-btns">
        <button className="pg-btn" onClick={() => onPageChange(1)} disabled={page === 1}>
          <FontAwesomeIcon icon={faAnglesLeft} />
        </button>
        <button className="pg-btn" onClick={() => onPageChange(page - 1)} disabled={page === 1}>
          <FontAwesomeIcon icon={faChevronLeft} />
        </button>

        {pages[0] > 1 && <span className="pg-ellipsis">…</span>}
        {pages.map(p => (
          <button
            key={p}
            className={`pg-btn ${p === page ? 'active' : ''}`}
            onClick={() => onPageChange(p)}
          >
            {p}
          </button>
        ))}
        {pages[pages.length - 1] < total_pages && <span className="pg-ellipsis">…</span>}

        <button className="pg-btn" onClick={() => onPageChange(page + 1)} disabled={page === total_pages}>
          <FontAwesomeIcon icon={faChevronRight} />
        </button>
        <button className="pg-btn" onClick={() => onPageChange(total_pages)} disabled={page === total_pages}>
          <FontAwesomeIcon icon={faAnglesRight} />
        </button>
      </div>
    </div>
  )
}
