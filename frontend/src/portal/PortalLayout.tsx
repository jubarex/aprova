import { Link, Outlet } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { LogOut } from 'lucide-react'
import { api } from '@/lib/api'
import { useSession } from '@/lib/session'
import type { PortalHome } from '@/lib/types'
import { ClientSeal } from '@/components/domain/client'
import { DemoBanner } from '@/components/domain/panels'
import { Button } from '@/components/ui/button'

/** Layout do Portal: uma coluna, sem barra lateral, sem tabelas (direcionamento §6.2). */
export function PortalLayout() {
  const { logout } = useSession()
  const home = useQuery({ queryKey: ['portal-home'], queryFn: () => api<PortalHome>('/api/portal/me') })
  return (
    <div className="min-h-screen bg-background">
      <DemoBanner />
      <div className="mx-auto max-w-[560px] px-4 pb-16">
        <header className="flex items-center gap-2 py-4">
          {home.data ? <ClientSeal client={home.data.municipality} /> : <span className="text-sm font-semibold">Aprova Command</span>}
          <Button variant="ghost" size="icon-sm" className="ml-auto" onClick={logout} aria-label="Sair"><LogOut /></Button>
        </header>
        <Outlet />
        <footer className="mt-10 border-t pt-4 text-center text-xs text-muted-foreground">
          <Link to="/portal" className="underline-offset-4 hover:underline">Início</Link> · Portal da prefeitura · Aprova
        </footer>
      </div>
    </div>
  )
}
