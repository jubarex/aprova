# 06 — Testes e métricas

**Objetivo.** Medir sem fabricar resultado.

**Modos separados.** Replay (offline), inferência ao vivo e entrada humana são sempre distinguidos. O cenário F (generalização) só roda com inferência ao vivo; sem credenciais fica `not_run`. Falha durante execução configurada é `failed`, nunca omitida.

**Protocolo de F.** Código, instruções, catálogo, gabarito e limiares congelados antes de revelar as entradas. Três formulários × três execuções, todas reportadas. O agente não acessa o gabarito. Comparação um a um por operação, campo e evidência; duplicata é falso positivo.

**Indicadores.** Cobertura auditável; rodadas até aprovação (únicas, canais e lembretes não multiplicam); precisão/recall de intenções; viabilidade correta; lacunas resolvidas por rodada; repetição de pergunta; tempo de espera e canal útil; intervenção e retomada; efeito indevido (meta zero).

**Regras de cálculo.** Denominador zero é `N/A`, nunca 100%. Seeds e processos não iniciados ficam fora. Pedidos rejeitados/retirados continuam no total. Todo resultado local é `benchmark_local_sintetico`.

**Artefato.** `artifacts/evaluation-<run_id>.json` com commit, adaptador/modelo, hashes de entradas, saídas validadas, contagens, resultado e limitações; segredos removidos.
