import {
  faBook, faUserGraduate, faUsers, faCreditCard,
  faChartBar, faCalendarCheck, faTag, faWallet, faUserShield,
  faChalkboardTeacher, faReceipt, faHeadset, faBullseye, faStar,
  faRightLeft, faBookOpen, faGraduationCap, faCommentDots, faPeopleRoof,
  faTriangleExclamation, faRobot, faComments, faMoneyBillWave,
  faSitemap, faListCheck, faUsersGear, faCashRegister, faDesktop,
  faRocket,
} from '@fortawesome/free-solid-svg-icons'

/**
 * Navigatsiya — YAGONA manba.
 *
 * Ilgari har bir tugma Sidebar.jsx ichida qo'lda `{isHunter && ...}` kabi
 * shartlar bilan o'ralgan edi: "kim nimani ko'radi" degan savolga javob berish
 * uchun 500 qatorli JSX'ni o'qib chiqish kerak edi va yangi sahifa qo'shilganda
 * shartni unutish oson edi. Endi ro'yxat ma'lumot sifatida shu yerda.
 *
 * MUHIM: bu yerdagi `roles` ro'yxatlari eski JSX shartlarining aynan
 * ko'chirmasi — hech kimning ruxsati kengaymagan yoki toraymagan.
 * Backend baribir har bir endpoint'ni mustaqil tekshiradi (asosiy himoya shu).
 */

const ALL = ['admin', 'support_teacher', 'teacher', 'hunter', 'sales', 'call_center', 'audit']
const EXCEPT = (...roles) => ALL.filter(r => !roles.includes(r))

/**
 * Modul rangi — har bir bo'limning semantik ohangi.
 *
 * Bu rang yon panelda DOIM ko'rinmaydi: tinch holatda barcha ikonkalar
 * neytral kulrang (#667085). Rang faqat sichqoncha element ustida bo'lganda
 * paydo bo'ladi. Sabab oddiy: agar 19 ta navigatsiya elementi bir vaqtda
 * rang-barang bo'lsa, rang hech narsani anglatmay qoladi va ko'z charchaydi.
 * Faol element esa brend binafshasida — "siz shu yerdasiz" bitta ma'noda.
 *
 * Qiymatlar `styles.css` dagi `--mod-*` token'lariga mos.
 */
const TONE = {
  dashboard: 'var(--mod-dashboard)', leads: 'var(--mod-leads)',
  students: 'var(--mod-students)',   groups: 'var(--mod-groups)',
  attendance: 'var(--mod-attendance)', payments: 'var(--mod-payments)',
  finance: 'var(--mod-finance)',     salary: 'var(--mod-salary)',
  expenses: 'var(--mod-expenses)',   academic: 'var(--mod-academic)',
  notifications: 'var(--mod-notifications)', chatbot: 'var(--mod-chatbot)',
  users: 'var(--mod-users)',         audit: 'var(--mod-audit)',
  settings: 'var(--mod-settings)',
}

export const NAV_GROUPS = [
  {
    id: 'home',
    label: 'Bosh sahifa',
    items: [
      { key: 'teacher_dashboard', label: 'Mening guruhlarim', icon: faChalkboardTeacher, tone: TONE.dashboard, roles: ['teacher'] },
      { key: 'dashboard',         label: 'Dashboard',         icon: faChartBar,          tone: TONE.dashboard, roles: ['admin'] },
    ],
  },
  {
    id: 'crm',
    label: 'CRM',
    items: [
      { key: 'work_center',   label: 'Ishlarim',      icon: faListCheck,   tone: TONE.attendance,    roles: ['hunter', 'call_center', 'admin'] },
      { key: 'team_activity', label: 'Jamoa faoliyati', icon: faUsersGear, tone: TONE.users,         roles: ['admin'] },
      { key: 'leads',         label: 'Lidlar',        icon: faBullseye,    tone: TONE.leads,         roles: ['hunter', 'sales', 'call_center', 'admin'] },
      // "Notifications" ilgari ikki xil narsani anglatardi (bu sahifa + Leads
      // ichidagi qo'ng'iroq menyusi). Bu sahifa aslida kelish-ketish jurnali.
      { key: 'tree',          label: 'Tree',          icon: faSitemap,     tone: TONE.leads,         roles: ['hunter', 'sales', 'call_center', 'admin'] },
      { key: 'notifications', label: 'Kelish-ketish', icon: faRightLeft,   tone: TONE.attendance,    roles: ['hunter', 'sales', 'call_center', 'admin'] },
      { key: 'chatbot',       label: 'Chatbot',       icon: faComments,    tone: TONE.chatbot,       roles: ['hunter', 'admin'] },
      { key: 'feedbacks',     label: 'Izohlar',       icon: faCommentDots, tone: TONE.notifications, roles: ['call_center', 'admin'], badge: 'feedback' },
      { key: 'parents',       label: 'Ota-onalar',    icon: faPeopleRoof,  tone: TONE.students,      roles: ['hunter', 'admin'] },
      { key: 'computers',     label: 'Kompyuterlar',  icon: faDesktop,     tone: TONE.groups,        roles: ['hunter', 'admin'] },
    ],
  },
  {
    id: 'education',
    label: "Ta'lim",
    items: [
      { key: 'students',         label: 'Talabalar',      icon: faUserGraduate,     tone: TONE.students,   roles: ['admin', 'support_teacher', 'hunter', 'sales', 'call_center'] },
      { key: 'groups',           label: 'Guruhlar',       icon: faUsers,            tone: TONE.groups,     roles: ['admin', 'support_teacher', 'hunter', 'sales', 'call_center'], alsoActiveOn: ['group_detail'] },
      { key: 'today_attendance', label: 'Bugungi darslar', icon: faCalendarCheck,   tone: TONE.attendance, roles: EXCEPT('audit') },
      { key: 'academic',         label: 'Baholar va izohlar', icon: faGraduationCap, tone: TONE.academic,   roles: ['admin', 'support_teacher', 'teacher'] },
      { key: 'lessons',          label: 'Dars rejalari',  icon: faBook,             tone: TONE.academic,   roles: ['admin', 'support_teacher', 'teacher'], expandable: 'categories' },
      { key: 'minar_accounts',   label: 'Minar Space',    icon: faRocket,           tone: TONE.students,   roles: ['admin', 'support_teacher'] },
    ],
  },
  {
    id: 'finance',
    label: 'Moliya',
    items: [
      { key: 'payments',         label: "To'lovlar",         icon: faCreditCard,     tone: TONE.payments, roles: ['admin', 'hunter'] },
      { key: 'expenses',         label: 'Xarajatlar',        icon: faReceipt,        tone: TONE.expenses, roles: ['admin', 'hunter'] },
      { key: 'cashbox',          label: 'Kassa',             icon: faCashRegister,   tone: TONE.payments, roles: ['admin'] },
      { key: 'finance',          label: 'Moliya hisoboti',   icon: faWallet,         tone: TONE.finance,  roles: ['admin'] },
      { key: 'tariffs',          label: 'Tariflar',          icon: faTag,            tone: TONE.finance,  roles: ['admin'] },
      { key: 'courses',          label: 'Kurslar',           icon: faBookOpen,       tone: TONE.finance,  roles: ['admin'] },
      { key: 'special',          label: 'Special chegirma',  icon: faStar,           tone: TONE.finance,  roles: ['admin'] },
      { key: 'teacher_salaries', label: "O'qituvchi maoshi", icon: faChalkboardTeacher, tone: TONE.salary, roles: ['admin'] },
      { key: 'salary',           label: 'Ish haqi',          icon: faMoneyBillWave,  tone: TONE.salary,   roles: ['admin'] },
    ],
  },
  {
    id: 'people',
    label: 'Xodimlar',
    items: [
      { key: 'employees',      label: 'Xodimlar',           icon: faUsers,               tone: TONE.audit, roles: ['audit', 'admin'] },
      { key: 'audit_warnings', label: 'Ogohlantirishlar',   icon: faTriangleExclamation, tone: TONE.audit, roles: ['audit', 'admin'] },
      { key: 'my_warnings',    label: 'Ogohlantirishlarim', icon: faTriangleExclamation, tone: TONE.audit, roles: EXCEPT('audit', 'admin') },
      { key: 'users',          label: 'Foydalanuvchilar',   icon: faUserShield,          tone: TONE.users, roles: ['admin'] },
    ],
  },
  {
    id: 'system',
    label: 'Tizim',
    items: [
      { key: 'bot_admin', label: 'Bot boshqaruvi', icon: faRobot, tone: TONE.settings, roles: ['admin'] },
    ],
  },
]

/** Rolga ko'rinadigan guruh/elementlarni qaytaradi (bo'sh guruhlar tushib qoladi). */
export function navForRole(role) {
  return NAV_GROUPS
    .map(g => ({ ...g, items: g.items.filter(i => i.roles.includes(role)) }))
    .filter(g => g.items.length > 0)
}

/** Sahifa kaliti bo'yicha uni o'z ichiga olgan guruh id'sini topadi. */
export function groupIdForPage(role, page) {
  for (const g of navForRole(role)) {
    if (g.items.some(i => i.key === page || i.alsoActiveOn?.includes(page))) return g.id
  }
  return null
}

/** Global qidiruv / command palette uchun tekis ro'yxat. */
export function flatNav(role) {
  return navForRole(role).flatMap(g => g.items.map(i => ({ ...i, group: g.label })))
}
