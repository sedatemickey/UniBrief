import type { ApiEnvelopeError } from './types'

export class ApiError extends Error {
  code: string
  status: number
  retryable: boolean
  details?: unknown

  constructor(status: number, payload: ApiEnvelopeError) {
    super(payload.error.message)
    this.name = 'ApiError'
    this.status = status
    this.code = payload.error.code
    this.retryable = payload.error.retryable
    this.details = payload.error.details
  }
}

function cookie(name: string): string | undefined {
  const prefix = `${name}=`
  return document.cookie.split('; ').find((item) => item.startsWith(prefix))?.slice(prefix.length)
}

export interface RequestOptions extends RequestInit {
  admin?: boolean
  json?: unknown
}

export async function api<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { admin, json, headers, ...init } = options
  const finalHeaders = new Headers(headers)
  if (json !== undefined) finalHeaders.set('Content-Type', 'application/json')
  const method = (init.method ?? 'GET').toUpperCase()
  if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) {
    const token = cookie(admin ? 'unibrief_admin_csrf' : 'unibrief_csrf')
    if (token) finalHeaders.set(admin ? 'X-Admin-CSRF-Token' : 'X-CSRF-Token', decodeURIComponent(token))
  }
  const response = await fetch(`/api/v1${path}`, {
    ...init,
    credentials: 'include',
    headers: finalHeaders,
    body: json === undefined ? init.body : JSON.stringify(json),
  })
  if (!response.ok) {
    const payload = (await response.json().catch(() => ({ error: { code: 'HTTP_ERROR', message: `请求失败 (${response.status})`, retryable: false } }))) as ApiEnvelopeError
    throw new ApiError(response.status, payload)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export function queryString(values: Record<string, string | number | boolean | null | undefined | Array<string | number>>): string {
  const params = new URLSearchParams()
  Object.entries(values).forEach(([key, value]) => {
    if (value === undefined || value === null || value === '') return
    if (Array.isArray(value)) value.forEach((item) => params.append(key, String(item)))
    else params.set(key, String(value))
  })
  const result = params.toString()
  return result ? `?${result}` : ''
}


