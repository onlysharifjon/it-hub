import { useTheme } from '../ThemeContext'

const PALETTE = {
  light: { fill: '#3d63d4', star: '#ffffff' },
  dark:  { fill: '#00e676', star: '#000000' },
  ocean: { fill: '#0ea5e9', star: '#ffffff' },
}

export default function MinarWatermark({ size = 360 }) {
  const { theme } = useTheme()
  const { fill, star } = PALETTE[theme] ?? PALETTE.light

  const S = 1.8, TX = 110, TY = 20
  const r = 25 * S

  const flowers = [
    [50, 28], [65.6, 34.4], [72, 50], [65.6, 65.6],
    [50, 72], [34.4, 65.6], [28, 50], [34.4, 34.4],
  ]

  const starPts = Array.from({ length: 16 }, (_, i) => {
    const a = (270 + i * 22.5) * (Math.PI / 180)
    const R = i % 2 === 0 ? 32 : 22
    return `${((50 + R * Math.cos(a)) * S + TX).toFixed(1)},${((50 + R * Math.sin(a)) * S + TY).toFixed(1)}`
  }).join(' ')

  return (
    <svg
      viewBox="0 0 400 440"
      width={size}
      height={size * 440 / 400}
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <defs>
        <clipPath id="minar-wm-clip">
          {flowers.map(([cx, cy], i) => (
            <circle key={i} cx={cx * S + TX} cy={cy * S + TY} r={r} />
          ))}
        </clipPath>
      </defs>

      <rect width="400" height="440" fill={fill} clipPath="url(#minar-wm-clip)" />
      <polygon points={starPts} fill={star} clipPath="url(#minar-wm-clip)" />

      <text x="200" y="232" textAnchor="middle" fill={fill}
        fontSize="26" fontFamily="Inter, sans-serif" fontWeight="500" letterSpacing="3">
        Academy
      </text>

      <text x="200" y="370" textAnchor="middle" fill={fill}
        fontSize="145" fontFamily="Inter, sans-serif" fontWeight="800" letterSpacing="-4">
        Minar
      </text>
    </svg>
  )
}
