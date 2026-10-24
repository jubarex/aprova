# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: cenarios.spec.ts >> Hoje mostra o cliente e o motivo em cada tarefa; teclado com foco visível
- Location: e2e\cenarios.spec.ts:104:1

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator:  getByText('Prefeitura de Vale do Ribeiro').first()
Expected: visible
Received: hidden
Timeout:  20000ms

Call log:
  - Expect "toBeVisible" getByText('Prefeitura de Vale do Ribeiro').first() with timeout 20000ms
  - waiting for getByText('Prefeitura de Vale do Ribeiro').first()
    43 × locator resolved to <option value="mun_vr">…</option>
       - unexpected value "hidden"

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
  - heading "O que fazer hoje" [level=1]
  - paragraph: Ações que dependem de você, por prazo. O que está com a prefeitura ou com o agente aparece nas outras abas.
  - tablist:
    - tab "Para você (1)" [selected]
    - tab "Aguardando prefeitura (0)"
    - tab "Agente trabalhando (0)"
  - tabpanel "Para você (1)":
    - list:
      - listitem:
        - paragraph: "Cliente: Prefeitura de Vale do Ribeiro · ISS-030"
        - heading "Iniciar validação de ISS-030" [level=3]
        - paragraph: "Por quê: Vence em 2 dia(s) e ainda não iniciado."
        - text: Vence em 2 dias · 26/10 agora
        - link "Iniciar caso":
          - /url: /processes/new?process=proc_vr_iss030
- region "Notifications alt+T"
```

# Test source

```ts
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
  87  |   await expect(page.getByText('Alterações prontas para revisão').first()).toBeVisible({ timeout: 40_000 })
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
> 107 |   await expect(page.getByText('Prefeitura de Vale do Ribeiro').first()).toBeVisible()
      |                                                                         ^ Error: expect(locator).toBeVisible() failed
  108 |   await expect(page.getByText('Por quê:').first()).toBeVisible()
  109 |   await expect(page.getByText('Ambiente de demonstração — dados sintéticos')).toBeVisible()
  110 |   await page.keyboard.press('Tab')
  111 |   await expect(page.locator(':focus')).toBeVisible()
  112 | })
  113 | 
```