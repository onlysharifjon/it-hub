import { useState, useRef, useEffect } from 'react'

const MONTHS   = ['Yanvar','Fevral','Mart','Aprel','May','Iyun','Iyul','Avgust','Sentyabr','Oktyabr','Noyabr','Dekabr']
const WEEKDAYS = ['Du','Se','Ch','Pa','Ju','Sh','Ya']

function toStr(d) {
  const p = n => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth()+1)}-${p(d.getDate())}`
}
const TODAY = toStr(new Date())

export default function DateRangePicker({ dateFrom, dateTo, onChange }) {
  const [open,    setOpen]    = useState(false)
  const [hover,   setHover]   = useState(null)
  // selFrom — faqat vizual uchun (picking paytida birinchi sana)
  const [selFrom, setSelFrom] = useState('')

  // ── Ref-lar (synchronous — re-render kutmaydi) ─────────────
  // pickRef.current = true ⟹ birinchi sana tanlandi, ikkinchi kutilmoqda
  const pickRef  = useRef(false)
  // firstRef.current = birinchi tanlangan sana
  const firstRef = useRef('')

  const [viewM, setViewM] = useState(() => {
    const d = dateFrom ? new Date(dateFrom) : new Date()
    return d.getMonth()
  })
  const [viewY, setViewY] = useState(() => {
    const d = dateFrom ? new Date(dateFrom) : new Date()
    return d.getFullYear()
  })
  const wrapRef = useRef()

  // Tashqi klikda yopish
  useEffect(() => {
    const h = e => {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) {
        setOpen(false)
        setHover(null)
        setSelFrom('')
        pickRef.current  = false
        firstRef.current = ''
      }
    }
    document.addEventListener('mousedown', h)
    return () => document.removeEventListener('mousedown', h)
  }, [])

  // Tashqi props o'zgarganda (preset) — lokal holatni reset
  useEffect(() => {
    pickRef.current  = false
    firstRef.current = ''
    setSelFrom('')
  }, [dateFrom, dateTo])

  // ── Click handler ──────────────────────────────────────────
  function handleDayClick(d) {
    if (d > TODAY) return

    if (!pickRef.current) {
      // 1-klik: boshlash sanasini saqlash (ref — synchronous)
      pickRef.current  = true
      firstRef.current = d
      setSelFrom(d)       // vizual yangilanish
    } else {
      // 2-klik: tugash sanasini tanlash
      const first = firstRef.current
      // Darhol reset — keyingi click uchun tayyor
      pickRef.current  = false
      firstRef.current = ''
      setSelFrom('')
      setHover(null)
      setOpen(false)
      // Tartibga solish
      const [f, t] = d < first ? [d, first] : [first, d]
      onChange({ date_from: f, date_to: t })
    }
  }

  function handleClear(e) {
    e.stopPropagation()
    pickRef.current  = false
    firstRef.current = ''
    setSelFrom('')
    setHover(null)
    onChange({ date_from: '', date_to: '' })
  }

  function toggleOpen() {
    if (open) {
      setOpen(false)
      setHover(null)
      setSelFrom('')
      pickRef.current  = false
      firstRef.current = ''
    } else {
      setOpen(true)
    }
  }

  // ── Kalendar hujayralari ───────────────────────────────────
  function buildCells() {
    const firstDow = new Date(viewY, viewM, 1).getDay()
    const offset   = firstDow === 0 ? 6 : firstDow - 1
    const total    = new Date(viewY, viewM + 1, 0).getDate()
    const p = n => String(n).padStart(2, '0')
    const cells = []
    for (let i = 0; i < offset; i++) cells.push(null)
    for (let day = 1; day <= total; day++) cells.push(`${viewY}-${p(viewM+1)}-${p(day)}`)
    return cells
  }

  function prevMonth() {
    if (viewM === 0) { setViewM(11); setViewY(y => y-1) }
    else setViewM(m => m-1)
  }
  function nextMonth() {
    if (viewM === 11) { setViewM(0); setViewY(y => y+1) }
    else setViewM(m => m+1)
  }

  // ── CSS class hisoblash ────────────────────────────────────
  function dayClass(d) {
    const picking = selFrom !== ''   // picking holatida ekanmiz
    const cls = ['drp-day']

    if (d > TODAY) { cls.push('future'); return cls.join(' ') }
    if (d === TODAY) cls.push('is-today')

    if (picking) {
      // Picking paytida: selFrom + hover preview
      const previewEnd = hover || null
      if (previewEnd) {
        const [f, t] = selFrom <= previewEnd ? [selFrom, previewEnd] : [previewEnd, selFrom]
        if (d === f) cls.push('range-start')
        if (d === t) cls.push('range-end')
        if (d > f && d < t) cls.push('in-range')
      } else {
        if (d === selFrom) cls.push('range-start')
      }
    } else {
      // Tanlash tugagan: props'dan ko'rsat
      if (dateFrom && dateTo) {
        const [f, t] = dateFrom <= dateTo ? [dateFrom, dateTo] : [dateTo, dateFrom]
        if (d === f) cls.push('range-start')
        if (d === t) cls.push('range-end')
        if (d > f && d < t) cls.push('in-range')
      } else if (dateFrom && d === dateFrom) {
        cls.push('range-start', 'range-end')
      }
    }

    return cls.join(' ')
  }

  // ── Label ──────────────────────────────────────────────────
  function getLabel() {
    if (selFrom) return `${selFrom}  →  ...`
    if (dateFrom && dateTo) return dateFrom === dateTo ? dateFrom : `${dateFrom}  →  ${dateTo}`
    if (dateFrom) return dateFrom
    return "Sana oralig'ini tanlang"
  }

  const hasValue = !!(dateFrom || dateTo)
  const cells    = buildCells()
  const picking  = selFrom !== ''

  return (
    <div className="drp-root" ref={wrapRef}>
      {/* Trigger */}
      <button
        type="button"
        className={`drp-trigger${open ? ' drp-open' : ''}${hasValue ? ' drp-has-value' : ''}`}
        onClick={toggleOpen}
      >
        <svg className="drp-icon" width="14" height="14" viewBox="0 0 24 24"
             fill="none" stroke="currentColor" strokeWidth="2">
          <rect x="3" y="4" width="18" height="18" rx="2"/>
          <line x1="16" y1="2" x2="16" y2="6"/>
          <line x1="8"  y1="2" x2="8"  y2="6"/>
          <line x1="3"  y1="10" x2="21" y2="10"/>
        </svg>
        <span className="drp-label">{getLabel()}</span>
        {hasValue && (
          <span className="drp-clear-btn" onClick={handleClear} title="Tozalash">✕</span>
        )}
      </button>

      {/* Popover */}
      {open && (
        <div className="drp-popover">
          {/* Navigatsiya */}
          <div className="drp-nav">
            <button type="button" className="drp-nav-btn" onClick={prevMonth}>‹</button>
            <span className="drp-nav-title">{MONTHS[viewM]} {viewY}</span>
            <button type="button" className="drp-nav-btn" onClick={nextMonth}>›</button>
          </div>

          {/* Grid */}
          <div className="drp-grid">
            {WEEKDAYS.map(w => (
              <div key={w} className="drp-weekday">{w}</div>
            ))}
            {cells.map((d, i) =>
              d ? (
                <div
                  key={d}
                  className={dayClass(d)}
                  onClick={() => handleDayClick(d)}
                  onMouseEnter={() => picking && d <= TODAY && setHover(d)}
                  onMouseLeave={() => picking && setHover(null)}
                >
                  <span>{parseInt(d.slice(8))}</span>
                </div>
              ) : (
                <div key={`e${i}`} className="drp-empty" />
              )
            )}
          </div>

          {picking && (
            <div className="drp-hint">Tugash sanasini tanlang</div>
          )}
        </div>
      )}
    </div>
  )
}
