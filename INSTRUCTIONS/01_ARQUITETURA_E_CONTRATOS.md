# 01 — Arquitetura e contratos

**Objetivo.** Definir o formato fechado das ações propostas pelo agente.

**Envelope (`AgentEnvelope`).** `schema_version`, `case_id`, `expected_case_version`, `change_requests` (lista de pedidos com citação `[start,end)` em pontos de código Unicode) e `change_set` (operações do catálogo + testes). Campos extras são rejeitados.

**Validação no backend.**
1. Citação deve coincidir exatamente com o texto persistido da fonte.
2. Operações pertencem ao catálogo (`04`) e são aplicadas em cópia da base; o resultado inteiro é validado.
3. Cada operação referencia ao menos um pedido (fonte). Sem fonte, a proposta é rejeitada.
4. Versão esperada do caso diferente da atual => proposta obsoleta, descartada.

**Ferramentas permitidas (proposta):** `propose_change_requests`, `propose_change_set`. Nenhuma ferramenta toca o banco, envia mensagem, aprova ou aplica.

**Metadados registrados:** adaptador, fixture/modelo, hash da entrada, id e hash das instruções carregadas.

**Aceite.** Proposta com referência inválida não produz efeito parcial.
