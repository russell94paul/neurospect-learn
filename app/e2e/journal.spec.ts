import { expect, test, type APIRequestContext } from '@playwright/test';

// Phase 5f — Journal + expectancy. These specs pin the create → list → feed
// flow, the mode filter, and that the expectancy charts render per-model bars
// (backtest vs live). They run SERIALLY against their OWN isolated debug user
// (injected via addInitScript) so they never race with the other suites.
test.describe.configure({ mode: 'serial' });

const API_URL = process.env.E2E_API_URL ?? 'http://localhost:8000';
const TOKEN_KEY = 'neurospect_learn_token'; // must match app/src/lib/api.ts
const DISCORD_ID = 'e2e-journal-5f';

let token = '';

async function mintToken(request: APIRequestContext): Promise<string> {
  const res = await request.post(`${API_URL}/auth/debug/token`, { data: { discord_id: DISCORD_ID } });
  return (await res.json()).access_token as string;
}

function authed(tok: string) {
  return { headers: { Authorization: `Bearer ${tok}` } };
}

/** Delete every existing entry for the test user so the suite is rerunnable. */
async function clearJournal(request: APIRequestContext, tok: string) {
  const res = await request.get(`${API_URL}/api/journal`, authed(tok));
  const entries = (await res.json()) as Array<{ id: string }>;
  for (const e of entries) {
    await request.delete(`${API_URL}/api/journal/${e.id}`, authed(tok));
  }
}

test.beforeAll(async ({ request }) => {
  token = await mintToken(request);
  await clearJournal(request, token);
});

test.beforeEach(async ({ page }) => {
  await page.addInitScript(
    ([k, v]) => window.localStorage.setItem(k as string, v as string),
    [TOKEN_KEY, token]
  );
});

test('create a backtest entry → it appears in the list and feeds expectancy', async ({ page }) => {
  await page.goto('/journal/new');
  await expect(page.getByRole('heading', { name: 'New entry' })).toBeVisible();

  // Mode defaults to backtest; fill the identity + a realized R (entry_model
  // stays the default "unified").
  await page.getByLabel('Instrument', { exact: true }).fill('NQ');
  await page.getByRole('tab', { name: /Execution/ }).click();
  await page.getByLabel('Realized R', { exact: true }).fill('2');
  await page.getByRole('button', { name: 'Create entry' }).click();

  // Lands on the list with the new backtest card.
  await expect(page).toHaveURL(/\/journal$/);
  const card = page.getByTestId('journal-card').first();
  await expect(card).toBeVisible();
  await expect(card).toHaveAttribute('data-mode', 'backtest');
  await expect(card).toContainText('NQ');
  await expect(card).toContainText('+2.00R');

  // Feeds the expectancy view: the unified/backtest row shows +2.00R expectancy.
  await page.goto('/expectancy');
  await expect(page.getByRole('heading', { name: 'Expectancy' })).toBeVisible();
  await expect(page.getByText('expectancy / trade').first()).toBeVisible();
  await expect(page.locator('table')).toContainText('Unified');
  await expect(page.locator('table')).toContainText('+2.00R');
});

test('filter by mode narrows the list', async ({ page }) => {
  // Add a LIVE entry (toggle the mode, different instrument + a losing R).
  await page.goto('/journal/new');
  await page.getByRole('button', { name: 'live', exact: true }).click();
  await page.getByLabel('Instrument', { exact: true }).fill('ES');
  await page.getByRole('tab', { name: /Execution/ }).click();
  await page.getByLabel('Realized R', { exact: true }).fill('-1');
  await page.getByRole('button', { name: 'Create entry' }).click();
  await expect(page).toHaveURL(/\/journal$/);

  // Both entries present initially.
  await expect(page.getByTestId('journal-card')).toHaveCount(2);

  // Filter to LIVE → only the ES/live entry.
  await page.getByRole('combobox', { name: 'Filter by mode' }).click();
  await page.getByRole('option', { name: 'Live' }).click();
  await expect(page.getByTestId('journal-card')).toHaveCount(1);
  await expect(page.getByTestId('journal-card').first()).toContainText('ES');

  // Filter to BACKTEST → only the NQ/backtest entry.
  await page.getByRole('combobox', { name: 'Filter by mode' }).click();
  await page.getByRole('option', { name: 'Backtest' }).click();
  await expect(page.getByTestId('journal-card')).toHaveCount(1);
  await expect(page.getByTestId('journal-card').first()).toContainText('NQ');
});

test('expectancy charts render per-model bars, backtest vs live', async ({ page }) => {
  await page.goto('/expectancy');
  await expect(page.getByRole('heading', { name: 'Expectancy' })).toBeVisible();

  // Both summary tiles.
  await expect(page.getByText('Backtest', { exact: true }).first()).toBeVisible();
  await expect(page.getByText('Live', { exact: true }).first()).toBeVisible();

  // The two named charts + the R distribution render an SVG with bar rects.
  await expect(page.getByText('Expectancy by model (R)')).toBeVisible();
  await expect(page.getByText('Win rate — backtest vs live')).toBeVisible();
  const surfaces = page.locator('svg.recharts-surface');
  await expect(surfaces.first()).toBeVisible();
  await expect(page.locator('.recharts-bar-rectangle').first()).toBeVisible();
});
