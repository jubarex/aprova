# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: cenarios.spec.ts >> B — indicação de responsável com repasse restrito
- Location: e2e\cenarios.spec.ts:71:1

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: getByText('Alterações prontas para revisão').first()
Expected: visible
Timeout: 40000ms
Error: element(s) not found

Call log:
  - Expect "toBeVisible" getByText('Alterações prontas para revisão').first() with timeout 40000ms
  - waiting for getByText('Alterações prontas para revisão').first()

```

```yaml
- note: "Ambiente de demonstração — dados sintéticos IA: replay offline Extração simulada"
- complementary "Navegação":
  - text: Aprova Command Cliente
  - combobox "Cliente":
    - option "Todos os clientes (1)" [selected]
    - option "SA · Prefeitura de Serra Alta (0)"
    - option "VR · Prefeitura de Vale do Ribeiro (1)"
  - navigation:
    - link "Hoje 1":
      - /url: /
    - link "Caixa de entrada":
      - /url: /inbox
    - link "Intervenções":
      - /url: /interventions
    - link "Clientes":
      - /url: /clients
    - link "Cronograma":
      - /url: /schedule
    - link "Métricas":
      - /url: /metrics
    - link "Capacidades":
      - /url: /templates
    - link "Demonstração":
      - /url: /settings/demo
  - text: "Persona: Rui Prado (implantador)"
  - button "Trocar persona"
- banner: Todos os clientes Atualizado há 0 s
- main:
  - navigation "breadcrumb":
    - list:
      - listitem:
        - link "Hoje":
          - /url: /
      - listitem: Prefeitura de Vale do Ribeiro
      - listitem: Vigilância Sanitária
      - listitem:
        - link "VIG-002 Licença sanitária" [disabled]
  - text: VR Prefeitura de Vale do Ribeiro
  - heading "VIG-002 · Licença sanitária" [level=1]
  - text: Aguardando resposta Vence em 15 dias · 08/11
  - region "O que está acontecendo":
    - heading "O que está acontecendo" [level=2]
    - paragraph: Aguardando resposta
    - term: Por quê
    - definition: Etapa do fluxo
    - term: Próximo passo
    - definition: Aguardar a resposta da prefeitura
    - term: Com quem está
    - definition: Com a prefeitura · agora
  - group "Ações do caso":
    - button "Pausar"
  - tablist:
    - tab "Dossiê"
    - tab "Rodadas e lacunas"
    - tab "Conversas"
    - tab "Pessoas"
    - tab "Formulário e testes"
    - tab "Aprovações"
    - tab "Linha do tempo"
    - tab "Simulador" [selected]
  - tabpanel "Simulador":
    - paragraph: "Simuladores: modo demonstração. Os canais reais (Pylon, WhatsApp) não são acessados."
    - region "Roteiro":
      - heading "Roteiro do cenário B — Indicação de responsável" [level=2]
      - paragraph: Ninguém autorizado cobre a Vigilância. Ana indica o técnico Carlos; só o assunto sanitário é transferido, o implantador autoriza e o documento enviado por Carlos retoma o caso.
      - list:
        - listitem:
          - text: 1 Ana indica Carlos Menezes (Vigilância)
          - button "Executar"
        - listitem:
          - text: 2 Implantador autoriza Carlos só para o assunto sanitário
          - button "Executar"
        - listitem:
          - text: 3 Carlos envia o documento (WhatsApp)
          - emphasis: “Segue o documento de referência da Vigilância.”
          - button "Executar"
    - region "Enviar mensagem":
      - heading "Enviar mensagem como contato" [level=2]
      - paragraph: Texto fora do roteiro não tem gravação no modo replay e resulta em REPLAY_MISS na análise (nada é inventado).
      - text: Quem escreve
      - combobox "Quem escreve":
        - option "Ana Souza" [selected]
        - option "Carlos Menezes"
        - option "João Lima"
      - text: Canal
      - combobox "Canal":
        - option "WhatsApp" [selected]
        - option "Portal"
        - option "Pylon (comentário no ticket)"
      - text: Mensagem
      - textbox "Mensagem"
      - text: Em resposta a
      - combobox "Em resposta a":
        - option "Última rodada" [selected]
        - 'option "Nenhuma (sem correlação: triagem)"'
        - option "Rodada 1"
      - text: Identidade externa (repetir = duplicata)
      - textbox "Identidade externa (repetir = duplicata)":
        - /placeholder: "ex.: wa-1001"
      - text: Anexo (TXT, MD, JSON, PDF, PNG, JPEG, WAV, MP3)
      - button "Anexo (TXT, MD, JSON, PDF, PNG, JPEG, WAV, MP3)"
      - text: Transcrição/OCR simulado (áudio e imagem)
      - textbox "Transcrição/OCR simulado (áudio e imagem)"
      - button "Enviar"
    - region "Falhas de canal":
      - heading "Falha de envio" [level=2]
      - paragraph: "Derruba um canal para a próxima entrega: o sistema tenta 3 vezes (1 s e 5 s), mantém a espera nos canais entregues e abre intervenção só se todos falharem."
      - 'button "whatsapp: normal"'
      - 'button "portal: normal"'
      - 'button "pylon: normal"'
- region "Notifications alt+T"
```

# Test source

```ts
  1   | import { expect, test } from '@playwright/test'
  2   | import { loginAs, openTab, resetDemo, startScenario } from './helpers'
  3   | 
  4   | test.beforeEach(async ({ request }) => { await resetDemo(request) })
  5   | 
  6   | test('G — ciclo completo: duas aprovações, aplicação, read-back e fechamento', async ({ page }) => {
  7   |   await loginAs(page, /Rui Prado/)
  8   |   const url = await startScenario(page, /G — Ciclo completo/)
  9   |   await expect(page.getByRole('button', { name: 'Confirmar resultados esperados' })).toBeVisible()
  10  |   await page.getByRole('button', { name: 'Confirmar resultados esperados' }).click()
  11  |   await expect(page.getByRole('button', { name: 'Pedir aprovação da prefeitura' })).toBeEnabled()
  12  |   await page.getByRole('button', { name: 'Pedir aprovação da prefeitura' }).click()
  13  |   await page.getByRole('alertdialog').getByRole('button', { name: 'Pedir aprovação' }).click()
  14  |   await expect(page.getByText('Aguardando aprovação da prefeitura').first()).toBeVisible()
  15  | 
  16  |   // Portal: Ana aprova em linguagem simples
  17  |   await loginAs(page, /Ana Souza/)
  18  |   await expect(page.getByText('Seu próximo passo')).toBeVisible()
  19  |   await page.getByRole('link', { name: 'Revisar e aprovar' }).click()
  20  |   await expect(page.getByText('Se: Ramo de atividade: Alimentação').first()).toBeVisible()
  21  |   await page.getByRole('button', { name: /Aprovar versão/ }).click()
  22  |   await page.getByRole('alertdialog').getByRole('button', { name: 'Sim, aprovar' }).click()
  23  |   await expect(page.getByText('Recebido')).toBeVisible()
  24  | 
  25  |   await loginAs(page, /Rui Prado/)
  26  |   await page.goto(url)
  27  |   await page.getByRole('button', { name: 'Aprovar pela Aprova' }).click()
  28  |   await page.getByRole('alertdialog').getByRole('button', { name: 'Aprovar e aplicar' }).click()
  29  |   await expect(page.getByText('Versão aplicada, verificada e ticket fechado')).toBeVisible()
  30  | 
  31  |   await page.goto('/metrics')
  32  |   await expect(page.getByText('Cobertura auditável')).toBeVisible()
  33  |   await expect(page.getByText('100%').first()).toBeVisible()
  34  | })
  35  | 
  36  | test('A — resposta confusa: pacote de lacunas, resposta no Portal e só o delta na rodada seguinte', async ({ page }) => {
  37  |   await loginAs(page, /Rui Prado/)
  38  |   const url = await startScenario(page, /A — Resposta confusa/)
  39  |   await openTab(page, 'Rodadas e lacunas')
  40  |   await expect(page.getByText('Primeira mensagem a Ana Souza: revise antes de enviar')).toBeVisible({ timeout: 30_000 })
  41  |   await expect(page.getByText('Para seguir, precisamos de 3 informações')).toBeVisible()
  42  |   await page.getByRole('button', { name: 'Enviar a rodada' }).click()
  43  |   await expect(page.getByText('aguardando resposta').first()).toBeVisible()
  44  | 
  45  |   // Portal: Ana responde pelo Portal
  46  |   await loginAs(page, /Ana Souza/)
  47  |   await page.getByRole('link', { name: 'Responder agora' }).click()
  48  |   await expect(page.getByText('Por que perguntamos:')).toBeVisible()
  49  |   await page.getByRole('button', { name: /Usar a resposta do roteiro/ }).click()
  50  |   await page.getByRole('button', { name: 'Enviar resposta' }).click()
  51  |   await expect(page.getByText('O que acontece agora:')).toBeVisible()
  52  | 
  53  |   // Implantador: duas lacunas respondidas, uma em aberto; espelho no Pylon
  54  |   await loginAs(page, /Rui Prado/)
  55  |   await page.goto(url)
  56  |   await openTab(page, 'Rodadas e lacunas')
  57  |   await expect(page.locator('li', { hasText: 'G1' }).getByText('respondida')).toBeVisible({ timeout: 40_000 })
  58  |   await expect(page.locator('li', { hasText: 'G3' }).getByText('em aberto')).toBeVisible()
  59  |   await openTab(page, 'Conversas')
  60  |   await expect(page.getByText('espelho no Pylon')).toBeVisible()
  61  | 
  62  |   // "ok" não encerra nada; depois o restante chega pelo WhatsApp
  63  |   await openTab(page, 'Simulador')
  64  |   await page.locator('li', { hasText: 'Ana responde só' }).getByRole('button', { name: 'Executar' }).click()
  65  |   await page.locator('li', { hasText: 'Ana responde o restante' }).getByRole('button', { name: 'Executar' }).click()
  66  |   await openTab(page, 'Rodadas e lacunas')
  67  |   await expect(page.getByRole('heading', { name: 'Rodada 2' })).toBeVisible({ timeout: 40_000 })
  68  |   await expect(page.getByText('Primeira mensagem a João Lima: revise antes de enviar')).toBeVisible()
  69  | })
  70  | 
  71  | test('B — indicação de responsável com repasse restrito', async ({ page }) => {
  72  |   await loginAs(page, /Rui Prado/)
  73  |   await startScenario(page, /B — Indicação de responsável/)
  74  |   await openTab(page, 'Pessoas')
  75  |   await expect(page.getByText('Ninguém autorizado cobre este assunto')).toBeVisible({ timeout: 30_000 })
  76  |   await openTab(page, 'Simulador')
  77  |   await page.locator('li', { hasText: 'Ana indica Carlos' }).getByRole('button', { name: 'Executar' }).click()
  78  |   await openTab(page, 'Pessoas')
  79  |   await expect(page.getByText('Receber um nome ou apelido não concede autorização')).toBeVisible()
  80  |   await page.getByRole('button', { name: 'Autorizar este assunto' }).click()
  81  |   await page.getByRole('alertdialog').getByRole('button', { name: 'Autorizar escopo' }).click()
  82  |   await expect(page.getByText('Autorizado: pode responder apenas sobre esse assunto.')).toBeVisible()
  83  |   await openTab(page, 'Rodadas e lacunas')
  84  |   await page.getByRole('button', { name: 'Enviar a rodada' }).click()
  85  |   await openTab(page, 'Simulador')
  86  |   await page.locator('li', { hasText: 'Carlos envia o documento' }).getByRole('button', { name: 'Executar' }).click()
> 87  |   await expect(page.getByText('Alterações prontas para revisão').first()).toBeVisible({ timeout: 40_000 })
      |                                                                           ^ Error: expect(locator).toBeVisible() failed
  88  | })
  89  | 
  90  | test('D — fontes contraditórias: sem escolha arbitrária; decisão humana retoma', async ({ page }) => {
  91  |   await loginAs(page, /Rui Prado/)
  92  |   await startScenario(page, /D — Fontes contraditórias/)
  93  |   await openTab(page, 'Rodadas e lacunas')
  94  |   await page.getByRole('button', { name: 'Enviar a rodada' }).click()
  95  |   await openTab(page, 'Simulador')
  96  |   await page.locator('li', { hasText: 'Marcos: obrigatório para todos' }).getByRole('button', { name: 'Executar' }).click()
  97  |   await page.locator('li', { hasText: 'Luiza: somente alimentação' }).getByRole('button', { name: 'Executar' }).click()
  98  |   await expect(page.getByText('Decisão necessária').first()).toBeVisible({ timeout: 40_000 })
  99  |   await page.getByLabel('Decisão e justificativa').fill('Decisão do secretário: a licença sanitária vale somente para Alimentação.')
  100 |   await page.getByRole('button', { name: 'Registrar decisão e retomar' }).click()
  101 |   await expect(page.getByText('Alterações prontas para revisão').first()).toBeVisible({ timeout: 40_000 })
  102 | })
  103 | 
  104 | test('Hoje mostra o cliente e o motivo em cada tarefa; teclado com foco visível', async ({ page }) => {
  105 |   await loginAs(page, /Rui Prado/)
  106 |   await expect(page.getByRole('heading', { name: 'O que fazer hoje' })).toBeVisible()
  107 |   await expect(page.getByText('Prefeitura de Vale do Ribeiro').first()).toBeVisible()
  108 |   await expect(page.getByText('Por quê:').first()).toBeVisible()
  109 |   await expect(page.getByText('Ambiente de demonstração — dados sintéticos')).toBeVisible()
  110 |   await page.keyboard.press('Tab')
  111 |   await expect(page.locator(':focus')).toBeVisible()
  112 | })
  113 | 
```