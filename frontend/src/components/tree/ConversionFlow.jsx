import { useId, useMemo, useState } from 'react'
import { LINK_LABEL } from './layout'
import { buildFlowGeometry, FLOW_NODE_W as NODE_W, FLOW_NODE_H as NODE_H } from './flowGeometry'

const tone = kind => kind === 'won' ? 'won' : kind === 'lost' ? 'lost' : 'open'

/** Actual stage visits and transitions, arranged as a readable horizontal flow. */
export default function ConversionFlow({ stages, transitions, total, selection, onSelectNode, onSelectTransition, availableWidth, zoom = 1 }) {
  const id = useId().replace(/:/g, '')
  const [hover, setHover] = useState(null)
  const graph = useMemo(() => buildFlowGeometry(stages, transitions), [stages, transitions])
  const scale = zoom * Math.min(1, Math.max(.72, (availableWidth || graph.width) / graph.width))
  const related = link => !selection || (selection.type === 'node' ? link.from_key === selection.key || link.to_key === selection.key : link.id === selection.id)
  const max = Math.max(1, ...graph.links.map(l => l.count))
  return <div className="conversion-flow-size" style={{ width: graph.width * scale, height: graph.height * scale }}>
    <div className="conversion-flow" style={{ width: graph.width, height: graph.height, transform: `scale(${scale})` }}>
      <svg className="conversion-connectors" width={graph.width} height={graph.height} aria-hidden="true">
        <defs><marker id={`${id}-arrow`} markerWidth="5" markerHeight="5" refX="4" refY="2.5" orient="auto" markerUnits="userSpaceOnUse"><path d="M0,0 L5,2.5 L0,5" fill="none" stroke="var(--muted)" strokeWidth="1" /></marker></defs>
        {graph.links.map(l => <g key={l.id} className={`flow-link ${tone(l.kind)}${related(l) ? '' : ' is-muted'}${hover === l.id ? ' is-hover' : ''}`}>
          <path d={l.d} fill="none" strokeWidth={1.5 + l.count / max * 2.5} markerEnd={`url(#${id}-arrow)`} />
          <path className="flow-link-touch" d={l.d} fill="none" stroke="transparent" strokeWidth="20" onMouseEnter={() => setHover(l.id)} onMouseLeave={() => setHover(null)} onClick={() => onSelectTransition(l)} />
        </g>)}
      </svg>
      {graph.nodes.map((n, i) => <button key={n.key} className={`flow-node ${tone(n.kind)}${selection?.type === 'node' && selection.key === n.key ? ' is-selected' : ''}`} style={{ left: n.x, top: n.y, width: NODE_W, height: NODE_H, '--item-index': i }} onClick={() => onSelectNode(n)} aria-pressed={selection?.type === 'node' && selection.key === n.key} aria-label={`${n.name}: ${n.count} lid, jami ${total} liddan ${n.percent}%`}>
        <span className="flow-node-title"><i />{n.name}</span><strong>{n.count.toLocaleString('uz-UZ')}<small>lid</small></strong><span className="flow-node-share"><i style={{ width: Math.min(100, Math.max(0, n.percent)) + '%' }} /></span><span className="flow-node-foot">{n.percent}% jami lidlardan <b>↗</b></span>
      </button>)}
      {graph.links.map(l => <button key={l.id} className={`flow-link-value${selection?.type === 'transition' && selection.id === l.id ? ' is-selected' : ''}${related(l) ? '' : ' is-muted'}`} style={{ left: l.lx, top: l.ly }} onClick={() => onSelectTransition(l)} onMouseEnter={() => setHover(l.id)} onMouseLeave={() => setHover(null)} title={`${l.from_name} → ${l.to_name}: ${l.count} lid (${l.percent}%). ${LINK_LABEL[l.kind] || ''}`} aria-label={`${l.from_name} dan ${l.to_name} ga ${l.count} lid, ${l.percent}%`}><strong>{l.count}</strong><span>{l.percent}%</span></button>)}
    </div>
  </div>
}
