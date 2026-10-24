import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { UserCheck, UserX } from 'lucide-react'
import { api, post } from '@/lib/api'
import { poll } from '@/lib/session'
import type { CaseDetail, Convo } from '@/lib/types'
import { ConfirmEffectDialog } from '@/components/domain/panels'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

export function PeopleTab({ c }: { c: CaseDetail }) {
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['convo', c.id], queryFn: () => api<Convo>(`/api/cases/${c.id}/conversations`), refetchInterval: poll })
  const [confirmId, setConfirmId] = useState<string | null>(null)
  const [owner, setOwner] = useState({ name: '', topic: '' })
  const decide = useMutation({
    mutationFn: ({ id, decision }: { id: string; decision: 'authorize' | 'reject' }) => post(`/api/referrals/${id}/authorize`, { decision }),
    onSuccess: () => { toast.success('Decisão registrada.'); setConfirmId(null); qc.invalidateQueries() },
    onError: (e: Error) => toast.error(e.message),
  })
  const authorizeOwner = useMutation({
    mutationFn: () => post(`/api/cases/${c.id}/authorize-owner`, { name: owner.name, topic: owner.topic || 'geral' }),
    onSuccess: () => { toast.success('Responsável autorizado.'); setOwner({ name: '', topic: '' }); qc.invalidateQueries() },
    onError: (e: Error) => toast.error(e.message),
  })
  const pending = q.data?.referrals.find((r) => r.id === confirmId)

  return (
    <div className="space-y-5">
      <section className="rounded-xl border bg-card p-4" aria-label="Indicações">
        <h2 className="text-base font-semibold">Indicações de responsável</h2>
        <p className="text-xs text-muted-foreground">Receber um nome ou apelido não concede autorização. Ao autorizar, só o assunto indicado é repassado: notas internas e assuntos de outros setores nunca vão junto.</p>
        {q.data?.referrals.length === 0 ? <p className="mt-2 text-sm text-muted-foreground">Nenhuma indicação neste caso.</p> : null}
        <ul className="mt-2 space-y-2">
          {q.data?.referrals.map((r) => (
            <li key={r.id} className="rounded-lg border p-3 text-sm">
              <p><b>{r.name}</b>{r.sector ? ` · ${r.sector}` : ''} <span className="text-muted-foreground">(assunto: {r.topic})</span></p>
              <p className="text-xs text-muted-foreground">Indicado por {r.from?.name ?? '—'}{r.alias ? ` · apelido: ${r.alias}` : ''} · {r.gaps.length} lacuna(s) transferida(s)</p>
              {r.status === 'pending' ? (
                <div className="mt-2 flex gap-2">
                  <Button size="sm" onClick={() => setConfirmId(r.id)}><UserCheck />Autorizar este assunto</Button>
                  <Button size="sm" variant="outline" onClick={() => decide.mutate({ id: r.id, decision: 'reject' })}><UserX />Recusar</Button>
                </div>
              ) : <p className="mt-1 text-xs font-medium">{r.status === 'authorized' ? 'Autorizado: pode responder apenas sobre esse assunto.' : 'Recusado.'}</p>}
            </li>
          ))}
        </ul>
      </section>

      {c.state === 'WAITING_OWNER' ? (
        <section className="rounded-xl border border-st-blocked-border bg-st-blocked-bg/40 p-4" aria-label="Definir responsável">
          <h2 className="text-base font-semibold">Ninguém autorizado cobre este assunto</h2>
          <p className="text-xs text-muted-foreground">Autorize alguém que você já conhece, ou aguarde uma indicação do contato central.</p>
          <form className="mt-3 grid gap-3 sm:grid-cols-[1fr_1fr_auto]" onSubmit={(e) => { e.preventDefault(); authorizeOwner.mutate() }}>
            <div className="space-y-1"><Label htmlFor="ow-name">Nome</Label><Input id="ow-name" value={owner.name} onChange={(e) => setOwner({ ...owner, name: e.target.value })} required minLength={2} /></div>
            <div className="space-y-1"><Label htmlFor="ow-topic">Assunto</Label><Input id="ow-topic" placeholder="ex.: vigilancia" value={owner.topic} onChange={(e) => setOwner({ ...owner, topic: e.target.value })} /></div>
            <Button type="submit" className="self-end" disabled={authorizeOwner.isPending}>Autorizar</Button>
          </form>
        </section>
      ) : null}

      <ConfirmEffectDialog
        open={!!pending} onOpenChange={(o) => !o && setConfirmId(null)} title={`Autorizar ${pending?.name ?? ''}`}
        client={c.municipality} process={`${c.process.code} · ${c.process.name}`}
        recipient={`${pending?.name ?? ''} · apenas sobre ${pending?.topic ?? ''}`} confirmLabel="Autorizar escopo"
        pending={decide.isPending} onConfirm={() => pending && decide.mutate({ id: pending.id, decision: 'authorize' })}
      />
    </div>
  )
}
