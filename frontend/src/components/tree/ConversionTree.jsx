import { useMemo, useState } from 'react'
import TreeNode from './TreeNode'
import { buildLayout, LINK_TONE, LINK_LABEL, NODE_H } from './layout'

const PAD_X = 32
const PAD_Y = 28

/**
 * Konversiya daraxti.
 *
 * Ikki qatlam ustma-ust turadi:
 *   1. <svg> — bog'lovchi chiziqlar;
 *   2. HTML tugmalar — tugunlar va o'tish yorliqlari.
 *
 * Nega aralash: chiziqlarni SVG'siz chiroyli chizib bo'lmaydi, lekin
 * tugunlarni SVG ichida (foreignObject) chizsak, klaviatura fokusi va
 * mavzu (light/dark) token'lari yaxshi ishlamaydi. Shuning uchun
 * chiziq — SVG, bosiladigan narsa — haqiqiy <button>.
 */
export default function ConversionTree({
  stages, transitions, selection, onSelectNode, onSelectTransition,
  zoom = 1, total = 0, availableWidth = 0,
}) {
  const [hover, setHover] = useState(null)

  const { nodes, links, width, height } = useMemo(
    () => buildLayout(stages, transitions), [stages, transitions],
  )

  // Tanlov bo'lganda — bog'liq bo'lmagan narsalar so'niq bo'ladi, lekin
  // ko'rinib turadi.
  const activeKeys = useMemo(() => {
    if (!selection) return null
    if (selection.type === 'node') return new Set([selection.key])
    return new Set([selection.from_key, selection.to_key])
  }, [selection])

  const isLinkActive = (l) => {
    if (!selection) return true
    if (selection.type === 'transition') return l.id === selection.id
    return l.from_key === selection.key || l.to_key === selection.key
  }

  if (!nodes.length) return null

  const hovered = hover && links.find(l => l.id === hover)

  /* Kenglikka moslash: grafik konteynerdan kengroq bo'lsa, avtomatik
     kichraytiriladi. Aks holda o'ng chekka kesilib qolardi va foydalanuvchi
     nima yo'qolganini bilmasdi. Foydalanuvchi masshtabi shu ustiga qo'shiladi. */
  const fit = availableWidth
    ? Math.min(1, availableWidth / (width + PAD_X * 2))
    : 1
  const scale = zoom * fit

  return (
    <div
      className="tree-canvas"
      style={{
        width: width + PAD_X * 2,
        height: height + PAD_Y * 2,
        transform: `scale(${scale})`,
        transformOrigin: 'top center',
      }}
    >
      <div className="tree-inner" style={{ transform: `translate(${PAD_X}px, ${PAD_Y}px)` }}>
        <svg
          className="tree-links" width={width} height={height}
          aria-hidden="true" focusable="false" style={{ overflow: 'visible' }}
        >
          <defs>
            {Object.entries(LINK_TONE).map(([tone, color]) => (
              <marker
                key={tone} id={`tree-arrow-${tone}`}
                markerWidth="8" markerHeight="8" refX="7" refY="4"
                orient="auto" markerUnits="userSpaceOnUse"
              >
                <path d="M0,0.5 L8,4 L0,7.5 z" fill={color} />
              </marker>
            ))}
          </defs>
          {links.map(l => {
            const active = isLinkActive(l)
            return (
              <g key={l.id}
                className={`tree-link tone-${l.tone}${active ? '' : ' is-dimmed'}${hover === l.id ? ' is-hover' : ''}`}>
                <path
                  d={l.d} fill="none"
                  stroke={LINK_TONE[l.tone] || LINK_TONE.normal}
                  strokeWidth={l.width}
                  strokeLinecap="round" strokeLinejoin="round"
                  markerEnd={`url(#tree-arrow-${l.tone})`}
                />
                {/* Kengaytirilgan bosish sohasi — ingichka chiziqni ham urish oson. */}
                <path
                  className="tree-link-hit"
                  d={l.d} fill="none" stroke="transparent" strokeWidth={20}
                  onClick={() => onSelectTransition(l)}
                  onMouseEnter={() => setHover(l.id)}
                  onMouseLeave={() => setHover(h => (h === l.id ? null : h))}
                />
              </g>
            )
          })}
        </svg>

        {nodes.map(n => (
          <TreeNode
            key={n.key} node={n} total={total}
            selected={selection?.type === 'node' && selection.key === n.key}
            dimmed={!!activeKeys && !activeKeys.has(n.key)}
            onSelect={onSelectNode}
          />
        ))}

        {links.map(l => {
          const active = isLinkActive(l)
          return (
            <button
              key={l.id}
              type="button"
              className={[
                'tree-link-label', `tone-${l.tone}`,
                selection?.type === 'transition' && selection.id === l.id ? 'is-selected' : '',
                active ? '' : 'is-dimmed',
              ].filter(Boolean).join(' ')}
              style={{ left: l.labelX, top: l.labelY }}
              onClick={() => onSelectTransition(l)}
              onMouseEnter={() => setHover(l.id)}
              onMouseLeave={() => setHover(h => (h === l.id ? null : h))}
              onFocus={() => setHover(l.id)}
              onBlur={() => setHover(h => (h === l.id ? null : h))}
              aria-label={
                `${l.from_name} dan ${l.to_name} ga: ${l.count} ta lid. ` +
                `${l.from_name} bosqichiga yetgan lidlarning ${l.percent} foizi. ${LINK_LABEL[l.tone]}`
              }
            >
              <strong>{l.count}</strong>
              <span>{l.percent}%</span>
            </button>
          )
        })}

        {/* Hover izohi — foizning ma'nosini SO'Z bilan aytadi, chunki
            "46.2%" o'zi hech narsani tushuntirmaydi. */}
        {hovered && (
          <div
            className="tree-tip"
            style={{ left: hovered.labelX, top: hovered.labelY }}
            role="tooltip"
          >
            <div className="tt-flow">
              <span>{hovered.from_name}</span>
              <span className="tt-arrow">→</span>
              <span>{hovered.to_name}</span>
            </div>
            <dl className="tt-rows">
              <div><dt>Lidlar</dt><dd>{hovered.count}</dd></div>
              <div><dt>Ulush</dt><dd>{hovered.percent}%</dd></div>
              <div><dt>Turi</dt><dd>{LINK_LABEL[hovered.tone]}</dd></div>
            </dl>
            <p className="tt-def">
              <strong>{hovered.from_name}</strong> bosqichiga yetgan lidlardan{' '}
              <strong>{hovered.count}</strong> tasi <strong>{hovered.to_name}</strong> ga o'tgan.
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
