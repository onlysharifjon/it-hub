// Shared geometry for the responsive charts; missing points stay missing.
export function chartScale(data) {
  const values = data.flatMap(d => [d.value, d.compare, d.line])
    .filter(v => v != null && Number.isFinite(Number(v))).map(Number)
  const low = Math.min(0, ...values)
  const high = Math.max(0, ...values)
  const raw = (high - low || 1) / 4
  const power = 10 ** Math.floor(Math.log10(raw))
  const step = [1, 2, 2.5, 5, 10].find(n => n * power >= raw) * power
  const min = Math.floor(low / step) * step
  const max = Math.ceil((high || step) / step) * step
  const span = max - min || 1
  const y = v => 100 - ((Number(v) - min) / span) * 100
  const ticks = Array.from({ length: Math.round(span / step) + 1 }, (_, i) => max - i * step)
  return { min, max, ticks, y, zero: y(0) }
}

// Monotone cubic segments do not invent peaks between the observed values.
export function linePath(points) {
  const runs = []
  let current = []
  for (const point of points) {
    if (point) current.push(point)
    else if (current.length) { runs.push(current); current = [] }
  }
  if (current.length) runs.push(current)
  return runs.map(run => {
    let d = `M ${run[0].x} ${run[0].y}`
    const slopes = run.slice(1).map((p, i) => (p.y - run[i].y) / (p.x - run[i].x))
    const tangents = run.map((_, i) => {
      if (i === 0) return slopes[0] || 0
      if (i === run.length - 1) return slopes[i - 1] || 0
      const a = slopes[i - 1], b = slopes[i]
      return a * b <= 0 ? 0 : 2 * a * b / (a + b)
    })
    for (let i = 1; i < run.length; i++) {
      const a = run[i - 1], b = run[i], dx = (b.x - a.x) / 3
      d += ` C ${a.x + dx} ${a.y + tangents[i - 1] * dx}, ${b.x - dx} ${b.y - tangents[i] * dx}, ${b.x} ${b.y}`
    }
    return d
  }).join(' ')
}
