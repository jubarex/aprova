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

## 3. Cores

### 3.1 Neutros e marca

| Token         | Hex       | Uso                                                  |
| ------------- | --------- | ---------------------------------------------------- |
| `--zinc-50`   | `#fafafa` | fundo do app, barra lateral, cabeçalhos de grupo     |
| `--zinc-100`  | `#f4f4f5` | `--muted`, `--accent`, fundo de hover de botão       |
| `--zinc-200`  | `#e4e4e7` | `--border`, `--input`, item de navegação ativo       |
| `--zinc-300`  | `#d4d4d8` | borda de checkbox                                    |
| `--zinc-500`  | `#71717a` | `--muted-foreground` (texto secundário)              |
| `--zinc-700`  | `#3f3f46` | texto terciário forte                                |
| `--zinc-950`  | `#09090b` | `--foreground`                                       |
| `--brand-50`  | `#eef3fb` | fundo do bloco "Seu próximo passo", item selecionado |
| `--brand-100` | `#d9e4f5` | borda do bloco de próximo passo                      |
| `--brand-400` | `#5a82c4` | `--ring` (foco)                                      |
| `--brand-600` | `#1f4785` | `--primary` (ação principal)                         |
| `--brand-700` | `#173866` | `--primary-hover`                                    |

### 3.2 Dois eixos de status (nunca misturar)

**Eixo 1 — Prazo.** É o sinal dominante da interface.

| Status              | Sólido    | Fundo     | Texto     | Borda     | Regra                               |
| ------------------- | --------- | --------- | --------- | --------- | ----------------------------------- |
| Em dia (`ontrack`)  | `#16a34a` | `#f0fdf4` | `#166534` | `#bbf7d0` | faltam mais de 3 dias, ou concluído |
| Em risco (`atrisk`) | `#d97706` | `#fffbeb` | `#92400e` | `#fde68a` | vence hoje ou em até 3 dias         |
| Atrasado (`late`)   | `#dc2626` | `#fef2f2` | `#991b1b` | `#fecaca` | prazo vencido                       |

**Eixo 2 — Estado do caso.** Mostra onde o caso está no fluxo.

| Estado      | Rótulo                | Ícone           | Sólido / Fundo / Texto / Borda                |
| ----------- | --------------------- | --------------- | --------------------------------------------- |
| `blocked`   | Sua ação              | `hand`          | `#ea580c` / `#fff7ed` / `#9a3412` / `#fed7aa` |
| `waiting`   | Aguardando prefeitura | `hourglass`     | `#0284c7` / `#f0f9ff` / `#075985` / `#bae6fd` |
| `running`   | Em andamento          | `loader`        | `#2c5aa0` / `#eef3fb` / `#173866` / `#b3c8eb` |
| `paused`    | Pausado               | `pause`         | `#71717a` / `#f4f4f5` / `#3f3f46` / `#d4d4d8` |
| `failed`    | Falha                 | `octagon-x`     | `#dc2626` / `#fef2f2` / `#991b1b` / `#fecaca` |
| `completed` | Concluído             | `check`         | `#16a34a` / `#f0fdf4` / `#166534` / `#bbf7d0` |
| `idle`      | Não iniciado          | `circle-dashed` | `#a1a1aa` / `#fafafa` / `#52525b` / `#e4e4e7` |
| `sim`       | Simulado              | `flask-conical` | `#7c3aed` / `#f5f3ff` / `#5b21b6` / `#ddd6fe` |

Regras:

- Badge de estado tem **sempre ícone + texto**. A cor nunca é o único sinal (seção 14.3).
- "Em andamento" não significa concluído. Concluído tem rótulo e ícone próprios.
- Processos **não iniciados** ficam fora de métricas e contagens de sucesso (seção 2.2).

### 3.3 Cliente (identificação, não status)

| Token        | Cor       | Fundo     | Borda     | Exemplo                            |
| ------------ | --------- | --------- | --------- | ---------------------------------- |
| `--client-1` | `#0f766e` | `#f0fdfa` | `#99f6e4` | Prefeitura de Vale do Ribeiro (VR) |
| `--client-2` | `#9d174d` | `#fdf2f8` | `#fbcfe8` | Prefeitura de Serra Alta (SA)      |
| `--client-3` | `#854d0e` | `#fefce8` | `#fde68a` | reserva                            |

A cor do cliente aparece só na sigla quadrada, no selo do cabeçalho e no cabeçalho de grupo do cronograma. Nunca a use para indicar prazo ou estado.

### 3.4 Canais

| Canal    | Cor       | Ícone            |
| -------- | --------- | ---------------- |
| Pylon    | `#4f46e5` | `ticket`         |
| WhatsApp | `#15803d` | `message-circle` |
| Portal   | `#1f4785` | `globe`          |
| Sistema  | `#71717a` | `cpu`            |
| Agente   | `#7c3aed` | `sparkles`       |

---

## 4. Tipografia

- **Geist** (400/500/600/700) para toda a interface; **Geist Mono** para códigos, versões, hashes, horários e datas em tabela.
- Fallbacks: `'Segoe UI', system-ui, sans-serif` e `ui-monospace, Consolas, monospace`.

| Papel            | Tamanho / peso                | Tracking |
| ---------------- | ----------------------------- | -------- |
| Título de página | 24px / 600                    | −0.02em  |
| Título de card   | 16px / 600                    | −0.01em  |
| Título de item   | 14px / 500–600                | 0        |
| Corpo            | 14px / 400, line-height 1.5   | 0        |
| Pequeno / meta   | 12–13px / 400–500             | 0        |
| Rótulo de seção  | 11–12px / 500–600, CAIXA ALTA | 0.04em   |
| Mono             | 11–13px / 500                 | 0        |

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

--

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
