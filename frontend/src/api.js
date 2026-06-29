const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

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

export { API_BASE }

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
  if (params.search) q.set('search', params.search)
  if (params.status) q.set('status', params.status)
  return request(`/leads${q.toString() ? '?' + q : ''}`)
}
export async function createLead(p)                    { return request('/leads', { method: 'POST', body: JSON.stringify(p) }) }
export async function updateLeadStatus(id, p)          { return request(`/leads/${id}/status`, { method: 'PATCH', body: JSON.stringify(p) }) }
export async function deleteLead(id)                   { return request(`/leads/${id}`, { method: 'DELETE' }) }

// ── Users ─────────────────────────────────────────────────────────────────────

export async function fetchUsers(params = {}) {
  const q = new URLSearchParams()
  if (params.search)    q.set('search', params.search)
  if (params.page)      q.set('page', params.page)
  if (params.page_size) q.set('page_size', params.page_size)
  return request(`/users${q.toString() ? '?' + q : ''}`)
}
export async function createUser(p)       { return request('/users', { method: 'POST', body: JSON.stringify(p) }) }
export async function updateUser(id, p)   { return request(`/users/${id}`, { method: 'PUT', body: JSON.stringify(p) }) }
export async function blockUser(id, p)    { return request(`/users/${id}/block`, { method: 'POST', body: JSON.stringify(p) }) }
export async function unblockUser(id)     { return request(`/users/${id}/unblock`, { method: 'POST' }) }

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

export async function fetchCourses()        { return request('/courses') }
export async function createCourse(p)       { return request('/courses', { method: 'POST', body: JSON.stringify(p) }) }
export async function updateCourse(id, p)   { return request(`/courses/${id}`, { method: 'PUT', body: JSON.stringify(p) }) }
export async function deleteCourse(id)      { return request(`/courses/${id}`, { method: 'DELETE' }) }

// ── Tariffs ───────────────────────────────────────────────────────────────────

export async function fetchTariffs()        { return request('/tariffs') }
export async function createTariff(p)       { return request('/tariffs', { method: 'POST', body: JSON.stringify(p) }) }
export async function updateTariff(id, p)   { return request(`/tariffs/${id}`, { method: 'PUT', body: JSON.stringify(p) }) }
export async function deleteTariff(id)      { return request(`/tariffs/${id}`, { method: 'DELETE' }) }

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

export function exportExcelUrl(month, year) {
  const q = new URLSearchParams()
  if (month) q.set('month', month)
  if (year)  q.set('year', year)
  return `${API_BASE}/stats/export/excel?${q}&_token=${token}`
}

export function receiptUrl(paymentId) {
  return `${API_BASE}/payments/${paymentId}/receipt?_token=${token}`
}
