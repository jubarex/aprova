import { expect, type Page, type APIRequestContext } from '@playwright/test'

export async function resetDemo(request: APIRequestContext) {
  const s = await request.post('/api/demo/session', { data: { actor_id: 'act_rui' } })
  const token = (await s.json()).token as string
  const r = await request.post('/api/demo/reset', {
    data: { confirm: 'RESETAR' },
    headers: { 'X-Demo-Token': token, 'Idempotency-Key': `reset-${Date.now()}` },
  })
  expect(r.ok()).toBeTruthy()
}

export async function loginAs(page: Page, name: RegExp) {
  await page.goto('/')
  const sair = page.getByRole('button', { name: /Trocar persona|Sair/ })
  if (await sair.isVisible().catch(() => false)) {
    await sair.click()
  }
  await page.getByRole('button', { name }).click()
  await page.waitForLoadState('networkidle')
}

export async function startScenario(page: Page, title: RegExp): Promise<string> {
  await page.goto('/settings/demo')
  await page.locator('li', { hasText: title }).getByRole('button', { name: 'Iniciar' }).click()
  await page.waitForURL(/\/processes\//)
  return page.url()
}

export async function openTab(page: Page, name: string | RegExp) {
  await page.getByRole('tab', { name }).click()
}
