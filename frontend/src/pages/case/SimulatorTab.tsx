import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { FlaskConical, Play } from 'lucide-react'
import { api, post, postForm } from '@/lib/api'
import type { CaseDetail, RoundRow, Scenario } from '@/lib/types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'

type Persona = { id: string; name: string; kind: string; municipality_id: string | null }

export function SimulatorTab({ c }: { c: CaseDetail }) {
  const qc = useQueryClient()
  const sc = useQuery({ queryKey: ['scenarios'], queryFn: () => api<Scenario[]>('/api/demo/scenarios') })
  const people = useQuery({ queryKey: ['personas'], queryFn: () => api<Persona[]>('/api/demo/personas') })
  const rounds = useQuery({ queryKey: ['rounds', c.id], queryFn: () => api<RoundRow[]>(`/api/cases/${c.id}/rounds`) })
  const faults = useQuery({ queryKey: ['faults'], queryFn: () => api<Record<string, string>>('/api/demo/faults') })
  const scenario = sc.data?.find((s) => s.process_id === c.process.id)
  const contacts = (people.data ?? []).filter((p) => p.municipality_id === c.municipality.id)

  const [actor, setActor] = useState('')
  const [channel, setChannel] = useState('whatsapp')
  const [text, setText] = useState('')
  const [replyTo, setReplyTo] = useState('latest')
  const [file, setFile] = useState<File | null>(null)
  const [sidecar, setSidecar] = useState('')
  const [key, setKey] = useState('')

  const step = useMutation({
    mutationFn: (id: string) => api(`/api/cases/${c.id}/script/${id}`, { method: 'POST', body: {} }),
    onSuccess: () => { toast.success('Passo do roteiro executado.'); qc.invalidateQueries() },
    onError: (e: Error) => toast.error(e.message),
  })
  const send = useMutation({
    mutationFn: () => {
      const f = new FormData()
      f.set('actor_id', actor || contacts[0]?.id || '')
      f.set('channel', channel)
      f.set('text', text)
      if (key) f.set('external_key', key)
      const target = replyTo === 'latest' ? rounds.data?.at(-1)?.id : replyTo === 'none' ? undefined : replyTo
      if (target) f.set('reply_to_round_id', target)
      if (file) f.append('files', file)
      if (sidecar) f.set('sidecar_text', sidecar)
      return postForm<{ substantive: boolean; triage: string | null; flagged: boolean; created: boolean }>(`/api/cases/${c.id}/messages`, f)
    },
    onSuccess: (r) => {
      toast.success(r.flagged ? 'Mensagem marcada como suspeita: sem efeito.' : r.triage ? 'Sem rodada inequívoca: foi para a triagem.' : r.substantive ? 'Mensagem recebida.' : 'Recebida, mas não substantiva: não encerra a espera.')
      setText(''); setFile(null); setSidecar(''); setKey(''); qc.invalidateQueries()
    },
    onError: (e: Error) => toast.error(e.message),
  })
  const fault = useMutation({
    mutationFn: ({ ch, mode }: { ch: string; mode: string | null }) => post('/api/demo/faults', { channel: ch, mode }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['faults'] }),
  })

  return (
    <div className="space-y-5">
      <p className="flex items-center gap-1.5 rounded-lg bg-st-sim-bg px-3 py-2 text-xs text-st-sim-fg"><FlaskConical className="size-3.5" aria-hidden />Simuladores: modo demonstração. Os canais reais (Pylon, WhatsApp) não são acessados.</p>

      <section className="rounded-xl border bg-card p-4" aria-label="Roteiro">
        <h2 className="text-base font-semibold">Roteiro do cenário {scenario ? scenario.title : '(este processo não tem roteiro)'}</h2>
        {scenario ? <p className="text-xs text-muted-foreground">{scenario.description}</p> : null}
        <ol className="mt-3 space-y-2">
          {scenario?.steps.map((s, i) => (
            <li key={s.id} className="flex flex-wrap items-center gap-2 rounded-lg border p-2 text-sm">
              <span className="font-mono text-xs text-muted-foreground">{i + 1}</span>
              <span className="min-w-48 flex-1">{s.label}{s.text ? <em className="block text-xs text-muted-foreground">“{s.text.slice(0, 110)}{s.text.length > 110 ? '…' : ''}”</em> : null}</span>
              <Button size="sm" variant="outline" disabled={step.isPending} onClick={() => step.mutate(s.id)}><Play />Executar</Button>
            </li>
          ))}
        </ol>
      </section>

      <section className="rounded-xl border bg-card p-4" aria-label="Enviar mensagem">
        <h2 className="text-base font-semibold">Enviar mensagem como contato</h2>
        <p className="text-xs text-muted-foreground">Texto fora do roteiro não tem gravação no modo replay e resulta em REPLAY_MISS na análise (nada é inventado).</p>
        <form className="mt-3 grid gap-3 sm:grid-cols-2" onSubmit={(e) => { e.preventDefault(); send.mutate() }}>
          <div className="space-y-1"><Label htmlFor="sim-actor">Quem escreve</Label>
            <select id="sim-actor" className="h-9 w-full rounded-md border bg-card px-2 text-sm" value={actor} onChange={(e) => setActor(e.target.value)}>
              {contacts.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select></div>
          <div className="space-y-1"><Label htmlFor="sim-ch">Canal</Label>
            <select id="sim-ch" className="h-9 w-full rounded-md border bg-card px-2 text-sm" value={channel} onChange={(e) => setChannel(e.target.value)}>
              <option value="whatsapp">WhatsApp</option><option value="portal">Portal</option><option value="pylon">Pylon (comentário no ticket)</option>
            </select></div>
          <div className="space-y-1 sm:col-span-2"><Label htmlFor="sim-text">Mensagem</Label><Textarea id="sim-text" rows={3} value={text} onChange={(e) => setText(e.target.value)} required /></div>
          <div className="space-y-1"><Label htmlFor="sim-reply">Em resposta a</Label>
            <select id="sim-reply" className="h-9 w-full rounded-md border bg-card px-2 text-sm" value={replyTo} onChange={(e) => setReplyTo(e.target.value)}>
              <option value="latest">Última rodada</option><option value="none">Nenhuma (sem correlação: triagem)</option>
              {rounds.data?.map((r) => <option key={r.id} value={r.id}>Rodada {r.seq}</option>)}
            </select></div>
          <div className="space-y-1"><Label htmlFor="sim-key">Identidade externa (repetir = duplicata)</Label><Input id="sim-key" value={key} onChange={(e) => setKey(e.target.value)} placeholder="ex.: wa-1001" /></div>
          <div className="space-y-1"><Label htmlFor="sim-file">Anexo (TXT, MD, JSON, PDF, PNG, JPEG, WAV, MP3)</Label><Input id="sim-file" type="file" onChange={(e) => setFile(e.target.files?.[0] ?? null)} /></div>
          <div className="space-y-1"><Label htmlFor="sim-side">Transcrição/OCR simulado (áudio e imagem)</Label><Input id="sim-side" value={sidecar} onChange={(e) => setSidecar(e.target.value)} /></div>
          <div className="sm:col-span-2"><Button type="submit" disabled={send.isPending}>Enviar</Button></div>
        </form>
      </section>

      <section className="rounded-xl border bg-card p-4" aria-label="Falhas de canal">
        <h2 className="text-base font-semibold">Falha de envio</h2>
        <p className="text-xs text-muted-foreground">Derruba um canal para a próxima entrega: o sistema tenta 3 vezes (1 s e 5 s), mantém a espera nos canais entregues e abre intervenção só se todos falharem.</p>
        <div className="mt-2 flex flex-wrap gap-2">
          {['whatsapp', 'portal', 'pylon'].map((ch) => {
            const down = faults.data?.[ch] === 'down'
            return <Button key={ch} size="sm" variant={down ? 'destructive' : 'outline'} onClick={() => fault.mutate({ ch, mode: down ? null : 'down' })}>{ch}: {down ? 'fora do ar (clique para restaurar)' : 'normal'}</Button>
          })}
        </div>
      </section>
    </div>
  )
}
