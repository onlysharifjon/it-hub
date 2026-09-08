import Overlay from './ui/Overlay'
import useFocusTrap from './ui/useFocusTrap'
import { useEffect, useMemo, useRef, useState } from 'react'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faMagnifyingGlass, faArrowTurnDown, faUserGraduate, faUsers, faBullseye } from '@fortawesome/free-solid-svg-icons'
import { flatNav } from '../constants/nav'
import { fetchStudents, fetchGroups, fetchLeads } from '../api'

/**
 * Global qidiruv / buyruqlar paneli (Cmd/Ctrl + K).
 *
 * Nima uchun: admin uchun yon menyuda ~19 ta tugma bor edi va ular soni har bir
 * yangi sahifa bilan o'sadi — vizual qayta tartiblash bu muammoni faqat
 * kechiktiradi. Palitra esa sahifalar soniga bog'liq emas: yozib topasiz.
 * Bundan tashqari talaba/guruh/lidni ismi bo'yicha to'g'ridan-to'g'ri topadi —
 * ilovada bunday umumiy qidiruv umuman yo'q edi.
 */
export default function CommandPalette({ open, onClose, role, onNavigate }) {
  const [q, setQ] = useState('')
  const [records, setRecords] = useState([])
  const [loading, setLoading] = useState(false)
  const [active, setActive] = useState(0)
  const inputRef = useRef(null)
  const listRef = useRef(null)
  const paletteRef = useRef(null)
  useFocusTrap(open, paletteRef, onClose)

  const pages = useMemo(() => flatNav(role), [role])

  useEffect(() => {
    if (open) { setQ(''); setRecords([]); setActive(0); setTimeout(() => inputRef.current?.focus(), 30) }
  }, [open])

  // Yozuvlarni qidirish (debounce) — 2 belgidan boshlab
  useEffect(() => {
    if (!open || q.trim().length < 2) { setRecords([]); return }
    let alive = true
    const t = setTimeout(async () => {
      setLoading(true)
      const term = q.trim()
      const out = []
      const canStudents = ['admin', 'support_teacher', 'hunter', 'sales', 'call_center'].includes(role)
      const canLeads = ['admin', 'hunter', 'sales', 'call_center'].includes(role)
      try {
        const jobs = []
        if (canStudents) {
          jobs.push(fetchStudents({ search: term, page: 1, page_size: 5 })
            .then(r => (r.items || []).forEach(s => out.push({
              type: 'student', icon: faUserGraduate, label: s.full_name, sub: s.phone1, page: 'students',
            }))).catch(() => {}))
          jobs.push(fetchGroups({ search: term, page: 1, page_size: 5 })
            .then(r => (r.items || r || []).slice(0, 5).forEach(g => out.push({
              type: 'group', icon: faUsers, label: g.name, sub: g.teacher_name || '', page: 'groups',
            }))).catch(() => {}))
        }
        if (canLeads) {
          jobs.push(fetchLeads({ search: term })
            .then(r => (Array.isArray(r) ? r : []).slice(0, 5).forEach(l => out.push({
              type: 'lead', icon: faBullseye, label: l.full_name, sub: l.phone, page: 'leads',
            }))).catch(() => {}))
        }
        await Promise.all(jobs)
      } finally {
        if (alive) { setRecords(out); setLoading(false) }
      }
    }, 250)
    return () => { alive = false; clearTimeout(t) }
  }, [q, open, role])

  const matchedPages = useMemo(() => {
    const term = q.trim().toLowerCase()
    if (!term) return pages.slice(0, 8)
    return pages.filter(p => p.label.toLowerCase().includes(term) || p.group.toLowerCase().includes(term))
  }, [q, pages])

  const items = useMemo(
    () => [...matchedPages.map(p => ({ kind: 'page', ...p })), ...records.map(r => ({ kind: 'record', ...r }))],
    [matchedPages, records],
  )

  useEffect(() => { setActive(0) }, [items.length])

  function choose(item) {
    onNavigate(item.kind === 'page' ? item.key : item.page)
    onClose()
  }

  function onKeyDown(e) {
    if (e.key === 'ArrowDown') { e.preventDefault(); setActive(a => Math.min(a + 1, items.length - 1)) }
    if (e.key === 'ArrowUp')   { e.preventDefault(); setActive(a => Math.max(a - 1, 0)) }
    if (e.key === 'Enter' && items[active]) { e.preventDefault(); choose(items[active]) }
  }

  if (!open) return null

  return (
    <Overlay layer={1200} className="cmdk-overlay" onClick={onClose}>
      <div className="cmdk" ref={paletteRef} onClick={e => e.stopPropagation()} role="dialog" aria-modal="true" aria-label="Qidiruv">
        <div className="cmdk-input-wrap">
          <FontAwesomeIcon icon={faMagnifyingGlass} className="cmdk-icon" />
          <input
            ref={inputRef}
            className="cmdk-input"
            placeholder="Sahifa, talaba, guruh yoki lid..."
            value={q}
            onChange={e => setQ(e.target.value)}
            onKeyDown={onKeyDown}
            aria-label="Qidiruv so'rovi"
          />
          <kbd>ESC</kbd>
        </div>

        <div className="cmdk-list" ref={listRef}>
          {items.length === 0 && !loading && (
            <div className="cmdk-empty">
              {q.trim().length >= 2 ? 'Hech narsa topilmadi' : 'Yozing — sahifalar va yozuvlar bo\'yicha qidiradi'}
            </div>
          )}

          {matchedPages.length > 0 && (
            <div className="cmdk-section">
              <div className="cmdk-section-label">Sahifalar</div>
              {matchedPages.map((p, i) => (
                <button
                  key={p.key}
                  className={`cmdk-item${active === i ? ' active' : ''}`}
                  onClick={() => choose({ kind: 'page', ...p })}
                  onMouseEnter={() => setActive(i)}
                >
                  <FontAwesomeIcon icon={p.icon} fixedWidth />
                  <span className="cmdk-item-label">{p.label}</span>
                  <span className="cmdk-item-sub">{p.group}</span>
                </button>
              ))}
            </div>
          )}

          {(records.length > 0 || loading) && (
            <div className="cmdk-section">
              <div className="cmdk-section-label">Yozuvlar {loading && <span className="cmdk-loading">qidirilmoqda...</span>}</div>
              {records.map((r, i) => {
                const idx = matchedPages.length + i
                return (
                  <button
                    key={`${r.type}-${i}`}
                    className={`cmdk-item${active === idx ? ' active' : ''}`}
                    onClick={() => choose({ kind: 'record', ...r })}
                    onMouseEnter={() => setActive(idx)}
                  >
                    <FontAwesomeIcon icon={r.icon} fixedWidth />
                    <span className="cmdk-item-label">{r.label}</span>
                    <span className="cmdk-item-sub">{r.sub}</span>
                  </button>
                )
              })}
            </div>
          )}
        </div>

        <div className="cmdk-foot">
          <span><kbd>↑</kbd><kbd>↓</kbd> tanlash</span>
          <span><kbd><FontAwesomeIcon icon={faArrowTurnDown} /></kbd> ochish</span>
          <span><kbd>ESC</kbd> yopish</span>
        </div>
      </div>
    </Overlay>
  )
}
