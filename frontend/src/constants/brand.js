/**
 * BREND AKTIVLARI — YAGONA MANBA.
 *
 * Ilgari logotip uch xil joyda uch xil usulda chizilardi: `MinaretLogo.jsx`
 * (qo'lda yozilgan SVG — rasmiy belgi EMAS, unga o'xshatib chizilgan),
 * sertifikatdagi ichki `<use href="#mcertMark">` va "Minar / Academy" matni.
 * Natijada bir mahsulotda uchta har xil "logotip" bor edi.
 *
 * Endi barcha joylar shu ro'yxatdagi HAQIQIY aktivlarni ishlatadi. Fayllar
 * `data/` dagi 4500×4500 asl nusxalardan tayyorlangan (kesish, trim, veb
 * o'lchamlariga siqish) — hech qanday qayta chizish yoki rang o'zgartirish
 * yo'q; oq variant esa rasmiy oq lokapning (Untitled-1-07/01) aynan
 * geometriyasidan olingan.
 *
 * Nisbatlar bu yerda saqlanadi, chunki <img> ga width/height berilsa brauzer
 * joyni oldindan band qiladi va rasm yuklanganda sahifa "sakramaydi".
 */

/* nginx `/brand/*.png` ni `Cache-Control: immutable, 1 yil` bilan beradi va
   fayl nomlarida hash yo'q. Logotip almashtirilsa brauzer eskisini bir yil
   ushlab turmasligi uchun manzilga versiya belgisi qo'shiladi — logotip
   yangilanganda faqat shu raqam oshiriladi. */
const V = '1'
const BASE = `/brand`
const u = (file) => `${BASE}/${file}?v=${V}`

/** variant → { src, srcSet, ratio (w/h) } */
export const BRAND_ASSETS = {
  // Gorizontal lokap: belgi + "Minar Academy". Asosiy brend ko'rinishi.
  full: {
    brand: { src: u('minar-logo-full.png'),       srcSet: `${u('minar-logo-full.png')} 1x, ${u('minar-logo-full@2x.png')} 2x`,       ratio: 1200 / 291 },
    white: { src: u('minar-logo-full-white.png'), srcSet: `${u('minar-logo-full-white.png')} 1x, ${u('minar-logo-full-white@2x.png')} 2x`, ratio: 1200 / 291 },
  },
  // Vertikal lokap: belgi ustida, yozuv ostida. Kvadratga yaqin joylar uchun.
  stack: {
    brand: { src: u('minar-logo-stack.png'),       ratio: 900 / 616 },
    white: { src: u('minar-logo-stack-white.png'), ratio: 900 / 616 },
  },
  // Faqat belgi. Tor joy: yig'ilgan menyu, mobil sarlavha, bo'sh holatlar.
  mark: {
    brand: { src: u('minar-mark.png'),       srcSet: `${u('minar-mark.png')} 1x, ${u('minar-mark@2x.png')} 2x`,             ratio: 1 },
    white: { src: u('minar-mark-white.png'), srcSet: `${u('minar-mark-white.png')} 1x, ${u('minar-mark-white@2x.png')} 2x`, ratio: 1 },
  },
  // Chop etish (sertifikat, hisobot): 3200px kenglikdagi lokap.
  print: {
    brand: { src: u('minar-logo-print.png'), ratio: 3200 / 775 },
  },
}

/** Ilova ikonkasi / favicon — oq belgi to'q ko'k kvadratda (Untitled-1-01). */
export const BRAND_ICON = {
  ico32:  u('minar-icon-32.png'),
  ico180: u('minar-icon-180.png'),
  ico192: u('minar-icon-192.png'),
  ico512: u('minar-icon-512.png'),
}

/** Rasmiy brend nomi — alt matn va sarlavhalar uchun yagona manba. */
export const BRAND_NAME = 'Minar Academy'
export const BRAND_PRODUCT = 'Minar Academy LMS'

/** Rasmiy brend ranglari (aktivlardan piksel bo'yicha olingan).
 *  Mahsulot interfeysi binafsha; bular faqat LOGOTIPGA tegishli. */
export const BRAND_COLORS = {
  blue:  '#2961FF',
  green: '#20CE94',
}

/** Balandlik bo'yicha o'lchamlar. Logotip har doim BALANDLIK bilan
 *  o'lchanadi — lokap va belgining nisbatlari har xil, shuning uchun
 *  kenglik bo'yicha o'lchash ularni bir qatorda turli kattalikda ko'rsatardi. */
export const BRAND_SIZES = { xs: 16, sm: 20, md: 24, lg: 32, xl: 44, hero: 64 }
