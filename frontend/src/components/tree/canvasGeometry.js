import { buildFlowGeometry, FLOW_NODE_W, FLOW_NODE_H } from './flowGeometry.js'

const SIZE = 1.4
export const CANVAS_NODE_W = FLOW_NODE_W * SIZE
export const CANVAS_NODE_H = FLOW_NODE_H * SIZE
export const clampZoom = value => Math.max(.2, Math.min(2.5, value))

export function validPositions(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return {}
  return Object.fromEntries(Object.entries(value).filter(([, p]) => p && Number.isFinite(p.x) && Number.isFinite(p.y) && Math.abs(p.x) <= 100000 && Math.abs(p.y) <= 100000).map(([key,p]) => [key, { x: p.x, y: p.y }]))
}

const scalePath = path => path.replace(/-?\d*\.?\d+(?:e[-+]?\d+)?/gi, value => String(Math.round(Number(value) * SIZE * 100) / 100))

export function connectNodes(a, b) {
  const ax = a.x + CANVAS_NODE_W / 2, ay = a.y + CANVAS_NODE_H / 2
  const bx = b.x + CANVAS_NODE_W / 2, by = b.y + CANVAS_NODE_H / 2
  if (a.key === b.key) return { d: `M ${a.x + CANVAS_NODE_W} ${ay - 22} C ${a.x + CANVAS_NODE_W + 100} ${ay - 60} ${a.x + CANVAS_NODE_W + 100} ${ay + 60} ${a.x + CANVAS_NODE_W} ${ay + 22}`, lx: a.x + CANVAS_NODE_W + 76, ly: ay }
  const horizontal = Math.abs(bx - ax) >= Math.abs(by - ay) * .8
  const sign = Math.sign(horizontal ? bx - ax : by - ay) || 1
  const start = horizontal ? { x: ax + sign * CANVAS_NODE_W / 2, y: ay } : { x: ax, y: ay + sign * CANVAS_NODE_H / 2 }
  const end = horizontal ? { x: bx - sign * CANVAS_NODE_W / 2, y: by } : { x: bx, y: by - sign * CANVAS_NODE_H / 2 }
  const reach = Math.max(64, Math.abs(horizontal ? end.x - start.x : end.y - start.y) * .45)
  const p = horizontal ? { x: start.x + sign * reach, y: start.y } : { x: start.x, y: start.y + sign * reach }
  const q = horizontal ? { x: end.x - sign * reach, y: end.y } : { x: end.x, y: end.y - sign * reach }
  return {
    d: `M ${start.x} ${start.y} C ${p.x} ${p.y} ${q.x} ${q.y} ${end.x} ${end.y}`,
    lx: (start.x + 3 * p.x + 3 * q.x + end.x) / 8 + (horizontal ? 0 : 35),
    ly: (start.y + 3 * p.y + 3 * q.y + end.y) / 8 - (horizontal ? 17 : 0),
  }
}

export function canvasGraph(stages, transitions, positions = {}) {
  const base = buildFlowGeometry(stages, transitions)
  const nodes = base.nodes.map(node => ({ ...node, x: node.x * SIZE, y: node.y * SIZE, ...positions[node.key] }))
  const byKey = new Map(nodes.map(n => [n.key, n]))
  const links = base.links.map(link => ({ ...link, ...(positions[link.from_key] || positions[link.to_key]
    ? connectNodes(byKey.get(link.from_key), byKey.get(link.to_key))
    : { d: scalePath(link.d), lx: link.lx * SIZE, ly: link.ly * SIZE }) }))
  return { nodes, links }
}

export function graphBounds({ nodes, links }) {
  if (!nodes.length) return { x: 0, y: 0, width: 600, height: 300 }
  const x = Math.min(...nodes.map(n => n.x), ...links.map(l => l.lx - 42)) - 20
  const y = Math.min(...nodes.map(n => n.y), ...links.map(l => l.ly - 20)) - 20
  const right = Math.max(...nodes.map(n => n.x + CANVAS_NODE_W), ...links.map(l => l.lx + 42)) + 20
  const bottom = Math.max(...nodes.map(n => n.y + CANVAS_NODE_H), ...links.map(l => l.ly + 20)) + 20
  return { x, y, width: right - x, height: bottom - y }
}

export function fitCamera(bounds, width, height) {
  const zoom = Math.max(.2, Math.min(1, (width - 80) / bounds.width, (height - 110) / bounds.height))
  return { zoom, x: width / 2 - (bounds.x + bounds.width / 2) * zoom, y: (height - 25) / 2 - (bounds.y + bounds.height / 2) * zoom }
}

export function zoomCamera(camera, factor, point) {
  const zoom = clampZoom(camera.zoom * factor)
  return { zoom, x: point.x - (point.x - camera.x) / camera.zoom * zoom, y: point.y - (point.y - camera.y) / camera.zoom * zoom }
}

export function layoutHistory(state, action) {
  if (action.type === 'load') return { entries: [validPositions(action.positions)], index: 0 }
  if (action.type === 'undo') return { ...state, index: Math.max(0, state.index - 1) }
  if (action.type === 'redo') return { ...state, index: Math.min(state.entries.length - 1, state.index + 1) }
  const current = state.entries[state.index]
  const next = action.type === 'reset' ? {} : action.type === 'move' ? validPositions({ ...current, [action.key]: action.position }) : current
  if (JSON.stringify(current) === JSON.stringify(next)) return state
  const entries = [...state.entries.slice(0, state.index + 1), next].slice(-40)
  return { entries, index: entries.length - 1 }
}
