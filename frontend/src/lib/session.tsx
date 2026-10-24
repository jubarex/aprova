import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api, ApiError, getToken, setToken } from './api'
import type { Me } from './types'

type Ctx = {
  me: Me | null
  loading: boolean
  login: (actorId: string) => Promise<Me>
  logout: () => void
  client: string | null // filtro de cliente do implantador (null = todos)
  setClient: (id: string | null) => void
}

const SessionCtx = createContext<Ctx | null>(null)
const CLIENT_KEY = 'aprova.client'

function readClient(): string | null {
  try { return localStorage.getItem(CLIENT_KEY) } catch { return null }
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient()
  const [client, setClientState] = useState<string | null>(readClient)
  const [token, setTokenState] = useState<string | null>(getToken)
  const q = useQuery({
    queryKey: ['me', token],
    enabled: !!token,
    retry: false,
    queryFn: async () => {
      try { return await api<Me>('/api/demo/me') } catch (e) {
        if (e instanceof ApiError && e.status === 401) { setToken(null); setTokenState(null); return null }
        throw e
      }
    },
  })
  const login = useCallback(async (actorId: string) => {
    const r = await api<{ token: string; actor: Me }>('/api/demo/session', { method: 'POST', body: { actor_id: actorId } })
    setToken(r.token)
    qc.clear()
    setTokenState(r.token)
    const me = await api<Me>('/api/demo/me')
    qc.setQueryData(['me', r.token], me)
    return me
  }, [qc])
  const logout = useCallback(() => { setToken(null); qc.clear(); window.location.assign('/') }, [qc])
  const setClient = useCallback((id: string | null) => {
    setClientState(id)
    try { if (id) localStorage.setItem(CLIENT_KEY, id); else localStorage.removeItem(CLIENT_KEY) } catch { /* sem armazenamento */ }
  }, [])
  const value = useMemo<Ctx>(() => ({
    me: token ? (q.data ?? null) : null, loading: !!token && q.isLoading, login, logout, client, setClient,
  }), [token, q.data, q.isLoading, login, logout, client, setClient])
  return <SessionCtx.Provider value={value}>{children}</SessionCtx.Provider>
}

export function useSession(): Ctx {
  const c = useContext(SessionCtx)
  if (!c) throw new Error('SessionProvider ausente')
  return c
}

/** Polling de 2 s enquanto a aba está visível (v2 §13.1). */
export const poll = () => (document.visibilityState === 'visible' ? 2000 : false)
