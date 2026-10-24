import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { Gavel } from 'lucide-react'
import { post } from '@/lib/api'
import type { CaseDetail } from '@/lib/types'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'

const KINDS = [
  { id: 'resolve_conflict', label: 'Resolver conflito entre fontes' },
  { id: 'provide_answer', label: 'Registrar resposta / recomendação' },
  { id: 'fix_interpretation', label: 'Corrigir interpretação' },
]

/** Decisão humana: vira evidência, resolve a intervenção e retoma o caso (nunca aprova nada por si). */
export function DecisionPanel({ c }: { c: CaseDetail }) {
  const qc = useQueryClient()
  const open = c.interventions.filter((i) => i.status === 'open')
  const [kind, setKind] = useState(open.some((i) => i.code === 'LACUNA_DISPUTADA') ? 'resolve_conflict' : 'provide_answer')
  const [text, setText] = useState('')
  const decide = useMutation({
    mutationFn: () => post(`/api/cases/${c.id}/decisions`, { kind, text, intervention_id: open[0]?.id, expected_case_version: c.version }),
    onSuccess: () => { toast.success('Decisão registrada como evidência. O caso foi retomado.'); setText(''); qc.invalidateQueries() },
    onError: (e: Error) => { toast.error(e.message); qc.invalidateQueries() },
  })
  if (open.length === 0) return null
  return (
    <section className="rounded-xl border border-st-blocked-border bg-st-blocked-bg/50 p-4" aria-label="Decisão necessária">
      <h2 className="flex items-center gap-1.5 text-base font-semibold"><Gavel className="size-4" aria-hidden />Decisão necessária</h2>
      <ul className="mt-1 list-disc pl-5 text-sm">{open.map((i) => <li key={i.id}><b>{i.reason}</b>{i.needed ? ` — ${i.needed}` : ''}</li>)}</ul>
      <form className="mt-3 space-y-2" onSubmit={(e) => { e.preventDefault(); decide.mutate() }}>
        <select aria-label="Tipo de decisão" className="h-9 w-full rounded-md border bg-card px-2 text-sm sm:w-80" value={kind} onChange={(e) => setKind(e.target.value)}>
          {KINDS.map((k) => <option key={k.id} value={k.id}>{k.label}</option>)}
        </select>
        <Textarea aria-label="Decisão e justificativa" rows={3} value={text} onChange={(e) => setText(e.target.value)} placeholder="Escreva a decisão e a justificativa. O texto vira a fonte citada pelo agente." required minLength={3} />
        <Button type="submit" disabled={decide.isPending || text.trim().length < 3}>Registrar decisão e retomar</Button>
      </form>
    </section>
  )
}
