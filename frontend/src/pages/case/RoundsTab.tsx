import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { CheckCircle2, Circle, CircleDashed, Send } from 'lucide-react'
import { api, post } from '@/lib/api'
import { poll } from '@/lib/session'
import { fmtDateTime } from '@/lib/format'
import type { Gap, RoundRow } from '@/lib/types'
import { ChannelBadge } from '@/components/domain/badges'
import { Button } from '@/components/ui/button'

const GAP_LABEL: Record<Gap['status'], string> = { open: 'em aberto', answered: 'respondida', obsolete: 'obsoleta', disputed: 'em disputa' }
const ROUND_LABEL: Record<string, string> = { planned: 'planejada', ready: 'pronta', sending: 'enviando', waiting: 'aguardando resposta', completed: 'concluída', superseded: 'substituída' }

export function RoundsTab({ caseId }: { caseId: string }) {
  const qc = useQueryClient()
  const rounds = useQuery({ queryKey: ['rounds', caseId], queryFn: () => api<RoundRow[]>(`/api/cases/${caseId}/rounds`), refetchInterval: poll })
  const gaps = useQuery({ queryKey: ['gaps', caseId], queryFn: () => api<Gap[]>(`/api/cases/${caseId}/gaps`), refetchInterval: poll })
  const release = useMutation({
    mutationFn: (id: string) => post(`/api/rounds/${id}/release`, {}),
    onSuccess: () => { toast.success('Rodada liberada para envio.'); qc.invalidateQueries() },
    onError: (e: Error) => toast.error(e.message),
  })

  return (
    <div className="space-y-5">
      <section aria-label="Lacunas" className="rounded-xl border bg-card p-4">
        <h2 className="text-base font-semibold">Lacunas</h2>
        <p className="text-xs text-muted-foreground">O que falta para propor a alteração. Resolver uma lacuna não apaga o pedido que a originou.</p>
        {gaps.data?.length === 0 ? <p className="mt-2 text-sm text-muted-foreground">Nenhuma lacuna: os pedidos estavam claros.</p> : null}
        <ul className="mt-2 divide-y text-sm">
          {gaps.data?.map((g) => (
            <li key={g.id} className="flex flex-wrap items-center gap-2 py-2">
              {g.status === 'answered' ? <CheckCircle2 className="size-4 text-ontrack" aria-hidden /> : g.status === 'disputed' ? <Circle className="size-4 text-late" aria-hidden /> : <CircleDashed className="size-4 text-muted-foreground" aria-hidden />}
              <span className="font-mono text-xs">{g.ref}</span>
              <span className="min-w-48 flex-1">{g.question}</span>
              <span className="rounded-sm border px-1.5 text-xs">{g.topic}</span>
              <span className={`text-xs font-medium ${g.status === 'answered' ? 'text-ontrack-fg' : g.status === 'disputed' ? 'text-late-fg' : 'text-muted-foreground'}`}>{GAP_LABEL[g.status]}</span>
              {g.note ? <span className="basis-full text-xs text-muted-foreground">Nota: {g.note}</span> : null}
            </li>
          ))}
        </ul>
      </section>

      {rounds.data?.length === 0 ? <p className="text-sm text-muted-foreground">Ainda não há rodadas neste caso.</p> : null}
      {rounds.data?.map((r) => (
        <section key={r.id} aria-label={`Rodada ${r.seq}`} className="rounded-xl border bg-card p-4">
          <header className="flex flex-wrap items-center gap-2">
            <h2 className="text-base font-semibold">Rodada {r.seq}</h2>
            <span className="rounded-sm border px-1.5 text-xs">{ROUND_LABEL[r.status] ?? r.status}</span>
            <span className="text-sm text-muted-foreground">para {r.recipient.name}</span>
            <span className="ml-auto flex items-center gap-2">{r.channels.map((c) => <ChannelBadge key={c} channel={c as 'pylon' | 'whatsapp' | 'portal'} />)}</span>
          </header>
          <p className="mt-1 text-sm">{r.objective}</p>
          <p className="mt-1 text-xs text-muted-foreground"><b>Por que assim:</b> {r.grouping_note}</p>
          {r.sent_at ? <p className="mt-1 text-xs text-muted-foreground">Enviada em {fmtDateTime(r.sent_at)} · lembretes enviados: {r.reminders_sent} de 2</p> : null}
          <ol className="mt-3 space-y-1 text-sm">
            {r.items.map((i) => (
              <li key={i.id} className="flex items-start gap-2">
                {i.status === 'answered' ? <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-ontrack" aria-label="respondido" /> : <CircleDashed className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-label="em aberto" />}
                <span>{i.position}. {i.question}</span>
                {i.due_at && i.status === 'open' ? <span className="ml-auto whitespace-nowrap text-xs text-muted-foreground">até {fmtDateTime(i.due_at)}</span> : null}
              </li>
            ))}
          </ol>
          {r.awaiting_review && r.preview ? (
            <div className="mt-4 space-y-2 border-t pt-3">
              <p className="text-sm font-medium">Primeira mensagem a {r.recipient.name}: revise antes de enviar</p>
              <pre className="whitespace-pre-wrap rounded-lg bg-muted/60 p-3 font-sans text-sm leading-relaxed">{r.preview}</pre>
              <p className="text-xs text-muted-foreground">Será enviada com o mesmo conteúdo por Pylon, WhatsApp e Portal (canais autorizados).</p>
              <Button onClick={() => release.mutate(r.id)} disabled={release.isPending}><Send />Enviar a rodada</Button>
            </div>
          ) : null}
        </section>
      ))}
    </div>
  )
}
