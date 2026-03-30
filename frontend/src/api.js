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
    throw Object.assign(new Error(err.detail || 'Server xatosi'), { status: res.status })
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

// ── Lessons ───────────────────────────────────────────────────────────────────

export async function fetchLessons() { return request('/lessons') }
export async function createLesson(p) { return request('/lessons', { method: 'POST', body: JSON.stringify(p) }) }
export async function updateLesson(id, p) { return request(`/lessons/${id}`, { method: 'PUT', body: JSON.stringify(p) }) }
export async function deleteLesson(id) { return request(`/lessons/${id}`, { method: 'DELETE' }) }
export async function reorderLessons(items) { return request('/lessons/reorder', { method: 'PUT', body: JSON.stringify({ items }) }) }

// ── Users ─────────────────────────────────────────────────────────────────────

export async function fetchUsers() { return request('/users') }
export async function createUser(p) { return request('/users', { method: 'POST', body: JSON.stringify(p) }) }
export async function updateUser(id, p) { return request(`/users/${id}`, { method: 'PUT', body: JSON.stringify(p) }) }

// ── Audit logs ────────────────────────────────────────────────────────────────

export async function fetchAuditLogs(limit = 100) { return request(`/audit-logs?limit=${limit}`) }
export async function fetchLessonAuditLogs(id) { return request(`/audit-logs/lesson/${id}`) }

// ── Students ──────────────────────────────────────────────────────────────────

export async function fetchStudents(params = {}) {
  const q = new URLSearchParams()
  if (params.search) q.set('search', params.search)
  if (params.is_active !== undefined) q.set('is_active', params.is_active)
  if (params.page) q.set('page', params.page)
  if (params.page_size) q.set('page_size', params.page_size)
  return request(`/students${q.toString() ? '?' + q : ''}`)
}

export async function getStudent(id) { return request(`/students/${id}`) }
export async function createStudent(p) { return request('/students', { method: 'POST', body: JSON.stringify(p) }) }
export async function updateStudent(id, p) { return request(`/students/${id}`, { method: 'PUT', body: JSON.stringify(p) }) }
export async function deleteStudent(id) { return request(`/students/${id}`, { method: 'DELETE' }) }

// ── Groups ────────────────────────────────────────────────────────────────────

export async function fetchGroups(params = {}) {
  const q = new URLSearchParams()
  if (params.is_active !== undefined) q.set('is_active', params.is_active)
  return request(`/groups${q.toString() ? '?' + q : ''}`)
}

export async function getGroup(id) { return request(`/groups/${id}`) }
export async function createGroup(p) { return request('/groups', { method: 'POST', body: JSON.stringify(p) }) }
export async function updateGroup(id, p) { return request(`/groups/${id}`, { method: 'PUT', body: JSON.stringify(p) }) }
export async function deleteGroup(id) { return request(`/groups/${id}`, { method: 'DELETE' }) }
export async function addStudentToGroup(groupId, studentId) {
  return request(`/groups/${groupId}/students`, { method: 'POST', body: JSON.stringify({ student_id: studentId }) })
}
export async function removeStudentFromGroup(groupId, studentId) {
  return request(`/groups/${groupId}/students/${studentId}`, { method: 'DELETE' })
}

// ── Payments ──────────────────────────────────────────────────────────────────

export async function fetchPayments(params = {}) {
  const q = new URLSearchParams()
  if (params.student_id) q.set('student_id', params.student_id)
  if (params.group_id) q.set('group_id', params.group_id)
  if (params.month) q.set('month', params.month)
  if (params.year) q.set('year', params.year)
  if (params.page) q.set('page', params.page)
  if (params.page_size) q.set('page_size', params.page_size)
  return request(`/payments${q.toString() ? '?' + q : ''}`)
}

export async function createPayment(p) { return request('/payments', { method: 'POST', body: JSON.stringify(p) }) }
export async function updatePayment(id, p) { return request(`/payments/${id}`, { method: 'PUT', body: JSON.stringify(p) }) }
export async function deletePayment(id) { return request(`/payments/${id}`, { method: 'DELETE' }) }

// ── Attendance ────────────────────────────────────────────────────────────────

export async function fetchAttendance(groupId, month, year) {
  return request(`/groups/${groupId}/attendance?month=${month}&year=${year}`)
}

export async function saveAttendance(groupId, lessonDate, records) {
  return request(`/groups/${groupId}/attendance/${lessonDate}`, {
    method: 'POST',
    body: JSON.stringify(records),
  })
}

export async function deleteAttendanceDate(groupId, lessonDate) {
  return request(`/groups/${groupId}/attendance/${lessonDate}`, { method: 'DELETE' })
}

// ── Stats ─────────────────────────────────────────────────────────────────────

export async function fetchStatsOverview() { return request('/stats/overview') }

export function exportExcelUrl(month, year) {
  const q = new URLSearchParams()
  if (month) q.set('month', month)
  if (year) q.set('year', year)
  return `${API_BASE}/stats/export/excel?${q}&_token=${token}`
}
