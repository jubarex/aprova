# Aprova Command — Adendo v2.1: Portal da prefeitura, "Hoje" do implantador e shadcn/ui

**Versão:** 2.1 (adendo)  
**Data:** 24/10/2026  
**Complementa:** [Plano consolidado de implementação v2](<Aprova Command — Plano consolidado de implementação v2.md>) e [Direcionamento visual](<direcionamento visual.md>).  
**Idioma:** português do Brasil.

Este adendo acrescenta ao plano v2 quatro decisões de produto: interface em shadcn/ui, cliente sempre explícito, a tela "Hoje" como ponto de partida do implantador e o Portal da prefeitura como terceiro canal. Também descreve a jornada do cliente no primeiro dia e supõe o que falta para o uso diário do implantador. Onde este adendo e o plano v2 divergem, vale o adendo. Tudo o mais do v2 continua valendo, inclusive os invariantes I01–I14, que este documento não flexibiliza.

**Situação:** especificação. Nada deste adendo está implementado.

## 1. Motivo e resultado esperado

O plano v2 define um motor confiável (casos, rodadas, evidências, aprovações, aplicação), mas deixa três perguntas operacionais sem resposta clara na interface:

1. **De qual cliente estamos falando?** O implantador atende quatro prefeituras ao mesmo tempo, cerca de 400 processos em cerca de 40 dias úteis (`desafios.txt`). Confundir um cliente com outro é o erro mais caro.
2. **O que eu tenho que fazer hoje?** A tela inicial precisa ser uma lista de ações, não um mapa nem um painel de métricas.
3. **Onde o cliente responde?** Hoje a prefeitura responde pelo Pylon ou pelo WhatsApp, e a informação se espalha. O cliente precisa de um lugar próprio, simples, que diga o que está pendente com ele e por quê, sem obrigá-lo a abandonar o WhatsApp.

Resultado esperado:

- Implantador abre o sistema e vê, por cliente, as ações do dia com prazo e motivo.
- Cliente abre um link no celular e vê "Seu próximo passo", responde e entende o que acontece em seguida.
- Pylon, WhatsApp e Portal alimentam **o mesmo caso e a mesma rodada**. O Pylon continua recebendo o histórico por espelhamento, o que permite substituir o portal do usePylon de forma gradual.

## 2. Alterações no plano v2

| Seção v2 | Alteração |
|---|---|
| §1 Fluxo principal | "respostas consolidadas de Pylon/WhatsApp simulados" passa a "respostas consolidadas de Pylon/WhatsApp simulados e do Portal da prefeitura" |
| §2.3 Fora de escopo | Continua sem integração real com o Pylon. O adaptador simulado passa a seguir o modelo de conta, ticket, comentário público/interno e webhook do Pylon (seção 7), para permitir troca futura por integração real |
| §3 Invariantes | I05 estendido: "Pylon, WhatsApp e Portal alimentam o mesmo caso e a mesma rodada". Novos I15–I19 (seção 10) |
| §4.1 Stack frontend | React + TypeScript + Vite + **Tailwind CSS v4 + shadcn/ui (Radix) + lucide-react + TanStack Query + React Router + react-hook-form/zod + sonner + Geist via @fontsource-variable**. As variáveis de tema continuam, agora no formato do shadcn (seção 12) |
| §5.1 Entidades | `Secretariat`, prazos de implantação/processo, `PortalAccess`, `ContactOnboarding`, `ResponsibilityClaim`, `ExternalRef`, `DigestDelivery` (seção 9) |
| §8 Rodadas e canais | Canal `portal`, resumo diário por contato, orçamento de atenção, revisão da primeira mensagem e espelhamento no Pylon (seções 5–8) |
| §13.2 Rotas | `/api/today`, `/api/inbox`, `/api/clients/*`, `/api/schedule`, `/api/cases/{id}/explanation` e `/api/portal/*` (seção 11) |
| §14.1 Navegação | `/` passa a ser **Hoje**. Navegação: Hoje · Caixa de entrada · Clientes · Cronograma · Processo · Portal. O mapa vira a grade de processos por secretaria dentro de Clientes |
| §14.2 Mapa | Sem metáfora militar no texto da interface (direcionamento §9). "Soldados" viram cartões compactos de processo com estado, prazo e bloqueio |
| §15 Cenários | Novos cenários I, J e K e regressões T17–T22 (seção 14) |
| §17 Fatias | Itens novos distribuídos nas fatias 1, 2, 3 e 5, com corte do hackathon (seção 13) |

## 3. O cliente está sempre explícito

Regra de produto: **nenhuma informação de caso, tarefa, mensagem ou contato aparece sem a prefeitura a que pertence**, mesmo quando um filtro já restringe a visão.

| Lugar | Como o cliente aparece |
|---|---|
| Barra lateral | Seletor de cliente: "Todos os clientes" ou uma prefeitura, com contagem de ações do dia por cliente |
| Cabeçalho | Selo com nome por extenso ("Prefeitura de Vale do Ribeiro") e cor `--client-n` quando um cliente está selecionado |
| Linhas e cards | `ClientMark` (sigla quadrada colorida) + sigla e cidade em linhas densas ("VR Vale do Ribeiro") |
| Processo | Breadcrumb: `Prefeitura de Vale do Ribeiro › Secretaria de Fazenda › ISS-012 Alvará de funcionamento` |
| Ações com efeito externo | `AlertDialog` de confirmação que repete prefeitura, processo, destinatário e versão/hash curto antes de enviar rodada, aprovar, aplicar ou autorizar contato |
| Busca global (Ctrl/Cmd+K) | Cada resultado começa pelo cliente |
| Portal | Selo da prefeitura no topo de todas as telas |

Contrato de API: todo DTO de caso, tarefa, mensagem, rodada e contato inclui `municipality {id, name, short, color_slot}`. O frontend nunca deduz o cliente pelo filtro ativo nem pela rota.

A cor do cliente identifica, não sinaliza: nunca indica prazo ou estado (direcionamento §3.3).

## 4. "Hoje" do implantador

### 4.1 Conceito

`/` mostra **o que o implantador precisa fazer**, calculado pelo servidor em `GET /api/today` a partir do estado persistido. A lista é uma projeção determinística: não é armazenada, não é gerada por LLM e é sempre igual para o mesmo estado e o mesmo relógio de negócio.

Cada tarefa contém:

```text
task_id (estável: tipo + entidade + revisão), client, process, case_id,
title (verbo no infinitivo, específico), why {code, text}, since,
deadline {status: ontrack|atrisk|late, due_at}, primary_action {label, route|command},
source_refs[]
```

### 4.2 Regras de geração

| Gatilho (estado/evento persistido) | Tarefa (exemplo de título) | Ação principal |
|---|---|---|
| Intervenção aberta / `BLOCKED_HUMAN` | "Resolver conflito: licença sanitária para todos ou só alimentação?" | Abrir decisão |
| `WAITING_IMPLANTER_APPROVAL` | "Aprovar pela Aprova a versão v2 de ISS-012" | Revisar e aprovar |
| Candidata com resultados esperados ainda não revisados por pessoa (v2 §6.3) | "Revisar resultados esperados dos testes de ISS-012" | Abrir testes |
| Mensagem com `round_id` nulo (triagem) | "Classificar mensagem de Ana (WhatsApp)" | Vincular à rodada |
| `ContactReferral` pendente | "Autorizar Maria (Vigilância) a responder sobre licença sanitária. Indicada por João" | Autorizar escopo |
| `ROUND_READY` com destinatário que ainda não recebeu nenhuma rodada | "Revisar a primeira mensagem para a Secretaria de Obras" | Revisar e enviar |
| Intervenção por silêncio (72h) ou secretaria sem resposta substantiva | "Acionar o contato central: Obras sem resposta há 5 dias" | Abrir rascunho |
| Todos os canais de uma entrega esgotados (v2 §10.2) | "Corrigir canal de contato de Pedro" | Abrir pessoa |
| `WAITING_MUNICIPAL_APPROVAL` há mais de 24h de negócio | "Cobrar aprovação municipal da versão v2" | Enviar lembrete |
| Processo do cronograma em risco ou atrasado e ainda não iniciado | "Iniciar validação de ISS-030 (vence em 3 dias · 27/10)" | Iniciar caso |

Ordenação: atrasado → em risco → urgência da intervenção → antiguidade (`since`). Agrupamento opcional por cliente. Cada linha usa `TaskRow` com `ClientMark`, `DeadlineBadge`, `StateBadge`, título, motivo e botão da ação.

### 4.3 Com quem está a bola

Todo caso não terminal tem o campo calculado `ball_owner`:

```text
ball_owner: implantador | prefeitura:<contact_id> | agente | sistema
```

| `ball_owner` | Estados típicos |
|---|---|
| `implantador` | `BLOCKED_HUMAN`, `WAITING_IMPLANTER_APPROVAL`, `PAUSED` por intervenção, triagem, revisão de primeira mensagem |
| `prefeitura:<contact>` | `WAITING_ANY_CHANNEL`, `WAITING_PRIMARY_CHANNEL`, `WAITING_REFERRAL`, `WAITING_MUNICIPAL_APPROVAL` |
| `agente` | `UNDERSTANDING_FORM`, `ANALYZING_INITIAL_REPLY`, `BUILDING_ROUND`, `PROCESSING_REPLY`, `RECONCILING_RESPONSES` |
| `sistema` | `SENDING_ROUND`, `APPLYING`, `VERIFYING`, `FAILED_RETRYABLE` |

A tela Hoje tem duas abas de leitura além das ações: **Aguardando prefeitura** (com tempo de espera e próximo lembrete) e **Agente trabalhando**. O implantador vê de imediato o que não depende dele. Caso não terminal sem `ball_owner` é defeito (T22).

## 5. Portal da prefeitura

### 5.1 Princípios

- **Simples e mobile-first.** O link chega pelo WhatsApp e é aberto no celular. Uma coluna, botões grandes, nenhuma tabela.
- **Cada tela responde três perguntas:** o que preciso fazer, até quando e por quê.
- **Mesmo caso, mesma rodada.** O Portal é um canal (`channel=portal`), não uma jornada paralela (I05).
- **Linguagem com "você"**, explicando sempre o motivo do pedido (direcionamento §9). Sem jargão interno: nada de "lacuna", "ChangeSet" ou "candidata". O cliente vê "pergunta", "alteração" e "versão".
- **Rótulos de demonstração continuam visíveis** (I12).

### 5.2 Telas

| Rota | Conteúdo |
|---|---|
| `/portal/entrar?t=<token>` | Troca o link mágico por sessão do portal. Na demo, também é gerado pelo painel de personas |
| `/portal` (Início) | Selo da prefeitura e "Olá, Ana · Secretaria de Fazenda". **Seu próximo passo:** bloco `--brand-50` com a pendência mais prioritária e um único botão. Depois: **Para hoje (n)** com prazo; **Próximos (n)**, os itens adiados pelo orçamento de atenção; **Aguardando a Aprova (n)**, "já recebemos, previsão dd/mm"; **Concluídos** |
| `/portal/pendencias/:id` | Processo e secretaria; **Por que perguntamos**; **Como está hoje** (preview do campo atual); resposta com opções rápidas derivadas do tipo da pergunta (sim/não, opções do campo, número), texto livre, anexo, **Não sei, indicar quem sabe** e **Não se aplica**. Rascunho salvo localmente. Ao enviar: **Recebido. O que acontece agora: …** |
| `/portal/aprovacoes/:changeSetId` | Alteração em linguagem simples (antes/depois por campo), exemplos derivados dos testes ("Se o ramo for Alimentação, a licença será exigida"), versão e hash curto. **Aprovar versão v2** ou **Pedir ajuste** (motivo obrigatório). Visível com ação apenas para quem tem papel de aprovador municipal |
| `/portal/historico` | Tudo o que a pessoa respondeu, por qualquer canal ("Respondido por WhatsApp em 23/10 às 14:02"), com as alterações que cada resposta gerou |
| `/portal/primeiro-acesso` | Assistente do primeiro acesso (seção 6). Fatia 3 |

### 5.3 Regras

- A resposta no Portal é uma `Message(channel=portal, round_id, round_item_id)`. É persistida antes de ser interpretada (I02), passa pela mesma consolidação de 2 a 10 segundos (v2 §8.2) e pela mesma máquina de estados (`WAITING_*` → `PROCESSING_REPLY`).
- O Portal tem **correlação estruturada**: a resposta já chega ligada à rodada e ao item, sem triagem. É o melhor argumento operacional para estimular o cliente a usá-lo, sem obrigá-lo.
- "Ok", agradecimento e confirmação de leitura no Portal também não encerram itens (v2 §8.2). O formulário de resposta exige conteúdo substantivo ou uma das opções explícitas.
- O cliente vê só o próprio município e os itens do seu escopo. Notas internas, assuntos de outras secretarias, nomes de modelo, prompts e hashes completos nunca aparecem (I16).
- A aprovação no Portal usa o mesmo endpoint de serviço da aprovação municipal do v2 (§7.1). O papel vem do servidor, não da tela (I18).
- A preferência de canal escolhida no Portal é uma "preferência explícita autorizada do contato" no sentido do v2 §8.2.

### 5.4 Acesso

- **Link mágico por contato:** token aleatório, armazenado só como hash em `PortalAccess`, com expiração de 14 dias e revogação. A sessão do portal é separada da sessão do implantador.
- Na demo, `POST /api/demo/portal-links` gera o link de qualquer persona sintética e o painel de demo permite abrir o Portal como aquela pessoa.
- Isso **não é autenticação produtiva** (v2 §12.1 e §19.4). Publicar o Portal fora de `127.0.0.1` exige a especificação posterior de identidade e autorização.

## 6. Dia 1 do cliente

### 6.1 Antes do Dia 1: preparação pelo implantador

1. Em **Clientes**, cadastrar a implantação com data de início e meta (45 a 60 dias), as secretarias, o contato central e os processos distribuídos em ondas com `due_date`.
2. Autorizar o contato central e os responsáveis já conhecidos, com papel e escopo explícitos (v2 §8.3).
3. O agente prepara a primeira rodada de cada processo da primeira onda. O sistema agrupa por destinatário e respeita o orçamento de atenção.
4. O implantador revisa a primeira mensagem de cada destinatário novo (tarefa no Hoje) e libera o envio.

### 6.2 Dia 1: primeira interação

1. **Mensagem de boas-vindas no WhatsApp**, e comentário no ticket do Pylon quando existir:

   > Olá, Ana. Aqui é a equipe de implantação da Aprova, que está colocando os processos eletrônicos da Prefeitura de Vale do Ribeiro no ar. Você foi indicada como responsável por processos da Secretaria de Fazenda. Para hoje temos 3 perguntas, cerca de 10 minutos. Você pode responder por aqui mesmo ou pelo link: [Portal]. Se algum assunto não for com você, é só dizer quem pode ajudar.

2. **Primeiro acesso** em `/portal/primeiro-acesso`, três passos:
   - (a) confirmar nome e secretaria;
   - (b) **Isso é com você?** para cada processo atribuído: "Sou eu", "Indicar outra pessoa" ou "Não sei";
   - (c) canal preferido: Portal, WhatsApp ou Pylon.

   As respostas são declarações (`ResponsibilityClaim`) e não concedem papel (I07, I18). "Indicar outra pessoa" cria um `ContactReferral` e a tarefa "Autorizar…" no Hoje. "Não sei" cria tarefa para o implantador acionar o contato central.
3. **Início** com **Seu próximo passo** apontando para a pendência mais prioritária. Ana responde à primeira pergunta.
4. **Recebido. O que acontece agora:** "A Aprova vai ajustar o formulário com a sua resposta. Se faltar algo, você recebe uma nova pergunta. Previsão: 25/10." O item passa para **Aguardando a Aprova**. Ana sabe que a bola voltou para a Aprova.

Sem o Portal, a mesma jornada funciona pelo WhatsApp: o primeiro acesso é feito pelas respostas à mensagem de boas-vindas, com o agente propondo as declarações e o implantador confirmando o que exigir autorização.

### 6.3 Dias seguintes

- **Um resumo diário por contato**, e não uma mensagem por processo. No WhatsApp, o resumo tem uma parte de cabeçalho e uma parte por rodada (v2 §8.1 permite partes sequenciais). Cada parte tem ID externo próprio.
- **Orçamento de atenção:** até 5 itens novos por contato por dia de negócio, configurável por implantação (`daily_item_budget`). O excedente fica em **Próximos**, ordenado pelo `due_date` do processo. Nada é descartado, só adiado e visível (I19, T21).
- **Prazos de pendência:** `RoundItem.due_at` = envio da rodada + 72h de negócio, alinhado ao limite de intervenção do v2 §8.4. O Portal mostra "Responder até 27/10".
- **Lembretes** seguem o v2 §8.4 (24h, 48h, intervenção em 72h). Depois da intervenção, o Hoje sugere ao implantador acionar o contato central com rascunho. O sistema nunca contata automaticamente alguém não autorizado.

## 7. Compatibilidade com o Pylon

### 7.1 Papel do Pylon

O Pylon continua sendo a **origem de tickets** e **um dos canais**. Ticket aberto no Pylon (simulado) cria o caso, como no v2. O Portal substitui o portal do cliente do usePylon como lugar de resposta, mas não substitui o Pylon como sistema de registro de tickets.

O adaptador simulado segue o modelo do Pylon:

| Pylon | Aprova Command |
|---|---|
| Account | `Municipality` |
| Issue/ticket | `Ticket` |
| Mensagem pública | `Message(direction, visibility=public)` |
| Nota interna | Comentário interno do `Ticket`, nunca enviado à prefeitura |
| Webhook de evento | `IntegrationEvent` com chave externa |

`ExternalRef(entity_type, entity_id, system, external_id)` mapeia identificadores de Pylon e WhatsApp sem acoplar o domínio a nenhum dos dois.

### 7.2 Espelhamento

- Cada resposta substantiva recebida pelo Portal ou pelo WhatsApp gera um efeito de outbox idempotente que publica **comentário público resumido** no ticket do Pylon:

  > Respondido no Portal Aprova Command por Ana (Secretaria de Fazenda) em 24/10 às 10:12: "A licença sanitária deve ser exigida apenas para alimentação."

- Quem ainda acompanha pelo Pylon vê o histórico completo, e nenhuma resposta fica presa a um canal.
- Notas internas nunca são espelhadas. Anexos aparecem no espelho como referência ("1 documento anexado no Portal"), sem reenviar o arquivo.

### 7.3 Prevenção de laço (I17)

O espelho leva `mirror_of_message_id` e chave externa própria (`mirror:<message_id>`). Na ingestão, o adaptador Pylon reconhece a chave ou o marcador e registra o evento como espelho, sem criar `Message` de entrada nem evidência.

### 7.4 Pedido novo pelo Portal

"Pedir alteração em formulário" no Portal cria o ticket no Pylon por outbox e só depois o caso, pelo fluxo normal de intake.

### 7.5 Migração gradual

Flags por implantação: `portal_enabled` e `pylon_mirror_enabled`.

| Fase | Comportamento |
|---|---|
| Coexistência | Rodadas saem por Pylon, WhatsApp e Portal; espelhamento ligado |
| Portal principal | Rodadas saem por WhatsApp + Portal; Pylon recebe espelho |
| Pylon como arquivo | Pylon recebe apenas abertura/fechamento e espelho; respostas pelo Portal/WhatsApp |

## 8. Suporte ao dia a dia do implantador

Itens não previstos no v2 e assumidos como necessários para operar cerca de 400 processos simultâneos:

1. **Secretarias como entidade.** Cada processo pertence a uma secretaria (12 a 13 por prefeitura). O engajamento é medido por secretaria, já que nem todas engajam ao mesmo tempo.
2. **Cronograma e prazos de processo.** `Implementation.start_date/target_date` e `ProcessDefinition.wave/due_date` alimentam o **eixo Prazo** do direcionamento: em dia (mais de 3 dias ou concluído), em risco (vence hoje ou em até 3 dias) e atrasado. O cálculo é do servidor, com o relógio de negócio injetável do v2 §8.4.
3. **"O que está acontecendo e por quê".** Todo caso expõe `explanation {what, why, next, who, since, source_refs}`, montada **por template determinístico** a partir do estado, da guarda pendente e do último evento de auditoria. A justificativa do agente, quando houver, aparece separada e rotulada "Sugestão do agente" (I01, I13). O `WhyPanel` mostra a explicação no processo, no Hoje e, em versão simplificada, no Portal.

   | Estado | what | why | next |
   |---|---|---|---|
   | `WAITING_PRIMARY_CHANNEL` | Aguardando resposta de Ana | 2 perguntas bloqueiam a condição da licença | Lembrete automático em 25/10 10:00 |
   | `BLOCKED_HUMAN` | Parado para sua decisão | Respostas conflitantes de Pylon e WhatsApp | Escolher a regra ou pedir esclarecimento |
   | `WAITING_IMPLANTER_APPROVAL` | Aprovado pela prefeitura | Falta a aprovação da Aprova para a versão v2 | Revisar diff e testes e aprovar |

4. **Caixa de entrada consolidada** (`/inbox`): todas as mensagens de todos os canais e clientes, com `ClientMark`, `ChannelBadge` e filtro "Precisa de triagem".
5. **Correlação do resumo diário.** Resposta no WhatsApp citando uma parte do resumo correlaciona com a rodada daquela parte. Resposta sem citação, com uma única rodada ativa para o contato, correlaciona com ela. Com mais de uma rodada ativa, vai para triagem, como determina o v2 §8.2 (T20).
6. **Escada de escalonamento por silêncio:** lembrete 24h → lembrete 48h → intervenção 72h → tarefa "Acionar o contato central" com rascunho. O envio depende do implantador.
7. **Revisão da primeira mensagem (modo copiloto).** A política de `ROUND_READY → SENDING_ROUND` exige revisão humana da primeira rodada enviada a cada destinatário. Depois, o envio segue autônomo dentro da política. É uma guarda de política, não um estado novo.
8. **Clientes** (`/clients`, `/clients/:id`): progresso por estado, contatos ativos e convidados, secretarias silenciosas, prazo da implantação e grade de processos por secretaria (a antiga visão de mapa).
9. **Cronograma** (`/schedule`): Gantt por cliente e onda, com hachura de atraso (direcionamento §5) e linha do dia de negócio atual.

## 9. Modelo de dados: acréscimos

| Entidade/campo | Conteúdo |
|---|---|
| `Secretariat` | `id, municipality_id, name, short` |
| `ProcessDefinition` | `+ secretariat_id, wave, due_date` |
| `Implementation` | `+ start_date, target_date, portal_enabled, pylon_mirror_enabled, daily_item_budget` |
| `RoundItem` | `+ due_at, answer_kind` (`yes_no | choose_options | number | text | document`), derivado do tipo da lacuna e do campo |
| `Channel` (enum) | `+ portal` |
| `Message` | `+ round_item_id, mirror_of_message_id` |
| `PortalAccess` | `id, contact_id, municipality_id, token_hash, created_at, expires_at, revoked_at, last_used_at` |
| `ContactOnboarding` | `contact_id, invited_at, first_access_at, identity_confirmed_at, preferred_channel_set_at` |
| `ResponsibilityClaim` | `id, contact_id, process_id, answer (mine | refer | unknown), referral_id, created_at`: declaração, não concede papel |
| `ExternalRef` | `entity_type, entity_id, system, external_id`; único por `(system, external_id)` |
| `DigestDelivery` | `id, contact_id, business_date, parts[{part_index, round_id, external_part_id}]`; único por `(contact_id, business_date)` |

Uma migração Alembic por fatia, testada do banco vazio ao schema atual (v2 §4.3). Toda FK nova valida o mesmo município (v2 §5.1). `ball_owner`, `deadline` e `explanation` são calculados, não armazenados.

## 10. Invariantes novos

| ID | Regra |
|---|---|
| I15 | Resposta pelo Portal segue o mesmo caminho de persistência, consolidação, evidência e transição dos outros canais |
| I16 | Sessão de portal lê e escreve apenas no seu município e escopo. Recurso fora do escopo retorna 404; nota interna nunca é serializada para o portal |
| I17 | Espelho para o Pylon nunca é reingerido como mensagem de entrada ou evidência |
| I18 | Aprovação no Portal exige papel de aprovador municipal atribuído no servidor. Declaração de responsabilidade, indicação ou primeiro acesso não concedem papel |
| I19 | Todo caso não terminal tem `ball_owner` e `explanation`. O orçamento de atenção adia itens, mas nunca os oculta nem os descarta |

## 11. API: rotas novas

Convenções do v2 §13.1 valem para todas: `Idempotency-Key` em mutações, `expected_case_version` em comandos sobre caso, formato de erro, 403/404/409/413/422 e paginação.

| Área | Rotas |
|---|---|
| Implantador | `GET /api/today`, `GET /api/inbox`, `GET /api/clients`, `GET /api/clients/{id}`, `GET /api/schedule`, `GET /api/cases/{id}/explanation` |
| Portal: sessão | `POST /api/portal/session` (troca token por sessão), `GET /api/portal/me` |
| Portal: pendências | `GET /api/portal/pending`, `GET /api/portal/items/{id}`, `POST /api/portal/items/{id}/answer`, `POST /api/portal/items/{id}/attachments`, `POST /api/portal/items/{id}/refer` |
| Portal: aprovação | `GET /api/portal/approvals/{change_set_id}`, `POST /api/portal/approvals/{change_set_id}` (`approve` ou `reject` com motivo) |
| Portal: histórico e primeiro acesso | `GET /api/portal/history`, `POST /api/portal/onboarding`, `POST /api/portal/preferred-channel` |
| Demo | `POST /api/demo/portal-links` |

Rotas do Portal usam a sessão do portal, nunca o token do implantador. As rotas do Portal chamam os mesmos serviços de aplicação das rotas do v2 (conversas, indicações, aprovação municipal); não há regra de negócio própria do Portal.

## 12. Frontend com shadcn/ui

### 12.1 Base

- `npx shadcn@latest init` com Vite, Tailwind v4 e tema claro. Fixar versões no lockfile na fatia 1 (v2 §4.1).
- Componentes shadcn: `sidebar, button, badge, card, table, tabs, dialog, alert-dialog, sheet, command, sonner, tooltip, skeleton, alert, progress, textarea, radio-group, form, input, select, separator, breadcrumb, avatar, dropdown-menu, scroll-area`. Tabelas no padrão data-table do shadcn com `@tanstack/react-table`.
- Dados com TanStack Query e `refetchInterval: 2000` apenas com a aba visível (v2 §13.1). Tipos e enums gerados do OpenAPI com `openapi-typescript`; o frontend não inventa enums.
- Ícones `lucide-react` conforme o mapa fixo do direcionamento §10.

### 12.2 Tokens

Mapeamento do direcionamento §3 para as variáveis do shadcn em `frontend/src/index.css`:

| Variável shadcn | Token do direcionamento |
|---|---|
| `--background` | `--zinc-50` |
| `--card`, `--popover` | branco |
| `--foreground`, `--card-foreground` | `--zinc-950` |
| `--primary` / hover | `--brand-600` / `--brand-700` |
| `--primary-foreground` | branco |
| `--secondary`, `--muted`, `--accent` | `--zinc-100` |
| `--muted-foreground` | `--zinc-500` |
| `--border`, `--input` | `--zinc-200` |
| `--ring` | `--brand-400` |
| `--destructive` | `#dc2626` |
| `--radius` | `8px` → sm 4px (badge), md 6px (botão/campo), lg 8px (item), xl 12px (card) |

Tokens semânticos adicionais em `@theme`: `deadline-{ontrack,atrisk,late}-{solid,bg,fg,border}`, `state-{blocked,waiting,running,paused,failed,completed,idle,sim}-*`, `client-{1,2,3}-*` e `channel-{pylon,whatsapp,portal,system,agent}`. Sombras, foco e movimento conforme o direcionamento §5, respeitando `prefers-reduced-motion`.

### 12.3 Componentes de domínio

Em `frontend/src/components/domain/`:

| Componente | Responsabilidade |
|---|---|
| `ClientMark`, `ClientSeal` | Sigla quadrada e selo com nome completo do cliente |
| `DeadlineBadge` | Prazo relativo + absoluto, ícone + texto ("Atrasado 2 dias · 22/10") |
| `StateBadge` | Estado do caso, sempre ícone + texto |
| `ChannelBadge` | Pylon, WhatsApp, Portal, Sistema ou Agente |
| `TaskRow` | Linha de tarefa do Hoje |
| `NextStepCard` | Bloco "Seu próximo passo" (implantador e Portal) |
| `WhyPanel` | O que está acontecendo, por quê, próximo passo, quem e desde quando |
| `DemoBanner` | "Ambiente de demonstração — dados sintéticos", modo de IA, extração simulada |
| `StaleIndicator` | "Atualizado há X s" e aviso de worker parado |
| `ConfirmEffectDialog` | Confirmação de efeito externo repetindo cliente, processo, destinatário e versão |

### 12.4 Rotas de tela

```text
/                       Hoje
/inbox                  Caixa de entrada
/clients                Clientes
/clients/:id            Cliente: progresso, secretarias, grade de processos
/schedule               Cronograma
/processes/:id/*        Processo (abas do v2 §14.1)
/interventions          Fila de intervenção
/tickets                Pylon simulado
/settings/demo          Personas, cenários, links do portal e relógio
/portal/*               Portal da prefeitura (layout próprio, sem barra lateral)
```

## 13. Fatias e corte do hackathon

| Fatia v2 | Acréscimos deste adendo |
|---|---|
| 1. Ciclo completo estreito | Scaffold shadcn, tokens, AppShell com cliente explícito, `DemoBanner`. Hoje mínimo (aprovar, revisar testes, intervenção). Portal: tela de aprovação municipal usada no cenário G |
| 2. Intake e rodadas multicanal | Canal Portal para responder pendências (Início, Pendência, "Recebido"). Espelhamento no Pylon com anti-laço. Caixa de entrada. `explanation` e `ball_owner`. Resumo diário no WhatsApp |
| 3. Exceções, anexos e responsáveis | Primeiro acesso, "Isso é com você?", indicação pelo Portal com tarefa "Autorizar…" no Hoje. Histórico do Portal. Escalonamento por silêncio. Orçamento de atenção. Revisão da primeira mensagem |
| 5. Demo completa | Clientes, Cronograma, grade por secretaria, métricas por cliente |

**Corte até 16h:** fatia 1, a parte de Portal da fatia 2 (responder pendência) para os cenários A e C, e o Hoje. Primeiro acesso e indicação pelo Portal ficam para a fatia 3. Se o tempo acabar, declarar o que foi concluído, conforme v2 §17.5.

**Roteiro curto atualizado (alvo de três minutos):** etiquetas de demo → ticket no Pylon → Hoje mostra o caso da Prefeitura de Vale do Ribeiro → rodada sai por WhatsApp e Portal → cliente responde no Portal em largura de celular → comentário espelhado aparece no Pylon → candidata e testes → cliente aprova no Portal → implantador aprova a partir do Hoje → aplicação, read-back e fechamento.

## 14. Cenários e regressões novos

| ID | Entrada/ação | Resultado obrigatório | Modo |
|---|---|---|---|
| I | Resposta no Portal + complemento no WhatsApp para a mesma rodada | Uma consolidação; espelho publicado no Pylon; nenhuma evidência duplicada | Offline e ao vivo |
| J | Dia 1: convite → primeiro acesso → "Indicar outra pessoa" → autorização no Hoje → resumo diário | Declaração sem papel; indicação só vale após autorização; resumo dentro do orçamento, excedente em Próximos | Offline |
| K | Sessão do portal de VR tenta acessar SA, nota interna e aprovação sem papel | 404 fora do escopo, nota interna ausente, 403 sem papel | Offline |

| ID | Condição | Aceite |
|---|---|---|
| T17 | Espelho chega de volta pelo webhook do Pylon | Registrado como espelho; nenhuma mensagem de entrada ou evidência |
| T18 | Mesmo texto pelo Portal e pelo WhatsApp, mesmo contato | Duas fontes preservadas; uma consolidação |
| T19 | Token do portal de um município lê recurso de outro | 404, sem vazamento em mensagens de erro |
| T20 | Resposta citando parte do resumo; resposta sem citação com várias rodadas ativas | Primeira correlacionada à rodada da parte; segunda em triagem |
| T21 | Mais itens prontos que o orçamento diário | Excedente adiado e listado em Próximos; nenhum item perdido ou oculto |
| T22 | Varredura de casos não terminais | Todos com `ball_owner` e `explanation`; os do implantador aparecem exatamente uma vez no Hoje |

## 15. Decisões em aberto

| Tema | Decisão provisória | Quem decide |
|---|---|---|
| Orçamento de atenção | 5 itens novos por contato por dia | Implantação, por cliente |
| Prazo de pendência | Envio + 72h de negócio | Produto |
| Validade do link mágico | 14 dias, com revogação | Segurança, antes de qualquer publicação |
| Fases de migração do Pylon | Começar em coexistência | Operação Aprova, por cliente |
| Integração real com o Pylon | Fora do escopo; adaptador simulado no formato do Pylon | Especificação posterior (v2 §19.4) |
