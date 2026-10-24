import os from 'node:os'
import path from 'node:path'
import { defineConfig } from '@playwright/test'

// E2E em banco e anexos isolados: nunca toca a demonstração em uso.
const run = `${Date.now()}`
const tmp = path.join(os.tmpdir(), `aprova-e2e-${run}`)
const API = 8100
const WEB = 5174

export default defineConfig({
  testDir: './e2e',
  timeout: 90_000,
  expect: { timeout: 20_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [['list'], ['html', { open: 'never', outputFolder: '../artifacts/e2e-report' }]],
  use: { baseURL: `http://127.0.0.1:${WEB}`, trace: 'retain-on-failure', screenshot: 'only-on-failure', locale: 'pt-BR' },
  webServer: [
    {
      command: `uv run uvicorn app.api.main:get_app --factory --host 127.0.0.1 --port ${API}`,
      cwd: '../backend',
      url: `http://127.0.0.1:${API}/api/health`,
      env: { APP_ENV: 'demo', DATABASE_URL: `sqlite:///${path.join(tmp, 'e2e.db').replace(/\\/g, '/')}`, ATTACHMENT_DIR: path.join(tmp, 'att') },
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      command: 'npm run dev',
      url: `http://127.0.0.1:${WEB}`,
      env: { WEB_PORT: String(WEB), VITE_API_TARGET: `http://127.0.0.1:${API}` },
      reuseExistingServer: false,
      timeout: 60_000,
    },
  ],
})
