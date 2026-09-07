import { useEffect as useReactEffect, useState as useReactState } from 'react'

/**
 * Mavzu (yorug'/qorong'i) — yagona boshqaruv nuqtasi.
 *
 * Ilgari ilovada uchta mavzu bor edi (light/dark/ocean) va ularning ikkitasi
 * yarim ishlardi: sahifalarning bir qismi xom hex bilan yozilgani uchun
 * almashtirilganda oq holicha qolardi. Endi ikkita rejim va bitta qoida —
 * hamma narsa `styles.css` dagi semantik tokenlardan rang oladi.
 *
 * Tanlov qanday aniqlanadi:
 *   1) foydalanuvchi aniq tanlagan bo'lsa — localStorage dagi qiymat;
 *   2) aks holda — operatsion tizim sozlamasi (prefers-color-scheme).
 * Foydalanuvchi tanlamagan bo'lsa, OS sozlamasi o'zgarganda ilova ham
 * darhol ergashadi.
 *
 * `data-theme` atributi <html> ga qo'yiladi. Boshlang'ich qiymat esa
 * index.html dagi kichik skript orqali React yuklanguncha o'rnatiladi —
 * shuning uchun sahifa hech qachon "oq chaqnab" keyin qorayimaydi.
 */

const KEY = 'theme'          // 'light' | 'dark'  (yo'q bo'lsa — OS bo'yicha)
const listeners = new Set()

function systemTheme() {
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

/** Foydalanuvchi aniq tanlagan qiymat (yoki null). */
export function storedTheme() {
  try {
    const v = localStorage.getItem(KEY)
    return v === 'light' || v === 'dark' ? v : null
  } catch { return null }
}

/** Hozir amalda bo'lgan rejim. */
export function currentTheme() {
  return storedTheme() ?? systemTheme()
}

function apply(theme) {
  const root = document.documentElement
  if (theme === 'dark') root.setAttribute('data-theme', 'dark')
  else root.removeAttribute('data-theme')
  // Brauzer UI (manzil paneli, form boshqaruvlari) ham moslashsin
  document.querySelector('meta[name="theme-color"]')
    ?.setAttribute('content', theme === 'dark' ? '#0B0F19' : '#FFFFFF')
}

/** Rejimni o'rnatadi va eslab qoladi. */
export function setTheme(theme) {
  try { localStorage.setItem(KEY, theme) } catch {}
  apply(theme)
  listeners.forEach(fn => fn(theme))
}

/** O'zgarishlarga obuna (Topbar tugmasi shu orqali yangilanadi). */
export function onThemeChange(fn) {
  listeners.add(fn)
  return () => listeners.delete(fn)
}

/** Ilova yuklanganda bir marta chaqiriladi. */
export function initTheme() {
  apply(currentTheme())

  // Foydalanuvchi aniq tanlamagan bo'lsa — OS sozlamasiga ergashamiz
  const mq = window.matchMedia?.('(prefers-color-scheme: dark)')
  mq?.addEventListener?.('change', () => {
    if (storedTheme()) return
    const t = systemTheme()
    apply(t)
    listeners.forEach(fn => fn(t))
  })

  // Boshqa tabda o'zgartirilsa — bu tab ham ergashadi
  window.addEventListener('storage', e => {
    if (e.key !== KEY) return
    const t = currentTheme()
    apply(t)
    listeners.forEach(fn => fn(t))
  })
}

/** React hook — joriy rejimni kuzatadi (komponentlar shu orqali moslashadi). */
export function useTheme() {
  const [theme, set] = useReactState(currentTheme)
  useReactEffect(() => onThemeChange(set), [])
  return theme
}
