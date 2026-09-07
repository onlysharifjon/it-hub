// Domain lug'atlari — rol/bosqich/holat nomlari va ranglari uchun YAGONA manba.
//
// Ilgari bu jadvallar fayldan-faylga ko'chirilgan edi (ROLE_LABELS 3 joyda,
// STAGE_COLORS 3 joyda) — rol nomini o'zgartirish 5 ta faylni tahrirlashni talab
// qilardi va nusxalar bir-biridan uzoqlashib ketardi (TeacherSalaries'dagi nusxada
// `fullstack` kaliti umuman yo'q edi, ya'ni Fullstack guruhlar rangsiz chiqardi).
// Yangi rol yoki bosqich qo'shilganda faqat shu fayl tahrirlanadi.

// ── Xodim rollari (backend UserRole enum bilan bir xil kalitlar) ─────────────

export const ROLE_LABELS = {
  admin: 'Admin', support_teacher: 'Support Teacher', teacher: "O'qituvchi",
  hunter: 'Hunter', call_center: 'Call Center', sales: 'Sales', audit: 'Audit',
}

// Rol ranglari — badge'da YUMSHOQ (10% tint fon + to'yingan matn) ishlatiladi,
// shuning uchun har biri oq va o'z tinti ustida AA dan o'tadigan darajada
// to'q bo'lishi kerak. To'ldirilgan (solid) variant rol uchun ishlatilmaydi:
// rol — holat emas, uni ekrandagi eng kuchli rang qilishning hojati yo'q.
// Rol ranglari — `--stage-*` tokenlaridan (mavzuga moslashadi).
// Badge ularni `color-mix(... , var(--surface))` bilan yumshatadi.
export const ROLE_COLORS = {
  admin:           'var(--stage-violet-text)',
  support_teacher: 'var(--stage-indigo-text)',
  teacher:         'var(--stage-slate-text)',
  hunter:          'var(--stage-orange-text)',
  call_center:     'var(--stage-teal-text)',
  sales:           'var(--stage-green-text)',
  audit:           'var(--stage-red-text)',
}

// Rol tanlash ro'yxati — ko'rsatish tartibi (eng ko'p ishlatiladigani yuqorida).
export const ROLE_ORDER = [
  'teacher', 'support_teacher', 'hunter', 'sales', 'call_center', 'audit', 'admin',
]
export const ROLE_OPTIONS = ROLE_ORDER.map(value => ({ value, label: ROLE_LABELS[value] }))

export const roleLabel = (role) => ROLE_LABELS[role] || role
export const roleColor = (role) => ROLE_COLORS[role] || 'var(--stage-slate-text)'

// ── Kurs bosqichlari ─────────────────────────────────────────────────────────
// `bar` — progress bar rangi (guruh kartalarida ishlatiladi).

export const STAGE_LABELS = {
  foundation: 'Foundation', fullstack: 'Fullstack', frontend: 'Frontend', backend: 'Backend',
}

// Bosqich ranglari — CSS tokenlari orqali, ya'ni MAVZUGA moslashadi.
//
// Ilgari bu yerda qat'iy hex turardi (`#F3E8FF` fon, `#6D28D9` matn) va
// qorong'i rejimda guruh kartalaridagi bosqich yorlig'i oq-binafsha
// dog' bo'lib qolardi. Endi qiymatlar `styles.css` dagi `--soft-*` va
// `--stage-*` tokenlariga tayanadi: yorug'da yumshoq tint + to'q matn,
// qorong'ida to'q tint + yorug' matn.
export const STAGE_COLORS = {
  foundation: { bg: 'var(--soft-purple)', color: 'var(--stage-violet-text)', bar: 'var(--stage-violet)' },
  fullstack:  { bg: 'var(--soft-green)',  color: 'var(--stage-teal-text)',   bar: 'var(--stage-teal)' },
  frontend:   { bg: 'var(--soft-blue)',   color: 'var(--stage-blue-text)',   bar: 'var(--stage-blue)' },
  backend:    { bg: 'var(--soft-amber)',  color: 'var(--stage-amber-text)',  bar: 'var(--stage-amber)' },
}

// Yangi guruh yaratishda tanlanadigan bosqichlar (frontend/backend — eski
// guruhlarda uchraydi, lekin yangi guruh uchun tanlanmaydi).
export const STAGE_OPTIONS = [
  { value: 'foundation', label: 'Foundation' },
  { value: 'fullstack', label: 'Fullstack' },
]

export const stageLabel = (stage) => STAGE_LABELS[stage] || stage || '—'
export const stageColor = (stage) => STAGE_COLORS[stage] || STAGE_COLORS.foundation

// ── Foydalanuvchi holati (Users sahifasi) ────────────────────────────────────

export const USER_STATUS = {
  active:   { label: 'Faol',            variant: 'success' },
  blocked:  { label: 'Bloklangan',      variant: 'danger'  },
  expired:  { label: "Muddati o'tgan",  variant: 'warning' },
  inactive: { label: 'Nofaol',          variant: 'neutral' },
}

/** Foydalanuvchi qatoridan holat kalitini hisoblaydi (blok > muddat > faollik). */
export function userStatus(user) {
  if (user?.blocked_at) return 'blocked'
  if (user?.expires_at && new Date(user.expires_at) < new Date()) return 'expired'
  if (!user?.is_active) return 'inactive'
  return 'active'
}
