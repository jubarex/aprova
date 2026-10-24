import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { CircleCheck, Hourglass } from 'lucide-react'
import { api } from '@/lib/api'
import { poll } from '@/lib/session'
import type { PortalHome, PortalItem } from '@/lib/types'
import { DeadlineBadge } from '@/components/domain/badges'
import { NextStepCard } from '@/components/domain/panels'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'

function Row({ i }: { i: PortalItem }) {
  const inner = (
    <>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium">{i.title}</p>
        <p className="mt-0.5 text-xs text-muted-foreground">{i.why}</p>
      </div>
      {i.kind !== 'done' ? <DeadlineBadge deadline={i.deadline} /> : <CircleCheck className="size-4 text-ontrack" aria-label="Concluído" />}
    </>
  )
  const cls = 'flex items-start gap-3 rounded-xl border bg-card p-3'
  return i.kind === 'approval' && i.change_set_id
    ? <li><Link to={`/portal/aprovacoes/${i.change_set_id}`} className={`${cls} hover:bg-muted/50`}>{inner}</Link></li>
    : <li className={cls}>{inner}</li>
}

export default function PortalHomePage() {
  const q = useQuery({ queryKey: ['portal-home'], queryFn: () => api<PortalHome>('/api/portal/me'), refetchInterval: poll })
  if (q.isLoading) return <div className="space-y-3"><Skeleton className="h-8 w-2/3" /><Skeleton className="h-40" /></div>
  if (q.isError || !q.data) return <p className="text-late-fg">Não foi possível carregar suas pendências. Tente de novo em instantes.</p>
  const h = q.data
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl">Olá, {h.person.name.split(' ')[0]}</h1>
        <p className="text-sm text-muted-foreground">{h.secretariat ?? h.municipality.name}</p>
      </div>

      {h.next_step ? (
        <NextStepCard
          title={h.next_step.title} why={h.next_step.why} deadline={<DeadlineBadge deadline={h.next_step.deadline} />}
          action={<Button size="lg" className="h-11 w-full text-base" render={<Link to={`/portal/aprovacoes/${h.next_step.change_set_id}`} />}>Revisar e aprovar</Button>}
        />
      ) : (
        <section className="rounded-xl border bg-card p-4">
          <p className="flex items-center gap-2 font-medium"><CircleCheck className="size-5 text-ontrack" aria-hidden />Você está em dia</p>
          <p className="mt-1 text-sm text-muted-foreground">No momento não há nada pendente com você. Avisaremos por aqui e pelo WhatsApp quando precisarmos de algo.</p>
        </section>
      )}

      {h.today.length > 1 ? (
        <section aria-label="Para hoje"><h2 className="mb-2 text-base font-semibold">Para hoje ({h.today.length})</h2><ul className="space-y-2">{h.today.map((i) => <Row key={i.case_id} i={i} />)}</ul></section>
      ) : null}

      <section aria-label="Aguardando a Aprova">
        <h2 className="mb-2 flex items-center gap-1.5 text-base font-semibold"><Hourglass className="size-4" aria-hidden />Aguardando a Aprova ({h.waiting.length})</h2>
        {h.waiting.length === 0 ? <p className="text-sm text-muted-foreground">Nada em andamento por nossa parte.</p> : <ul className="space-y-2">{h.waiting.map((i) => <Row key={i.case_id} i={i} />)}</ul>}
      </section>

      <section aria-label="Concluídos">
        <h2 className="mb-2 text-base font-semibold">Concluídos ({h.done.length})</h2>
        {h.done.length === 0 ? <p className="text-sm text-muted-foreground">Ainda não há itens concluídos.</p> : <ul className="space-y-2">{h.done.map((i) => <Row key={i.case_id} i={i} />)}</ul>}
      </section>
    </div>
  )
}
