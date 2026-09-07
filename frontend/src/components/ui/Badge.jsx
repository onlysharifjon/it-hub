import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'

/**
 * Yagona badge komponenti — status/rol/holat belgilari uchun.
 *
 * Ilgari ranglar har bir joyda `style={{background, color}}` bilan qo'lda
 * yozilardi (~18 ta alohida nusxa) — natijada bir xil ma'nodagi belgilar turli
 * sahifalarda turlicha ko'rinardi va dark/ocean mavzuda buzilardi. Endi ranglar
 * design token'lardan keladi, ya'ni mavzu bilan birga o'zgaradi.
 *
 * Variantlar: neutral · primary · accent · success · warning · danger · info
 * O'lchamlar: sm · md (standart)
 *
 *   <Badge variant="success">Faol</Badge>
 *   <Badge variant="danger" icon={faLock}>Bloklangan</Badge>
 *   <Badge color="#ea580c" solid>Hunter</Badge>   // maxsus rang kerak bo'lsa
 */
export default function Badge({
  children,
  variant = 'neutral',
  size = 'md',
  icon,
  solid = false,
  color,
  className = '',
  ...rest
}) {
  // `color` berilgan bo'lsa — token'lar o'rniga aniq rang (masalan rol ranglari,
  // ular domain lug'atida saqlanadi va mavzuga bog'liq emas).
  // Yumshoq variant foni — rangning joriy YUZA ustidagi tinti.
  // Ilgari `${color}1a` (alfa) edi: fon nima bo'lsa shunga qo'shilib
  // ketardi. Endi `color-mix` bilan qattiq rang, va u `--surface` ga
  // tayangani uchun qorong'i rejimda o'zi to'q tintga aylanadi.
  const style = color
    ? (solid
        ? { background: color, color: 'var(--primary-on)' }
        : { background: `color-mix(in srgb, ${color} 16%, var(--surface))`, color })
    : undefined

  return (
    <span
      className={`ui-badge ui-badge-${size} ${color ? '' : `ui-badge-${variant}`} ${solid && !color ? 'is-solid' : ''} ${className}`.trim()}
      style={style}
      {...rest}
    >
      {icon && <FontAwesomeIcon icon={icon} />}
      {children}
    </span>
  )
}
