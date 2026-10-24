import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { ArrowLeft, CircleCheck, Info } from 'lucide-react'
import { api, ApiError, post } from '@/lib/api'
import type { PortalApproval } from '@/lib/types'
import { DeadlineBadge } from '@/components/domain/badges'
import { ConfirmEffectDialog } from '@/components/domain/panels'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Textarea } from '@/components/ui/textarea'

export default function PortalApprovalPage() {
  const { id = '' } = useParams()
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['portal-approval', id], queryFn: () => api<PortalApproval>(`/api/portal/approvals/${id}`) })
  const [dlg, setDlg] = useState<null | 'approve' | 'reject'>(null)
  const [reason, setReason] = useState('')
  const [done, setDone] = useState<null | 'approve' | 'reject'>(null)

  const decide = useMutation({
    mutationFn: (decision: 'approve' | 'reject') =>
      post(`/api/portal/approvals/${id}`, { decision, expected_case_version: q.data!.case_version, rationale: reason }),
    onSuccess: (_r, decision) => { setDone(decision); setDlg(null); qc.invalidateQueries() },
    onError: (e: unknown) => {
      const err = e as ApiError
      toast.error(err.status === 409 ? 'Esta alteração mudou enquanto você a revisava. Releia e decida novamente.' : err.message)
      if (err.status === 409) { setDlg(null); qc.invalidateQueries() }
    },
  })

  if (q.isLoading) return <Skeleton className="h-64" />
  if (q.isError || !q.data) return <p className="text-late-fg">Não encontramos esta alteração. <Link className="underline" to="/portal">Voltar ao início</Link></p>
  const a = q.data

  if (done) {
    return (
      <section className="space-y-4 rounded-xl border bg-card p-5" aria-live="polite">
        <p className="flex items-center gap-2 text-lg font-semibold"><CircleCheck className="size-6 text-ontrack" aria-hidden />Recebido</p>
        {done === 'approve' ? (
          <p className="text-sm">Obrigado. <b>O que acontece agora:</b> a equipe da Aprova faz a segunda conferência, publica a alteração e confirma que ela ficou correta. Você não precisa fazer mais nada.</p>
        ) : (
          <p className="text-sm">Obrigado pelo retorno. <b>O que acontece agora:</b> a equipe da Aprova vai ajustar a alteração com base no que você escreveu e pode voltar a falar com você.</p>
        )}
        <Button className="h-11 w-full" render={<Link to="/portal" />}>Voltar ao início</Button>
      </section>
    )
  }

  return (
    <div className="space-y-5">
      <Link to="/portal" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"><ArrowLeft className="size-4" aria-hidden />Início</Link>
      <div>
        <p className="text-xs text-muted-foreground">{a.secretariat ? `${a.secretariat} · ` : ''}<span className="font-mono">{a.process.code}</span></p>
        <h1 className="text-2xl">Aprovar a alteração de “{a.process.name}”</h1>
        <div className="mt-2"><DeadlineBadge deadline={a.deadline} /></div>
      </div>

      <section className="flex gap-2 rounded-xl border border-brand-100 bg-brand-50 p-3 text-sm" aria-label="Por que você está vendo isto">
        <Info className="mt-0.5 size-4 shrink-0 text-brand-600" aria-hidden /><p><b>Por que pedimos:</b> {a.why}</p>
      </section>

      <section aria-label="O que muda">
        <h2 className="mb-2 text-base font-semibold">O que vai mudar</h2>
        <ul className="space-y-2">{a.changes.map((c, i) => <li key={i} className="rounded-xl border bg-card p-3 text-sm">{c.text}</li>)}</ul>
      </section>

      <section aria-label="Como vai funcionar">
        <h2 className="mb-2 text-base font-semibold">Como vai funcionar</h2>
        <ul className="space-y-2">
          {a.examples.map((e, i) => (
            <li key={i} className="rounded-xl border bg-card p-3 text-sm">
              <p className="font-medium">{e.title}</p>
              <p className="text-muted-foreground">Se: {e.when}</p>
              <p>{e.result}</p>
            </li>
          ))}
        </ul>
        <p className="mt-2 text-xs text-muted-foreground">Estes exemplos foram executados no sistema antes de chegar até você. Versão <span className="font-mono">{a.version_label}</span>.</p>
      </section>

      {a.can_decide ? (
        <div className="sticky bottom-0 -mx-4 space-y-2 border-t bg-background/95 px-4 py-3">
          <Button size="lg" className="h-11 w-full text-base" onClick={() => setDlg('approve')}>Aprovar versão {a.version_label}</Button>
          <Button size="lg" variant="outline" className="h-11 w-full" onClick={() => setDlg('reject')}>Pedir ajuste</Button>
        </div>
      ) : (
        <p className="rounded-xl border bg-muted/50 p-3 text-sm text-muted-foreground">
          {a.case_state === 'WAITING_MUNICIPAL_APPROVAL' ? 'Você pode ver esta alteração, mas a aprovação é de outra pessoa responsável pelo processo.' : 'Esta alteração não está mais aguardando a sua aprovação.'}
        </p>
      )}

      <ConfirmEffectDialog
        open={dlg === 'approve'} onOpenChange={(o) => !o && setDlg(null)} title="Aprovar esta alteração?"
        client={a.municipality} process={`${a.process.code} · ${a.process.name}`} version={a.version_label}
        confirmLabel="Sim, aprovar" pending={decide.isPending} onConfirm={() => decide.mutate('approve')}
      />
      <ConfirmEffectDialog
        open={dlg === 'reject'} onOpenChange={(o) => !o && setDlg(null)} title="Pedir ajuste"
        client={a.municipality} process={`${a.process.code} · ${a.process.name}`} version={a.version_label}
        confirmLabel="Enviar pedido de ajuste" pending={decide.isPending}
        onConfirm={() => { if (reason.trim().length < 3) { toast.error('Conte o que precisa ser ajustado.'); return } decide.mutate('reject') }}
      >
        <Textarea value={reason} onChange={(e) => setReason(e.target.value)} placeholder="O que precisa mudar?" aria-label="O que precisa mudar" />
      </ConfirmEffectDialog>
    </div>
  )
}
