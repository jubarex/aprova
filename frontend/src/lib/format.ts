const dm = new Intl.DateTimeFormat('pt-BR', { day: '2-digit', month: '2-digit' })
const dmHm = new Intl.DateTimeFormat('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })

export const fmtDate = (iso: string | null | undefined) => (iso ? dm.format(new Date(iso)) : '—')
export const fmtDateTime = (iso: string | null | undefined) => (iso ? dmHm.format(new Date(iso)) : '—')

/** Prazo relativo + absoluto (direcionamento §9): "Atrasado 2 dias · 22/10". */
export function deadlineText(d: { status: string; due_at: string | null; days: number | null }): string {
  if (!d.due_at || d.days === null) return 'Sem prazo'
  const abs = fmtDate(d.due_at)
  if (d.status === 'late') return `Atrasado ${Math.abs(d.days)} ${Math.abs(d.days) === 1 ? 'dia' : 'dias'} · ${abs}`
  if (d.days === 0) return `Vence hoje · ${abs}`
  return `Vence em ${d.days} ${d.days === 1 ? 'dia' : 'dias'} · ${abs}`
}

export function sinceText(iso: string, now = Date.now()): string {
  const min = Math.max(0, Math.round((now - new Date(iso).getTime()) / 60000))
  if (min < 1) return 'agora'
  if (min < 60) return `há ${min} min`
  const h = Math.round(min / 60)
  if (h < 24) return `há ${h} h`
  const d = Math.round(h / 24)
  return `há ${d} ${d === 1 ? 'dia' : 'dias'}`
}

export const WHO: Record<string, string> = {
  implantador: 'Com você', prefeitura: 'Com a prefeitura', agente: 'Com o agente', sistema: 'Com o sistema', nenhum: 'Concluído',
}
