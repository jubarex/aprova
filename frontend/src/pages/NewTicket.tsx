import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { api, post } from '@/lib/api'
import type { ClientRow } from '@/lib/types'
import { ClientSeal } from '@/components/domain/client'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'

type Proc = { id: string; code: string; name: string; municipality: ClientRow }

export default function NewTicketPage() {
  const [sp] = useSearchParams()
  const nav = useNavigate()
  const qc = useQueryClient()
  const procs = useQuery({ queryKey: ['processes'], queryFn: () => api<Proc[]>('/api/processes') })
  const p = procs.data?.find((x) => x.id === sp.get('process'))
  const [title, setTitle] = useState('')
  const [reply, setReply] = useState('')
  const create = useMutation({
    mutationFn: () => post<{ case_id: string }>('/api/tickets', { process_id: p!.id, title, description: '', initial_reply: reply, start_case: true }),
    onSuccess: (r) => { qc.invalidateQueries(); nav(`/processes/${r.case_id}`) },
    onError: (e: Error) => toast.error(e.message),
  })
  if (!p) return <p className="text-muted-foreground">Escolha o processo em Clientes.</p>
  return (
    <form className="max-w-2xl space-y-4" onSubmit={(e) => { e.preventDefault(); create.mutate() }}>
      <h1>Iniciar validação de {p.code}</h1>
      <ClientSeal client={p.municipality} />
      <p className="text-sm text-muted-foreground">Cole o ticket e a resposta inicial do cliente. O agente separa os pedidos, cita a fonte de cada um e propõe a alteração; nada é aplicado sem as duas aprovações.</p>
      <div className="space-y-1.5"><Label htmlFor="t">Título do ticket</Label><Input id="t" value={title} onChange={(e) => setTitle(e.target.value)} minLength={3} required /></div>
      <div className="space-y-1.5"><Label htmlFor="r">Resposta inicial do cliente</Label><Textarea id="r" rows={8} value={reply} onChange={(e) => setReply(e.target.value)} required /></div>
      <Button type="submit" disabled={create.isPending}>Iniciar validação</Button>
    </form>
  )
}
