import { useEffect } from 'react'

/**
 * Escape bilan yopish + Tab fokusini modal ichida ushlab turish.
 *
 * Ilgari bu hook Leads.jsx ichida yopiq turgan va faqat o'sha sahifadagi 4 ta
 * oyna/drawer'da ishlatilgan edi — qolgan ~30 ta modal Escape'ni ham, fokus
 * tutqichini ham bilmasdi. Endi umumiy: Modal/Drawer shu hookdan foydalanadi.
 *
 * @param {boolean} active         hook faolmi (oyna ochiqmi)
 * @param {object}  containerRef   oyna konteyneriga ref
 * @param {function} onEscape      Escape bosilganda chaqiriladi
 */
export default function useFocusTrap(active, containerRef, onEscape) {
  useEffect(() => {
    if (!active) return
    const el = containerRef.current
    if (!el) return
    const focusables = () => Array.from(
      el.querySelectorAll('button, a[href], input, select, textarea, [tabindex]:not([tabindex="-1"])')
    ).filter(n => !n.disabled)
    focusables()[0]?.focus()
    function onKey(e) {
      if (e.key === 'Escape') { onEscape(); return }
      if (e.key !== 'Tab') return
      const f = focusables()
      if (!f.length) return
      const first = f[0], last = f[f.length - 1]
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus() }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus() }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [active])
}
