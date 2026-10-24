import { useQuery } from '@tanstack/react-query'
import { CircleCheck, CircleX } from 'lucide-react'
import { api } from '@/lib/api'

type Entry = { available: boolean; inputs?: string[]; approval?: string; reason?: string }

/** Templates e capacidades: o que o simulador de formulários consegue aplicar (e o que não consegue). */
export default function CatalogPage() {
  const q = useQuery({ queryKey: ['runtime'], queryFn: () => api<{ catalog: Record<string, Entry> }>('/api/demo/runtime') })
  const rows = Object.entries(q.data?.catalog ?? {})
  return (
    <div className="space-y-5">
      <div><h1>Templates e capacidades</h1>
        <p className="mt-1 text-muted-foreground">Catálogo de operações do motor de formulários <b>simulado</b>. Nova etapa de fluxo ou regra fora desta linguagem exige revisão de produto. Não descreve a Aprova real.</p></div>
      <ul className="divide-y rounded-xl border bg-card">
        {rows.map(([op, e]) => (
          <li key={op} className="flex flex-wrap items-center gap-3 px-4 py-3 text-sm">
            {e.available ? <CircleCheck className="size-4 text-ontrack" aria-label="disponível" /> : <CircleX className="size-4 text-late" aria-label="indisponível" />}
            <span className="w-56 font-mono text-xs">{op}</span>
            <span className="min-w-48 flex-1 text-muted-foreground">{e.available ? `Entradas: ${e.inputs?.join(', ')} · aprovação ${e.approval}` : e.reason}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
