import { useEffect, useState } from 'react'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faSun, faMoon } from '@fortawesome/free-solid-svg-icons'
import { currentTheme, setTheme, onThemeChange } from '../../theme'

const MODES = [
  { key: 'light', icon: faSun,  label: "Yorug' rejim" },
  { key: 'dark',  icon: faMoon, label: "Qorong'i rejim" },
]

/**
 * Yorug'/qorong'i almashtirgichi.
 *
 * Ilgari bu yerda uchta variantli tanlagich turardi (light/dark/ocean) va
 * uchtasidan ikkitasi to'liq ishlamasdi. Endi ikkita rejim, segmentli
 * boshqaruv ko'rinishida: joriy holat ko'tarilgan plashka bilan ko'rinadi,
 * `aria-pressed` esa uni skrinriderga aytadi. Klaviatura bilan ham
 * ishlaydi — bular oddiy tugmalar.
 */
export default function ThemeToggle() {
  const [theme, setLocal] = useState(currentTheme)

  // Boshqa manba (OS sozlamasi, boshqa tab) o'zgartirsa ham yangilanamiz
  useEffect(() => onThemeChange(setLocal), [])

  return (
    <div className="theme-toggle" role="group" aria-label="Ko'rinish rejimi">
      {MODES.map(m => (
        <button
          key={m.key}
          type="button"
          className={theme === m.key ? 'active' : ''}
          onClick={() => { setTheme(m.key); setLocal(m.key) }}
          title={m.label}
          aria-label={m.label}
          aria-pressed={theme === m.key}
        >
          <FontAwesomeIcon icon={m.icon} />
        </button>
      ))}
    </div>
  )
}
