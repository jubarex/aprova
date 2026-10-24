import { Bot, CheckCircle2, CircleAlert, CircleCheck, CircleDashed, Clock, Cpu, FlaskConical, Globe, Hand, Hourglass, Loader, MessageCircle, OctagonX, Pause, Sparkles, Ticket } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'
import { deadlineText } from '@/lib/format'
import type { Axis, Deadline } from '@/lib/types'

const base = 'inline-flex w-fit items-center gap-1 rounded-sm border px-1.5 py-0.5 text-xs font-medium whitespace-nowrap'

/** Eixo 1 — prazo. Ícone + texto relativo + data; nunca só cor. */
const DL = {
  ontrack: { cls: 'bg-ontrack-bg text-ontrack-fg border-ontrack-border', Icon: CircleCheck },
  atrisk: { cls: 'bg-atrisk-bg text-atrisk-fg border-atrisk-border', Icon: Clock },
  late: { cls: 'bg-late-bg text-late-fg border-late-border', Icon: CircleAlert },
} as const

export function DeadlineBadge({ deadline, className }: { deadline: Deadline; className?: string }) {
  const { cls, Icon } = DL[deadline.status]
  return (
    <span className={cn(base, cls, className)}>
      <Icon className="size-3.5" aria-hidden />
      {deadlineText(deadline)}
    </span>
  )
}

/** Eixo 2 — estado do caso. */
const ST: Record<Axis | 'idle' | 'sim', { cls: string; Icon: LucideIcon; label: string }> = {
  blocked: { cls: 'bg-st-blocked-bg text-st-blocked-fg border-st-blocked-border', Icon: Hand, label: 'Sua ação' },
  waiting: { cls: 'bg-st-waiting-bg text-st-waiting-fg border-st-waiting-border', Icon: Hourglass, label: 'Aguardando prefeitura' },
  running: { cls: 'bg-st-running-bg text-st-running-fg border-st-running-border', Icon: Loader, label: 'Em andamento' },
  paused: { cls: 'bg-st-paused-bg text-st-paused-fg border-st-paused-border', Icon: Pause, label: 'Pausado' },
  failed: { cls: 'bg-st-failed-bg text-st-failed-fg border-st-failed-border', Icon: OctagonX, label: 'Falha' },
  completed: { cls: 'bg-st-completed-bg text-st-completed-fg border-st-completed-border', Icon: CheckCircle2, label: 'Concluído' },
  idle: { cls: 'bg-st-idle-bg text-st-idle-fg border-st-idle-border', Icon: CircleDashed, label: 'Não iniciado' },
  sim: { cls: 'bg-st-sim-bg text-st-sim-fg border-st-sim-border', Icon: FlaskConical, label: 'Simulado' },
}

export function StateBadge({ axis, label, className }: { axis: Axis | 'idle' | 'sim'; label?: string; className?: string }) {
  const { cls, Icon, label: def } = ST[axis]
  return (
    <span className={cn(base, cls, className)}>
      <Icon className="size-3.5" aria-hidden />
      {label ?? def}
    </span>
  )
}

const CH = {
  pylon: { Icon: Ticket, cls: 'text-ch-pylon', label: 'Pylon' },
  whatsapp: { Icon: MessageCircle, cls: 'text-ch-whatsapp', label: 'WhatsApp' },
  portal: { Icon: Globe, cls: 'text-ch-portal', label: 'Portal' },
  system: { Icon: Cpu, cls: 'text-ch-system', label: 'Sistema' },
  agent: { Icon: Sparkles, cls: 'text-ch-agent', label: 'Agente' },
  command: { Icon: Bot, cls: 'text-ch-system', label: 'Aprova Command' },
} as const

export function ChannelBadge({ channel }: { channel: keyof typeof CH }) {
  const { Icon, cls, label } = CH[channel] ?? CH.system
  return (
    <span className={cn('inline-flex items-center gap-1 text-xs font-medium', cls)}>
      <Icon className="size-3.5" aria-hidden />
      {label}
    </span>
  )
}
