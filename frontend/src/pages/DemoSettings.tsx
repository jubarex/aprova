import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { Copy, Play } from 'lucide-react'
import { api, post } from '@/lib/api'
import { useSession } from '@/lib/session'
import { fmtDateTime } from '@/lib/format'
import type { Persona, Runtime, Scenario } from '@/lib/types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

export default function DemoSettingsPage() {
  const nav = useNavigate()
  const qc = useQueryClient()
  const { login } = useSession()
  const rt = useQuery({ queryKey: ['runtime'], queryFn: () => api<Runtime>('/api/demo/runtime'), refetchInterval: 5000 })
  const people = useQuery({ queryKey: ['personas'], queryFn: () => api<Persona[]>('/api/demo/personas') })
  const scs = useQuery({ queryKey: ['scenarios'], queryFn: () => api<Scenario[]>('/api/demo/scenarios') })
  const [confirm, setConfirm] = useState('')
  const [link, setLink] = useState<string | null>(null)
  const start = useMutation({
    mutationFn: (id: string) => post<{ case_id: string }>(`/api/demo/scenarios/${id}/start`),
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
  const magic = useMutation({
    mutationFn: (id: string) => post<{ url: string }>('/api/demo/portal-links', { actor_id: id }),
    onSuccess: (r) => setLink(`${window.location.origin}${r.url}`),
    onError: (e: Error) => toast.error(e.message),
  })
  const asPersona = async (id: string, kind: string) => { await login(id); nav(kind === 'contato' ? '/portal' : '/') }
  const contacts = (people.data ?? []).filter((p) => p.kind === 'contato')

  return (
    <div className="max-w-3xl space-y-6">
      <div><h1>Demonstração</h1><p className="mt-1 text-muted-foreground">Controles de simulação. Exclusivos do ambiente de demonstração; não são autenticação.</p></div>

      <section className="space-y-3 rounded-xl border bg-card p-4" aria-label="Cenários">
        <h2 className="text-base font-semibold">Cenários</h2>
        <ul className="space-y-2">
          {scs.data?.map((s) => (
            <li key={s.id} className="flex flex-wrap items-start gap-3 rounded-lg border p-3">
              <div className="min-w-60 flex-1"><p className="text-sm font-medium">{s.title}</p><p className="text-xs text-muted-foreground">{s.description}</p></div>
              <Button size="sm" onClick={() => start.mutate(s.id)} disabled={start.isPending}><Play />Iniciar</Button>
            </li>
          ))}
        </ul>
        <p className="text-xs text-muted-foreground">Cada cenário usa um processo próprio. Dentro do caso, a aba <b>Simulador</b> executa o roteiro passo a passo.</p>
      </section>

      <section className="space-y-2 rounded-xl border bg-card p-4" aria-label="Personas">
        <h2 className="text-base font-semibold">Entrar como persona</h2>
        <p className="text-sm text-muted-foreground">Contatos da prefeitura veem apenas o Portal do seu município.</p>
        <ul className="grid gap-2 sm:grid-cols-2">
          {people.data?.map((p) => (
            <li key={p.id}><Button variant="outline" className="w-full justify-start" onClick={() => asPersona(p.id, p.kind)}>{p.name} <span className="ml-auto text-xs text-muted-foreground">{p.kind}</span></Button></li>
          ))}
        </ul>
      </section>

      <section className="space-y-2 rounded-xl border bg-card p-4" aria-label="Link do Portal">
        <h2 className="text-base font-semibold">Link de acesso ao Portal</h2>
        <p className="text-sm text-muted-foreground">Link mágico por contato, válido por 14 dias e guardado só como hash. É o link que iria na mensagem de boas-vindas.</p>
        <div className="flex flex-wrap gap-2">{contacts.map((p) => <Button key={p.id} size="sm" variant="outline" onClick={() => magic.mutate(p.id)}>{p.name}</Button>)}</div>
        {link ? <div className="flex items-center gap-2 rounded-lg bg-muted p-2 text-xs"><code className="min-w-0 flex-1 break-all">{link}</code>
          <Button size="icon-sm" variant="ghost" aria-label="Copiar link" onClick={() => void navigator.clipboard?.writeText(link)}><Copy /></Button></div> : null}
      </section>

      <section className="space-y-2 rounded-xl border bg-card p-4" aria-label="Relógio">
        <h2 className="text-base font-semibold">Relógio de negócio</h2>
        <p className="text-sm text-muted-foreground">Agora: <span className="font-mono">{fmtDateTime(rt.data?.business_now)}</span>. Prazos e lembretes usam este relógio (24 h lembrete, 48 h segundo, 72 h intervenção).</p>
        <div className="flex gap-2">{[24, 72].map((h) => <Button key={h} variant="outline" size="sm" onClick={() => clock.mutate(h)}>+{h} h</Button>)}</div>
      </section>

      <section className="space-y-2 rounded-xl border border-late-border bg-late-bg/40 p-4" aria-label="Restaurar">
        <h2 className="text-base font-semibold">Restaurar demonstração</h2>
        <p className="text-sm text-muted-foreground">Apaga todo o progresso sintético. Digite <b>RESETAR</b> para confirmar.</p>
        <div className="flex gap-2"><Input value={confirm} onChange={(e) => setConfirm(e.target.value)} className="max-w-48" aria-label="Confirmação" />
          <Button variant="destructive" disabled={confirm !== 'RESETAR' || reset.isPending} onClick={() => reset.mutate()}>Restaurar</Button></div>
      </section>
    </div>
  )
}
