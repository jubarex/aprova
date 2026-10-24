import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { api, post } from '@/lib/api'
import { poll, useSession } from '@/lib/session'
import { sinceText } from '@/lib/format'
import type { InboxMsg, RoundRow } from '@/lib/types'
import { ClientMark } from '@/components/domain/client'
import { ChannelBadge } from '@/components/domain/badges'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'

function LinkControl({ m }: { m: InboxMsg }) {
  const qc = useQueryClient()
  const rounds = useQuery({ queryKey: ['rounds', m.case_id], queryFn: () => api<RoundRow[]>(`/api/cases/${m.case_id}/rounds`) })
  const [round, setRound] = useState('')
  const link = useMutation({
    mutationFn: () => post(`/api/messages/${m.id}/link`, { round_id: round }),
    onSuccess: () => { toast.success('Mensagem vinculada à rodada.'); qc.invalidateQueries() },
    onError: (e: Error) => toast.error(e.message),
  })
  if (!rounds.data?.length) return <span className="text-xs text-muted-foreground">Sem rodada neste caso para vincular.</span>
  return (
    <div className="flex flex-wrap items-center gap-2">
      <select aria-label="Rodada" className="h-8 rounded-md border bg-card px-2 text-sm" value={round} onChange={(e) => setRound(e.target.value)}>
        <option value="">Escolha a rodada…</option>
        {rounds.data.map((r) => <option key={r.id} value={r.id}>Rodada {r.seq} · {r.recipient.name}</option>)}
      </select>
      <Button size="sm" disabled={!round || link.isPending} onClick={() => link.mutate()}>Vincular e processar</Button>
    </div>
  )
}

export default function InboxPage() {
  const { client } = useSession()
  const [sp, setSp] = useSearchParams()
  const triage = sp.get('triage') === '1'
  const q = useQuery({ queryKey: ['inbox', client, triage], queryFn: () => api<InboxMsg[]>(`/api/inbox?triage=${triage}${client ? `&client=${client}` : ''}`), refetchInterval: poll })
  return (
    <div className="space-y-5">
      <div>
        <h1>Caixa de entrada</h1>
        <p className="mt-1 text-muted-foreground">Mensagens de todos os canais e clientes, juntas. Sem rodada inequívoca, a mensagem espera aqui: o sistema não a atribui por conveniência.</p>
      </div>
      <div className="flex gap-2" role="group" aria-label="Filtro">
        <Button size="sm" variant={triage ? 'outline' : 'default'} onClick={() => setSp({})}>Todas</Button>
        <Button size="sm" variant={triage ? 'default' : 'outline'} onClick={() => setSp({ triage: '1' })}>Precisa de triagem</Button>
      </div>
      {q.isLoading ? <Skeleton className="h-24" /> : null}
      {q.data?.length === 0 ? <p className="rounded-xl border border-dashed bg-card p-10 text-center text-muted-foreground">{triage ? 'Nenhuma mensagem aguardando triagem.' : 'Nenhuma mensagem recebida ainda.'}</p> : null}
      <ul className="space-y-3">
        {q.data?.map((m) => (
          <li key={m.id} className="rounded-xl border bg-card p-4 shadow-xs">
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <ClientMark client={m.municipality} />
              <span className="font-medium">{m.municipality.name}</span>
              <span className="font-mono">{m.process.code}</span>
              <ChannelBadge channel={m.channel} />
              <span className="text-muted-foreground">{m.actor} · {sinceText(m.at)}</span>
              {m.flagged ? <span className="rounded-sm bg-late-bg px-1.5 text-late-fg">instrução suspeita</span> : null}
              {m.triage === 'pending' ? <span className="rounded-sm bg-atrisk-bg px-1.5 text-atrisk-fg">precisa de triagem</span> : null}
              <Button className="ml-auto" size="sm" variant="outline" render={<Link to={`/processes/${m.case_id}`} />}>Abrir caso</Button>
            </div>
            <p className="mt-2 text-sm">{m.body}</p>
            {m.triage === 'pending' ? <div className="mt-3 border-t pt-3"><LinkControl m={m} /></div> : null}
          </li>
        ))}
      </ul>
    </div>
  )
}
