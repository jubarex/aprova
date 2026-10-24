import { cn } from '@/lib/utils'
import type { Municipality } from '@/lib/types'

/* Classes completas (o Tailwind só enxerga strings literais). A cor identifica o cliente; nunca prazo ou estado. */
const SLOT: Record<number, string> = {
  1: 'bg-client-1-bg text-client-1 border-client-1-border',
  2: 'bg-client-2-bg text-client-2 border-client-2-border',
  3: 'bg-client-3-bg text-client-3 border-client-3-border',
}
const slot = (m: Pick<Municipality, 'color_slot'>) => SLOT[m.color_slot] ?? SLOT[3]

/** Sigla quadrada colorida da prefeitura. */
export function ClientMark({ client, className }: { client: Municipality; className?: string }) {
  return (
    <span
      aria-hidden
      className={cn('inline-flex size-6 shrink-0 items-center justify-center rounded-sm border text-[11px] font-semibold', slot(client), className)}
    >
      {client.short}
    </span>
  )
}

/** Selo com sigla e nome por extenso, para cabeçalhos. */
export function ClientSeal({ client, className }: { client: Municipality; className?: string }) {
  return (
    <span className={cn('inline-flex items-center gap-2 rounded-lg border px-2.5 py-1 text-sm font-medium', slot(client), className)}>
      <span className="font-mono text-xs font-semibold">{client.short}</span>
      {client.name}
    </span>
  )
}

/** Linha densa: "VR Vale do Ribeiro". */
export function ClientInline({ client }: { client: Municipality }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
      <ClientMark client={client} className="size-5 text-[10px]" />
      <span className="sr-only">Cliente: </span>
      {client.city}
    </span>
  )
}
