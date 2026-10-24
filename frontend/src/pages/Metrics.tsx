import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { poll, useSession } from '@/lib/session'
import type { EvalReport, Metrics } from '@/lib/types'
import { StateBadge } from '@/components/domain/badges'
import { Skeleton } from '@/components/ui/skeleton'

const na = (v: number | null | undefined, fmt: (n: number) => string = (n) => String(n)) => (v === null || v === undefined ? 'N/A' : fmt(v))

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-xl border bg-card p-4 shadow-xs">
      <p className="text-xs font-medium text-muted-foreground">{label}</p>
      <p className="mt-1 font-mono text-2xl font-semibold tracking-tight">{value}</p>
      {hint ? <p className="mt-1 text-xs text-muted-foreground">{hint}</p> : null}
    </div>
  )
}

export default function MetricsPage() {
  const { client } = useSession()
  const m = useQuery({ queryKey: ['metrics', client], queryFn: () => api<Metrics>(`/api/command/metrics${client ? `?client=${client}` : ''}`), refetchInterval: poll })
  const ev = useQuery({ queryKey: ['evals'], queryFn: () => api<{ offline: EvalReport; generalization: EvalReport }>('/api/evaluations/latest') })
  const d = m.data
  return (
    <div className="space-y-6">
      <div><h1>Métricas</h1>
        <p className="mt-1 text-muted-foreground">Benchmark local com dados sintéticos. Não mede impacto em prefeituras reais. Denominador zero aparece como N/A, e processos não iniciados ficam fora das contagens de sucesso.</p></div>
      {m.isLoading ? <Skeleton className="h-40" /> : null}
      {d ? (<>
        <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4" aria-label="Indicadores">
          <Stat label="Cobertura auditável" value={na(d.cobertura_auditavel.valor, (n) => `${Math.round(n * 100)}%`)} hint={`${d.cobertura_auditavel.num} de ${d.cobertura_auditavel.den} solicitações aceitas, com fonte, teste e dupla aprovação`} />
          <Stat label="Rodadas até a aprovação" value={na(d.rodadas_ate_aprovacao.media)} hint={`média em ${d.rodadas_ate_aprovacao.casos} caso(s); canais e lembretes não contam`} />
          <Stat label="Lacunas resolvidas por rodada" value={na(d.lacunas_resolvidas_por_rodada.valor)} hint={`${d.lacunas_resolvidas_por_rodada.lacunas} lacunas em ${d.lacunas_resolvidas_por_rodada.rodadas} rodada(s)`} />
          <Stat label="Espera até a 1ª resposta útil" value={na(d.espera_horas.media, (n) => `${n} h`)} hint={`${d.espera_horas.n} rodada(s) respondida(s)`} />
          <Stat label="Intervenções" value={String(d.intervencoes.total)} hint={`${d.intervencoes.abertas} aberta(s)`} />
          <Stat label="Retomadas" value={String(d.retomadas.total)} />
          <Stat label="Efeito indevido" value={String(d.efeito_indevido.valor)} hint="Ações proibidas executadas (meta: zero)" />
          <Stat label="Processos" value={`${d.processes.com_caso}/${d.processes.total}`} hint={`${d.processes.nao_iniciados} não iniciados, fora das métricas`} />
        </section>

        <section className="rounded-xl border bg-card p-4" aria-label="Solicitações">
          <h2 className="text-base font-semibold">Solicitações</h2>
          <p className="text-xs text-muted-foreground">Rejeitadas e retiradas continuam no total, para a taxa não melhorar por exclusão.</p>
          <dl className="mt-2 grid grid-cols-2 gap-3 text-sm sm:grid-cols-5">
            {Object.entries(d.solicitacoes).map(([k, v]) => <div key={k}><dt className="text-xs capitalize text-muted-foreground">{k}</dt><dd className="font-mono text-lg font-semibold">{v}</dd></div>)}
          </dl>
        </section>

        <section className="rounded-xl border bg-card p-4" aria-label="Agrupamento">
          <h2 className="text-base font-semibold">Agrupar em rodadas vs. um item por rodada</h2>
          <p className="text-xs text-muted-foreground">Comparação roteirizada, com o mesmo pacote de lacunas por caso. Não é experimento com prefeitura.</p>
          {d.baseline_roteirizado.length === 0 ? <p className="mt-2 text-sm text-muted-foreground">N/A: nenhum caso teve lacunas.</p> : (
            <table className="mt-2 w-full text-sm"><thead><tr className="text-left text-xs text-muted-foreground"><th className="py-1 font-medium">Caso</th><th className="font-medium">Um item por rodada</th><th className="font-medium">Agrupado (este sistema)</th></tr></thead>
              <tbody>{d.baseline_roteirizado.map((b) => <tr key={b.case_id} className="border-t"><td className="py-1 font-mono text-xs">{b.case_id}</td><td className="font-mono">{b.um_item_por_rodada}</td><td className="font-mono">{b.agrupado}</td></tr>)}</tbody></table>
          )}
        </section>

        <section className="rounded-xl border bg-card p-4" aria-label="Modos">
          <h2 className="text-base font-semibold">Origem das análises</h2>
          <p className="text-xs text-muted-foreground">Replay, inferência ao vivo e entrada humana são sempre separados.</p>
          <ul className="mt-2 flex flex-wrap gap-4 text-sm">
            {Object.entries(d.modos.ia).map(([k, v]) => <li key={k}><span className="font-mono">{k}</span>: {v}</li>)}
            <li>entrada humana: {d.modos.entrada_humana}</li>
          </ul>
          {Object.keys(d.intervencoes.por_motivo).length ? <p className="mt-2 text-xs text-muted-foreground">Intervenções por motivo: {Object.entries(d.intervencoes.por_motivo).map(([k, v]) => `${k} (${v})`).join(', ')}</p> : null}
        </section>
      </>) : null}

      <section className="rounded-xl border bg-card p-4" aria-label="Avaliação">
        <h2 className="text-base font-semibold">Avaliação</h2>
        <div className="mt-2 grid gap-3 sm:grid-cols-2">
          <div className="rounded-lg border p-3 text-sm">
            <p className="font-medium">Gate offline (replay identificado)</p>
            {ev.data?.offline ? (<>
              <p className="mt-1"><StateBadge axis={ev.data.offline.result === 'passed' ? 'completed' : 'failed'} label={ev.data.offline.result === 'passed' ? 'Aprovado' : 'Reprovado'} /></p>
              <p className="mt-1 text-xs text-muted-foreground">Cenários: {ev.data.offline.scenarios?.map((s) => `${s.scenario} ${s.passed ? 'ok' : 'falhou'}`).join(' · ')}. Commit {ev.data.offline.commit}.</p>
            </>) : <p className="mt-1 text-xs text-muted-foreground">Ainda não executado. Rode <code>python -m app.evaluation --gate offline</code>.</p>}
          </div>
          <div className="rounded-lg border p-3 text-sm">
            <p className="font-medium">Cenário F — generalização (inferência ao vivo)</p>
            {ev.data?.generalization ? (<>
              <p className="mt-1"><StateBadge axis={ev.data.generalization.result === 'passed' ? 'completed' : ev.data.generalization.result === 'not_run' ? 'idle' : 'failed'} label={ev.data.generalization.result === 'passed' ? 'Aprovado' : ev.data.generalization.result === 'not_run' ? 'Não executado' : 'Reprovado'} /></p>
              <p className="mt-1 text-xs text-muted-foreground">{ev.data.generalization.reason}</p>
            </>) : <p className="mt-1 text-xs text-muted-foreground">Não executado: exige credenciais de um modelo. Nenhum resultado é fabricado.</p>}
          </div>
        </div>
      </section>
    </div>
  )
}
