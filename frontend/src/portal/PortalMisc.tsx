import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { api, post, setToken } from '@/lib/api'
import { useSession } from '@/lib/session'
import { fmtDateTime } from '@/lib/format'
import type { Onboarding } from '@/lib/types'
import { ChannelBadge } from '@/components/domain/badges'
import { DemoBanner } from '@/components/domain/panels'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'

/** Link mágico: troca o token por uma sessão do Portal. Funciona sem sessão prévia. */
export function PortalEnter() {
  const [sp] = useSearchParams()
  const nav = useNavigate()
  const qc = useQueryClient()
  const [err, setErr] = useState<string | null>(null)
  useEffect(() => {
    const t = sp.get('t')
    if (!t) { setErr('O link está incompleto.'); return }
    api<{ token: string }>('/api/portal/session', { method: 'POST', body: { token: t } })
      .then((r) => { setToken(r.token); qc.clear(); window.location.replace('/portal') })
      .catch((e: Error) => setErr(e.message))
  }, [sp, nav, qc])
  return (
    <div className="min-h-screen"><DemoBanner />
      <main className="mx-auto max-w-[560px] p-6">
        {err ? <p className="rounded-xl border border-late-border bg-late-bg p-4 text-sm text-late-fg">{err} Peça um novo link à equipe da Aprova.</p> : <Skeleton className="h-24" />}
      </main></div>
  )
}

export function PortalHistory() {
  const q = useQuery({ queryKey: ['portal-history'], queryFn: () => api<{ id: string; channel: 'pylon' | 'whatsapp' | 'portal'; body: string; at: string }[]>('/api/portal/history') })
  return (
    <div className="space-y-4">
      <Link to="/portal" className="text-sm text-muted-foreground hover:text-foreground">← Início</Link>
      <h1 className="text-2xl">O que você já respondeu</h1>
      <p className="text-sm text-muted-foreground">Tudo o que você enviou, por qualquer canal, fica aqui.</p>
      {q.data?.length === 0 ? <p className="text-sm text-muted-foreground">Você ainda não respondeu nada.</p> : null}
      <ul className="space-y-2">{q.data?.map((m) => (
        <li key={m.id} className="rounded-xl border bg-card p-3 text-sm">
          <p className="flex items-center gap-2 text-xs text-muted-foreground"><ChannelBadge channel={m.channel} />Respondido em {fmtDateTime(m.at)}</p>
          <p className="mt-1">{m.body}</p>
        </li>))}</ul>
    </div>
  )
}

/** Primeiro acesso em 3 passos. Declarar não é autorizar: nada aqui concede papel. */
export function PortalFirstAccess() {
  const nav = useNavigate()
  const qc = useQueryClient()
  const { me } = useSession()
  const q = useQuery({ queryKey: ['portal-onb'], queryFn: () => api<Onboarding>('/api/portal/onboarding') })
  const [step, setStep] = useState(1)
  const [claims, setClaims] = useState<Record<string, { answer: string; name: string }>>({})
  const [channel, setChannel] = useState('portal')
  const save = useMutation({
    mutationFn: () => post('/api/portal/onboarding', {
      preferred_channel: channel,
      claims: Object.entries(claims).map(([process_id, c]) => ({ process_id, answer: c.answer, refer_name: c.name })),
    }),
    onSuccess: () => { qc.invalidateQueries(); toast.success('Tudo certo. Vamos à sua primeira pergunta.'); nav('/portal') },
    onError: (e: Error) => toast.error(e.message),
  })
  if (q.isLoading || !q.data) return <Skeleton className="h-64" />
  const o = q.data
  const allClaimed = o.processes.every((p) => claims[p.id]?.answer && (claims[p.id].answer !== 'refer' || claims[p.id].name.trim().length > 1))
  return (
    <div className="space-y-5">
      <div><p className="text-xs font-semibold tracking-wider text-muted-foreground uppercase">Primeiro acesso · passo {step} de 3</p>
        <h1 className="text-2xl">{step === 1 ? 'Confirme seus dados' : step === 2 ? 'Isso é com você?' : 'Como prefere ser avisado?'}</h1></div>
      {step === 1 ? (<section className="space-y-3 rounded-xl border bg-card p-4">
        <p className="text-sm">A Aprova está colocando os processos eletrônicos da <b>{o.municipality.name}</b> no ar. Você foi indicado(a) como contato.</p>
        <dl className="text-sm"><dt className="text-xs text-muted-foreground">Nome</dt><dd className="font-medium">{o.name || me?.name}</dd><dt className="mt-2 text-xs text-muted-foreground">Secretaria</dt><dd className="font-medium">{o.secretariat ?? '—'}</dd></dl>
        <Button className="h-11 w-full" onClick={() => setStep(2)}>Sim, são meus dados</Button></section>) : null}
      {step === 2 ? (<section className="space-y-3">
        <p className="text-sm text-muted-foreground">Para cada processo, diga se é com você. Isso ajuda a perguntar para a pessoa certa. Não muda o que você pode aprovar.</p>
        {o.processes.map((p) => (
          <div key={p.id} className="rounded-xl border bg-card p-3">
            <p className="text-sm font-medium"><span className="font-mono text-xs">{p.code}</span> · {p.name}</p>
            <div className="mt-2 grid grid-cols-3 gap-2">
              {[['mine', 'Sou eu'], ['refer', 'Indicar outra pessoa'], ['unknown', 'Não sei']].map(([v, l]) => (
                <Button key={v} type="button" size="sm" variant={claims[p.id]?.answer === v ? 'default' : 'outline'} className="h-auto min-h-10 whitespace-normal py-1.5" onClick={() => setClaims({ ...claims, [p.id]: { answer: v, name: claims[p.id]?.name ?? '' } })}>{l}</Button>))}
            </div>
            {claims[p.id]?.answer === 'refer' ? <div className="mt-2 space-y-1"><Label htmlFor={`n-${p.id}`}>Nome de quem sabe</Label><Input id={`n-${p.id}`} value={claims[p.id].name} onChange={(e) => setClaims({ ...claims, [p.id]: { answer: 'refer', name: e.target.value } })} /></div> : null}
          </div>))}
        <Button className="h-11 w-full" disabled={!allClaimed} onClick={() => setStep(3)}>Continuar</Button></section>) : null}
      {step === 3 ? (<section className="space-y-3 rounded-xl border bg-card p-4">
        <fieldset className="space-y-2"><legend className="sr-only">Canal preferido</legend>
          {[['portal', 'Portal (aqui)'], ['whatsapp', 'WhatsApp'], ['pylon', 'Pylon (ticket)']].map(([v, l]) => (
            <label key={v} className="flex min-h-11 cursor-pointer items-center gap-3 rounded-xl border px-3 text-sm has-[:checked]:border-brand-400 has-[:checked]:bg-brand-50">
              <input type="radio" name="ch" value={v} checked={channel === v} onChange={() => setChannel(v)} className="size-4" />{l}</label>))}</fieldset>
        <p className="text-xs text-muted-foreground">Você pode responder por qualquer canal; o histórico fica junto.</p>
        <Button className="h-11 w-full" onClick={() => save.mutate()} disabled={save.isPending}>Concluir</Button></section>) : null}
    </div>
  )
}
