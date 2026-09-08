import { useCallback, useEffect, useId, useMemo, useRef, useState } from 'react'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faArrowPointer, faHand, faExpand, faRotateLeft, faRotateRight, faWandMagicSparkles, faArrowUpRightFromSquare, faGripVertical } from '@fortawesome/free-solid-svg-icons'
import { CANVAS_NODE_W, CANVAS_NODE_H, canvasGraph, graphBounds, fitCamera, zoomCamera } from './canvasGeometry'

const tone = kind => ['won', 'lost', 'back'].includes(kind) ? kind : 'open'

export default function ConversionCanvas({ stages, transitions, total, selection, onSelectNode, onSelectTransition, layout }) {
  const id = useId().replace(/:/g, '')
  const viewport = useRef(null)
  const gesture = useRef(null)
  const currentGraph = useRef(null)
  const currentSize = useRef({ width: 1000, height: 580 })
  const initialized = useRef(false)
  const fitAfterLayout = useRef(false)
  const [camera, setCamera] = useState({ x: 30, y: 30, zoom: .8 })
  const cameraRef = useRef(camera)
  cameraRef.current = camera
  const [draft, setDraft] = useState(null)
  const [tool, setTool] = useState('select')
  const [space, setSpace] = useState(false)
  const [moving, setMoving] = useState(false)
  const positions = useMemo(() => draft ? { ...layout.positions, [draft.key]: draft.position } : layout.positions, [layout.positions, draft])
  const graph = useMemo(() => canvasGraph(stages, transitions, positions), [stages, transitions, positions])
  currentGraph.current = graph
  const fit = useCallback(() => {
    const { width, height } = currentSize.current
    setCamera(fitCamera(graphBounds(currentGraph.current), width, height))
  }, [])

  useEffect(() => {
    if (fitAfterLayout.current) { fitAfterLayout.current = false; fit() }
  }, [layout.positions, fit])

  useEffect(() => {
    const el = viewport.current
    const observer = new ResizeObserver(([entry]) => {
      currentSize.current = { width: entry.contentRect.width, height: entry.contentRect.height }
      if (!initialized.current && entry.contentRect.width > 0 && currentGraph.current.nodes.length) { initialized.current = true; fit() }
    })
    observer.observe(el)
    return () => observer.disconnect()
  }, [fit])

  useEffect(() => {
    const el = viewport.current
    const wheel = e => {
      if (e.target.closest('[data-canvas-control]')) return
      e.preventDefault()
      if (e.ctrlKey || e.metaKey) {
        const box = el.getBoundingClientRect()
        setCamera(c => zoomCamera(c, Math.exp(-e.deltaY * .008), { x: e.clientX - box.left, y: e.clientY - box.top }))
      } else {
        const unit = e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? el.clientHeight : 1
        setCamera(c => ({ ...c, x: c.x - (e.shiftKey ? e.deltaY : e.deltaX) * unit, y: c.y - (e.shiftKey ? e.deltaX : e.deltaY) * unit }))
      }
    }
    el.addEventListener('wheel', wheel, { passive: false })
    return () => el.removeEventListener('wheel', wheel)
  }, [])

  const begin = e => {
    if ((e.button !== 0 && e.button !== 1) || e.target.closest('[data-canvas-control], .canvas-link-hit')) return
    const nodeElement = e.target.closest('[data-node-key]')
    const node = nodeElement && graph.nodes.find(n => n.key === nodeElement.dataset.nodeKey)
    if (!node && e.target.closest('button')) return
    e.preventDefault()
    const moveNode = node && tool === 'select' && !space && e.button !== 1
    gesture.current = { type: moveNode ? 'node' : 'pan', node, startX: e.clientX, startY: e.clientY, camera: cameraRef.current, moved: false }
    ;(moveNode ? nodeElement : viewport.current).focus({ preventScroll: true })
    viewport.current.setPointerCapture(e.pointerId)
    setMoving(true)
  }
  const move = e => {
    const g = gesture.current
    if (!g) return
    const dx = e.clientX - g.startX, dy = e.clientY - g.startY
    if (Math.hypot(dx, dy) > 4) g.moved = true
    if (!g.moved) return
    if (g.type === 'pan') setCamera({ ...g.camera, x: g.camera.x + dx, y: g.camera.y + dy })
    else {
      const point = { x: Math.round(g.node.x + dx / g.camera.zoom), y: Math.round(g.node.y + dy / g.camera.zoom) }
      if (e.shiftKey) { point.x = Math.round(point.x / 20) * 20; point.y = Math.round(point.y / 20) * 20 }
      g.position = point
      setDraft({ key: g.node.key, position: point })
    }
  }
  const end = e => {
    const g = gesture.current
    if (!g) return
    if (viewport.current.hasPointerCapture(e.pointerId)) viewport.current.releasePointerCapture(e.pointerId)
    gesture.current = null; setMoving(false); setDraft(null)
    if (g.type === 'node') {
      if (g.moved && g.position) layout.move(g.node.key, g.position)
      else if (!g.moved) onSelectNode(g.node)
    }
  }
  const cancel = () => { gesture.current = null; setMoving(false); setDraft(null) }
  const zoom = factor => setCamera(c => zoomCamera(c, factor, { x: currentSize.current.width / 2, y: currentSize.current.height / 2 }))
  const max = Math.max(1, ...graph.links.map(l => l.count))
  const related = link => !selection || (selection.type === 'node' ? link.from_key === selection.key || link.to_key === selection.key : link.id === selection.id)

  return <div className={'conversion-canvas' + (tool === 'hand' || space ? ' is-hand' : '') + (moving ? ' is-moving' : '')} ref={viewport} tabIndex={0} role="region" aria-label="Konversiya xaritasi. Bosqichlarni suring, bo‘sh joy orqali xaritani siljiting."
    style={{ '--grid-size': `${24 * camera.zoom}px`, '--grid-x': `${camera.x}px`, '--grid-y': `${camera.y}px` }}
    onPointerDown={begin} onPointerMove={move} onPointerUp={end} onPointerCancel={cancel}
    onKeyUp={e => { if (e.code === 'Space') setSpace(false) }} onBlur={e => { if (!e.currentTarget.contains(e.relatedTarget)) setSpace(false) }}
    onKeyDown={e => {
      if (e.code === 'Space' && !e.target.closest('[data-canvas-control]')) { e.preventDefault(); setSpace(true); return }
      if (e.key === 'Escape' && gesture.current) { e.preventDefault(); e.stopPropagation(); cancel(); return }
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') { e.preventDefault(); e.shiftKey ? layout.redo() : layout.undo(); return }
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'y') { e.preventDefault(); layout.redo(); return }
      if (e.key === '+' || e.key === '=') { e.preventDefault(); zoom(1.2) }
      if (e.key === '-') { e.preventDefault(); zoom(1 / 1.2) }
    }}>
    <div className="canvas-tools" data-canvas-control role="toolbar" aria-label="Xarita asboblari">
      <button type="button" aria-label="Tanlash va ko‘chirish" aria-pressed={tool === 'select'} onClick={() => setTool('select')}><FontAwesomeIcon icon={faArrowPointer} /></button>
      <button type="button" aria-label="Xaritani siljitish" aria-pressed={tool === 'hand'} onClick={() => setTool('hand')}><FontAwesomeIcon icon={faHand} /></button><i />
      <button type="button" aria-label="Joylashuvni bekor qilish" title="Bekor qilish · Ctrl Z" disabled={!layout.canUndo} onClick={layout.undo}><FontAwesomeIcon icon={faRotateLeft} /></button>
      <button type="button" aria-label="Joylashuvni qaytarish" title="Qaytarish · Ctrl Shift Z" disabled={!layout.canRedo} onClick={layout.redo}><FontAwesomeIcon icon={faRotateRight} /></button>
    </div>
    <div className="canvas-save-state" data-canvas-control><i />{layout.saved ? 'Joylashuv saqlandi' : 'Joylashuv shu sessiyada'}</div>
    <div className="canvas-world" style={{ transform: `translate(${camera.x}px, ${camera.y}px) scale(${camera.zoom})` }}>
      <svg className="canvas-links" aria-hidden="true"><defs><marker id={`${id}-arrow`} markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto"><path d="M1 1 L6 3.5 L1 6" fill="none" stroke="context-stroke" strokeWidth="1.2" /></marker></defs>
        {graph.links.map(l => <g key={l.id} className={`canvas-link ${tone(l.kind)}${related(l) ? '' : ' is-muted'}`}><path d={l.d} fill="none" strokeWidth={1.5 + l.count / max * 1.6} vectorEffect="non-scaling-stroke" markerEnd={`url(#${id}-arrow)`} /><path className="canvas-link-hit" d={l.d} fill="none" strokeWidth="18" onClick={() => onSelectTransition(l)} /></g>)}
      </svg>
      {graph.nodes.map((n,i) => <button type="button" key={n.key} data-node-key={n.key} className={`canvas-node ${tone(n.kind)}${selection?.type === 'node' && selection.key === n.key ? ' is-selected' : ''}${draft?.key === n.key ? ' is-dragging' : ''}`} style={{ left: n.x, top: n.y, width: CANVAS_NODE_W, height: CANVAS_NODE_H }} aria-label={`${n.name}: ${n.count} lid. Enter: tafsilotlar. Alt va yo‘nalish tugmalari: ko‘chirish.`} aria-pressed={selection?.type === 'node' && selection.key === n.key}
        onClick={e => { if (e.detail === 0) onSelectNode(n) }} onKeyDown={e => {
          if (!e.altKey || !['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.key)) return
          e.preventDefault(); e.stopPropagation()
          const step = e.shiftKey ? 40 : 10
          layout.move(n.key, { x: n.x + (e.key === 'ArrowRight' ? step : e.key === 'ArrowLeft' ? -step : 0), y: n.y + (e.key === 'ArrowDown' ? step : e.key === 'ArrowUp' ? -step : 0) })
        }}>
        <span className="canvas-node-head"><span><i />{n.kind === 'won' ? 'Natija' : n.kind === 'lost' ? 'Yo‘qotish' : 'Bosqich ' + String(i + 1).padStart(2,'0')}</span><FontAwesomeIcon icon={faGripVertical} /></span>
        <span className="canvas-node-name">{n.name}</span>
        <span className="canvas-node-value"><strong>{Number(n.count || 0).toLocaleString('uz-UZ')}</strong><span>lid</span><b>{n.percent}%</b></span>
        <span className="canvas-node-bottom"><span>Jami {total} ta liddan</span><FontAwesomeIcon icon={faArrowUpRightFromSquare} /></span>
        <i className="canvas-port in" /><i className="canvas-port out" />
      </button>)}
      {graph.links.map(l => <button type="button" key={l.id} className={'canvas-link-label' + (related(l) ? '' : ' is-muted')} style={{ left: l.lx, top: l.ly }} onClick={() => onSelectTransition(l)} aria-label={`${l.from_name} → ${l.to_name}: ${l.count} lid, ${l.percent}%`}><strong>{l.count}</strong><span>{l.percent}%</span></button>)}
    </div>
    <div className="canvas-bottom" data-canvas-control>
      <span className="canvas-hint">Bosqichni suring <i /> Bo‘sh joyni tortib siljiting</span>
      <div className="canvas-zoom"><button type="button" onClick={() => zoom(1 / 1.2)} aria-label="Kichraytirish">−</button><span>{Math.round(camera.zoom * 100)}%</span><button type="button" onClick={() => zoom(1.2)} aria-label="Kattalashtirish">+</button><i /><button type="button" onClick={fit} aria-label="Xaritani ekranga sig‘dirish" title="Ekranga sig‘dirish"><FontAwesomeIcon icon={faExpand} /></button><button type="button" onClick={() => { if (Object.keys(layout.positions).length) { fitAfterLayout.current = true; layout.reset() } else fit() }} aria-label="Avtomatik joylashtirish" title="Avtomatik joylashtirish"><FontAwesomeIcon icon={faWandMagicSparkles} /></button></div>
    </div>
  </div>
}
