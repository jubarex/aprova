import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { api, post } from '@/lib/api'
import { useSession } from '@/lib/session'
import { fmtDateTime } from '@/lib/format'
import type { Persona, Runtime } from '@/lib/types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

export default function DemoSettingsPage() {
  const nav = useNavigate()
  const qc = useQueryClient()
  const { login } = useSession()
  const rt = useQuery({ queryKey: ['runtime'], queryFn: () => api<Runtime>('/api/demo/runtime'), refetchInterval: 5000 })
  const people = useQuery({ queryKey: ['personas'], queryFn: () => api<Persona[]>('/api/demo/personas') })
  const [confirm, setConfirm] = useState('')
  const start = useMutation({
    mutationFn: () => post<{ case_id: string }>('/api/demo/scenarios/G/start'),
    onSuccess: (r) => { qc.invalidateQueries(); nav(`/processes/${r.case_id}`) },
    onError: (e: Error) => toast.error(e.message),
  })
  const clock = useMutation({
    mutationFn: (hours: number) => post('/api/demo/clock/advance', { hours }),
    onSuccess: () => { toast.success('Relógio de negócio avançado.'); qc.invalidateQueries() },
  })
  const reset = useMutation({
    mutationFn: () => post('/api/demo/reset', { confirm }),
    onSuccess: () => { toast.success('Demonstração restaurada.'); setConfirm(''); qc.invalidateQueries() },
    onError: (e: Error) => toast.error(e.message),
  })
  const asPersona = async (id: string, kind: string) => { await login(id); nav(kind === 'contato' ? '/portal' : '/') }

  return (
    <div className="max-w-3xl space-y-6">
      <div><h1>Demonstração</h1><p className="mt-1 text-muted-foreground">Controles de simulação. Exclusivos do ambiente de demonstração; não são autenticação.</p></div>
      <section className="rounded-xl border bg-card p-4 space-y-2">
        <h2 className="text-base font-semibold">Cenários</h2>
        <p className="text-sm text-muted-foreground"><b>G</b> — ticket com dois pedidos claros → candidata e testes → aprovação da prefeitura no Portal → aprovação da Aprova → aplicação, verificação e fechamento.</p>
        <Button onClick={() => start.mutate()} disabled={start.isPending}>Iniciar cenário G</Button>
      </section>
      <section className="rounded-xl border bg-card p-4 space-y-2">
        <h2 className="text-base font-semibold">Entrar como persona</h2>
        <p className="text-sm text-muted-foreground">Contatos da prefeitura veem apenas o Portal do seu município.</p>
        <ul className="grid gap-2 sm:grid-cols-2">
          {people.data?.map((p) => (
            <li key={p.id}><Button variant="outline" className="w-full justify-start" onClick={() => asPersona(p.id, p.kind)}>{p.name} <span className="ml-auto text-xs text-muted-foreground">{p.kind}</span></Button></li>
          ))}
        </ul>
      </section>
      <section className="rounded-xl border bg-card p-4 space-y-2">
        <h2 className="text-base font-semibold">Relógio de negócio</h2>
        <p className="text-sm text-muted-foreground">Agora: <span className="font-mono">{fmtDateTime(rt.data?.business_now)}</span>. Prazos e lembretes usam este relógio.</p>
        <div className="flex gap-2">{[24, 72].map((h) => <Button key={h} variant="outline" size="sm" onClick={() => clock.mutate(h)}>+{h} h</Button>)}</div>
      </section>
      <section className="rounded-xl border border-late-border bg-late-bg/40 p-4 space-y-2">
        <h2 className="text-base font-semibold">Restaurar demonstração</h2>
        <p className="text-sm text-muted-foreground">Apaga todo o progresso sintético. Digite <b>RESETAR</b> para confirmar.</p>
        <div className="flex gap-2"><Input value={confirm} onChange={(e) => setConfirm(e.target.value)} className="max-w-48" aria-label="Confirmação" />
          <Button variant="destructive" disabled={confirm !== 'RESETAR' || reset.isPending} onClick={() => reset.mutate()}>Restaurar</Button></div>
      </section>
    </div>
  )
}
