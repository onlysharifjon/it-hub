import { BRAND_ASSETS, BRAND_NAME, BRAND_SIZES } from '../../constants/brand'
import { useTheme } from '../../theme'

/**
 * Yagona brend komponenti.
 *
 * Nima uchun: logotip ilova bo'ylab uch xil usulda chizilardi va har bir
 * joyda o'lchami qo'lda tanlanardi. Bu komponent bitta qoidani majburlaydi:
 *   • logotip BALANDLIK bilan o'lchanadi, kenglik nisbatdan hisoblanadi
 *     (shuning uchun hech qachon cho'zilmaydi/siqilmaydi);
 *   • <img> ga width/height beriladi — rasm yuklanguncha joy band bo'ladi,
 *     sahifa sakramaydi;
 *   • `object-fit: contain` — hech qanday holatda kesilmaydi;
 *   • bezak sifatida ishlatilganda alt bo'sh bo'ladi (skrinriderga ortiqcha
 *     "Minar Academy" o'qib berilmaydi).
 *
 * variant : full  — belgi + yozuv (keng joy: kirish, ochiq forma, yon panel)
 *           stack — belgi ustida yozuv ostida (kvadratga yaqin joy)
 *           mark  — faqat belgi (tor joy: yig'ilgan menyu, mobil, bo'sh holat)
 *           print — chop uchun yuqori aniqlik (sertifikat)
 * tone    : 'auto'  — mavzuga qarab o'zi tanlaydi (standart)
 *           'brand' — brend ko'ki (ochiq yuzalar uchun)
 *           'white' — oq variant (to'q/rangli yuzalar uchun)
 * size    : xs 16 · sm 20 · md 24 · lg 32 · xl 44 · hero 64 — yoki `height`
 */
export default function BrandLogo({
  variant = 'full',
  tone = 'auto',
  size = 'md',
  height,
  decorative = false,
  className = '',
  style,
  ...rest
}) {
  const theme = useTheme()
  const group = BRAND_ASSETS[variant] || BRAND_ASSETS.full
  // 'auto' — qorong'i rejimda oq variant. Brend ko'ki (#2961FF) to'q
  // fonda kontrastda yutqazadi va logotip "so'nib" ko'rinadi.
  const resolved = tone === 'auto' ? (theme === 'dark' ? 'white' : 'brand') : tone
  const asset = group[resolved] || group.brand
  const h = height ?? BRAND_SIZES[size] ?? BRAND_SIZES.md
  const w = Math.round(h * asset.ratio)

  return (
    <img
      src={asset.src}
      srcSet={asset.srcSet}
      width={w}
      height={h}
      alt={decorative ? '' : BRAND_NAME}
      aria-hidden={decorative ? 'true' : undefined}
      draggable="false"
      className={`brand-logo ${className}`.trim()}
      style={{ height: h, width: w, ...style }}
      {...rest}
    />
  )
}
