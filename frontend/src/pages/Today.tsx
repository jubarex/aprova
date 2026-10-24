import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowRight, CalendarCheck } from 'lucide-react'
import { api } from '@/lib/api'
import { poll, useSession } from '@/lib/session'
import { sinceText, WHO } from '@/lib/format'
import type { CaseCard, Task, Today } from '@/lib/types'
import { ClientMark } from '@/components/domain/client'
import { DeadlineBadge, StateBadge } from '@/components/domain/badges'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'

function TaskRow({ t }: { t: Task }) {
  return (
    <li className="flex flex-wrap items-start gap-3 rounded-xl border bg-card p-4 shadow-xs">
      <ClientMark client={t.client} className="mt-0.5" />
      <div className="min-w-0 flex-1">
        <p className="text-xs text-muted-foreground">
          <span className="sr-only">Cliente: </span>{t.client.name} · <span className="font-mono">{t.process.code}</span>
          {t.secretariat ? ` · ${t.secretariat}` : ''}
        </p>
        <h3 className="mt-0.5 text-sm font-semibold">{t.title}</h3>
        <p className="mt-1 text-sm text-muted-foreground"><span className="font-medium text-foreground">Por quê:</span> {t.why.text}</p>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <DeadlineBadge deadline={t.deadline} />
          <span className="text-xs text-muted-foreground">{sinceText(t.since)}</span>
        </div>
      </div>
      <Button render={<Link to={t.primary_action.route} />} className="shrink-0">
        {t.primary_action.label}<ArrowRight data-icon="inline-end" />
      </Button>
    </li>
  )
}

function CaseRow({ c }: { c: CaseCard }) {
  return (
    <li className="flex flex-wrap items-center gap-3 rounded-xl border bg-card p-4 shadow-xs">
      <ClientMark client={c.municipality} />
      <div className="min-w-0 flex-1">
        <p className="text-xs text-muted-foreground">{c.municipality.name} · <span className="font-mono">{c.process.code}</span></p>
        <p className="text-sm font-medium">{c.explanation.what}</p>
        <p className="text-xs text-muted-foreground">{c.explanation.why}</p>
      </div>
      <div className="flex flex-col items-end gap-1">
        <StateBadge axis={c.axis} label={c.state_label} />
        <span className="text-xs text-muted-foreground">{WHO[c.ball_owner]} · {sinceText(c.since)}</span>
      </div>
      <Button variant="outline" size="sm" render={<Link to={`/processes/${c.id}`} />}>Abrir</Button>
    </li>
  )
}

export default function TodayPage() {
  const { client } = useSession()
  const q = useQuery({ queryKey: ['today', client], queryFn: () => api<Today>(`/api/today${client ? `?client=${client}` : ''}`), refetchInterval: poll })

  return (
    <div className="space-y-6">
      <div>
        <h1>O que fazer hoje</h1>
        <p className="mt-1 text-muted-foreground">Ações que dependem de você, por prazo. O que está com a prefeitura ou com o agente aparece nas outras abas.</p>
      </div>

      {q.isError ? (
        <Alert variant="destructive"><AlertTitle>Não foi possível carregar</AlertTitle><AlertDescription>{(q.error as Error).message} <Button variant="link" onClick={() => q.refetch()}>Tentar de novo</Button></AlertDescription></Alert>
      ) : null}

      <Tabs defaultValue="tasks">
        <TabsList>
          <TabsTrigger value="tasks">Para você ({q.data?.tasks.length ?? 0})</TabsTrigger>
          <TabsTrigger value="waiting">Aguardando prefeitura ({q.data?.waiting.length ?? 0})</TabsTrigger>
          <TabsTrigger value="agent">Agente trabalhando ({q.data?.agent.length ?? 0})</TabsTrigger>
        </TabsList>

        <TabsContent value="tasks" className="mt-4">
          {q.isLoading ? <div className="space-y-3"><Skeleton className="h-24" /><Skeleton className="h-24" /></div> : null}
          {q.data && q.data.tasks.length === 0 ? (
            <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed bg-card p-10 text-center">
              <CalendarCheck className="size-8 text-muted-foreground" aria-hidden />
              <p className="font-medium">Nada pendente com você{client ? ' neste cliente' : ''}.</p>
              <p className="text-sm text-muted-foreground">Quando algo precisar da sua decisão, aparece aqui com o motivo e o prazo.</p>
            </div>
          ) : null}
          <ul className="space-y-3">{q.data?.tasks.map((t) => <TaskRow key={t.task_id} t={t} />)}</ul>
        </TabsContent>

        <TabsContent value="waiting" className="mt-4">
          {q.data && q.data.waiting.length === 0 ? <p className="p-6 text-center text-muted-foreground">Nenhum caso aguardando a prefeitura.</p> : null}
          <ul className="space-y-3">{q.data?.waiting.map((c) => <CaseRow key={c.id} c={c} />)}</ul>
        </TabsContent>

        <TabsContent value="agent" className="mt-4">
          {q.data && q.data.agent.length === 0 ? <p className="p-6 text-center text-muted-foreground">O agente não está trabalhando em nada agora.</p> : null}
          <ul className="space-y-3">{q.data?.agent.map((c) => <CaseRow key={c.id} c={c} />)}</ul>
        </TabsContent>
      </Tabs>
    </div>
  )
}
