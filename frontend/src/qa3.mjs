import { chromium } from 'playwright'
const SP = process.env.SP
const b = await chromium.launch()
const ctx = await b.newContext({ viewport: { width: 1440, height: 950 }, deviceScaleFactor: 2 })
const p = await ctx.newPage()
p.on('pageerror', e => console.log('PAGEERROR', e.message))
await p.goto('http://127.0.0.1:8098/', { waitUntil: 'networkidle' })
await p.fill('input[type="text"]', 'admin'); await p.fill('input[type="password"]', 'PreviewOnly#2026')
await p.click('.lp-btn'); await p.waitForTimeout(2500)
await p.goto('http://127.0.0.1:8098/#groups', { waitUntil: 'domcontentloaded' }); await p.waitForTimeout(2200)
await p.click('.group-card'); await p.waitForTimeout(2600)
const cert = await p.$('button:has-text("Sertifikat")')
if (cert) { await cert.click(); await p.waitForTimeout(1500) }
const gen = await p.$('button:has-text("Generatsiya qilish")')
if (gen) { await gen.click(); await p.waitForTimeout(4000) }
await p.screenshot({ path: `${SP}/shots/b-cert.png` })
const info = await p.evaluate(() => {
  const l = document.querySelector('.mcert-logo')
  if (!l) return 'no logo'
  const r = l.getBoundingClientRect()
  return { src: l.getAttribute('src'), css: `${Math.round(r.width)}x${Math.round(r.height)}`, nat: `${l.naturalWidth}x${l.naturalHeight}` }
})
console.log('cert logo:', JSON.stringify(info))
await b.close()
