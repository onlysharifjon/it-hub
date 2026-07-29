export const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

let token = localStorage.getItem('token') || ''

export function setToken(newToken) {
  token = newToken
  if (newToken) localStorage.setItem('token', newToken)
  else localStorage.removeItem('token')
}

function authHeaders() {
  return token
    ? { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }
    : { 'Content-Type': 'application/json' }
}

async function request(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, { headers: authHeaders(), ...options })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    const msg = typeof err.detail === 'string' ? err.detail : 'Server xatosi'
    const error = Object.assign(new Error(msg), { status: res.status })
    if (err.detail && typeof err.detail === 'object') error.detail = err.detail
    throw error
  }
  if (res.status === 204) return null
  return res.json()
}

// ── Auth ──────────────────────────────────────────────────────────────────────

export async function login(username, password) {
  const data = await request('/auth/login', { method: 'POST', body: JSON.stringify({ username, password }) })
  setToken(data.access_token)
  return data
}

export async function fetchMe() { return request('/auth/me') }

export async function uploadAvatar(file) {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(`${API_BASE}/me/avatar`, {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: form,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(typeof err.detail === 'string' ? err.detail : 'Yuklash xatosi')
  }
  return res.json()
}

// ── Lessons ───────────────────────────────────────────────────────────────────

export async function fetchLessons(category) {
  const q = category ? `?category=${category}` : ''
  return request(`/lessons${q}`)
}
export async function createLesson(p)        { return request('/lessons', { method: 'POST', body: JSON.stringify(p) }) }
export async function updateLesson(id, p)    { return request(`/lessons/${id}`, { method: 'PUT', body: JSON.stringify(p) }) }
export async function deleteLesson(id)       { return request(`/lessons/${id}`, { method: 'DELETE' }) }
export async function reorderLessons(items)  { return request('/lessons/reorder', { method: 'PUT', body: JSON.stringify({ items }) }) }

// ── Leads ─────────────────────────────────────────────────────────────────────

export async function fetchLeads(params = {}) {
  const q = new URLSearchParams()
  if (params.search)    q.set('search', params.search)
  if (params.status)    q.set('status', params.status)
  if (params.stage)     q.set('stage', params.stage)
  if (params.source_id) q.set('source_id', params.source_id)
  return request(`/leads${q.toString() ? '?' + q : ''}`)
}
export async function createLead(p)                    { return request('/leads', { method: 'POST', body: JSON.stringify(p) }) }
export async function updateLeadStatus(id, p)          { return request(`/leads/${id}/status`, { method: 'PATCH', body: JSON.stringify(p) }) }
export async function moveLeadStage(id, p)             { return request(`/leads/${id}/stage`, { method: 'PATCH', body: JSON.stringify(p) }) }
export async function deleteLead(id)                   { return request(`/leads/${id}`, { method: 'DELETE' }) }
export async function fetchLeadStats()                 { return request('/leads/stats') }
export async function fetchLeadActivities(id)          { return request(`/leads/${id}/activities`) }

// Lead stages (pipeline)
export async function fetchLeadStages()                { return request('/lead-stages') }
export async function createLeadStage(p)               { return request('/lead-stages', { method: 'POST', body: JSON.stringify(p) }) }
export async function updateLeadStage(id, p)           { return request(`/lead-stages/${id}`, { method: 'PUT', body: JSON.stringify(p) }) }
export async function reorderLeadStages(ordered_ids)   { return request('/lead-stages/reorder', { method: 'PUT', body: JSON.stringify({ ordered_ids }) }) }
export async function deleteLeadStage(id)              { return request(`/lead-stages/${id}`, { method: 'DELETE' }) }

// Lead sources
export async function fetchLeadSources()               { return request('/lead-sources') }
export async function createLeadSource(p)              { return request('/lead-sources', { method: 'POST', body: JSON.stringify(p) }) }
export async function updateLeadSource(id, p)          { return request(`/lead-sources/${id}`, { method: 'PUT', body: JSON.stringify(p) }) }
export async function deleteLeadSource(id)             { return request(`/lead-sources/${id}`, { method: 'DELETE' }) }

// Lead analytics
export async function fetchLeadAnalytics()             { return request('/leads/analytics') }

// Reminders
export async function fetchReminders(params = {}) {
  const q = new URLSearchParams()
  if (params.status)  q.set('status', params.status)
  if (params.lead_id) q.set('lead_id', params.lead_id)
  if (params.mine === false) q.set('mine', 'false')
  return request(`/reminders${q.toString() ? '?' + q : ''}`)
}
export async function createReminder(p)                { return request('/reminders', { method: 'POST', body: JSON.stringify(p) }) }
export async function updateReminder(id, p)            { return request(`/reminders/${id}`, { method: 'PATCH', body: JSON.stringify(p) }) }
export async function deleteReminder(id)               { return request(`/reminders/${id}`, { method: 'DELETE' }) }

// Notifications
export async function fetchNotifications(unreadOnly = false) { return request(`/notifications${unreadOnly ? '?unread_only=true' : ''}`) }
export async function fetchUnreadCount()               { return request('/notifications/unread-count') }
export async function markNotificationRead(id)         { return request(`/notifications/${id}/read`, { method: 'POST' }) }
export async function markAllNotificationsRead()       { return request('/notifications/read-all', { method: 'POST' }) }

// Shared pool / claim
export async function claimLead(id)                    { return request(`/leads/${id}/claim`, { method: 'POST' }) }
export async function releaseLead(id)                  { return request(`/leads/${id}/release`, { method: 'POST' }) }
export async function shareLead(id)                    { return request(`/leads/${id}/share`, { method: 'POST' }) }

// Intake forms (admin)
export async function fetchIntakeForms()               { return request('/intake-forms') }
export async function createIntakeForm(p)              { return request('/intake-forms', { method: 'POST', body: JSON.stringify(p) }) }
export async function updateIntakeForm(id, p)          { return request(`/intake-forms/${id}`, { method: 'PUT', body: JSON.stringify(p) }) }
export async function deleteIntakeForm(id)             { return request(`/intake-forms/${id}`, { method: 'DELETE' }) }

// Public intake (no auth)
export async function fetchPublicIntake(slug)          { return request(`/public/intake/${slug}`) }
export async function submitPublicIntake(slug, p)      { return request(`/public/intake/${slug}`, { method: 'POST', body: JSON.stringify(p) }) }

// ── Users ─────────────────────────────────────────────────────────────────────

export async function fetchUsers(params = {}) {
  const q = new URLSearchParams()
  if (params.search)    q.set('search', params.search)
  if (params.page)      q.set('page', params.page)
  if (params.page_size) q.set('page_size', params.page_size)
  return request(`/users${q.toString() ? '?' + q : ''}`)
}
export async function fetchTeachers()     { return request('/teachers') }
export async function updateProfile(p)    { return request('/me', { method: 'PUT', body: JSON.stringify(p) }) }
export async function createUser(p)       { return request('/users', { method: 'POST', body: JSON.stringify(p) }) }
export async function updateUser(id, p)   { return request(`/users/${id}`, { method: 'PUT', body: JSON.stringify(p) }) }
export async function blockUser(id, p)    { return request(`/users/${id}/block`, { method: 'POST', body: JSON.stringify(p) }) }
export async function unblockUser(id)     { return request(`/users/${id}/unblock`, { method: 'POST' }) }
export async function deleteUserPermanent(id) { return request(`/users/${id}/permanent`, { method: 'DELETE' }) }

// ── Audit logs ────────────────────────────────────────────────────────────────

export async function fetchAuditLogs(params = {}) {
  const q = new URLSearchParams()
  if (params.page)      q.set('page', params.page)
  if (params.page_size) q.set('page_size', params.page_size)
  if (params.date_from) q.set('date_from', params.date_from)
  if (params.date_to)   q.set('date_to', params.date_to)
  return request(`/audit-logs${q.toString() ? '?' + q : ''}`)
}
export async function fetchLessonAuditLogs(id) { return request(`/audit-logs/lesson/${id}`) }

// ── Students ──────────────────────────────────────────────────────────────────

export async function fetchStudents(params = {}) {
  const q = new URLSearchParams()
  if (params.search)              q.set('search', params.search)
  if (params.is_active !== undefined)   q.set('is_active', params.is_active)
  if (params.is_archived !== undefined) q.set('is_archived', params.is_archived)
  if (params.date_from)           q.set('date_from', params.date_from)
  if (params.date_to)             q.set('date_to', params.date_to)
  if (params.payment)             q.set('payment', params.payment)
  if (params.month)               q.set('month', params.month)
  if (params.year)                q.set('year', params.year)
  if (params.page)                q.set('page', params.page)
  if (params.page_size)           q.set('page_size', params.page_size)
  return request(`/students${q.toString() ? '?' + q : ''}`)
}

export async function getStudent(id)          { return request(`/students/${id}`) }
export async function createStudent(p)        { return request('/students', { method: 'POST', body: JSON.stringify(p) }) }
export async function updateStudent(id, p)    { return request(`/students/${id}`, { method: 'PUT', body: JSON.stringify(p) }) }
export async function archiveStudent(id)      { return request(`/students/${id}/archive`, { method: 'POST' }) }
export async function unarchiveStudent(id)    { return request(`/students/${id}/unarchive`, { method: 'POST' }) }

// ── Groups ────────────────────────────────────────────────────────────────────

export async function fetchGroups(params = {}) {
  const q = new URLSearchParams()
  if (params.is_active !== undefined) q.set('is_active', params.is_active)
  if (params.search)    q.set('search', params.search)
  if (params.date_from) q.set('date_from', params.date_from)
  if (params.date_to)   q.set('date_to', params.date_to)
  if (params.page)      q.set('page', params.page)
  if (params.page_size) q.set('page_size', params.page_size)
  return request(`/groups${q.toString() ? '?' + q : ''}`)
}

export async function getGroup(id)          { return request(`/groups/${id}`) }
export async function createGroup(p)        { return request('/groups', { method: 'POST', body: JSON.stringify(p) }) }
export async function updateGroup(id, p)    { return request(`/groups/${id}`, { method: 'PUT', body: JSON.stringify(p) }) }
export async function deleteGroup(id)       { return request(`/groups/${id}`, { method: 'DELETE' }) }
export async function addStudentToGroup(groupId, studentId, tariffId = null) {
  return request(`/groups/${groupId}/students`, {
    method: 'POST',
    body: JSON.stringify({ student_id: studentId, tariff_id: tariffId }),
  })
}
export async function removeStudentFromGroup(groupId, studentId) {
  return request(`/groups/${groupId}/students/${studentId}`, { method: 'DELETE' })
}

// ── Payments ──────────────────────────────────────────────────────────────────

export async function fetchPayments(params = {}) {
  const q = new URLSearchParams()
  if (params.student_id) q.set('student_id', params.student_id)
  if (params.group_id)   q.set('group_id', params.group_id)
  if (params.month)      q.set('month', params.month)
  if (params.year)       q.set('year', params.year)
  if (params.date_from)  q.set('date_from', params.date_from)
  if (params.date_to)    q.set('date_to', params.date_to)
  if (params.page)       q.set('page', params.page)
  if (params.page_size)  q.set('page_size', params.page_size)
  return request(`/payments${q.toString() ? '?' + q : ''}`)
}

export async function fetchPaymentExpected({ student_id, group_id, month, year }) {
  const q = new URLSearchParams({ student_id, group_id, month, year })
  return request(`/payments/expected?${q}`)
}

export async function fetchStudentPaymentSummary(id, { month, year } = {}) {
  const q = new URLSearchParams()
  if (month) q.set('month', month)
  if (year)  q.set('year', year)
  return request(`/students/${id}/payments/summary${q.toString() ? '?' + q : ''}`)
}
export async function createPayment(p)       { return request('/payments', { method: 'POST', body: JSON.stringify(p) }) }
export async function updatePayment(id, p)   { return request(`/payments/${id}`, { method: 'PUT', body: JSON.stringify(p) }) }
export async function deletePayment(id)      { return request(`/payments/${id}`, { method: 'DELETE' }) }

// ── Attendance ────────────────────────────────────────────────────────────────

export async function fetchAttendance(groupId, month, year) {
  return request(`/groups/${groupId}/attendance?month=${month}&year=${year}`)
}
export async function saveAttendance(groupId, lessonDate, records) {
  return request(`/groups/${groupId}/attendance/${lessonDate}`, { method: 'POST', body: JSON.stringify(records) })
}
export async function deleteAttendanceDate(groupId, lessonDate) {
  return request(`/groups/${groupId}/attendance/${lessonDate}`, { method: 'DELETE' })
}

// ── Courses ───────────────────────────────────────────────────────────────────

export async function fetchStudentCameraAttendance(studentId, days = 30) {
  return request(`/students/${studentId}/camera-attendance?days=${days}`)
}

export async function fetchGroupCameraAttendance(groupId, days = 7) {
  return request(`/groups/${groupId}/camera-attendance?days=${days}`)
}

export async function fetchCourses()        { return request('/courses') }
export async function createCourse(p)       { return request('/courses', { method: 'POST', body: JSON.stringify(p) }) }
export async function updateCourse(id, p)   { return request(`/courses/${id}`, { method: 'PUT', body: JSON.stringify(p) }) }
export async function deleteCourse(id)      { return request(`/courses/${id}`, { method: 'DELETE' }) }

export async function uploadStudentPhoto(studentId, file) {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(`${API_BASE}/students/${studentId}/photo`, {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: form,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(typeof err.detail === 'string' ? err.detail : 'Yuklash xatosi')
  }
  return res.json()
}

// ── Tariffs ───────────────────────────────────────────────────────────────────

export async function fetchTariffs()        { return request('/tariffs') }
export async function createTariff(p)       { return request('/tariffs', { method: 'POST', body: JSON.stringify(p) }) }
export async function updateTariff(id, p)   { return request(`/tariffs/${id}`, { method: 'PUT', body: JSON.stringify(p) }) }
export async function deleteTariff(id)      { return request(`/tariffs/${id}`, { method: 'DELETE' }) }


// ── Discounts ─────────────────────────────────────────────────────────────────

export async function fetchDiscounts()         { return request('/discounts') }
export async function createDiscount(p)        { return request('/discounts', { method: 'POST', body: JSON.stringify(p) }) }
export async function updateDiscount(id, p)    { return request(`/discounts/${id}`, { method: 'PUT', body: JSON.stringify(p) }) }
export async function deleteDiscount(id)       { return request(`/discounts/${id}`, { method: 'DELETE' }) }

// ── Finance ───────────────────────────────────────────────────────────────────

export async function fetchFinanceMonthly(month, year) {
  return request(`/finance/monthly?month=${month}&year=${year}`)
}

// ── Today Attendance ──────────────────────────────────────────────────────────

export async function fetchTodayGroups(targetDate) {
  const q = targetDate ? `?target_date=${targetDate}` : ''
  return request(`/attendance/today${q}`)
}

// ── Expenses ──────────────────────────────────────────────────────────────────

export async function fetchExpenses(month, year) {
  const q = new URLSearchParams()
  if (month) q.set('month', month)
  if (year)  q.set('year', year)
  return request(`/expenses${q.toString() ? '?' + q : ''}`)
}
export async function createExpense(p)      { return request('/expenses', { method: 'POST', body: JSON.stringify(p) }) }
export async function updateExpense(id, p)  { return request(`/expenses/${id}`, { method: 'PUT', body: JSON.stringify(p) }) }
export async function deleteExpense(id)     { return request(`/expenses/${id}`, { method: 'DELETE' }) }

// ── Stats ─────────────────────────────────────────────────────────────────────

export async function fetchTeacherSalaries(month, year) {
  return request(`/stats/teacher-salaries?month=${month}&year=${year}`)
}

export async function fetchTeacherDashboard(month, year) {
  const q = new URLSearchParams()
  if (month) q.set('month', month)
  if (year)  q.set('year', year)
  return request(`/teacher/dashboard${q.toString() ? '?' + q : ''}`)
}

export async function fetchStatsOverview(year) {
  const q = year ? `?year=${year}` : ''
  return request(`/stats/overview${q}`)
}

// Yuklab-olish URL'lari uzoq muddatli kirish tokenini emas, har safar olinadigan qisqa
// muddatli (2 daqiqa) `download` tokenini query-parametrda ishlatadi — token sizib chiqsa ham
// deyarli darhol yaroqsiz bo'ladi. Shu sababli bu funksiyalar async.
async function downloadToken() {
  const { token: t } = await request('/auth/download-token')
  return t
}

export async function exportExcelUrl(month, year) {
  const q = new URLSearchParams()
  if (month) q.set('month', month)
  if (year)  q.set('year', year)
  q.set('_token', await downloadToken())
  return `${API_BASE}/stats/export/excel?${q}`
}

export async function receiptUrl(paymentId) {
  return `${API_BASE}/payments/${paymentId}/receipt?_token=${await downloadToken()}`
}

// URL async yasalgani uchun oynani avval (foydalanuvchi bosishida) ochamiz — popup-blocker
// aks holda keyinchalik ochilgan oynani bloklardi — keyin URL tayyor bo'lgach yo'naltiramiz.
export async function openDownload(urlPromise) {
  const w = window.open('', '_blank')
  try {
    const url = await urlPromise
    if (w) w.location = url
    else window.location = url
  } catch (e) {
    if (w) w.close()
    throw e
  }
}

// ── Student visits — Notifications (keldi/ketdi) ──────────────────────────────

export async function fetchVisits({ visit_date, student_id } = {}) {
  const q = new URLSearchParams()
  if (visit_date) q.set('visit_date', visit_date)
  if (student_id) q.set('student_id', student_id)
  return request(`/visits${q.toString() ? '?' + q : ''}`)
}
export async function createVisit(p) { return request('/visits', { method: 'POST', body: JSON.stringify(p) }) }

export async function uploadStudentFacePhoto(studentId, file) {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(`${API_BASE}/students/${studentId}/face-photo`, {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: form,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(typeof err.detail === 'string' ? err.detail : 'Yuklash xatosi')
  }
  return res.json()
}

// ── Special chegirmalar ───────────────────────────────────────────────────────

export async function fetchSpecialDiscounts(studentId) {
  const q = studentId ? `?student_id=${studentId}` : ''
  return request(`/special-discounts${q}`)
}
export async function createSpecialDiscount(p)     { return request('/special-discounts', { method: 'POST', body: JSON.stringify(p) }) }
export async function updateSpecialDiscount(id, p) { return request(`/special-discounts/${id}`, { method: 'PATCH', body: JSON.stringify(p) }) }
export async function deleteSpecialDiscount(id)    { return request(`/special-discounts/${id}`, { method: 'DELETE' }) }

// ── Holidays (dam olish kunlari) ──────────────────────────────────────────────

export async function fetchHolidays(year) {
  const q = year ? `?year=${year}` : ''
  return request(`/holidays${q}`)
}
export async function createHoliday(p)  { return request('/holidays', { method: 'POST', body: JSON.stringify(p) }) }
export async function deleteHoliday(id) { return request(`/holidays/${id}`, { method: 'DELETE' }) }

// ── Akademik: baholar / izohlar / sertifikatlar / tadbirlar ──────────────────

export async function fetchAcademicOptions() { return request('/academic/options') }

export async function fetchGrades(params = {}) {
  const q = new URLSearchParams()
  if (params.student_id) q.set('student_id', params.student_id)
  if (params.group_id)   q.set('group_id', params.group_id)
  return request(`/grades${q.toString() ? '?' + q : ''}`)
}
export async function createGrade(p)     { return request('/grades', { method: 'POST', body: JSON.stringify(p) }) }
export async function updateGrade(id, p) { return request(`/grades/${id}`, { method: 'PATCH', body: JSON.stringify(p) }) }
export async function deleteGrade(id)    { return request(`/grades/${id}`, { method: 'DELETE' }) }

export async function fetchFeedbacks(studentId, status) {
  const params = new URLSearchParams()
  if (studentId) params.set('student_id', studentId)
  if (status) params.set('status', status)
  const q = params.toString()
  return request(`/teacher-feedbacks${q ? `?${q}` : ''}`)
}
export async function updateFeedbackStatus(id, status) {
  return request(`/teacher-feedbacks/${id}/status`, { method: 'PATCH', body: JSON.stringify({ status }) })
}
export async function fetchFeedbackNewCount() { return request('/teacher-feedbacks/new-count') }
export async function createFeedback(p)     { return request('/teacher-feedbacks', { method: 'POST', body: JSON.stringify(p) }) }
export async function updateFeedback(id, p) { return request(`/teacher-feedbacks/${id}`, { method: 'PATCH', body: JSON.stringify(p) }) }
export async function deleteFeedback(id)    { return request(`/teacher-feedbacks/${id}`, { method: 'DELETE' }) }

export async function uploadCertificatePdf(file) {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(`${API_BASE}/certificates/upload`, {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: form,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(typeof err.detail === 'string' ? err.detail : 'Yuklash xatosi')
  }
  return res.json()   // { file_url }
}

export async function fetchCertificates(studentId) {
  const q = studentId ? `?student_id=${studentId}` : ''
  return request(`/certificates${q}`)
}
export async function createCertificate(p)     { return request('/certificates', { method: 'POST', body: JSON.stringify(p) }) }
export async function updateCertificate(id, p) { return request(`/certificates/${id}`, { method: 'PATCH', body: JSON.stringify(p) }) }
export async function deleteCertificate(id)    { return request(`/certificates/${id}`, { method: 'DELETE' }) }

export async function fetchEvents()        { return request('/events') }
export async function createEvent(p)       { return request('/events', { method: 'POST', body: JSON.stringify(p) }) }
export async function updateEvent(id, p)   { return request(`/events/${id}`, { method: 'PATCH', body: JSON.stringify(p) }) }
export async function deleteEvent(id)      { return request(`/events/${id}`, { method: 'DELETE' }) }

// ── Coinlar ──────────────────────────────────────────────────────────────────

export async function fetchCoinSummary()      { return request('/coins/summary') }
export async function giveCoins(p)            { return request('/coins/give', { method: 'POST', body: JSON.stringify(p) }) }
export async function deductCoins(p)          { return request('/coins/deduct', { method: 'POST', body: JSON.stringify(p) }) }
export async function fetchCoinTransactions(studentId) {
  const q = studentId ? `?student_id=${studentId}` : ''
  return request(`/coins/transactions${q}`)
}
export async function fetchCoinTotals()       { return request('/coins/totals') }

// ── Homework (uy vazifasi) ────────────────────────────────────────────────────

export async function fetchNextLesson(groupId) { return request(`/groups/${groupId}/next-lesson`) }
export async function fetchHomeworks(groupId)  { return request(`/groups/${groupId}/homeworks`) }
export async function createHomework(groupId, p) {
  return request(`/groups/${groupId}/homeworks`, { method: 'POST', body: JSON.stringify(p) })
}

// ── Ota-ona akkauntlari (mobil ilova uchun) ──────────────────────────────────

export async function fetchParents(search) {
  const q = search ? `?search=${encodeURIComponent(search)}` : ''
  return request(`/parents${q}`)
}
export async function createParent(p)            { return request('/parents', { method: 'POST', body: JSON.stringify(p) }) }
export async function updateParent(id, p)        { return request(`/parents/${id}`, { method: 'PATCH', body: JSON.stringify(p) }) }
export async function resetParentPassword(id, p) { return request(`/parents/${id}/reset-password`, { method: 'POST', body: JSON.stringify(p || {}) }) }
export async function linkParentChild(id, studentId) {
  return request(`/parents/${id}/children`, { method: 'POST', body: JSON.stringify({ student_id: studentId }) })
}
export async function unlinkParentChild(id, studentId) {
  return request(`/parents/${id}/children/${studentId}`, { method: 'DELETE' })
}
export async function broadcastToParents(text) {
  return request('/parents/broadcast', { method: 'POST', body: JSON.stringify({ text }) })
}
export async function broadcastToStaff(text) {
  return request('/users/broadcast', { method: 'POST', body: JSON.stringify({ text }) })
}

// ── Audit ogohlantirishlar ────────────────────────────────────────────────────

export async function fetchStaffOptions()    { return request('/staff-options') }
export async function fetchDisciplineCodes() { return request('/discipline-codes') }
export async function fetchStaffWarnings(staffId) {
  const q = staffId ? `?staff_id=${staffId}` : ''
  return request(`/staff-warnings${q}`)
}
export async function createStaffWarning(p)   { return request('/staff-warnings', { method: 'POST', body: JSON.stringify(p) }) }
export async function resendStaffWarning(id)  { return request(`/staff-warnings/${id}/resend`, { method: 'POST' }) }
export async function cancelStaffWarning(id)  { return request(`/staff-warnings/${id}/cancel`, { method: 'POST' }) }
export async function fetchMyWarnings()       { return request('/staff-warnings/mine') }

// ── Bot boshqaruvi (Xodimlar/Rollar/Sozlamalar/Admin-CEO — bot.db'dan) ──────────

export async function fetchBotEmployees()  { return request('/bot/employees') }
export async function fetchBotRoles()      { return request('/bot/roles') }
export async function createBotRole(p)     { return request('/bot/roles', { method: 'POST', body: JSON.stringify(p) }) }
export async function toggleBotRole(id)    { return request(`/bot/roles/${id}/toggle`, { method: 'PATCH' }) }
export async function setBotEmployeeRole(employeeId, roleId) {
  return request(`/bot/employees/${employeeId}/role`, { method: 'POST', body: JSON.stringify({ role_id: roleId }) })
}
export async function setBotEmployeeAdmin(employeeId, tier) {
  return request(`/bot/employees/${employeeId}/admin`, { method: 'POST', body: JSON.stringify({ tier }) })
}
export async function fetchBotSetting(key)      { return request(`/bot/settings/${key}`) }
export async function setBotSetting(key, value) {
  return request(`/bot/settings/${key}`, { method: 'PUT', body: JSON.stringify({ value }) })
}
export async function createBotInviteLink(tier) {
  return request('/bot/invite-links', { method: 'POST', body: JSON.stringify({ tier }) })
}
