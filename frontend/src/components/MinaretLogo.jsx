import { useId } from 'react'
import { useTheme } from '../ThemeContext'

const PALETTES = {
  light: { starA: '#6d28d9', starB: '#2563eb', starC: '#06b6d4', centA: '#1e1b4b', centB: '#0c4a6e' },
  dark:  { starA: '#00e676', starB: '#00c853', starC: '#00a040', centA: '#050505', centB: '#000000' },
  ocean: { starA: '#38bdf8', starB: '#0ea5e9', starC: '#0284c7', centA: '#082f49', centB: '#0c1a2e' },
}

export default function MinaretLogo({ size = 36, className = '', style = {} }) {
  const { theme } = useTheme()
  const p = PALETTES[theme] ?? PALETTES.light

  const uid = useId().replace(/\W/g, '')
  const cid  = `itfl${uid}`
  const grad = `itgr${uid}`
  const grd2 = `itgr2${uid}`

  const R = 32, r = 22, cx = 50, cy = 50
  const starPts = Array.from({ length: 16 }, (_, i) => {
    const angle = (270 + i * 22.5) * (Math.PI / 180)
    const radius = i % 2 === 0 ? R : r
    return `${(cx + radius * Math.cos(angle)).toFixed(2)},${(cy + radius * Math.sin(angle)).toFixed(2)}`
  }).join(' ')

  const centerPts = Array.from({ length: 8 }, (_, i) => {
    const angle = (292.5 + i * 45) * (Math.PI / 180)
    return `${(cx + 13 * Math.cos(angle)).toFixed(2)},${(cy + 13 * Math.sin(angle)).toFixed(2)}`
  }).join(' ')

  return (
    <svg
      width={size} height={size}
      viewBox="0 0 100 100"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      style={style}
      aria-hidden="true"
    >
      <defs>
        <clipPath id={cid}>
          <circle cx="50"   cy="28"   r="25" />
          <circle cx="65.6" cy="34.4" r="25" />
          <circle cx="72"   cy="50"   r="25" />
          <circle cx="65.6" cy="65.6" r="25" />
          <circle cx="50"   cy="72"   r="25" />
          <circle cx="34.4" cy="65.6" r="25" />
          <circle cx="28"   cy="50"   r="25" />
          <circle cx="34.4" cy="34.4" r="25" />
        </clipPath>

        <linearGradient id={grad} x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%"   stopColor={p.starA} />
          <stop offset="50%"  stopColor={p.starB} />
          <stop offset="100%" stopColor={p.starC} />
        </linearGradient>

        <linearGradient id={grd2} x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%"   stopColor={p.centA} />
          <stop offset="100%" stopColor={p.centB} />
        </linearGradient>
      </defs>

      {/* Outer flower — white */}
      <rect x="0" y="0" width="100" height="100"
        fill="#ffffff"
        clipPath={`url(#${cid})`}
      />

      {/* 8-pointed star — theme gradient */}
      <polygon
        points={starPts}
        fill={`url(#${grad})`}
        clipPath={`url(#${cid})`}
      />

      {/* Center octagon — dark (not jigar) */}
      <polygon
        points={centerPts}
        fill={`url(#${grd2})`}
        clipPath={`url(#${cid})`}
      />
    </svg>
  )
}
