import { test } from 'node:test'
import assert from 'node:assert/strict'
import { buildFlowGeometry, FLOW_NODE_W, FLOW_NODE_H } from '../src/components/tree/flowGeometry.js'

const stages = Array.from({ length: 9 }, (_, i) => ({ key: String(i), order: i, count: 100 - i * 8, kind: i === 5 ? 'won' : i > 5 ? 'lost' : 'lead' }))
const chain = Array.from({ length: 5 }, (_, i) => ({ from_key: String(i), to_key: String(i + 1), count: 90 - i * 8 }))
const branches = [[0, 3], [1, 4], [2, 5], [4, 1], [3, 0], [1, 6], [2, 6], [3, 7], [4, 8], [6, 7], [7, 8], [8, 6]].map(([from, to]) => ({ from_key: String(from), to_key: String(to), count: 3 }))

test('dense flows preserve every stage and transition within the diagram', () => {
  const graph = buildFlowGeometry(stages, [...chain, ...branches])
  assert.equal(graph.nodes.length, stages.length)
  assert.equal(graph.links.length, chain.length + branches.length)
  for (const node of graph.nodes) {
    assert.ok(node.x >= 0 && node.x + FLOW_NODE_W <= graph.width)
    assert.ok(node.y >= 0 && node.y + FLOW_NODE_H <= graph.height)
  }
  for (const link of graph.links) {
    assert.doesNotMatch(link.d, /NaN|Infinity/)
    assert.ok(link.lx >= 0 && link.lx <= graph.width)
    assert.ok(link.ly >= 0 && link.ly + 24 <= graph.height)
  }
})

test('return, skip and branch labels have separate readable positions', () => {
  const { links } = buildFlowGeometry(stages, [...chain, ...branches])
  for (let i = 0; i < links.length; i++) {
    for (let j = i + 1; j < links.length; j++) {
      assert.ok(Math.abs(links[i].lx - links[j].lx) >= 62 || Math.abs(links[i].ly - links[j].ly) >= 25,
        `Overlapping labels: ${links[i].id}, ${links[j].id}`)
    }
  }
})

test('empty, isolated stages and removed transition endpoints remain safe', () => {
  assert.equal(buildFlowGeometry([], []).nodes.length, 0)
  const graph = buildFlowGeometry(stages.slice(0, 1), [{ from_key: '0', to_key: 'removed', count: 1 }])
  assert.equal(graph.nodes.length, 1)
  assert.equal(graph.links.length, 0)
  assert.ok(Number.isFinite(graph.height))
})
