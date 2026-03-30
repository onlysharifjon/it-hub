const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

let token = localStorage.getItem('token') || ''

export function setToken(newToken) {
  token = newToken
  if (newToken) {
    localStorage.setItem('token', newToken)
  } else {
    localStorage.removeItem('token')
  }
}

function authHeaders() {
  return token
    ? { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }
    : { 'Content-Type': 'application/json' }
}

async function request(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: authHeaders(),
    ...options,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw Object.assign(new Error(err.detail || 'Server xatosi'), { status: res.status })
  }
  if (res.status === 204) return null
  return res.json()
}

// ── Auth ─────────────────────────────────────────────────────────────────────

export async function login(username, password) {
  const data = await request('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  })
  setToken(data.access_token)
  return data
}

export async function fetchMe() {
  return request('/auth/me')
}

// ── Lessons ───────────────────────────────────────────────────────────────────

export async function fetchLessons() {
  return request('/lessons')
}

export async function createLesson(payload) {
  return request('/lessons', { method: 'POST', body: JSON.stringify(payload) })
}

export async function updateLesson(id, updates) {
  return request(`/lessons/${id}`, { method: 'PUT', body: JSON.stringify(updates) })
}

export async function deleteLesson(id) {
  return request(`/lessons/${id}`, { method: 'DELETE' })
}

export async function reorderLessons(items) {
  return request('/lessons/reorder', { method: 'PUT', body: JSON.stringify({ items }) })
}

// ── Users ─────────────────────────────────────────────────────────────────────

export async function fetchUsers() {
  return request('/users')
}

export async function createUser(payload) {
  return request('/users', { method: 'POST', body: JSON.stringify(payload) })
}

export async function updateUser(id, payload) {
  return request(`/users/${id}`, { method: 'PUT', body: JSON.stringify(payload) })
}

// ── Audit logs ────────────────────────────────────────────────────────────────

export async function fetchAuditLogs(limit = 100) {
  return request(`/audit-logs?limit=${limit}`)
}

export async function fetchLessonAuditLogs(lessonId) {
  return request(`/audit-logs/lesson/${lessonId}`)
}
