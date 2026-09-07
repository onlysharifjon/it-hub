/**
 * Daraxt geometriyasi — sof hisob-kitob, React'dan mustaqil.
 *
 * ── Nega qayta yozildi ──────────────────────────────────────────────────────
 * Avvalgi variant har bir o'tishni bitta katta yoy (bezier) bilan chizardi.
 * Yoyning kengligi faqat masofaga bog'liq edi, shuning uchun:
 *   • chiziqlar oradagi tugunlar USTIDAN kesib o'tardi;
 *   • uzun yoylar juda ko'p joy egallardi;
 *   • yorliqlar tasodifiy joyga tushardi.
 *
 * Yangi yondashuv — USTUN + YO'LAK (column + lane routing), ya'ni sxema
 * chizmalarida (Linear, Stripe) ishlatiladigan klassik usul:
 *
 *   1. Asosiy yo'l (eng ko'p lid oqadigan zanjir) MARKAZIY ustunga tik tiziladi.
 *   2. Yo'qotish bosqichlari o'ngdagi, qolgan chetki bosqichlar chapdagi
 *      ustunga chiqadi.
 *   3. Ustunlar ORASIDA bo'sh vertikal "yo'lak"lar bor. Qo'shni bo'lmagan
 *      har qanday bog'lanish shu yo'lakdan o'tadi: gorizontal chiqadi →
 *      yo'lakda tik yuradi → gorizontal kiradi.
 *
 * Yo'lakda tugun yo'q, shuning uchun chiziq tugunni kesib o'tishi
 * MATEMATIK JIHATDAN mumkin emas — bu "taxminan yaxshi ko'rinadi" emas,
 * kafolat. Har bir yo'lning o'z yo'lagi bor, shuning uchun chiziqlar ham
 * bir-birining ustiga tushmaydi.
 */

export const NODE_W = 280
export const NODE_H = 92
export const ROW_GAP = 60
export const ROW_PITCH = NODE_H + ROW_GAP

const GUTTER_PAD = 48      // tugun chetidan birinchi yo'lakkacha
const LANE_W = 34          // yo'laklar orasi
const COL_GAP_MIN = 120    // ustunlar orasidagi eng kichik masofa
const CORNER = 14          // burchak radiusi
const LABEL_W = 86         // yorliqning taxminiy kengligi (to'qnashuvni oldini olish)
const LABEL_H = 28

/** Chiziq qalinligi — lidlar soniga mutanosib, 2–9px oralig'ida. */
export function strokeFor(count, max) {
  if (!max || count <= 0) return 2
  return 2 + Math.min(7, Math.round((count / max) * 7))
}

/**
 * Asosiy yo'l — eng ko'p lid oqadigan zanjir.
 *
 * Qattiq kodlangan "Yangi → Keladi → To'landi" yo'q: zanjir HAQIQIY
 * o'tishlardan dinamik hisoblanadi. Admin bosqichlarni o'zgartirsa yoki
 * lidlar boshqacha harakat qilsa, asosiy yo'l ham o'zgaradi.
 *
 * Usul: bosqichlar `order` bo'yicha tartiblangani uchun oldinga yo'nalgan
 * o'tishlar sikl hosil qilmaydi (DAG). Shu DAG ustida dinamik dasturlash
 * bilan eng "og'ir" (ko'p lidli) zanjir topiladi.
 */
export function findMainPath(stages, transitions) {
  if (!stages.length) return []
  const idx = new Map(stages.map((s, i) => [s.key, i]))
  const score = new Map()
  const prev = new Map()

  // Boshlanish nuqtasi — eng birinchi bosqich (eng kichik `order`).
  const start = stages[0]
  score.set(start.key, start.count)

  const forward = transitions
    .filter(t => idx.has(t.from_key) && idx.has(t.to_key) && idx.get(t.to_key) > idx.get(t.from_key))
    .sort((a, b) => idx.get(a.from_key) - idx.get(b.from_key))

  for (const t of forward) {
    const base = score.get(t.from_key)
    if (base == null) continue
    const cand = base + t.count
    if (cand > (score.get(t.to_key) ?? -1)) {
      score.set(t.to_key, cand)
      prev.set(t.to_key, t.from_key)
    }
  }

  // Tugash nuqtasi: imkon bo'lsa "won" bosqichi, aks holda eng og'ir zanjir uchi.
  let end = null
  let bestWon = -1
  for (const s of stages) {
    if (s.kind !== 'won') continue
    const sc = score.get(s.key)
    if (sc != null && sc > bestWon) { bestWon = sc; end = s.key }
  }
  if (!end) {
    let best = -1
    for (const [key, sc] of score) {
      // "lost" bosqichi asosiy yo'lning uchi bo'lmasligi kerak — u chetga chiqadi.
      const st = stages[idx.get(key)]
      if (st.kind === 'lost') continue
      if (sc > best) { best = sc; end = key }
    }
  }
  if (!end) return [start.key]

  const path = []
  let cur = end
  const guard = new Set()
  while (cur && !guard.has(cur)) {
    guard.add(cur)
    path.unshift(cur)
    cur = prev.get(cur)
  }
  return path
}

/**
 * To'liq joylashuv: tugunlar, bog'lovchilar, o'lchamlar.
 */
export function buildLayout(stages, transitions) {
  if (!stages.length) {
    return { nodes: [], links: [], width: 0, height: 0, mainPath: [], mainSet: new Set() }
  }

  const mainPath = findMainPath(stages, transitions)
  const mainSet = new Set(mainPath)
  const byKey = new Map(stages.map(s => [s.key, s]))

  // ── 1. Qatorlar ──
  // Asosiy yo'l tugunlari 0,1,2… qatorlarga tik tiziladi.
  const row = new Map()
  mainPath.forEach((k, i) => row.set(k, i))

  const incoming = new Map()
  for (const t of transitions) {
    if (!byKey.has(t.from_key) || !byKey.has(t.to_key)) continue
    const cur = incoming.get(t.to_key)
    if (!cur || t.count > cur.count) incoming.set(t.to_key, t)
  }

  // Chetki bosqichlar — HAMMASI bitta (o'ng) ustunda.
  //
  // Ilgari ular chap va o'ng ustunlarga bo'lingan edi. Bu chiroyli
  // ko'rinardi, lekin chapdagi tugundan o'ngdagi tugunga boradigan
  // bog'lanish (masalan "Qayta qo'ng'iroq → Rad etildi") markaziy ustunni
  // KESIB O'TISHGA majbur bo'lardi. Bitta yon ustun bilan bunday holat
  // umuman yuzaga kelmaydi: har bir bog'lanishning ikkala uchi ham
  // markaz yoki o'ng ustunda bo'ladi, yo'lak esa ular orasida.
  const offPath = stages.filter(s => !mainSet.has(s.key))
  offPath.sort((a, b) => a.order - b.order)

  const usedSideRows = new Set()
  for (const s of offPath) {
    const src = incoming.get(s.key)
    let want = src && row.has(src.from_key) ? row.get(src.from_key) : 0
    while (usedSideRows.has(want)) want += 1
    usedSideRows.add(want)
    row.set(s.key, want)
  }

  const isCenter = (k) => mainSet.has(k)

  // ── 2. Yo'laklar ──
  const isAdjacentMain = (t) => {
    const a = row.get(t.from_key), b = row.get(t.to_key)
    return isCenter(t.from_key) && isCenter(t.to_key) && b === a + 1
  }

  const routed = transitions.filter(t =>
    byKey.has(t.from_key) && byKey.has(t.to_key) && !isAdjacentMain(t))

  /**
   * Qaysi yo'lak zonasi:
   *   'A' — markaz va o'ng ustun ORASIDA. Barcha bog'lanishlar shu yerdan
   *         o'tadi, chunki ikkala uch ham shu zonaga tegib turadi.
   *   'B' — markazdan CHAPDA. Faqat markaz→markaz ORQAGA qaytishlar uchun —
   *         ular vizual jihatdan ajralib tursin.
   * Ikkala zonada ham tugun yo'q, shuning uchun kesishish mumkin emas.
   */
  const zoneOf = (t) => {
    const back = row.get(t.to_key) < row.get(t.from_key)
    return (back && isCenter(t.from_key) && isCenter(t.to_key)) ? 'B' : 'A'
  }

  const zone = new Map()
  const laneIndex = new Map()
  const counts = { A: 0, B: 0 }

  /* Yo'laklarni ULASHISH.
     Har bir bog'lanishga alohida yo'lak berilsa, 14 ta o'tish 14 ta parallel
     tik chiziq hosil qilardi — natija "elektron plata"ga o'xshab qolgan edi.
     Aslida ikkita bog'lanish TIK oralig'i kesishmasa, bitta yo'lakda bemalol
     tura oladi. Bu — klassik "interval partitioning": har bir yo'lak uchun
     oxirgi band qilingan `y` saqlanadi va yangi bog'lanish shu `y` dan
     pastda boshlansa, o'sha yo'lakka tushadi. */
  const rowY = (k) => (row.get(k) ?? 0) * ROW_PITCH + NODE_H / 2
  const spanOf = (t) => {
    const y1 = rowY(t.from_key), y2 = rowY(t.to_key)
    return [Math.min(y1, y2), Math.max(y1, y2)]
  }
  const LANE_PAD = LABEL_H + 8      // yorliqlar ham bir-biriga tegmasin

  const laneEnds = { A: [], B: [] }
  const byStart = [...routed].sort((a, b) => spanOf(a)[0] - spanOf(b)[0])
  for (const t of byStart) {
    const key = `${t.from_key}->${t.to_key}`
    const z = zoneOf(t)
    const [lo, hi] = spanOf(t)
    let lane = laneEnds[z].findIndex(end => end + LANE_PAD < lo)
    if (lane === -1) { lane = laneEnds[z].length; laneEnds[z].push(hi) }
    else laneEnds[z][lane] = hi
    zone.set(key, z)
    laneIndex.set(key, lane)
  }
  counts.A = laneEnds.A.length
  counts.B = laneEnds.B.length

  // ── 3. Koordinatalar ──
  const hasSideCol = offPath.length > 0
  const bandA = counts.A ? GUTTER_PAD * 2 + (counts.A - 1) * LANE_W : (hasSideCol ? COL_GAP_MIN : 0)
  const bandAW = Math.max(hasSideCol ? COL_GAP_MIN : 0, bandA)
  const bandBW = counts.B ? GUTTER_PAD * 2 + (counts.B - 1) * LANE_W : 0

  const centerLeft = bandBW
  const centerRight = centerLeft + NODE_W
  const sideLeft = centerRight + bandAW
  const width = sideLeft + (hasSideCol ? NODE_W : 0)

  const nodes = stages.map(s => {
    const r = row.get(s.key) ?? 0
    const center = isCenter(s.key)
    const x = center ? centerLeft : sideLeft
    const y = r * ROW_PITCH
    return {
      ...s, row: r, col: center ? 'center' : 'side', x, y,
      cx: x + NODE_W / 2, cy: y + NODE_H / 2,
      left: x, right: x + NODE_W, top: y, bottom: y + NODE_H,
      onMain: center,
    }
  })
  const nodeByKey = new Map(nodes.map(n => [n.key, n]))

  const laneX = (z, i) => z === 'A'
    ? centerRight + GUTTER_PAD + i * LANE_W
    : centerLeft - GUTTER_PAD - i * LANE_W

  const maxCount = transitions.reduce((m, t) => Math.max(m, t.count), 0)

  // ── 4. Bog'lovchilar ──
  const links = []
  for (const t of transitions) {
    const a = nodeByKey.get(t.from_key)
    const b = nodeByKey.get(t.to_key)
    if (!a || !b) continue
    const id = `${t.from_key}->${t.to_key}`
    const onMain = isAdjacentMain(t)

    let d, labelX, labelY, span
    if (onMain) {
      d = `M ${a.cx} ${a.bottom} L ${b.cx} ${b.top}`
      labelX = a.cx
      labelY = (a.bottom + b.top) / 2
      span = [a.bottom, b.top]
    } else {
      const lx = laneX(zone.get(id) || 'A', laneIndex.get(id) || 0)
      // Chiqish/kirish chekkasi YO'LAK TOMONIGA qarab tanlanadi.
      // Ilgari u ustun nomiga qarab tanlanardi va yon ustundagi tugundan
      // chiqqan chiziq o'sha tugunning O'ZINI kesib o'tardi.
      const sx = lx > a.cx ? a.right : a.left
      const tx = lx > b.cx ? b.right : b.left
      d = orthPath(sx, a.cy, tx, b.cy, lx)
      labelX = lx
      labelY = (a.cy + b.cy) / 2
      span = [Math.min(a.cy, b.cy) + CORNER, Math.max(a.cy, b.cy) - CORNER]
    }

    links.push({
      ...t, id, d, labelX, labelY, span, onMain,
      tone: onMain && t.kind === 'normal' ? 'main' : t.kind,
      width: strokeFor(t.count, maxCount) + (onMain ? 1 : 0),
    })
  }

  spreadLabels(links)

  const maxRow = Math.max(0, ...nodes.map(n => n.row))
  const height = maxRow * ROW_PITCH + NODE_H

  return { nodes, links, width, height, mainPath, mainSet }
}

/**
 * Yorliqlarni bir-birining ustidan siljitadi.
 *
 * Yo'laklar 34px oralatilgan, yorliq esa ~58px keng — shuning uchun qo'shni
 * yo'laklardagi yorliqlar bir xil balandlikda bo'lsa ustma-ust tushardi.
 * Yorliq o'z chizig'ining TIK qismida istalgan joyda tura oladi, shuning
 * uchun uni shu oraliq ichida pastga suramiz.
 */
function spreadLabels(links) {
  const placed = []
  const clashes = (x, y) => placed.some(p =>
    Math.abs(p.x - x) < LABEL_W && Math.abs(p.y - y) < LABEL_H)

  // Kalta chiziqlar avval joylashadi — ularda manevr uchun joy kam.
  const sorted = [...links].sort((a, b) => {
    const sa = Math.abs((a.span?.[1] ?? 0) - (a.span?.[0] ?? 0))
    const sb = Math.abs((b.span?.[1] ?? 0) - (b.span?.[0] ?? 0))
    return sa - sb
  })

  for (const l of sorted) {
    const [a, b] = l.span || [l.labelY, l.labelY]
    const lo = Math.min(a, b)
    const hi = Math.max(a, b)
    let best = l.labelY

    if (clashes(l.labelX, best)) {
      // Ikkala yo'nalishda ham qidiramiz — faqat pastga surish yetarli emas edi.
      let found = false
      for (let step = 1; step <= 12 && !found; step++) {
        for (const dir of [1, -1]) {
          const y = l.labelY + dir * step * (LABEL_H * 0.7)
          if (y < lo || y > hi) continue
          if (!clashes(l.labelX, y)) { best = y; found = true; break }
        }
      }
      if (!found) {
        // Chiziq bo'ylab joy yo'q — yorliqni yo'lakdan biroz chetga suramiz.
        // U baribir o'z chizig'ining yonida qoladi, lekin ustma-ust tushmaydi.
        for (const dx of [LABEL_W * 0.62, -LABEL_W * 0.62, LABEL_W * 1.15, -LABEL_W * 1.15]) {
          if (!clashes(l.labelX + dx, l.labelY)) { l.labelX += dx; break }
        }
      }
    }
    l.labelY = best
    placed.push({ x: l.labelX, y: l.labelY })
  }
}

/**
 * To'g'ri burchakli yo'l (burchaklari yumaloqlangan).
 *
 * Gorizontal chiqadi → `laneX` da tik yuradi → gorizontal kiradi.
 * Oraliq qismda x DOIM `laneX` ga teng, ya'ni chiziq ustunlar orasidagi
 * bo'sh yo'lakdan chiqmaydi va hech qanday tugunni kesmaydi.
 */
function orthPath(sx, sy, tx, ty, laneX) {
  const dirY = Math.sign(ty - sy) || 1
  const outSgn = Math.sign(laneX - sx) || 1
  const inSgn = Math.sign(tx - laneX) || 1
  // Burchak radiusi mavjud joydan oshmasin (aks holda yo'l "buriladi").
  const r = Math.max(
    2,
    Math.min(CORNER, Math.abs(laneX - sx) / 2, Math.abs(tx - laneX) / 2, Math.abs(ty - sy) / 2),
  )
  if (Math.abs(ty - sy) < 1) {
    // Bir qatordagi ikki tugun — oddiy to'g'ri chiziq.
    return `M ${sx} ${sy} L ${tx} ${ty}`
  }
  return [
    `M ${sx} ${sy}`,
    `L ${laneX - outSgn * r} ${sy}`,
    `Q ${laneX} ${sy} ${laneX} ${sy + dirY * r}`,
    `L ${laneX} ${ty - dirY * r}`,
    `Q ${laneX} ${ty} ${laneX + inSgn * r} ${ty}`,
    `L ${tx} ${ty}`,
  ].join(' ')
}

/** O'tish ohangi → chiziq rangi (semantik, tasodifiy emas). */
export const LINK_TONE = {
  main:   'var(--primary)',
  normal: 'var(--border-2)',
  skip:   'var(--info)',
  back:   'var(--warning)',
  won:    'var(--success)',
  lost:   'var(--danger)',
}

export const LINK_LABEL = {
  main:   'Asosiy oqim',
  normal: 'Oddiy o‘tish',
  skip:   "To'g'ridan-to'g'ri o'tish",
  back:   'Orqaga qaytish',
  won:    'Konversiya',
  lost:   "Yo'qotish",
}

/** Afsonada ko'rsatiladigan tartib. */
export const LEGEND_ORDER = ['main', 'won', 'lost', 'skip', 'back', 'normal']

/** Bosqich rangi — backend kalitini CSS token'iga bog'laydi. */
const STAGE_COLORS = new Set([
  'sky', 'indigo', 'amber', 'violet', 'emerald', 'red', 'slate',
  'purple', 'teal', 'rose', 'blue', 'green', 'orange', 'cyan',
])
export function stageColor(color, kind) {
  if (color && STAGE_COLORS.has(color)) return `var(--stage-${color})`
  if (kind === 'won') return 'var(--success)'
  if (kind === 'lost') return 'var(--danger)'
  if (kind === 'unknown') return 'var(--muted)'
  return 'var(--stage-slate)'
}
