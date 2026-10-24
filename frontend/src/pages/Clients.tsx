import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { poll } from '@/lib/session'
import { fmtDate } from '@/lib/format'
import type { CaseCard, ClientRow } from '@/lib/types'
import { ClientMark } from '@/components/domain/client'
import { DeadlineBadge, StateBadge } from '@/components/domain/badges'
import { Skeleton } from '@/components/ui/skeleton'

type Proc = { id: string; code: string; name: string; municipality: ClientRow; started: boolean; wave: number; deadline: CaseCard['deadline'] }

export default function ClientsPage() {
  const clients = useQuery({ queryKey: ['clients'], queryFn: () => api<ClientRow[]>('/api/clients'), refetchInterval: poll })
  const procs = useQuery({ queryKey: ['processes'], queryFn: () => api<Proc[]>('/api/processes'), refetchInterval: poll })
  const cases = useQuery({ queryKey: ['cases'], queryFn: () => api<CaseCard[]>('/api/cases'), refetchInterval: poll })

  return (
    <div className="space-y-6">
      <div><h1>Clientes</h1><p className="mt-1 text-muted-foreground">Uma implantação por prefeitura. Processos não iniciados ficam fora das contagens de sucesso.</p></div>
      {clients.isLoading ? <Skeleton className="h-40" /> : null}
      {clients.data?.map((c) => {
        const list = procs.data?.filter((p) => p.municipality.id === c.id) ?? []
        return (
          <section key={c.id} className="rounded-xl border bg-card shadow-xs" aria-label={c.name}>
            <header className="flex flex-wrap items-center gap-3 border-b p-4">
              <ClientMark client={c} className="size-8 text-xs" />
              <div className="mr-auto"><h2 className="text-base font-semibold">{c.name}</h2><p className="text-xs text-muted-foreground">Meta de conclusão: {fmtDate(c.target_date)}</p></div>
              <dl className="flex gap-5 text-sm">
                <div><dt className="text-xs text-muted-foreground">Processos</dt><dd className="font-semibold">{c.processes}</dd></div>
                <div><dt className="text-xs text-muted-foreground">Em andamento</dt><dd className="font-semibold">{c.active_cases}</dd></div>
                <div><dt className="text-xs text-muted-foreground">Concluídos</dt><dd className="font-semibold">{c.completed}</dd></div>
                <div><dt className="text-xs text-muted-foreground">Não iniciados</dt><dd className="font-semibold">{c.not_started}</dd></div>
              </dl>
            </header>
            <ul className="divide-y">
              {list.map((p) => {
                const k = cases.data?.find((x) => x.process.id === p.id && x.state !== 'COMPLETED') ?? cases.data?.find((x) => x.process.id === p.id)
                return (
                  <li key={p.id} className="flex flex-wrap items-center gap-3 px-4 py-2.5 text-sm">
                    <span className="w-20 font-mono text-xs">{p.code}</span>
                    <span className="min-w-40 flex-1">{p.name}</span>
                    <span className="text-xs text-muted-foreground">Onda {p.wave}</span>
                    {k ? <StateBadge axis={k.axis} label={k.state_label} /> : <StateBadge axis="idle" />}
                    <DeadlineBadge deadline={p.deadline} />
                    {k ? <Link className="text-xs font-medium text-primary underline-offset-4 hover:underline" to={`/processes/${k.id}`}>Abrir</Link>
                      : <Link className="text-xs font-medium text-primary underline-offset-4 hover:underline" to={`/processes/new?process=${p.id}`}>Iniciar</Link>}
                  </li>
                )
              })}
            </ul>
          </section>
        )
      })}
    </div>
  )
}
