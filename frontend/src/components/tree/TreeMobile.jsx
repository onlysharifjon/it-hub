import { useMemo, useState } from 'react'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faArrowDown, faChevronDown, faChevronRight } from '@fortawesome/free-solid-svg-icons'
import { findMainPath, stageColor, LINK_TONE, LINK_LABEL } from './layout'

/**
 * Mobil ko'rinish — soddalashtirilgan tik oqim.
 *
 * 375px ekranga to'liq grafikni siqib joylashtirishga urinish ma'nosiz:
 * chiziqlar chalkashadi, sonlar o'qilmaydi. Shuning uchun mobilda faqat
 * ASOSIY YO'L tik ro'yxat sifatida chiziladi, chetki tarmoqlar esa har bir
 * bosqich ostida yig'ilgan holda turadi va bosilganda ochiladi.
 *
 * Ma'lumot bir xil — faqat taqdimot boshqacha.
 */
export default function TreeMobile({ stages, transitions, total, onSelectNode, onSelectTransition }) {
  const [open, setOpen] = useState(() => new Set())

  const { path, byKey, branchesOf, mainEdge } = useMemo(() => {
    const keys = findMainPath(stages, transitions)
    const map = new Map(stages.map(s => [s.key, s]))
    const mainSet = new Set(keys)

    // Har bosqichdan chiqadigan, asosiy yo'lga TEGISHLI BO'LMAGAN o'tishlar.
    const branches = new Map()
    const main = new Map()
    for (const t of transitions) {
      if (!map.has(t.from_key) || !map.has(t.to_key)) continue
      const i = keys.indexOf(t.from_key)
      const j = keys.indexOf(t.to_key)
      if (i >= 0 && j === i + 1) { main.set(t.from_key, t); continue }
      if (!branches.has(t.from_key)) branches.set(t.from_key, [])
      branches.get(t.from_key).push(t)
    }
    for (const list of branches.values()) list.sort((a, b) => b.count - a.count)
    return { path: keys.map(k => map.get(k)).filter(Boolean), byKey: map, branchesOf: branches, mainEdge: main, mainSet }
  }, [stages, transitions])

  function toggle(key) {
    setOpen(prev => {
      const next = new Set(prev)
      next.has(key) ? next.delete(key) : next.add(key)
      return next
    })
  }

  if (!path.length) return null

  return (
    <div className="tree-mobile">
      {path.map((s, i) => {
        const edge = mainEdge.get(s.key)
        const branches = branchesOf.get(s.key) || []
        const isOpen = open.has(s.key)
        return (
          <div key={s.key} className="tm-step">
            <button className="tm-node" onClick={() => onSelectNode(s)}
              style={{ '--node-color': stageColor(s.color, s.kind) }}
              aria-label={`${s.name}: ${s.count} ta lid, kogortadagi ${total} ta liddan ${s.percent} foizi`}>
              <span className="tm-dot" aria-hidden="true" />
              <span className="tm-main">
                <span className="tm-name">{s.name}</span>
                <span className="tm-pct">{s.percent}% kogortadan</span>
              </span>
              <span className="tm-count">{s.count}</span>
            </button>

            {branches.length > 0 && (
              <>
                <button className="tm-toggle" onClick={() => toggle(s.key)}
                  aria-expanded={isOpen}>
                  <FontAwesomeIcon icon={isOpen ? faChevronDown : faChevronRight} />
                  {' '}Boshqa yo'nalishlar ({branches.length})
                </button>
                {isOpen && (
                  <ul className="tm-branches">
                    {branches.map(t => (
                      <li key={`${t.from_key}->${t.to_key}`}>
                        <button onClick={() => onSelectTransition({
                          ...t, id: `${t.from_key}->${t.to_key}`,
                          tone: t.kind,
                        })}
                          className={`tm-branch tone-${t.kind}`}>
                          <span className="tm-branch-line" style={{ background: LINK_TONE[t.kind] }} />
                          <span className="tm-branch-body">
                            <span className="tm-branch-to">{t.to_name}</span>
                            <span className="tm-branch-meta">
                              {t.count} lid · {t.percent}% · {LINK_LABEL[t.kind]}
                            </span>
                          </span>
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </>
            )}

            {i < path.length - 1 && (
              <button className="tm-arrow" onClick={() => edge && onSelectTransition({
                ...edge, id: `${edge.from_key}->${edge.to_key}`, tone: 'main',
              })} disabled={!edge}
                aria-label={edge
                  ? `${edge.from_name} dan ${edge.to_name} ga: ${edge.count} ta lid, ${edge.percent} foiz`
                  : undefined}>
                <FontAwesomeIcon icon={faArrowDown} />
                {edge && <span>{edge.count} · {edge.percent}%</span>}
              </button>
            )}
          </div>
        )
      })}
    </div>
  )
}
