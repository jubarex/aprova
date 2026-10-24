# Aprova Command — Direcionamento visual

**Versão:** 2.0 (tema claro institucional)
**Data:** 24/10/2026
**Escopo:** referência visual para implementar o frontend (React + TypeScript + CSS com variáveis de tema), como prevê a seção 4.1 do plano. Este documento não altera regras de produto; ele traduz as seções 14.1–14.4 em decisões de interface.

---

## 1. Princípios

1. **O cliente está sempre explícito.** Toda tela, linha e card diz de qual prefeitura se trata. Nunca dependa só do filtro ativo.
2. **Prazo primeiro.** A pergunta "está em dia ou atrasado?" deve ser respondida sem clique, hover ou zoom.
3. **O que fazer, não só o que existe.** A tela inicial da implantadora é uma lista de ações ("O que fazer hoje"), não um painel de métricas.
4. **Um caso, vários canais.** Pylon, WhatsApp e Portal são canais do mesmo caso e da mesma rodada. A interface mostra isso juntando tudo, nunca em abas separadas por canal.
5. **Institucional e discreto.** Estilo shadcn/ui: fundo claro, bordas finas, um azul-marinho de marca e cor só onde há significado.
6. **Honestidade de demonstração (I12).** Os rótulos de ambiente, de modo de IA e de extração simulada ficam sempre visíveis.

---

## 2. Públicos e superfícies

| Público | Superfície | Pergunta que a tela responde |
|---|---|---|
| Implantadora (Aprova) | **Hoje** | O que eu tenho que fazer hoje, e de qual cliente? |
| Implantadora | **Caixa de entrada** | O que a prefeitura respondeu, por qual canal, e onde isso entrou? |
| Implantadora | **Clientes** | Como está cada implantação, e quando entrego? |
| Implantadora | **Cronograma** | Qual processo de qual cliente vence quando, e o que está atrasado? |
| Implantadora | **Processo** | Em que etapa está, qual o meu próximo passo, o que falta da prefeitura? |
| Prefeitura (cliente) | **Portal da prefeitura** | O que a Aprova precisa de mim, e até quando? |

### 2.1 Portal da prefeitura (novo canal)

- É o **terceiro canal** do caso, junto de Pylon e WhatsApp. Respostas do portal entram como `Message` com `channel = portal`, na mesma conversa e rodada (I05).
- A prefeitura vê apenas **as próprias pendências** (escopo por município e processo; nada de notas internas, conforme a seção 8.3).
- Há dois tipos de pendência:
  - **Responder:** texto e anexo, sujeitos aos mesmos limites de upload da seção 12.2.
  - **Aprovar versão:** "Aprovar versão vX" ou "Pedir ajuste". Disponível só para quem tem papel explícito de aprovador municipal (I07).
- Cada pendência mostra o prazo, quem pediu, a rodada e um aviso de que foi enviada também por Pylon e WhatsApp.
- Na demo, a troca para a visão da prefeitura é um controle de persona visível (seção 12.1), em violeta, com o texto "Voltar à visão da implantadora".

---

## 3. Cores

### 3.1 Neutros e marca

| Token | Hex | Uso |
|---|---|---|
| `--zinc-50` | `#fafafa` | fundo do app, barra lateral, cabeçalhos de grupo |
| `--zinc-100` | `#f4f4f5` | `--muted`, `--accent`, fundo de hover de botão |
| `--zinc-200` | `#e4e4e7` | `--border`, `--input`, item de navegação ativo |
| `--zinc-300` | `#d4d4d8` | borda de checkbox |
| `--zinc-500` | `#71717a` | `--muted-foreground` (texto secundário) |
| `--zinc-700` | `#3f3f46` | texto terciário forte |
| `--zinc-950` | `#09090b` | `--foreground` |
| `--brand-50` | `#eef3fb` | fundo do bloco "Seu próximo passo", item selecionado |
| `--brand-100` | `#d9e4f5` | borda do bloco de próximo passo |
| `--brand-400` | `#5a82c4` | `--ring` (foco) |
| `--brand-600` | `#1f4785` | `--primary` (ação principal) |
| `--brand-700` | `#173866` | `--primary-hover` |

### 3.2 Dois eixos de status (nunca misturar)

**Eixo 1 — Prazo.** É o sinal dominante da interface.

| Status | Sólido | Fundo | Texto | Borda | Regra |
|---|---|---|---|---|---|
| Em dia (`ontrack`) | `#16a34a` | `#f0fdf4` | `#166534` | `#bbf7d0` | faltam mais de 3 dias, ou concluído |
| Em risco (`atrisk`) | `#d97706` | `#fffbeb` | `#92400e` | `#fde68a` | vence hoje ou em até 3 dias |
| Atrasado (`late`) | `#dc2626` | `#fef2f2` | `#991b1b` | `#fecaca` | prazo vencido |

**Eixo 2 — Estado do caso.** Mostra onde o caso está no fluxo.

| Estado | Rótulo | Ícone | Sólido / Fundo / Texto / Borda |
|---|---|---|---|
| `blocked` | Sua ação | `hand` | `#ea580c` / `#fff7ed` / `#9a3412` / `#fed7aa` |
| `waiting` | Aguardando prefeitura | `hourglass` | `#0284c7` / `#f0f9ff` / `#075985` / `#bae6fd` |
| `running` | Em andamento | `loader` | `#2c5aa0` / `#eef3fb` / `#173866` / `#b3c8eb` |
| `paused` | Pausado | `pause` | `#71717a` / `#f4f4f5` / `#3f3f46` / `#d4d4d8` |
| `failed` | Falha | `octagon-x` | `#dc2626` / `#fef2f2` / `#991b1b` / `#fecaca` |
| `completed` | Concluído | `check` | `#16a34a` / `#f0fdf4` / `#166534` / `#bbf7d0` |
| `idle` | Não iniciado | `circle-dashed` | `#a1a1aa` / `#fafafa` / `#52525b` / `#e4e4e7` |
| `sim` | Simulado | `flask-conical` | `#7c3aed` / `#f5f3ff` / `#5b21b6` / `#ddd6fe` |

Regras:
- Badge de estado tem **sempre ícone + texto**. A cor nunca é o único sinal (seção 14.3).
- "Em andamento" não significa concluído. Concluído tem rótulo e ícone próprios.
- Processos **não iniciados** ficam fora de métricas e contagens de sucesso (seção 2.2).

### 3.3 Cliente (identificação, não status)

| Token | Cor | Fundo | Borda | Exemplo |
|---|---|---|---|---|
| `--client-1` | `#0f766e` | `#f0fdfa` | `#99f6e4` | Prefeitura de Vale do Ribeiro (VR) |
| `--client-2` | `#9d174d` | `#fdf2f8` | `#fbcfe8` | Prefeitura de Serra Alta (SA) |
| `--client-3` | `#854d0e` | `#fefce8` | `#fde68a` | reserva |

A cor do cliente aparece só na sigla quadrada, no selo do cabeçalho e no cabeçalho de grupo do cronograma. Nunca a use para indicar prazo ou estado.

### 3.4 Canais

| Canal | Cor | Ícone |
|---|---|---|
| Pylon | `#4f46e5` | `ticket` |
| WhatsApp | `#15803d` | `message-circle` |
| Portal | `#1f4785` | `globe` |
| Sistema | `#71717a` | `cpu` |
| Agente | `#7c3aed` | `sparkles` |

---

## 4. Tipografia

- **Geist** (400/500/600/700) para toda a interface; **Geist Mono** para códigos, versões, hashes, horários e datas em tabela.
- Fallbacks: `'Segoe UI', system-ui, sans-serif` e `ui-monospace, Consolas, monospace`.

| Papel | Tamanho / peso | Tracking |
|---|---|---|
| Título de página | 24px / 600 | −0.02em |
| Título de card | 16px / 600 | −0.01em |
| Título de item | 14px / 500–600 | 0 |
| Corpo | 14px / 400, line-height 1.5 | 0 |
| Pequeno / meta | 12–13px / 400–500 | 0 |
| Rótulo de seção | 11–12px / 500–600, CAIXA ALTA | 0.04em |
| Mono | 11–13px / 500 | 0 |

Use sentence case em tudo. Caixa alta só em rótulos pequenos ("CLIENTE", "SEU PRÓXIMO PASSO").

---

## 5. Espaçamento, raios, sombras e movimento

- **Espaçamento:** base 4px (4, 8, 12, 16, 20, 24, 32, 40, 48).
- **Raios:** 4px badges pequenos · **6px botões e campos** · 8px itens e blocos internos · **12px cards** · pill só em contadores e no switch.
- **Sombras:**
  - `xs` `0 1px 2px rgba(9,9,11,.05)`: controles.
  - `sm` `0 1px 3px rgba(9,9,11,.08), 0 1px 2px -1px rgba(9,9,11,.08)`: cards.
  - `lg` `0 12px 24px -6px rgba(9,9,11,.14), 0 4px 8px -4px rgba(9,9,11,.08)`: toast e diálogo.
- **Foco:** contorno 2px `--ring` mais halo `0 0 0 3px rgba(90,130,196,.35)`, sempre visível.
- **Movimento:** 120ms (hover), 180ms (abas), 260ms (diálogo), curva `cubic-bezier(.2,.7,.2,1)`. Nada de bounce, loop ou animação decorativa. Respeitar `prefers-reduced-motion`.
- **Transparência:** só o overlay do diálogo (`rgba(9,9,11,.5)`). Sem blur.
- **Textura:** só a hachura vermelha de atraso no cronograma (`repeating-linear-gradient(135deg, rgba(220,38,38,.18) 0 4px, transparent 4px 8px)`).

---

## 6. Layout

```text
┌──────────────────────────────────────────────────────────────────────────────────┐
│ Faixa demo 28px: Ambiente de demonstração — dados sintéticos · Persona · IA · OCR │
├────────────┬─────────────────────────────────────────────────────────────────────┤
│ Sidebar    │ Cabeçalho 56px: [selo do cliente] › Tela          [busca] [24/10]  │
│ 248px      ├─────────────────────────────────────────────────────────────────────┤
│ Marca      │ Conteúdo (max-width 1240px, padding 24px)                          │
│ CLIENTE ▾  │                                                                     │
│ Hoje    7  │                                                                     │
│ Entrada 3  │                                                                     │
│ Clientes   │                                                                     │
│ Cronograma │                                                                     │
│            │                                                                     │
│ [Portal]   │                                                                     │
│ Usuário    │                                                                     │
└────────────┴─────────────────────────────────────────────────────────────────────┘
```

- **Seletor de cliente** na barra lateral: "Todos os clientes" ou uma prefeitura. Filtra **todas** as telas. O cliente ativo aparece como selo no cabeçalho, com nome completo, UF e data de entrega.
- O contador de **Hoje** fica vermelho quando há tarefas atrasadas.
- **Responsivo:** colunas usam `flex-wrap` / `auto-fit` e empilham abaixo de ~1000px. Nada de largura fixa em texto. Em ~900px o título da tela continua legível; o rótulo do cliente é o que encolhe com reticências.

---

## 7. Telas

### 7.1 Hoje (tela inicial da implantadora)
- Título "O que fazer hoje" e resumo: "7 tarefas abertas · 2 atrasadas · 2 vencem hoje".
- Quatro indicadores: Atrasadas, Vencem hoje, Aguardando prefeitura, Processos em dia (X de Y).
- **Lista de tarefas** em três grupos, nesta ordem: **Atrasadas → Vencem hoje → Próximos dias**. Cada linha (TaskRow) tem:
  - checkbox para marcar como feita;
  - ícone do tipo de tarefa (cor do estado);
  - **título começando pelo verbo**;
  - meta: sigla e cidade do cliente · processo · código · canal de origem;
  - badge de prazo ("Atrasado 2 dias · 22/10") e botão "Abrir".
- Coluna lateral **Entregas por cliente**: data de entrega, dias restantes, status da entrega, processos validados (X de 70) e contagem de atrasados, em risco e em dia. Clicar no card filtra pelo cliente.

### 7.2 Caixa de entrada
- Lista única com Pylon, WhatsApp e Portal, em ordem cronológica, com indicador de não lida.
- Detalhe ao lado com:
  - cliente, processo e código;
  - autor, canal e horário;
  - texto original e anexo (com etiqueta "extraído (simulado)" quando aplicável);
  - badge de vínculo: "Vinculada à rodada 1", "Conflita com o Pylon", "Triagem: contato não autorizado", "Sem informação nova";
  - bloco "Leitura do agente";
  - ações "Abrir processo" e "Corrigir vínculo".
- Mensagem sem correlação vai para **triagem**, nunca para a rodada mais recente (seção 8.2).

### 7.3 Clientes
- Um card por prefeitura com:
  - sigla, nome, UF, implantação e contato central;
  - status da entrega;
  - três blocos: Entrega (data e dias restantes), Validados (X / 70), Em andamento (e atrasados);
  - lista dos processos ativos ordenada por prazo;
  - ações "Ver cronograma" e "Filtrar por este cliente".

### 7.4 Cronograma
- Tabela com as colunas Processo (nome, código, responsável) · Etapa atual · Prazo (data e status) · linha do tempo semanal.
- Linhas **agrupadas por cliente**. O cabeçalho do grupo leva a cor do cliente e a bandeira da data de entrega.
- Barra do processo:
  - do início ao prazo, na cor do status de prazo, com o progresso preenchido;
  - **marco preto** de 2px no prazo;
  - processo atrasado: trecho **hachurado vermelho** do prazo até hoje;
  - linha tracejada azul de **hoje** em todas as linhas.
- Legenda sempre visível. Linhas ordenadas por prazo.

### 7.5 Processo
- Cabeçalho: sigla e nome do cliente (na cor do cliente), nome do processo, código, responsável na prefeitura e badge de prazo.
- **Etapas** (stepper): Recebido → Dossiê → Esclarecimento → Candidata e testes → Aprovação municipal → Aprovação Aprova → Aplicação → Concluído.
- Bloco **Seu próximo passo** (fundo brand-50): ação no infinitivo, motivo e botão primário ("Decidir agora", "Corrigir versão", "Revisar"), mais "Assumir conversa".
- **Pendências com a prefeitura:** cada item mostra os canais em que foi enviado (Pylon, WhatsApp, Portal) e o estado em cada um (enviada / respondida).
- **Histórico:** mensagens de todos os canais na ordem de recepção persistida.
- As demais abas previstas na seção 14.1 (dossiê, rodadas, formulário, pessoas, aprovações) seguem o mesmo padrão de card.

### 7.6 Portal da prefeitura
- Cabeçalho próprio: marca, "Portal da prefeitura", selo do cliente, nome e papel do usuário ("Contato central · aprovador municipal").
- Título "Suas pendências" e um texto que explica que dá para responder por aqui, pelo WhatsApp ou pelo Pylon, e que tudo entra no mesmo histórico.
- Indicadores: Aguardando você · Atrasadas · Entrega da implantação.
- Card por pendência:
  - processo e código, título e prazo;
  - itens numerados;
  - linha de contexto (quem pediu, rodada, outros canais);
  - **Responder:** textarea, "Anexar documento" e "Enviar resposta" (desabilitado com texto vazio);
  - **Aprovar:** "Ver formulário e testes", "Pedir ajuste" e "Aprovar versão vX".
- Ao enviar: toast "Resposta enviada — a equipe Aprova foi notificada". O item vai para **Respondidas** e aparece na hora na Caixa de entrada da implantadora como canal Portal.

---

## 8. Componentes

Todos seguem a convenção shadcn: `--background`, `--foreground`, `--muted`, `--border`, `--primary`, `--ring` etc.

| Componente | Variantes / props principais |
|---|---|
| Button | `default`, `secondary`, `outline`, `ghost`, `destructive`, `link` · `sm` 32px / `md` 36px / `lg` 40px |
| IconButton | `ghost`, `outline`; `label` obrigatório |
| Input, Textarea, Select | rótulo acima, ajuda/erro abaixo; borda `--input`; foco com halo |
| Checkbox, Switch | marca `--primary` |
| StatusBadge | 8 estados (eixo 2), ícone + texto |
| DeadlineBadge | `ontrack` / `atrisk` / `late` + texto relativo + data |
| Progress | barra 6px; `primary` ou cor de prazo |
| Toast, Tooltip, Dialog | sombra `lg`, raio 8–12px |
| Card | borda zinc-200, raio 12px, `shadow-sm`, cabeçalho, corpo e rodapé |
| Tabs | segmentadas sobre `--muted` |
| DemoRibbon | faixa violeta fixa no topo |
| **ClientChip** | sigla quadrada + nome; `sm`/`md` |
| **TaskRow** | ação + cliente + processo + prazo + "Abrir" |
| **ScheduleBar** | barra de cronograma com progresso, marco, atraso e hoje |
| **ActivityItem** | mensagem multicanal com estado de vínculo |
| **DecisionCard** | motivo, decisão, contexto, sugestão do agente, ações |
| **HashChip** | versão + `sha256:xxxxxxxx…xxxx`, com selo de verificado |
| **EvidenceQuote** | citação literal com o trecho marcado (offsets em code points) |

---

## 9. Texto e tom

- Português do Brasil, com tom institucional, direto e cordial. Sem gíria, sem metáfora militar, sem exclamação, sem emoji.
- **Implantadora:** tarefas e botões no infinitivo e específicos ("Resolver conflito: licença sanitária para todos ou só alimentação?", "Cobrar aprovação municipal da versão v2"). Evite "OK" e "Enviar" genérico.
- **Prefeitura:** fale com "você" e explique o motivo do pedido.
- **Prazos:** relativo + absoluto ("Atrasado 2 dias · 22/10", "Vence hoje", "Vence em 3 dias · 27/10").
- **Cliente:** nome por extenso em cabeçalhos ("Prefeitura de Vale do Ribeiro"), sigla + cidade em linhas densas ("VR Vale do Ribeiro").
- **Métricas:** denominador zero vira "N/A". Seeds e não iniciados ficam fora das métricas.
- **Rótulos fixos:** "Ambiente de demonstração — dados sintéticos", "IA: replay offline" / "IA: inferência ao vivo", "Extração simulada".

---

## 10. Iconografia

- **Lucide** (traço 2px, 16px padrão). No projeto React, use o pacote `lucide-react`. No protótipo, a icon font `lucide-static@0.460.0`.
- **Mapa fixo:**
  - navegação: Hoje `calendar-check` · Caixa de entrada `inbox` · Clientes `building-2` · Cronograma `chart-gantt` · Portal `globe`;
  - prazo: atrasado `circle-alert` · em risco `clock` · em dia `circle-check`;
  - ações: aprovação `stamp` · anexo `paperclip` · enviar `send`.
- Sem emoji, PNG ou SVG próprio.
- **Logo:** ainda não fornecido. Use a marca nominativa "Aprova Command" em Geist, com o quadrado "A" na cor `--primary`. Troque pelo logo oficial quando houver.

---

## 11. Acessibilidade (aceite manual da seção 14.3)

- Contraste mínimo 4.5:1 para texto. Todos os pares de texto e fundo de status acima atendem.
- Fluxo principal navegável por teclado, com foco sempre visível.
- Estados indicados por **ícone + texto**, além de cor.
- Exceções e atrasos localizáveis sem hover, zoom ou animação.
- Zoom de 200% sem perda de conteúdo (layout com `flex-wrap` e `auto-fit`).
- Toda tela cobre os estados carregando, vazio, sem resultados, erro recuperável e dados desatualizados ("atualizado há X s" / worker parado).
- Em 409, recarregar a versão e exigir nova decisão. Nunca reenviar uma aprovação automaticamente.

---

## 12. Referências no projeto de design

- Tokens: `tokens/colors.css`, `typography.css`, `spacing.css`, `effects.css`.
- Componentes: `components/**` (`.jsx` + `.d.ts` + `.prompt.md`).
- Protótipo clicável: `ui_kits/command/Aprova Command.dc.html` (Hoje, Caixa de entrada, Clientes, Cronograma, Processo, Portal da prefeitura).
- Guia completo: `readme.md`.
