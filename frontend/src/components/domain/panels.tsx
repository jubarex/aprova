import type { ReactNode } from 'react'
import { FlaskConical, Info, WifiOff } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { sinceText, WHO } from '@/lib/format'
import { cn } from '@/lib/utils'
import type { Explanation, Runtime } from '@/lib/types'
import { Button } from '@/components/ui/button'
import {
  AlertDialog, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { ClientMark } from './client'
import type { Municipality } from '@/lib/types'

/** Rótulos fixos de honestidade de demonstração (I12): sempre visíveis. */
export function DemoBanner({ className }: { className?: string }) {
  const { data } = useQuery({ queryKey: ['runtime'], queryFn: () => api<Runtime>('/api/demo/runtime'), staleTime: 30_000 })
  return (
    <div role="note" className={cn('flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-st-sim-border bg-st-sim-bg px-4 py-1.5 text-xs text-st-sim-fg', className)}>
      <span className="inline-flex items-center gap-1 font-medium"><FlaskConical className="size-3.5" aria-hidden />{data?.banner ?? 'Ambiente de demonstração — dados sintéticos'}</span>
      <span>{data?.ai_mode ?? 'IA: replay offline'}</span>
      <span>Extração simulada</span>
    </div>
  )
}

/** "Atualizado há X s" e aviso de servidor parado. */
export function StaleIndicator({ updatedAt, error }: { updatedAt: number; error?: boolean }) {
  const secs = Math.max(0, Math.round((Date.now() - updatedAt) / 1000))
  if (error) {
    return <span className="inline-flex items-center gap-1 text-xs font-medium text-late-fg"><WifiOff className="size-3.5" aria-hidden />Sem conexão com o servidor</span>
  }
  return <span className="text-xs text-muted-foreground">{updatedAt ? `Atualizado há ${secs} s` : 'Carregando…'}</span>
}

/** O que está acontecendo e por quê (adendo v2.1 §8). */
export function WhyPanel({ e, title = 'O que está acontecendo' }: { e: Explanation; title?: string }) {
  return (
    <section aria-label={title} className="rounded-xl border bg-card p-4 shadow-xs">
      <h2 className="mb-2 flex items-center gap-1.5 text-[11px] font-semibold tracking-wider text-muted-foreground uppercase"><Info className="size-3.5" aria-hidden />{title}</h2>
      <p className="text-base font-semibold tracking-tight">{e.what}</p>
      <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-3">
        <div><dt className="text-xs font-medium text-muted-foreground">Por quê</dt><dd>{e.why}</dd></div>
        <div><dt className="text-xs font-medium text-muted-foreground">Próximo passo</dt><dd>{e.next}</dd></div>
        <div><dt className="text-xs font-medium text-muted-foreground">Com quem está</dt><dd>{WHO[e.who] ?? e.who} · {sinceText(e.since)}</dd></div>
      </dl>
    </section>
  )
}

/** Bloco "Seu próximo passo": um título, um motivo, um botão. */
export function NextStepCard({ label = 'Seu próximo passo', title, why, deadline, action }: { label?: string; title: string; why: string; deadline?: ReactNode; action: ReactNode }) {
  return (
    <section className="rounded-xl border border-brand-100 bg-brand-50 p-4 shadow-xs">
      <p className="text-[11px] font-semibold tracking-wider text-brand-700 uppercase">{label}</p>
      <h2 className="mt-1 text-lg font-semibold tracking-tight">{title}</h2>
      <p className="mt-1 text-sm text-muted-foreground">{why}</p>
      {deadline ? <div className="mt-2">{deadline}</div> : null}
      <div className="mt-4">{action}</div>
    </section>
  )
}

/** Confirmação de efeito externo: repete cliente, processo, destinatário e versão (adendo v2.1 §3). */
export function ConfirmEffectDialog(props: {
  open: boolean; onOpenChange: (o: boolean) => void; title: string; client: Municipality
  process: string; recipient?: string; version?: string; confirmLabel: string; onConfirm: () => void; pending?: boolean
  destructive?: boolean; children?: ReactNode
}) {
  const { client } = props
  return (
    <AlertDialog open={props.open} onOpenChange={props.onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{props.title}</AlertDialogTitle>
          <AlertDialogDescription>Confira antes de continuar. Esta ação tem efeito fora desta tela.</AlertDialogDescription>
        </AlertDialogHeader>
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 rounded-lg border bg-muted/50 p-3 text-sm">
          <dt className="text-muted-foreground">Cliente</dt><dd className="flex items-center gap-2 font-medium"><ClientMark client={client} />{client.name}</dd>
          <dt className="text-muted-foreground">Processo</dt><dd className="font-medium">{props.process}</dd>
          {props.recipient ? (<><dt className="text-muted-foreground">Destinatário</dt><dd>{props.recipient}</dd></>) : null}
          {props.version ? (<><dt className="text-muted-foreground">Versão</dt><dd className="font-mono text-xs">{props.version}</dd></>) : null}
        </dl>
        {props.children}
        <AlertDialogFooter>
          <Button variant="outline" onClick={() => props.onOpenChange(false)} disabled={props.pending}>Voltar</Button>
          <Button variant={props.destructive ? 'destructive' : 'default'} onClick={props.onConfirm} disabled={props.pending}>{props.pending ? 'Enviando…' : props.confirmLabel}</Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
