export class ApiError extends Error {
  status: number
  code: string
  requestId?: string
  retryable: boolean
  constructor(status: number, code: string, message: string, requestId?: string, retryable = false) {
    super(message)
    this.status = status
    this.code = code
    this.requestId = requestId
    this.retryable = retryable
  }
}

const KEY = 'aprova.demo.token'
let memoryToken: string | null = null

export function getToken(): string | null {
  try { return localStorage.getItem(KEY) ?? memoryToken } catch { return memoryToken }
}
export function setToken(t: string | null) {
  memoryToken = t
  try { if (t) localStorage.setItem(KEY, t); else localStorage.removeItem(KEY) } catch { /* armazenamento indisponível */ }
}

function newKey(): string {
  return globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(16).slice(2)}`
}

type Opts = { method?: string; body?: unknown; idempotencyKey?: string | true }

export async function api<T>(path: string, opts: Opts = {}): Promise<T> {
  const headers: Record<string, string> = {}
  const token = getToken()
  if (token) headers['X-Demo-Token'] = token
  if (opts.body !== undefined) headers['Content-Type'] = 'application/json'
  if (opts.idempotencyKey) headers['Idempotency-Key'] = opts.idempotencyKey === true ? newKey() : opts.idempotencyKey
  let res: Response
  try {
    res = await fetch(path, {
      method: opts.method ?? 'GET', headers,
      body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
    })
  } catch {
    throw new ApiError(0, 'NETWORK', 'Não foi possível falar com o servidor. Verifique se a API está em execução.', undefined, true)
  }
  if (!res.ok) {
    let j: { code?: string; message?: string; request_id?: string; retryable?: boolean } = {}
    try { j = await res.json() } catch { /* corpo vazio */ }
    throw new ApiError(res.status, j.code ?? 'ERROR', j.message ?? `Erro ${res.status}`, j.request_id, j.retryable)
  }
  return res.json() as Promise<T>
}

export const post = <T,>(path: string, body: unknown = {}) =>
  api<T>(path, { method: 'POST', body, idempotencyKey: true })
