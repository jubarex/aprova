import { expect, test } from '@playwright/test'
import { loginAs, openTab, resetDemo, startScenario } from './helpers'

test.beforeEach(async ({ request }) => { await resetDemo(request) })

test('G — ciclo completo: duas aprovações, aplicação, read-back e fechamento', async ({ page }) => {
  await loginAs(page, /Rui Prado/)
  const url = await startScenario(page, /G — Ciclo completo/)
  await expect(page.getByRole('button', { name: 'Confirmar resultados esperados' })).toBeVisible()
  await page.getByRole('button', { name: 'Confirmar resultados esperados' }).click()
  await expect(page.getByRole('button', { name: 'Pedir aprovação da prefeitura' })).toBeEnabled()
  await page.getByRole('button', { name: 'Pedir aprovação da prefeitura' }).click()
  await page.getByRole('alertdialog').getByRole('button', { name: 'Pedir aprovação' }).click()
  await expect(page.getByText('Aguardando aprovação da prefeitura').first()).toBeVisible()

  // Portal: Ana aprova em linguagem simples
  await loginAs(page, /Ana Souza/)
  await expect(page.getByText('Seu próximo passo')).toBeVisible()
  await page.getByRole('link', { name: 'Revisar e aprovar' }).click()
  await expect(page.getByText('Se: Ramo de atividade: Alimentação').first()).toBeVisible()
  await page.getByRole('button', { name: /Aprovar versão/ }).click()
  await page.getByRole('alertdialog').getByRole('button', { name: 'Sim, aprovar' }).click()
  await expect(page.getByText('Recebido')).toBeVisible()

  await loginAs(page, /Rui Prado/)
  await page.goto(url)
  await page.getByRole('button', { name: 'Aprovar pela Aprova' }).click()
  await page.getByRole('alertdialog').getByRole('button', { name: 'Aprovar e aplicar' }).click()
  await expect(page.getByText('Versão aplicada, verificada e ticket fechado')).toBeVisible()

  await page.goto('/metrics')
  await expect(page.getByText('Cobertura auditável')).toBeVisible()
  await expect(page.getByText('100%').first()).toBeVisible()
})

test('A — resposta confusa: pacote de lacunas, resposta no Portal e só o delta na rodada seguinte', async ({ page }) => {
  await loginAs(page, /Rui Prado/)
  const url = await startScenario(page, /A — Resposta confusa/)
  await openTab(page, 'Rodadas e lacunas')
  await expect(page.getByText('Primeira mensagem a Ana Souza: revise antes de enviar')).toBeVisible({ timeout: 30_000 })
  await expect(page.getByText('Para seguir, precisamos de 3 informações')).toBeVisible()
  await page.getByRole('button', { name: 'Enviar a rodada' }).click()
  await expect(page.getByText('aguardando resposta').first()).toBeVisible()

  // Portal: Ana responde pelo Portal
  await loginAs(page, /Ana Souza/)
  await page.getByRole('link', { name: 'Responder agora' }).click()
  await expect(page.getByText('Por que perguntamos:')).toBeVisible()
  await page.getByRole('button', { name: /Usar a resposta do roteiro/ }).click()
  await page.getByRole('button', { name: 'Enviar resposta' }).click()
  await expect(page.getByText('O que acontece agora:')).toBeVisible()

  // Implantador: duas lacunas respondidas, uma em aberto; espelho no Pylon
  await loginAs(page, /Rui Prado/)
  await page.goto(url)
  await openTab(page, 'Rodadas e lacunas')
  await expect(page.locator('li', { hasText: 'G1' }).getByText('respondida')).toBeVisible({ timeout: 40_000 })
  await expect(page.locator('li', { hasText: 'G3' }).getByText('em aberto')).toBeVisible()
  await openTab(page, 'Conversas')
  await expect(page.getByText('espelho no Pylon')).toBeVisible()

  // "ok" não encerra nada; depois o restante chega pelo WhatsApp
  await openTab(page, 'Simulador')
  await page.locator('li', { hasText: 'Ana responde só' }).getByRole('button', { name: 'Executar' }).click()
  await page.locator('li', { hasText: 'Ana responde o restante' }).getByRole('button', { name: 'Executar' }).click()
  await openTab(page, 'Rodadas e lacunas')
  await expect(page.getByRole('heading', { name: 'Rodada 2' })).toBeVisible({ timeout: 40_000 })
  await expect(page.getByText('Primeira mensagem a João Lima: revise antes de enviar')).toBeVisible()
})

test('B — indicação de responsável com repasse restrito', async ({ page }) => {
  await loginAs(page, /Rui Prado/)
  await startScenario(page, /B — Indicação de responsável/)
  await openTab(page, 'Pessoas')
  await expect(page.getByText('Ninguém autorizado cobre este assunto')).toBeVisible({ timeout: 30_000 })
  await openTab(page, 'Simulador')
  await page.locator('li', { hasText: 'Ana indica Carlos' }).getByRole('button', { name: 'Executar' }).click()
  await openTab(page, 'Pessoas')
  await expect(page.getByText('Receber um nome ou apelido não concede autorização')).toBeVisible()
  await page.getByRole('button', { name: 'Autorizar este assunto' }).click()
  await page.getByRole('alertdialog').getByRole('button', { name: 'Autorizar escopo' }).click()
  await expect(page.getByText('Autorizado: pode responder apenas sobre esse assunto.')).toBeVisible()
  await openTab(page, 'Rodadas e lacunas')
  await page.getByRole('button', { name: 'Enviar a rodada' }).click()
  await openTab(page, 'Simulador')
  await page.locator('li', { hasText: 'Carlos envia o documento' }).getByRole('button', { name: 'Executar' }).click()
  await expect(page.getByText('Alterações prontas para revisão').first()).toBeVisible({ timeout: 40_000 })
})

test('D — fontes contraditórias: sem escolha arbitrária; decisão humana retoma', async ({ page }) => {
  await loginAs(page, /Rui Prado/)
  await startScenario(page, /D — Fontes contraditórias/)
  await openTab(page, 'Rodadas e lacunas')
  await page.getByRole('button', { name: 'Enviar a rodada' }).click()
  await openTab(page, 'Simulador')
  await page.locator('li', { hasText: 'Marcos: obrigatório para todos' }).getByRole('button', { name: 'Executar' }).click()
  await page.locator('li', { hasText: 'Luiza: somente alimentação' }).getByRole('button', { name: 'Executar' }).click()
  await expect(page.getByText('Decisão necessária').first()).toBeVisible({ timeout: 40_000 })
  await page.getByLabel('Decisão e justificativa').fill('Decisão do secretário: a licença sanitária vale somente para Alimentação.')
  await page.getByRole('button', { name: 'Registrar decisão e retomar' }).click()
  await expect(page.getByText('Alterações prontas para revisão').first()).toBeVisible({ timeout: 40_000 })
})

test('Hoje mostra o cliente e o motivo em cada tarefa; teclado com foco visível', async ({ page }) => {
  await loginAs(page, /Rui Prado/)
  await expect(page.getByRole('heading', { name: 'O que fazer hoje' })).toBeVisible()
  await expect(page.getByText('Prefeitura de Vale do Ribeiro').first()).toBeVisible()
  await expect(page.getByText('Por quê:').first()).toBeVisible()
  await expect(page.getByText('Ambiente de demonstração — dados sintéticos')).toBeVisible()
  await page.keyboard.press('Tab')
  await expect(page.locator(':focus')).toBeVisible()
})
