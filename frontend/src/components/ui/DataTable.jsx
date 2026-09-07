import { useMemo, useState } from 'react'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faSort, faSortUp, faSortDown,
  faBars, faGripLines, faEquals,
} from '@fortawesome/free-solid-svg-icons'
import Pagination from '../Pagination'
import { EmptyState, ErrorState, TableSkeleton } from './States'

/**
 * Umumiy jadval komponenti — mavjud `.data-table` klassi ustiga qurilgan.
 *
 * Nima uchun: ilgari 43 ta jadvaldan 31 tasida sahifalash yo'q edi, saralash esa
 * ilovaning HECH bir joyida yo'q edi — har bir jadval qo'lda <thead>/<tbody>
 * yozib chiqilardi va yuklanish/bo'sh holat har xil ko'rinardi. Bu komponent
 * shu takrorlanishni tugatadi.
 *
 * Ikkala rejim ham qo'llab-quvvatlanadi (ikkalasi ham kodda mavjud):
 *   • server rejimi — `meta` + `onPageChange` beriladi (Students/Payments kabi),
 *     saralash `onSortChange` orqali serverga uzatiladi;
 *   • client rejimi — oddiy massiv beriladi, saralash/sahifalash shu yerda.
 *
 * columns: [{
 *   key,                       // qator obyektidagi maydon (yoki faqat id sifatida)
 *   header,                    // ustun sarlavhasi
 *   render?: (row, i) => node, // maxsus ko'rinish
 *   sortable?: bool,           // saralash mumkinmi
 *   sortValue?: (row) => any,  // client saralash uchun qiymat (default: row[key])
 *   align?: 'left'|'right'|'center',
 *   width?, className?, hideable?: bool
 * }]
 */
export default function DataTable({
  columns,
  rows,
  rowKey = (row, i) => row.id ?? i,
  loading = false,
  error = null,
  onRetry,
  empty,                        // {title, description, icon, action} yoki tayyor node
  meta = null,                  // server sahifalash meta'si
  onPageChange,
  sort = null,                  // {key, dir} — nazorat qilinadigan saralash (server rejimi)
  onSortChange,                 // berilsa — saralash serverga uzatiladi
  clientPageSize = 0,           // >0 bo'lsa client rejimida sahifalanadi
  rowClassName,
  onRowClick,
  stickyHeader = true,
  density: densityProp,          // 'compact' | 'default' | 'relaxed' — berilsa boshqariladi
  densityToggle = false,         // zichlik almashtirgichini ko'rsatish
  densityKey,                    // localStorage kaliti (foydalanuvchi tanlovi eslab qolinadi)
  scroll = false,                // true — jadval o'z ichida aylanadi, sarlavha yopishadi
  toolbar = null,                // jadval ustidagi qo'shimcha boshqaruv
  className = '',
}) {
  // Client rejimidagi saralash holati (server rejimida `sort` prop ishlatiladi)
  const [localSort, setLocalSort] = useState(null)
  const [clientPage, setClientPage] = useState(1)

  // Zichlik — foydalanuvchi tanlovi (ma'lumot ekranlarida shaxsiy odat masalasi:
  // kimdir ko'proq qator, kimdir kengroq nafas xohlaydi).
  const [localDensity, setLocalDensity] = useState(() => {
    if (!densityKey) return 'default'
    try { return localStorage.getItem(`table:density:${densityKey}`) || 'default' }
    catch { return 'default' }
  })
  const density = densityProp || localDensity
  function changeDensity(next) {
    setLocalDensity(next)
    if (densityKey) { try { localStorage.setItem(`table:density:${densityKey}`, next) } catch {} }
  }

  const activeSort = onSortChange ? sort : localSort

  function toggleSort(col) {
    if (!col.sortable) return
    const key = col.key
    const dir = activeSort?.key === key && activeSort.dir === 'asc' ? 'desc' : 'asc'
    const next = { key, dir }
    if (onSortChange) onSortChange(next)
    else { setLocalSort(next); setClientPage(1) }
  }

  // Client tomonda saralash — faqat onSortChange berilmagan bo'lsa
  const sortedRows = useMemo(() => {
    if (onSortChange || !localSort) return rows
    const col = columns.find(c => c.key === localSort.key)
    if (!col) return rows
    const valueOf = col.sortValue || (row => row[col.key])
    const dir = localSort.dir === 'asc' ? 1 : -1
    return [...rows].sort((a, b) => {
      const av = valueOf(a), bv = valueOf(b)
      if (av == null && bv == null) return 0
      if (av == null) return 1              // bo'sh qiymatlar doim oxirida
      if (bv == null) return -1
      if (typeof av === 'number' && typeof bv === 'number') return (av - bv) * dir
      return String(av).localeCompare(String(bv), 'uz') * dir
    })
  }, [rows, localSort, onSortChange, columns])

  // Client tomonda sahifalash — faqat clientPageSize berilgan bo'lsa
  const clientMeta = useMemo(() => {
    if (!clientPageSize || onPageChange) return null
    const total = sortedRows.length
    const total_pages = Math.max(1, Math.ceil(total / clientPageSize))
    return { page: Math.min(clientPage, total_pages), total_pages, total, page_size: clientPageSize }
  }, [sortedRows.length, clientPageSize, clientPage, onPageChange])

  const visibleRows = useMemo(() => {
    if (!clientMeta) return sortedRows
    const start = (clientMeta.page - 1) * clientMeta.page_size
    return sortedRows.slice(start, start + clientMeta.page_size)
  }, [sortedRows, clientMeta])

  if (error) return <ErrorState message={typeof error === 'string' ? error : error.message} onRetry={onRetry} />
  if (loading) return <TableSkeleton cols={columns.length} />

  const isEmpty = visibleRows.length === 0
  if (isEmpty && empty && typeof empty === 'object' && !empty.type) {
    return <EmptyState {...empty} />
  }

  const densityClass = density === 'compact' ? 'is-compact' : density === 'relaxed' ? 'is-relaxed' : ''

  return (
    <>
      {(toolbar || densityToggle) && (
        <div className="table-toolbar">
          {toolbar}
          <span className="spacer" />
          {densityToggle && (
            <div className="segmented" role="group" aria-label="Jadval zichligi">
              {DENSITIES.map(d => (
                <button
                  key={d.key}
                  type="button"
                  className={density === d.key ? 'active' : ''}
                  onClick={() => changeDensity(d.key)}
                  title={d.label}
                  aria-label={d.label}
                  aria-pressed={density === d.key}
                >
                  <FontAwesomeIcon icon={d.icon} />
                </button>
              ))}
            </div>
          )}
        </div>
      )}
      <div className={`table-wrap ${scroll ? 'is-scroll' : ''} ${className}`.trim()}>
        <table className={`data-table ${stickyHeader ? 'has-sticky-head' : ''} ${densityClass}`.trim()}>
          <thead>
            <tr>
              {columns.map(col => {
                const isSorted = activeSort?.key === col.key
                return (
                  <th
                    key={col.key}
                    style={{ width: col.width, textAlign: col.align }}
                    className={`${col.className || ''} ${col.sortable ? 'is-sortable' : ''} ${isSorted ? 'is-sorted' : ''}`.trim()}
                    onClick={col.sortable ? () => toggleSort(col) : undefined}
                    aria-sort={isSorted ? (activeSort.dir === 'asc' ? 'ascending' : 'descending') : undefined}
                    scope="col"
                  >
                    {col.sortable ? (
                      <button className="th-sort-btn" type="button">
                        {col.header}
                        <FontAwesomeIcon
                          icon={isSorted ? (activeSort.dir === 'asc' ? faSortUp : faSortDown) : faSort}
                          className="th-sort-icon"
                        />
                      </button>
                    ) : col.header}
                  </th>
                )
              })}
            </tr>
          </thead>
          <tbody>
            {visibleRows.map((row, i) => (
              <tr
                key={rowKey(row, i)}
                className={rowClassName ? rowClassName(row) : undefined}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
                style={onRowClick ? { cursor: 'pointer' } : undefined}
              >
                {columns.map(col => (
                  <td
                    key={col.key}
                    style={{ textAlign: col.align }}
                    className={col.className}
                  >
                    {col.render ? col.render(row, i) : row[col.key]}
                  </td>
                ))}
              </tr>
            ))}
            {isEmpty && (
              <tr>
                <td colSpan={columns.length} className="muted center py-4">
                  {/* `empty` config-obyekt bo'lsa yuqorida to'liq EmptyState qaytarilgan;
                      bu yerga faqat matn yoki tayyor element tushadi. */}
                  {empty || "Ma'lumot yo'q"}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      {meta && onPageChange && <Pagination meta={meta} onPageChange={onPageChange} />}
      {clientMeta && <Pagination meta={clientMeta} onPageChange={setClientPage} />}
    </>
  )
}

const DENSITIES = [
  { key: 'compact', label: 'Zich',    icon: faBars },
  { key: 'default', label: 'Odatiy',  icon: faGripLines },
  { key: 'relaxed', label: 'Keng',    icon: faEquals },
]

/**
 * Qator amallari — faqat sichqoncha qator ustida yoki fokus ichida bo'lganda
 * ko'rinadi. Shunda jadval tinch turadi va ko'z ma'lumotga qaraydi, har
 * qatordagi uch-to'rt ikonkaga emas.
 */
export function RowActions({ children }) {
  return <span className="row-actions">{children}</span>
}
