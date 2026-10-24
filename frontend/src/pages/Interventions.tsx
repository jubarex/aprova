import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { api, post } from '@/lib/api'
import { poll, useSession } from '@/lib/session'
import { sinceText } from '@/lib/format'
import type { Intervention } from '@/lib/types'
import { ClientMark } from '@/components/domain/client'
import { DeadlineBadge } from '@/components/domain/badges'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Textarea } from '@/components/ui/textarea'

export default function InterventionsPage() {
  const { client } = useSession()
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['interventions', client], queryFn: () => api<Intervention[]>(`/api/interventions${client ? `?client=${client}` : ''}`), refetchInterval: poll })
  const [open, setOpen] = useState<string | null>(null)
  const [text, setText] = useState('')
  const resolve = useMutation({
    mutationFn: (id: string) => post(`/api/interventions/${id}/resolve`, { resolution: text }),
    onSuccess: () => { toast.success('Intervenção resolvida.'); setOpen(null); setText(''); qc.invalidateQueries() },
    onError: (e: Error) => toast.error(e.message),
  })
  const resume = useMutation({
    mutationFn: (i: Intervention) => post(`/api/cases/${i.case.id}/resume`, { expected_case_version: i.case.version, rationale: 'Retomada após resolver a intervenção' }),
    onSuccess: () => { toast.success('Caso retomado.'); qc.invalidateQueries() },
    onError: (e: Error) => toast.error(e.message),
  })

  return (
    <div className="space-y-5">
      <div>
        <h1>Intervenções</h1>
        <p className="mt-1 text-muted-foreground">Casos parados que esperam uma decisão sua, ordenados por urgência e tempo de espera.</p>
      </div>
      {q.isLoading ? <Skeleton className="h-24" /> : null}
      {q.data?.length === 0 ? <p className="rounded-xl border border-dashed bg-card p-10 text-center text-muted-foreground">Nenhuma intervenção aberta.</p> : null}
      <ul className="space-y-3">
        {q.data?.map((i) => (
          <li key={i.id} className="rounded-xl border bg-card p-4 shadow-xs">
            <div className="flex flex-wrap items-start gap-3">
              <ClientMark client={i.case.municipality} />
              <div className="min-w-0 flex-1">
                <p className="text-xs text-muted-foreground">{i.case.municipality.name} · <span className="font-mono">{i.case.process.code}</span> · {sinceText(i.since)}</p>
                <h3 className="text-sm font-semibold">{i.reason}</h3>
                {i.needed ? <p className="mt-1 text-sm text-muted-foreground"><span className="font-medium text-foreground">Decisão necessária:</span> {i.needed}</p> : null}
                <div className="mt-2"><DeadlineBadge deadline={i.case.deadline} /></div>
              </div>
              <Button variant="outline" size="sm" render={<Link to={`/processes/${i.case.id}`} />}>Abrir caso</Button>
              <Button size="sm" onClick={() => setOpen(open === i.id ? null : i.id)}>Resolver</Button>
            </div>
            {open === i.id ? (
              <div className="mt-3 space-y-2 border-t pt-3">
                <Textarea value={text} onChange={(e) => setText(e.target.value)} placeholder="Registre a decisão e a justificativa" aria-label="Decisão" />
                <div className="flex gap-2">
                  <Button size="sm" disabled={text.trim().length < 3 || resolve.isPending} onClick={() => resolve.mutate(i.id)}>Registrar decisão</Button>
                  <Button size="sm" variant="ghost" onClick={() => setOpen(null)}>Cancelar</Button>
                </div>
              </div>
            ) : null}
            <div className="mt-3 flex items-center gap-2 border-t pt-3 text-xs text-muted-foreground">
              Resolver não aprova nem retoma sozinho.
              <Button variant="link" size="sm" onClick={() => resume.mutate(i)} disabled={resume.isPending}>Retomar o caso</Button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}
