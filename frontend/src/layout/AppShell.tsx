import { NavLink, Outlet } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Building2, CalendarCheck, Inbox, LogOut, TriangleAlert, FlaskConical } from 'lucide-react'
import { api } from '@/lib/api'
import { poll, useSession } from '@/lib/session'
import type { ClientRow, Today } from '@/lib/types'
import { cn } from '@/lib/utils'
import { ClientMark, ClientSeal } from '@/components/domain/client'
import { DemoBanner, StaleIndicator } from '@/components/domain/panels'
import { Button } from '@/components/ui/button'

const nav = [
  { to: '/', label: 'Hoje', Icon: CalendarCheck, end: true },
  { to: '/interventions', label: 'Intervenções', Icon: TriangleAlert, end: false },
  { to: '/clients', label: 'Clientes', Icon: Building2, end: false },
  { to: '/settings/demo', label: 'Demonstração', Icon: FlaskConical, end: false },
]

export function AppShell() {
  const { me, logout, client, setClient } = useSession()
  const clients = useQuery({ queryKey: ['clients'], queryFn: () => api<ClientRow[]>('/api/clients') })
  const today = useQuery({ queryKey: ['today', null], queryFn: () => api<Today>('/api/today'), refetchInterval: poll })
  const selected = clients.data?.find((c) => c.id === client) ?? null
  const total = today.data?.tasks.length ?? 0

  return (
    <div className="flex min-h-screen flex-col">
      <DemoBanner />
      <div className="flex flex-1 flex-col md:flex-row">
        <aside className="flex shrink-0 flex-col gap-4 border-b bg-sidebar p-3 md:w-60 md:border-r md:border-b-0" aria-label="Navegação">
          <div className="flex items-center gap-2 px-1">
            <span className="flex size-7 items-center justify-center rounded-md bg-primary text-sm font-semibold text-primary-foreground" aria-hidden>A</span>
            <span className="text-sm font-semibold tracking-tight">Aprova Command</span>
          </div>

          <div>
            <label htmlFor="client-select" className="mb-1 block px-1 text-[11px] font-semibold tracking-wider text-muted-foreground uppercase">Cliente</label>
            <select
              id="client-select"
              value={client ?? ''}
              onChange={(e) => setClient(e.target.value || null)}
              className="h-9 w-full rounded-md border bg-card px-2 text-sm shadow-xs"
            >
              <option value="">Todos os clientes ({total})</option>
              {clients.data?.map((c) => (
                <option key={c.id} value={c.id}>{c.short} · {c.name} ({today.data?.counts_by_client[c.id] ?? 0})</option>
              ))}
            </select>
          </div>

          <nav className="flex flex-row flex-wrap gap-1 md:flex-col">
            {nav.map(({ to, label, Icon, end }) => (
              <NavLink
                key={to} to={to} end={end}
                className={({ isActive }) => cn('flex items-center gap-2 rounded-md px-2 py-1.5 text-sm font-medium transition-colors', isActive ? 'bg-sidebar-accent' : 'hover:bg-muted')}
              >
                <Icon className="size-4" aria-hidden />
                {label}
                {to === '/' && total > 0 ? <span className="ml-auto rounded-full bg-primary px-1.5 text-[11px] text-primary-foreground">{total}</span> : null}
              </NavLink>
            ))}
            <span className="hidden items-center gap-2 rounded-md px-2 py-1.5 text-sm text-muted-foreground md:flex" title="Disponível em uma fatia futura"><Inbox className="size-4" aria-hidden />Caixa de entrada <em className="ml-auto text-[11px] not-italic">em breve</em></span>
          </nav>

          <div className="mt-auto flex items-center justify-between gap-2 border-t pt-3 text-xs">
            <span className="truncate text-muted-foreground">Persona: {me?.name}</span>
            <Button variant="ghost" size="icon-sm" onClick={logout} aria-label="Trocar persona"><LogOut /></Button>
          </div>
        </aside>

        <div className="min-w-0 flex-1">
          <header className="flex flex-wrap items-center gap-3 border-b bg-card px-6 py-2.5">
            {selected ? <ClientSeal client={selected} /> : (
              <span className="inline-flex items-center gap-2 text-sm font-medium">
                {clients.data?.map((c) => <ClientMark key={c.id} client={c} />)}Todos os clientes
              </span>
            )}
            <span className="ml-auto"><StaleIndicator updatedAt={today.dataUpdatedAt} error={today.isError} /></span>
          </header>
          <main className="mx-auto max-w-[1200px] p-6"><Outlet /></main>
        </div>
      </div>
    </div>
  )
}
