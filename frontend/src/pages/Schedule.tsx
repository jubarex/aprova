import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { useSession } from '@/lib/session'
import { fmtDate } from '@/lib/format'
import type { ScheduleClient } from '@/lib/types'
import { ClientSeal } from '@/components/domain/client'
import { DeadlineBadge, StateBadge } from '@/components/domain/badges'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'

const BAR: Record<string, string> = {
  ontrack: 'bg-ontrack-bg border-ontrack-border', atrisk: 'bg-atrisk-bg border-atrisk-border', late: 'bg-late-bg border-late-border late-hatch',
}

/** Cronograma por cliente e onda. Atraso aparece com hachura e texto, nunca só com cor. */
export default function SchedulePage() {
  const { client } = useSession()
  const q = useQuery({ queryKey: ['schedule', client], queryFn: () => api<ScheduleClient[]>(`/api/schedule${client ? `?client=${client}` : ''}`), refetchInterval: 5000 })
  return (
    <div className="space-y-6">
      <div><h1>Cronograma</h1><p className="mt-1 text-muted-foreground">Cada barra vai do início da implantação ao prazo do processo. A linha vertical é hoje (relógio de negócio).</p></div>
      {q.isLoading ? <Skeleton className="h-40" /> : null}
      {q.data?.map((c) => {
        const start = new Date(c.start ?? c.now).getTime()
        const end = new Date(c.target ?? c.now).getTime()
        const now = new Date(c.now).getTime()
        const span = Math.max(1, end - start)
        const pct = (t: number) => Math.min(100, Math.max(0, ((t - start) / span) * 100))
        const waves = [...new Set(c.processes.map((p) => p.wave))].sort()
        return (
          <section key={c.id} className="rounded-xl border bg-card shadow-xs" aria-label={c.name}>
            <header className="flex flex-wrap items-center gap-3 border-b p-4">
              <ClientSeal client={c} />
              <span className="text-xs text-muted-foreground">início {fmtDate(c.start)} · meta {fmtDate(c.target)} · {c.processes.length} processos</span>
            </header>
            {waves.map((w) => {
              const list = c.processes.filter((p) => p.wave === w)
              const late = list.filter((p) => p.deadline.status === 'late').length
              return (
                <details key={w} open={w === waves[0]} className="border-b last:border-b-0">
                  <summary className="cursor-pointer px-4 py-2.5 text-sm font-semibold">Onda {w} <span className="ml-2 font-normal text-muted-foreground">{list.length} processos{late ? ` · ${late} atrasado(s)` : ''}</span></summary>
                  <ul className="divide-y">
                    {list.map((p) => {
                      const due = p.due_at ? new Date(p.due_at).getTime() : end
                      return (
                        <li key={p.id} className="grid grid-cols-[88px_1fr] items-center gap-x-3 gap-y-1 px-4 py-2 text-sm md:grid-cols-[88px_minmax(160px,1fr)_minmax(180px,2fr)_auto]">
                          <span className="font-mono text-xs">{p.code}</span>
                          <span className="truncate">{p.case_id ? <Link className="underline-offset-4 hover:underline" to={`/processes/${p.case_id}`}>{p.name}</Link> : p.name}</span>
                          <div className="relative col-span-2 h-5 rounded-sm bg-muted md:col-span-1" role="img" aria-label={`Prazo ${fmtDate(p.due_at)}`}>
                            <div className={cn('absolute inset-y-0 left-0 rounded-sm border', BAR[p.deadline.status])} style={{ width: `${pct(due)}%` }} />
                            <div className="absolute inset-y-[-2px] w-0.5 bg-foreground/70" style={{ left: `${pct(now)}%` }} aria-hidden />
                          </div>
                          <span className="col-span-2 flex flex-wrap items-center gap-2 md:col-span-1"><StateBadge axis={p.axis} label={p.state_label} /><DeadlineBadge deadline={p.deadline} /></span>
                        </li>
                      )
                    })}
                  </ul>
                </details>
              )
            })}
          </section>
        )
      })}
    </div>
  )
}
