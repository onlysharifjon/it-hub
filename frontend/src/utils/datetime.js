/**
 * Vaqt bilan ishlash — yagona joy.
 *
 * Backend `datetime.utcnow()` (naive UTC) saqlaydi, lekin javob berishda
 * `backend/main.py` dagi global encoder uni Toshkent vaqtiga o'giradi va
 * mintaqa bilan qaytaradi: "2026-09-05T02:42:55+05:00". Bunday qator
 * `new Date()` tomonidan to'g'ri o'qiladi.
 *
 * Shunga qaramay `parseTs` mintaqasiz qatorlarga 'Z' qo'shadi: agar biror
 * endpoint (yoki kelajakdagi yangi kod) o'sha global encoder'dan chetlab
 * o'tsa, mintaqasiz vaqt BROWSER mintaqasi deb o'qilib, Toshkentda 5 soat
 * xato ko'rsatardi. Mintaqasi bor qatorlarga tegilmaydi — aks holda ular
 * ikki marta siljib ketardi.
 */

/** ISO qatorni Date'ga o'giradi; noto'g'ri qiymat uchun null. */
export function parseTs(iso) {
  if (!iso) return null
  const hasZone = /(?:Z|[+-]\d{2}:?\d{2})$/.test(iso)
  const d = new Date(hasZone ? iso : iso + 'Z')
  return isNaN(d) ? null : d
}

/** "04.09.2026, 16:27" */
export function fmtDateTime(iso) {
  const d = parseTs(iso)
  return d ? d.toLocaleString('uz-UZ', { dateStyle: 'short', timeStyle: 'short' }) : ''
}

/** "16:27" */
export function fmtTime(iso) {
  const d = parseTs(iso)
  return d ? d.toLocaleTimeString('uz-UZ', { hour: '2-digit', minute: '2-digit' }) : ''
}

/** "04.09.2026" */
export function fmtDay(iso) {
  const d = parseTs(iso)
  return d ? d.toLocaleDateString('uz-UZ', { day: '2-digit', month: '2-digit', year: 'numeric' }) : ''
}

/**
 * Kun sarlavhasi — "Bugun" / "Kecha" / "04.09.2026".
 * Izohlar oqimida sanani har qatorda takrorlamaslik uchun.
 */
export function fmtDayLabel(iso) {
  const d = parseTs(iso)
  if (!d) return ''
  const today = new Date()
  const yesterday = new Date(today.getTime() - 86400000)
  if (d.toDateString() === today.toDateString()) return 'Bugun'
  if (d.toDateString() === yesterday.toDateString()) return 'Kecha'
  return fmtDay(iso)
}

/** "hozirgina" / "12 daqiqa oldin" / "3 soat oldin" / "04.09.2026". */
export function fmtRelative(iso) {
  const d = parseTs(iso)
  if (!d) return ''
  const sec = Math.round((Date.now() - d.getTime()) / 1000)
  if (sec < 0) return fmtDateTime(iso)     // kelajakdagi vaqt — aniq ko'rsatamiz
  if (sec < 60) return 'hozirgina'
  const min = Math.floor(sec / 60)
  if (min < 60) return `${min} daqiqa oldin`
  const hour = Math.floor(min / 60)
  if (hour < 24) return `${hour} soat oldin`
  const day = Math.floor(hour / 24)
  if (day === 1) return 'kecha'
  if (day < 7) return `${day} kun oldin`
  return fmtDay(iso)
}

/** Sana kaliti — kun bo'yicha guruhlash uchun ("2026-09-04"). */
export function dayKey(iso) {
  const d = parseTs(iso)
  if (!d) return ''
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

/**
 * Toshkent kalendaridagi bugungi sana ("2026-09-05").
 *
 * Nega brauzerning o'z sanasi yaramaydi: backend sana filtrlarini DOIM
 * Toshkent kuni deb tushunadi (`_wc_day_bounds`). Agar frontend qurilma
 * mintaqasidagi "bugun"ni yuborsa, boshqa mintaqadagi (yoki UTC'da ishlayotgan)
 * brauzer bir kun oldingi/keyingi oraliqni so'rab, statistikani bo'sh
 * ko'rsatardi. Sana hisobi ikkala tomonda bir xil bo'lishi shart.
 */
export function tashkentToday() {
  return tashkentDate(new Date())
}

/** Berilgan vaqtning Toshkentdagi kalendar sanasi ("YYYY-MM-DD"). */
export function tashkentDate(d) {
  const utcMs = d.getTime() + d.getTimezoneOffset() * 60000
  const tk = new Date(utcMs + 5 * 3600000)
  return `${tk.getFullYear()}-${String(tk.getMonth() + 1).padStart(2, '0')}-${String(tk.getDate()).padStart(2, '0')}`
}

/**
 * Toshkent devor-soati `Date` ko'rinishida.
 *
 * Qaytgan obyektning MAHALLIY getter'lari (`getFullYear`, `getMonth`,
 * `getDate`, `getHours`) Toshkent qiymatlarini beradi — shuning uchun
 * `new Date()` o'rniga to'g'ridan-to'g'ri qo'yish mumkin.
 *
 * DIQQAT: bu "siljitilgan" sana — u haqiqiy paytni bildirmaydi. Uni
 * `getTime()`, `toISOString()` yoki boshqa vaqt bilan taqqoslash uchun
 * ISHLATMANG; faqat "hozir qaysi oy/yil/kun?" degan savolga javob beradi.
 * Haqiqiy payt kerak bo'lsa — oddiy `new Date()`.
 */
export function tashkentNow() {
  return tashkentWall(new Date())
}

/** Ixtiyoriy `Date` → Toshkent devor-soatini ko'rsatuvchi "siljitilgan" Date. */
export function tashkentWall(d) {
  return new Date(d.getTime() + d.getTimezoneOffset() * 60000 + 5 * 3600000)
}

/**
 * `<input type="datetime-local">` qiymati → serverga yuboriladigan ISO.
 *
 * Brauzer `new Date("2026-09-07T14:11")` ni O'Z mintaqasi bo'yicha o'qiydi.
 * Xodimning noutbuki boshqa mintaqada (yoki UTC'da) bo'lsa, "14:11 ga
 * qo'ng'iroq" boshqa paytga saqlanardi. CRM'da kiritilgan vaqt HAR DOIM
 * Toshkent vaqti — shuning uchun bu yerda qo'lda +05:00 deb belgilanadi.
 */
export function inputToIso(value) {
  if (!value) return null
  const m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(value)
  if (!m) return null
  const [, y, mo, d, h, mi] = m
  const ms = Date.UTC(+y, +mo - 1, +d, +h, +mi) - 5 * 3600000
  return new Date(ms).toISOString()
}

/** Serverdan kelgan ISO → `<input type="datetime-local">` qiymati (Toshkent). */
export function isoToInput(iso) {
  const d = parseTs(iso)
  if (!d) return ''
  const t = tashkentWall(d)
  const p = n => String(n).padStart(2, '0')
  return `${t.getFullYear()}-${p(t.getMonth() + 1)}-${p(t.getDate())}T${p(t.getHours())}:${p(t.getMinutes())}`
}

/** Toshkent sanasini kun bo'yicha suradi ("2026-09-05", -1 → "2026-09-04"). */
export function shiftDay(isoDay, days) {
  const [y, m, d] = isoDay.split('-').map(Number)
  const dt = new Date(Date.UTC(y, m - 1, d))
  dt.setUTCDate(dt.getUTCDate() + days)
  return dt.toISOString().slice(0, 10)
}
