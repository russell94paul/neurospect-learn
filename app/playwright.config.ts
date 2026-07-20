import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright E2E config for neurospect-learn (introduced in Phase 5d).
 *
 * Prereqs to run locally:
 *   1. The API is up with the 5d schema + seed + ingested content
 *      (default http://localhost:8000; override with E2E_API_URL).
 *   2. DEBUG=true on the API (global-setup mints a debug token).
 * The frontend dev server is started automatically by `webServer` below and is
 * pointed at the same API. Run:  npm run test:e2e
 */

const BASE_URL = process.env.E2E_BASE_URL ?? 'http://localhost:5173';
const API_URL = process.env.E2E_API_URL ?? 'http://localhost:8000';

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? 'github' : 'list',
  globalSetup: './e2e/global-setup.ts',

  use: {
    baseURL: BASE_URL,
    storageState: './e2e/.auth/state.json', // authenticated via global-setup
    trace: 'on-first-retry',
  },

  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],

  webServer: {
    command: 'npm run dev -- --port 5173 --strictPort',
    url: BASE_URL,
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
    env: { VITE_API_URL: API_URL, VITE_DEBUG: 'true' },
  },
});
