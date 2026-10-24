import { useQuery } from '@tanstack/react-query'
import { FlaskConical, Paperclip, ShieldAlert } from 'lucide-react'
import { api, getToken } from '@/lib/api'
import { poll } from '@/lib/session'
import { fmtDateTime } from '@/lib/format'
import type { Convo } from '@/lib/types'
import { ChannelBadge } from '@/components/domain/badges'
import { cn } from '@/lib/utils'

/** Um caso, vários canais: tudo junto, em ordem de recepção, nunca em abas por canal. */
export function ConversationTab({ caseId }: { caseId: string }) {
  const q = useQuery({ queryKey: ['convo', caseId], queryFn: () => api<Convo>(`/api/cases/${caseId}/conversations`), refetchInterval: poll })
  const msgs = q.data?.messages ?? []
  return (
    <div className="space-y-3">
      <p className="text-xs text-muted-foreground">Pylon, WhatsApp e Portal alimentam o mesmo caso e a mesma rodada. Mensagens entram na ordem de recepção; citações e anexos aparecem com a fonte.</p>
      {msgs.length === 0 ? <p className="text-sm text-muted-foreground">Ainda não há mensagens.</p> : null}
      <ol className="space-y-2">
        {msgs.map((m) => (
          <li key={m.id} className={cn('rounded-xl border p-3 text-sm', m.direction === 'out' ? 'bg-brand-50 border-brand-100' : 'bg-card', m.flagged && 'border-late-border bg-late-bg/40')}>
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <ChannelBadge channel={m.channel} />
              <span className="font-medium">{m.direction === 'out' ? 'Aprova → ' : ''}{m.actor?.name ?? 'Sistema'}</span>
              <span className="text-muted-foreground">{fmtDateTime(m.at)}</span>
              {m.mirror ? <span className="rounded-sm bg-muted px-1.5">espelho no Pylon</span> : null}
              {m.direction === 'in' && !m.substantive && !m.flagged ? <span className="rounded-sm bg-muted px-1.5">não substantiva: não encerra espera</span> : null}
              {m.triage === 'pending' ? <span className="rounded-sm bg-atrisk-bg px-1.5 text-atrisk-fg">em triagem</span> : null}
              {m.direction === 'in' && m.substantive && !m.consolidated ? <span className="rounded-sm bg-st-waiting-bg px-1.5 text-st-waiting-fg">aguardando consolidação</span> : null}
            </div>
            <p className="mt-1 whitespace-pre-wrap">{m.body}</p>
            {m.flagged ? <p className="mt-1 flex items-center gap-1 text-xs font-medium text-late-fg"><ShieldAlert className="size-3.5" aria-hidden />Trecho com instruções ao sistema: tratado como texto, sem efeito.</p> : null}
            {m.attachments.map((a) => (
              <div key={a.id} className="mt-2 rounded-lg border bg-background p-2 text-xs">
                <span className="inline-flex items-center gap-1 font-medium"><Paperclip className="size-3.5" aria-hidden />{a.filename}</span>
                <span className="ml-2 text-muted-foreground">{(a.size / 1024).toFixed(1)} KiB · {a.status === 'needs_review' ? 'precisa de revisão humana' : a.status === 'extracted' ? 'texto extraído' : a.status}</span>
                <a className="ml-2 underline underline-offset-4" href={`/api/attachments/${a.id}`} onClick={(e) => { e.preventDefault(); void download(a.id, a.filename) }}>baixar</a>
              </div>
            ))}
            {m.derived.filter((d) => d.status === 'ok').map((d) => (
              <blockquote key={d.id} className="mt-1 border-l-2 border-brand-400 pl-2 text-xs text-muted-foreground">
                {d.simulated ? <span className="mr-1 inline-flex items-center gap-1 font-medium text-st-sim-fg"><FlaskConical className="size-3" aria-hidden />Extração simulada</span> : <span className="mr-1 font-medium">Texto extraído do arquivo</span>}
                “{d.text.slice(0, 240)}”
              </blockquote>
            ))}
          </li>
        ))}
      </ol>
      {q.data?.decisions.length ? (
        <section aria-label="Decisões humanas" className="rounded-xl border bg-card p-3">
          <h2 className="text-sm font-semibold">Decisões humanas (viram evidência)</h2>
          <ul className="mt-1 space-y-1 text-sm">{q.data.decisions.map((d) => <li key={d.id}><span className="rounded-sm border px-1 text-xs">{d.kind}</span> {d.text}</li>)}</ul>
        </section>
      ) : null}
    </div>
  )
}

async function download(id: string, filename: string) {
  const res = await fetch(`/api/attachments/${id}`, { headers: { 'X-Demo-Token': getToken() ?? '' } })
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
