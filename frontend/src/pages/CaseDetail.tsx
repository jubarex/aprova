import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { CheckCircle2, CircleX, FileText, Pause, Play, ShieldCheck } from 'lucide-react'
import { api, ApiError, post } from '@/lib/api'
import { poll } from '@/lib/session'
import { fmtDateTime, sinceText } from '@/lib/format'
import type { CaseDetail, ChangeSetDetail, DiffItem, TimelineEvent } from '@/lib/types'
import { ClientSeal } from '@/components/domain/client'
import { ChannelBadge, DeadlineBadge, StateBadge } from '@/components/domain/badges'
import { ConfirmEffectDialog, WhyPanel } from '@/components/domain/panels'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { RoundsTab } from './case/RoundsTab'
import { ConversationTab } from './case/ConversationTab'
import { PeopleTab } from './case/PeopleTab'
import { SimulatorTab } from './case/SimulatorTab'
import { DecisionPanel } from './case/DecisionPanel'
import { Textarea } from '@/components/ui/textarea'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  Breadcrumb, BreadcrumbItem, BreadcrumbLink, BreadcrumbList, BreadcrumbPage, BreadcrumbSeparator,
} from '@/components/ui/breadcrumb'

function describeDiff(d: DiffItem): string {
  const v = (x: unknown) => (typeof x === 'string' ? x : JSON.stringify(x))
  switch (d.kind) {
    case 'campo_adicionado': return `Novo campo “${d.label}”`
    case 'campo_alterado': return `“${d.label}” · ${d.attr}: ${v(d.before)} → ${v(d.after)}`
    case 'regra_adicionada': return `Nova regra ${d.rule_id}`
    case 'regra_alterada': return `Regra ${d.rule_id} alterada`
    case 'regra_removida': return `Regra ${d.rule_id} removida`
    default: return d.kind
  }
}

const ACTION_LABEL: Record<string, string> = {
  start: 'Caso iniciado', ticket_persisted: 'Ticket registrado', schema_validated: 'Formulário-base validado',
  dossier_changes_ready: 'Candidata e testes prontos', dossier_blocked: 'Parado para decisão humana',
  dossier_created: 'Dossiê criado pelo agente', change_set_proposed: 'Candidata proposta pelo agente',
  tests_run_pre_approval: 'Testes executados', tests_reviewed: 'Resultados esperados revisados por uma pessoa',
  approval_requested: 'Aprovação municipal solicitada', candidate_valid: 'Candidata validada',
  municipal_approved: 'Aprovada pela prefeitura', implanter_approved: 'Aprovada pela Aprova',
  apply_receipt: 'Versão aplicada (recibo gravado)', readback_verified: 'Versão conferida após leitura do motor',
  tests_run_post_readback: 'Testes executados após o read-back', verified_and_closed: 'Ticket fechado',
  intervention_opened: 'Intervenção aberta', intervention_resolved: 'Intervenção resolvida',
  approvals_invalidated: 'Aprovações invalidadas', replay_miss: 'Sem gravação de replay', pause: 'Pausado', resume: 'Retomado',
  rejected_or_revoked: 'Rejeitada ou revogada', case_created: 'Caso criado', ticket_created: 'Ticket criado', tests_edited: 'Testes editados',
}

export default function CaseDetailPage() {
  const { id = '' } = useParams()
  const qc = useQueryClient()
  const c = useQuery({ queryKey: ['case', id], queryFn: () => api<CaseDetail>(`/api/cases/${id}`), refetchInterval: poll })
  const csId = c.data?.change_set_id
  const cs = useQuery({
    queryKey: ['cs', id], enabled: !!csId, refetchInterval: poll,
    queryFn: async () => (await api<ChangeSetDetail[]>(`/api/cases/${id}/change-sets`)).at(-1) ?? null,
  })
  const tl = useQuery({ queryKey: ['timeline', id], queryFn: () => api<TimelineEvent[]>(`/api/cases/${id}/timeline`), refetchInterval: poll })
  const [confirm, setConfirm] = useState<null | 'request' | 'approve' | 'reject' | 'revoke'>(null)
  const [reason, setReason] = useState('')

  const refresh = () => ['case', 'cs', 'timeline', 'today'].forEach((k) => qc.invalidateQueries({ queryKey: [k] }))
  const onError = (e: unknown) => {
    const err = e as ApiError
    if (err.code === 'VERSION_CONFLICT' || err.status === 409) refresh()
    toast.error(err.message ?? 'Não foi possível concluir a ação.')
  }
  const act = useMutation({
    mutationFn: ({ path, body }: { path: string; body?: unknown }) => post(path, body),
    onSuccess: () => { toast.success('Feito.'); setConfirm(null); setReason(''); refresh() },
    onError,
  })
  const review = useMutation({
    mutationFn: () => api(`/api/change-sets/${csId}/tests/review`, { method: 'POST', body: {} }),
    onSuccess: () => { toast.success('Resultados esperados marcados como revisados.'); refresh() }, onError,
  })
  const run = useMutation({
    mutationFn: () => api(`/api/change-sets/${csId}/tests/run`, { method: 'POST', body: {} }),
    onSuccess: () => { toast.success('Testes executados.'); refresh() }, onError,
  })

  if (c.isLoading) return <div className="space-y-4"><Skeleton className="h-10 w-1/2" /><Skeleton className="h-32" /></div>
  if (c.isError || !c.data) return <p className="text-late-fg">Caso não encontrado. <Link className="underline" to="/">Voltar ao Hoje</Link></p>
  const k = c.data
  const set = cs.data
  const v = k.version
  const allReviewed = !!set && set.tests.length > 0 && set.tests.every((t) => t.reviewed)

  return (
    <div className="space-y-5">
      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem><BreadcrumbLink render={<Link to="/" />}>Hoje</BreadcrumbLink></BreadcrumbItem><BreadcrumbSeparator />
          <BreadcrumbItem>{k.municipality.name}</BreadcrumbItem><BreadcrumbSeparator />
          {k.secretariat ? (<><BreadcrumbItem>{k.secretariat}</BreadcrumbItem><BreadcrumbSeparator /></>) : null}
          <BreadcrumbItem><BreadcrumbPage>{k.process.code} {k.process.name}</BreadcrumbPage></BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>

      <div className="flex flex-wrap items-center gap-3">
        <ClientSeal client={k.municipality} />
        <h1 className="mr-auto">{k.process.code} · {k.process.name}</h1>
        <StateBadge axis={k.axis} label={k.state_label} />
        <DeadlineBadge deadline={k.deadline} />
      </div>

      <WhyPanel e={k.explanation} />

      <DecisionPanel c={k} />

      <div className="flex flex-wrap gap-2" role="group" aria-label="Ações do caso">
        {k.state === 'CHANGES_READY' && set ? (<>
          <Button variant="outline" onClick={() => run.mutate()} disabled={run.isPending}>Rodar testes</Button>
          <Button variant="outline" onClick={() => review.mutate()} disabled={review.isPending || allReviewed}>
            <ShieldCheck />{allReviewed ? 'Resultados esperados revisados' : 'Confirmar resultados esperados'}
          </Button>
          <Button onClick={() => setConfirm('request')} disabled={!allReviewed}>Pedir aprovação da prefeitura</Button>
          {!allReviewed ? <p className="self-center text-xs text-muted-foreground">Uma pessoa precisa confirmar os resultados esperados antes de pedir a aprovação.</p> : null}
        </>) : null}
        {k.state === 'WAITING_IMPLANTER_APPROVAL' ? (<>
          <Button onClick={() => setConfirm('approve')}><CheckCircle2 />Aprovar pela Aprova</Button>
          <Button variant="destructive" onClick={() => setConfirm('reject')}><CircleX />Rejeitar</Button>
        </>) : null}
        {k.state === 'WAITING_MUNICIPAL_APPROVAL' || k.state === 'WAITING_IMPLANTER_APPROVAL' ? (
          <Button variant="outline" onClick={() => setConfirm('revoke')}>Revogar aprovação</Button>) : null}
        {k.state === 'PAUSED' ? (
          <Button variant="outline" onClick={() => act.mutate({ path: `/api/cases/${id}/resume`, body: { expected_case_version: v } })}><Play />Retomar</Button>
        ) : k.state !== 'COMPLETED' ? (
          <Button variant="ghost" onClick={() => act.mutate({ path: `/api/cases/${id}/pause`, body: { expected_case_version: v, rationale: 'Pausado pelo implantador' } })}><Pause />Pausar</Button>
        ) : null}
      </div>

      <Tabs defaultValue="dossier">
        <TabsList>
          <TabsTrigger value="dossier">Dossiê</TabsTrigger>
          <TabsTrigger value="rounds">Rodadas e lacunas</TabsTrigger>
          <TabsTrigger value="messages">Conversas</TabsTrigger>
          <TabsTrigger value="people">Pessoas</TabsTrigger>
          <TabsTrigger value="form">Formulário e testes</TabsTrigger>
          <TabsTrigger value="approvals">Aprovações</TabsTrigger>
          <TabsTrigger value="timeline">Linha do tempo</TabsTrigger>
          <TabsTrigger value="sim">Simulador</TabsTrigger>
        </TabsList>

        <TabsContent value="dossier" className="mt-4 grid gap-4 lg:grid-cols-2">
          <section className="rounded-xl border bg-card p-4" aria-label="Fonte">
            <h2 className="mb-2 flex items-center gap-1.5 text-base font-semibold"><FileText className="size-4" aria-hidden />Resposta inicial no ticket</h2>
            <p className="mb-1 text-xs text-muted-foreground">{k.ticket.title}</p>
            <p className="rounded-lg bg-muted/60 p-3 text-sm leading-relaxed whitespace-pre-wrap">
              {highlight(k.ticket.initial_reply, k.change_requests.map((r) => r.quote))}
            </p>
          </section>
          <section className="space-y-2" aria-label="Interpretação">
            <h2 className="text-base font-semibold">Pedidos identificados</h2>
            {k.change_requests.length === 0 ? <p className="text-sm text-muted-foreground">Nenhum pedido foi extraído ainda.</p> : null}
            {k.change_requests.map((r) => (
              <article key={r.id} className="rounded-xl border bg-card p-3">
                <p className="text-sm font-medium">{r.summary}</p>
                <blockquote className="mt-1 border-l-2 border-brand-400 pl-2 text-xs text-muted-foreground">“{r.quote}”</blockquote>
                <p className="mt-2 text-xs text-muted-foreground">Clareza: {r.clarity} · Viabilidade: {r.feasibility} · Risco: {r.risk} · <span className="font-medium">{r.disposition === 'accepted' ? 'aceito' : 'pendente'}</span></p>
              </article>
            ))}
            <p className="text-xs text-muted-foreground">Interpretação feita pelo agente em modo replay (simulado); a citação é conferida pelo servidor.</p>
          </section>
        </TabsContent>

        <TabsContent value="rounds" className="mt-4"><RoundsTab caseId={k.id} /></TabsContent>
        <TabsContent value="messages" className="mt-4"><ConversationTab caseId={k.id} /></TabsContent>
        <TabsContent value="people" className="mt-4"><PeopleTab c={k} /></TabsContent>
        <TabsContent value="sim" className="mt-4"><SimulatorTab c={k} /></TabsContent>

        <TabsContent value="form" className="mt-4 space-y-4">
          {!set ? <p className="text-sm text-muted-foreground">Ainda não há candidata para este caso.</p> : (<>
            <section className="rounded-xl border bg-card p-4">
              <h2 className="text-base font-semibold">O que muda <span className="ml-2 font-mono text-xs font-medium text-muted-foreground">versão {set.short_hash}</span></h2>
              <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">{set.diff.map((d, i) => <li key={i}>{describeDiff(d)}</li>)}</ul>
              {set.rationale ? <p className="mt-2 text-xs text-muted-foreground">Sugestão do agente: {set.rationale}</p> : null}
            </section>
            <section className="rounded-xl border bg-card p-4">
              <h2 className="text-base font-semibold">Testes da regra</h2>
              <ul className="mt-2 divide-y text-sm">
                {set.tests.map((t) => {
                  const r = set.last_run?.results.find((x) => x.name === t.name)
                  return (
                    <li key={t.id} className="flex flex-wrap items-center gap-3 py-2">
                      <span className="font-medium">{t.name}</span>
                      <span className="rounded-sm border px-1.5 text-xs">{t.kind}</span>
                      <span className="text-xs text-muted-foreground">espera: {t.expected_codes.length ? t.expected_codes.join(', ') : 'formulário válido'}</span>
                      {t.reviewed ? <span className="text-xs text-ontrack-fg">revisado</span> : <span className="text-xs text-atrisk-fg">não revisado</span>}
                      {r ? <span className={`ml-auto text-xs font-medium ${r.passed ? 'text-ontrack-fg' : 'text-late-fg'}`}>{r.passed ? 'passou' : 'falhou'}</span> : null}
                    </li>
                  )
                })}
              </ul>
              {set.coverage_gaps.length ? <p className="mt-2 text-xs text-late-fg">Cobertura incompleta: {set.coverage_gaps.join('; ')}</p> : null}
              {set.last_run?.stale ? <p className="mt-2 text-xs text-atrisk-fg">A candidata ou os testes mudaram depois da última execução. Rode os testes de novo.</p> : null}
              {set.readback_run ? <p className="mt-2 text-xs text-ontrack-fg">Após aplicar, a leitura do motor foi conferida e os testes {set.readback_run.passed ? 'passaram' : 'falharam'}.</p> : null}
              <p className="mt-2 font-mono text-[11px] text-muted-foreground">candidata {set.candidate_hash.slice(0, 16)} · suíte {set.suite_hash.slice(0, 16)}</p>
            </section>
          </>)}
        </TabsContent>

        <TabsContent value="approvals" className="mt-4 space-y-2">
          {k.approvals.length === 0 ? <p className="text-sm text-muted-foreground">Nenhuma decisão registrada ainda.</p> : null}
          {k.approvals.map((a) => (
            <article key={a.id} className="flex flex-wrap items-center gap-3 rounded-xl border bg-card p-3 text-sm">
              <span className="font-medium">{a.role === 'municipal' ? 'Prefeitura' : 'Aprova'}</span>
              <span>{a.decision === 'approve' ? 'aprovou' : a.decision === 'reject' ? 'pediu ajuste' : 'revogou'}</span>
              <ChannelBadge channel={a.channel === 'portal' ? 'portal' : 'command'} />
              <span className="font-mono text-xs">{a.candidate_hash.slice(0, 8)}</span>
              <span className="text-xs text-muted-foreground">{fmtDateTime(a.at)}</span>
              {!a.valid ? <span className="rounded-sm bg-late-bg px-1.5 text-xs text-late-fg">invalidada: {a.invalidated_reason}</span> : null}
            </article>
          ))}
        </TabsContent>

        <TabsContent value="timeline" className="mt-4">
          <ol className="space-y-3 border-l pl-4">
            {tl.data?.map((e) => (
              <li key={e.seq} className="relative text-sm">
                <span className="absolute -left-[21px] top-1.5 size-2 rounded-full bg-brand-400" aria-hidden />
                <p className="font-medium">{ACTION_LABEL[e.action] ?? e.action}</p>
                <p className="text-xs text-muted-foreground">{e.why || (e.from && e.to ? `${e.from} → ${e.to}` : '')}</p>
                <p className="text-[11px] text-muted-foreground">{e.actor} · {sinceText(e.at)}</p>
              </li>
            ))}
          </ol>
        </TabsContent>
      </Tabs>

      <ConfirmEffectDialog
        open={confirm === 'request'} onOpenChange={(o) => !o && setConfirm(null)} title="Pedir a aprovação da prefeitura"
        client={k.municipality} process={`${k.process.code} · ${k.process.name}`} recipient={k.secretariat ?? undefined}
        version={set?.short_hash} confirmLabel="Pedir aprovação" pending={act.isPending}
        onConfirm={() => act.mutate({ path: `/api/change-sets/${csId}/request-approval`, body: { expected_case_version: v } })}
      />
      <ConfirmEffectDialog
        open={confirm === 'approve'} onOpenChange={(o) => !o && setConfirm(null)} title="Aprovar pela Aprova"
        client={k.municipality} process={`${k.process.code} · ${k.process.name}`} version={set?.short_hash}
        confirmLabel="Aprovar e aplicar" pending={act.isPending}
        onConfirm={() => act.mutate({ path: `/api/change-sets/${csId}/implanter-approval`, body: { decision: 'approve', expected_case_version: v } })}
      >
        <p className="text-sm text-muted-foreground">A versão aprovada pela prefeitura será aplicada ao motor e depois conferida por leitura.</p>
      </ConfirmEffectDialog>
      <ConfirmEffectDialog
        open={confirm === 'reject' || confirm === 'revoke'} onOpenChange={(o) => !o && setConfirm(null)} destructive
        title={confirm === 'revoke' ? 'Revogar aprovação' : 'Rejeitar a candidata'}
        client={k.municipality} process={`${k.process.code} · ${k.process.name}`} version={set?.short_hash}
        confirmLabel={confirm === 'revoke' ? 'Revogar' : 'Rejeitar'} pending={act.isPending}
        onConfirm={() => {
          if (reason.trim().length < 3) { toast.error('Informe o motivo.'); return }
          if (confirm === 'revoke') act.mutate({ path: `/api/change-sets/${csId}/revoke`, body: { expected_case_version: v, rationale: reason } })
          else act.mutate({ path: `/api/change-sets/${csId}/implanter-approval`, body: { decision: 'reject', expected_case_version: v, rationale: reason } })
        }}
      >
        <Textarea value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Motivo (obrigatório)" aria-label="Motivo" />
      </ConfirmEffectDialog>
    </div>
  )
}

function highlight(text: string, quotes: string[]) {
  const spans: [number, number][] = []
  for (const q of quotes) { const i = text.indexOf(q); if (i >= 0) spans.push([i, i + q.length]) }
  spans.sort((a, b) => a[0] - b[0])
  const out: React.ReactNode[] = []
  let pos = 0
  spans.forEach(([s, e], n) => {
    if (s < pos) return
    out.push(text.slice(pos, s))
    out.push(<mark key={n} className="rounded-sm bg-brand-100 px-0.5">{text.slice(s, e)}</mark>)
    pos = e
  })
  out.push(text.slice(pos))
  return out
}
