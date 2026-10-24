import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { useSession } from '@/lib/session'
import type { Persona } from '@/lib/types'
import { DemoBanner } from '@/components/domain/panels'
import { Button } from '@/components/ui/button'

const KIND: Record<string, string> = { implantador: 'Implantador da Aprova', contato: 'Contato da prefeitura', aprova: 'Aprova' }

export default function LoginPage() {
  const { login } = useSession()
  const q = useQuery({ queryKey: ['personas'], queryFn: () => api<Persona[]>('/api/demo/personas'), retry: false })
  return (
    <div className="min-h-screen">
      <DemoBanner />
      <main className="mx-auto max-w-md space-y-5 p-6">
        <div className="flex items-center gap-2"><span className="flex size-8 items-center justify-center rounded-md bg-primary font-semibold text-primary-foreground" aria-hidden>A</span><span className="text-lg font-semibold tracking-tight">Aprova Command</span></div>
        <div><h1>Escolha uma persona</h1><p className="mt-1 text-sm text-muted-foreground">Esta é uma demonstração com dados sintéticos. A troca de persona não é autenticação de produção.</p></div>
        {q.isError ? <p className="text-late-fg">Não foi possível falar com a API. Confirme que ela está em execução em http://127.0.0.1:8000.</p> : null}
        <ul className="space-y-2">
          {q.data?.map((p) => (
            <li key={p.id}><Button variant="outline" className="h-auto w-full justify-between py-2.5" onClick={() => login(p.id)}><span className="font-medium">{p.name}</span><span className="text-xs text-muted-foreground">{KIND[p.kind] ?? p.kind}</span></Button></li>
          ))}
        </ul>
      </main>
    </div>
  )
}
