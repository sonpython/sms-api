/** API helper for admin endpoints */

const TOKEN_KEY = 'sms_admin_token'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY)
}

export async function login(adminKey) {
  const form = new URLSearchParams()
  form.set('admin_key', adminKey)

  const res = await fetch('/admin/login', {
    method: 'POST',
    body: form,
  })

  if (!res.ok) {
    const err = await res.json()
    throw new Error(err.detail || 'Login failed')
  }

  const data = await res.json()
  setToken(data.token)
  return data.token
}

export async function fetchSmsFiles(folder, { sortBy = 'modified', sortOrder = 'desc', search = '', page = 1, perPage = 50 } = {}) {
  const params = new URLSearchParams({ sort_by: sortBy, sort_order: sortOrder, page, per_page: perPage })
  if (search) params.set('search', search)

  const res = await fetch(`/admin/api/sms/${folder}?${params}`, {
    headers: { Authorization: `Bearer ${getToken()}` },
  })

  if (res.status === 401) {
    clearToken()
    throw new Error('UNAUTHORIZED')
  }
  if (!res.ok) throw new Error('Failed to fetch files')

  return res.json()
}

export async function fetchSmsFile(folder, filename) {
  const res = await fetch(`/admin/api/sms/${folder}/${encodeURIComponent(filename)}`, {
    headers: { Authorization: `Bearer ${getToken()}` },
  })

  if (res.status === 401) {
    clearToken()
    throw new Error('UNAUTHORIZED')
  }
  if (!res.ok) throw new Error('Failed to read file')

  return res.json()
}

export async function sendTestSms(phone, message) {
  const form = new URLSearchParams()
  form.set('phone', phone)
  form.set('message', message)

  const res = await fetch('/admin/api/send-test-sms', {
    method: 'POST',
    headers: { Authorization: `Bearer ${getToken()}` },
    body: form,
  })

  if (res.status === 401) {
    clearToken()
    throw new Error('UNAUTHORIZED')
  }
  if (!res.ok) throw new Error('Failed to send SMS')

  return res.json()
}

export async function restartSmsd(onChunk) {
  const res = await fetch('/admin/api/restart-smsd', {
    method: 'POST',
    headers: { Authorization: `Bearer ${getToken()}` },
  })

  if (res.status === 401) {
    clearToken()
    throw new Error('UNAUTHORIZED')
  }
  if (!res.ok) throw new Error('Failed to restart smsd')

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    onChunk(decoder.decode(value))
  }
}

export function createWebSocket() {
  const token = getToken()
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  return new WebSocket(`${proto}://${location.host}/admin/ws?token=${token}`)
}
