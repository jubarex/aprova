import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { ArrowLeft, CircleCheck, Info, Paperclip, Sparkles } from 'lucide-react'
import { api, postForm } from '@/lib/api'
import type { PortalQuestion } from '@/lib/types'
import { DeadlineBadge } from '@/components/domain/badges'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { Textarea } from '@/components/ui/textarea'
import {
  AlertDialog, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { post } from '@/lib/api'

export default function PortalItemPage() {
  const { id = '' } = useParams()
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['portal-item', id], queryFn: () => api<PortalQuestion>(`/api/portal/items/${id}`), retry: false })
  const [choice, setChoice] = useState('')
  const [text, setText] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [done, setDone] = useState<null | 'answered' | 'referred'>(null)
  const [refer, setRefer] = useState(false)
  const [who, setWho] = useState({ name: '', sector: '', alias: '' })

  const answer = useMutation({
    mutationFn: (kind: 'answer' | 'not_applicable') => {
      const f = new FormData()
      f.set('kind', kind)
      f.set('text', kind === 'answer' ? [choice, text].filter(Boolean).join(choice && text ? '. ' : '') : '')
      if (file) f.append('files', file)
      return postForm(`/api/portal/items/${id}/answer`, f)
    },
    onSuccess: () => { setDone('answered'); qc.invalidateQueries() },
    onError: (e: Error) => toast.error(e.message),
  })
  const referral = useMutation({
    mutationFn: () => post(`/api/portal/items/${id}/refer`, who),
    onSuccess: () => { setRefer(false); setDone('referred'); qc.invalidateQueries() },
    onError: (e: Error) => toast.error(e.message),
  })

  if (q.isLoading) return <Skeleton className="h-64" />
  if (q.isError || !q.data) {
    return <p className="rounded-xl border bg-card p-4 text-sm">Esta pergunta já foi respondida ou não está mais aberta. <Link className="underline" to="/portal">Voltar ao início</Link></p>
  }
  const it = q.data
  if (done) {
    return (
      <section className="space-y-4 rounded-xl border bg-card p-5" aria-live="polite">
        <p className="flex items-center gap-2 text-lg font-semibold"><CircleCheck className="size-6 text-ontrack" aria-hidden />Recebido</p>
        {done === 'answered' ? (
          <p className="text-sm"><b>O que acontece agora:</b> a equipe da Aprova usa a sua resposta para ajustar o formulário. Se ainda faltar algo, você recebe uma nova pergunta apenas com o que falta. Sua resposta também fica registrada no ticket.</p>
        ) : (
          <p className="text-sm"><b>O que acontece agora:</b> a Aprova confirma a indicação e só então fala com essa pessoa, apenas sobre este assunto. Você não precisa fazer mais nada.</p>
        )}
        <Button className="h-11 w-full" render={<Link to="/portal" />}>Ver o que mais falta</Button>
      </section>
    )
  }
  const quick = it.answer_kind === 'yes_no' ? ['Sim', 'Não'] : it.answer_kind === 'choose_options' ? it.options : []
  const canSend = (choice || text.trim() || file) && !answer.isPending

  return (
    <div className="space-y-5">
      <Link to="/portal" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"><ArrowLeft className="size-4" aria-hidden />Início</Link>
      <div>
        <p className="text-xs text-muted-foreground"><span className="font-mono">{it.process.code}</span> · {it.process.name} · pergunta {it.position} de {it.total}</p>
        <h1 className="mt-1 text-2xl">{it.question}</h1>
        <div className="mt-2"><DeadlineBadge deadline={it.deadline} /></div>
      </div>
      <section className="flex gap-2 rounded-xl border border-brand-100 bg-brand-50 p-3 text-sm" aria-label="Por que perguntamos">
        <Info className="mt-0.5 size-4 shrink-0 text-brand-600" aria-hidden />
        <p><b>Por que perguntamos:</b> {it.why || 'Sem essa informação a alteração do formulário não pode seguir.'}</p>
      </section>

      <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); answer.mutate('answer') }}>
        {quick.length ? (
          <fieldset className="space-y-2"><legend className="mb-1 text-sm font-medium">Escolha uma resposta</legend>
            {quick.map((o) => (
              <label key={o} className="flex min-h-11 cursor-pointer items-center gap-3 rounded-xl border bg-card px-3 text-sm has-[:checked]:border-brand-400 has-[:checked]:bg-brand-50">
                <input type="radio" name="choice" value={o} checked={choice === o} onChange={() => setChoice(o)} className="size-4" />{o}
              </label>
            ))}
          </fieldset>
        ) : null}
        <div className="space-y-1.5">
          <Label htmlFor="resp">{quick.length ? 'Quer acrescentar algo? (opcional)' : it.answer_kind === 'number' ? 'Sua resposta (número)' : 'Sua resposta'}</Label>
          <Textarea id="resp" rows={it.answer_kind === 'number' ? 1 : 4} value={text} onChange={(e) => setText(e.target.value)} inputMode={it.answer_kind === 'number' ? 'numeric' : undefined} />
          {it.demo_hint ? (
            <Button type="button" variant="outline" size="sm" onClick={() => { setText(it.demo_hint ?? ''); setChoice('') }}><Sparkles />Usar a resposta do roteiro (demonstração)</Button>
          ) : null}
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="arq" className="flex items-center gap-1"><Paperclip className="size-4" aria-hidden />Anexar um documento (opcional)</Label>
          <Input id="arq" type="file" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        </div>
        <Button type="submit" size="lg" className="h-11 w-full text-base" disabled={!canSend}>{answer.isPending ? 'Enviando…' : 'Enviar resposta'}</Button>
      </form>

      <div className="space-y-2 border-t pt-4">
        <Button variant="outline" className="h-11 w-full" onClick={() => setRefer(true)}>Não sei. Indicar quem sabe</Button>
        <Button variant="ghost" className="h-11 w-full" onClick={() => answer.mutate('not_applicable')} disabled={answer.isPending}>Não se aplica</Button>
      </div>

      <AlertDialog open={refer} onOpenChange={setRefer}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Quem sabe responder?</AlertDialogTitle>
            <AlertDialogDescription>Só esta pergunta será encaminhada, e só depois de a equipe da Aprova confirmar a indicação.</AlertDialogDescription>
          </AlertDialogHeader>
          <div className="space-y-2">
            <div className="space-y-1"><Label htmlFor="w1">Nome</Label><Input id="w1" value={who.name} onChange={(e) => setWho({ ...who, name: e.target.value })} /></div>
            <div className="space-y-1"><Label htmlFor="w2">Setor</Label><Input id="w2" value={who.sector} onChange={(e) => setWho({ ...who, sector: e.target.value })} /></div>
          </div>
          <AlertDialogFooter>
            <Button variant="outline" onClick={() => setRefer(false)}>Voltar</Button>
            <Button disabled={who.name.trim().length < 2 || referral.isPending} onClick={() => referral.mutate()}>Indicar</Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
