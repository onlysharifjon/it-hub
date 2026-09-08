import test from 'node:test'
import assert from 'node:assert/strict'
import { chartScale, linePath } from '../src/components/ui/chartGeometry.js'

test('income, expense and loss share an axis containing zero and every value', () => {
  const scale = chartScale([{ value: 24000000, compare: 30000000, line: -6000000 }])
  assert.ok(scale.min <= -6000000)
  assert.ok(scale.max >= 30000000)
  assert.ok(scale.y(-6000000) > scale.zero)
  assert.ok(scale.y(24000000) < scale.zero)
  assert.ok(scale.ticks.includes(0))
})

test('empty, zero and invalid inputs produce a finite nonzero scale', () => {
  for (const data of [[], [{ value: 0 }], [{ value: null, line: undefined }], [{ value: 'invalid' }]]) {
    const scale = chartScale(data)
    assert.ok(Number.isFinite(scale.zero))
    assert.ok(scale.max > scale.min)
    assert.ok(scale.ticks.every(Number.isFinite))
  }
})

test('missing months break the line instead of connecting unrelated observations', () => {
  const path = linePath([{ x: 0, y: 30 }, { x: 50, y: 20 }, null, { x: 150, y: 50 }, { x: 200, y: 10 }])
  assert.equal((path.match(/M /g) || []).length, 2)
  assert.equal((path.match(/ C /g) || []).length, 2)
  assert.ok(!path.includes('NaN'))
})

test('flat and isolated observations remain finite', () => {
  assert.equal(linePath([null, { x: 50, y: 20 }, null]), 'M 50 20')
  assert.equal(linePath([]), '')
  const path = linePath([{ x: 0, y: 20 }, { x: 50, y: 20 }, { x: 100, y: 20 }])
  assert.ok(!path.includes('NaN'))
  assert.ok(!path.includes('Infinity'))
})

test('curves flatten at local extrema, avoiding misleading overshoot', () => {
  const path = linePath([{ x: 0, y: 50 }, { x: 30, y: 10 }, { x: 60, y: 50 }])
  assert.match(path, /20 10, 30 10 C 40 10/)
})
