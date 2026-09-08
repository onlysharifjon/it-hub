import { findMainPath } from './layout.js'

export const FLOW_NODE_W = 166
export const FLOW_NODE_H = 112
const PITCH = 228

// Transitions with overlapping horizontal spans use separate lanes. This keeps
// labels legible when a center has many stages, returns and skipped stages.
function assignLanes(links) {
  const ends = []
  for (const link of [...links].sort((a, b) => a.lo - b.lo || a.hi - b.hi)) {
    let lane = ends.findIndex(end => end + 78 < link.lo)
    if (lane < 0) { lane = ends.length; ends.push(link.hi) }
    else ends[lane] = link.hi
    link.lane = lane
  }
  return ends.length
}

function roundedRoute(x1, y1, x2, y2, lane) {
  if (Math.abs(x1 - x2) < 1) {
    if (y1 !== y2) return `M ${x1} ${y1} L ${x2} ${y2}`
    return `M ${x1 - 14} ${y1} C ${x1 - 44} ${lane} ${x1 + 44} ${lane} ${x1 + 14} ${y2}`
  }
  const direction = Math.sign(x2 - x1)
  const out = Math.sign(lane - y1), into = Math.sign(y2 - lane)
  const radius = Math.min(16, Math.abs(x2 - x1) / 2, Math.abs(lane - y1) / 2, Math.abs(y2 - lane) / 2)
  return `M ${x1} ${y1} L ${x1} ${lane - out * radius} Q ${x1} ${lane} ${x1 + direction * radius} ${lane} L ${x2 - direction * radius} ${lane} Q ${x2} ${lane} ${x2} ${lane + into * radius} L ${x2} ${y2}`
}

export function buildFlowGeometry(stages = [], transitions = []) {
  const path = findMainPath(stages, transitions)
  const main = path.map(key => stages.find(s => s.key === key)).filter(Boolean)
  const other = stages.filter(s => !path.includes(s.key))
  const cols = Math.max(main.length, other.length, 2)
  const width = cols * PITCH - (PITCH - FLOW_NODE_W) + 56
  const nodes = [
    ...main.map((s, i) => ({ ...s, x: 28 + i * PITCH, main: true })),
    ...other.map((s, i) => ({ ...s, x: 28 + (i + (cols - other.length) / 2) * PITCH, main: false })),
  ]
  const byKey = new Map(nodes.map(n => [n.key, n]))
  const links = transitions.flatMap(t => {
    const a = byKey.get(t.from_key), b = byKey.get(t.to_key)
    if (!a || !b) return []
    const zone = a.main && b.main
      ? b.x - a.x === PITCH ? 'direct' : 'top'
      : a.main !== b.main ? 'middle' : 'bottom'
    return [{ ...t, id: `${t.from_key}->${t.to_key}`, zone, a, b, lo: Math.min(a.x, b.x), hi: Math.max(a.x, b.x) }]
  })
  const topCount = assignLanes(links.filter(l => l.zone === 'top'))
  const middleCount = assignLanes(links.filter(l => l.zone === 'middle'))
  const bottomCount = assignLanes(links.filter(l => l.zone === 'bottom'))
  const mainY = Math.max(62, 30 + topCount * 32)
  const gutter = Math.max(124, 96 + Math.max(0, middleCount - 1) * 32)
  const otherY = mainY + FLOW_NODE_H + gutter
  for (const node of nodes) node.y = node.main ? mainY : otherY

  for (const link of links) {
    const { a, b, zone, lane } = link
    const x1 = a.x + FLOW_NODE_W / 2, x2 = b.x + FLOW_NODE_W / 2
    if (zone === 'direct') {
      const start = a.x + FLOW_NODE_W, end = b.x, y = mainY + FLOW_NODE_H / 2
      link.d = `M ${start} ${y} C ${start + 24} ${y} ${end - 24} ${y} ${end} ${y}`
      link.lx = (start + end) / 2; link.ly = y - 23
      continue
    }
    const routeY = zone === 'top' ? mainY - (lane + 1) * 32
      : zone === 'middle' ? mainY + FLOW_NODE_H + 48 + lane * 32
      : otherY + FLOW_NODE_H + 40 + lane * 32
    const y1 = zone === 'top' ? a.y : zone === 'bottom' || a.main ? a.y + FLOW_NODE_H : a.y
    const y2 = zone === 'top' ? b.y : zone === 'bottom' || b.main ? b.y + FLOW_NODE_H : b.y
    link.d = roundedRoute(x1, y1, x2, y2, routeY)
    link.lx = (x1 + x2) / 2; link.ly = routeY - 14
  }
  const height = other.length
    ? otherY + FLOW_NODE_H + Math.max(50, 38 + bottomCount * 32)
    : mainY + FLOW_NODE_H + 61
  return { nodes, links, width, height }
}
