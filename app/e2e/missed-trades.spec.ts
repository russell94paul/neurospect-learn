import { expect, test, type APIRequestContext } from '@playwright/test';

// Phase 6b/6c — the missed-trade log, its opportunity-cost surface, and
// `position_size`. These specs pin the rendered surfaces AND the invariant that
// makes the feature safe: writing a missed trade or a position size must not move
// a single number on /expectancy.
//
// Serial, against their OWN isolated debug user (injected via addInitScript) so
// they never race with the other suites.
test.describe.configure({ mode: 'serial' });

const API_URL = process.env.E2E_API_URL ?? 'http://localhost:8000';
const TOKEN_KEY = 'neurospect_learn_token'; // must match app/src/lib/api.ts
const DISCORD_ID = 'e2e-missed-6b';

let token = '';

function authed(tok: string) {
  return { headers: { Authorization: `Bearer ${tok}` } };
}

async function clearAll(request: APIRequestContext, tok: string) {
  for (const path of ['journal', 'missed-trades'] as const) {
    const res = await request.get(`${API_URL}/api/${path}`, authed(tok));
    for (const row of (await res.json()) as Array<{ id: string }>) {
      await request.delete(`${API_URL}/api/${path}/${row.id}`, authed(tok));
    }
  }
}

/** The full expectancy surface as JSON — the thing that must not move. */
async function expectancySnapshot(request: APIRequestContext, tok: string) {
  const parts = await Promise.all(
    ['expectancy', 'summary', 'r-distribution'].map((p) =>
      request.get(`${API_URL}/api/analytics/${p}`, authed(tok)).then((r) => r.json())
    )
  );
  return JSON.stringify(parts);
}

test.beforeAll(async ({ request }) => {
  const res = await request.post(`${API_URL}/auth/debug/token`, {
    data: { discord_id: DISCORD_ID },
  });
  token = (await res.json()).access_token as string;
  await clearAll(request, token);
  // One executed backtest trade so /expectancy has a real number to protect.
  await request.post(`${API_URL}/api/journal`, {
    ...authed(token),
    data: {
      entry_date: '2026-07-20', instrument: 'NQ', mode: 'backtest',
      entry_model: 'london', r_multiple: 2.0, rr_planned: 2.0,
    },
  });
});

test.beforeEach(async ({ page }) => {
  await page.addInitScript(
    ([k, v]) => window.localStorage.setItem(k as string, v as string),
    [TOKEN_KEY, token]
  );
});

test('the journal has a missed tab, and logging a miss shows opportunity cost', async ({
  page,
  request,
}) => {
  const before = await expectancySnapshot(request, token);

  await page.goto('/journal');
  await page.getByRole('tab', { name: /Missed/ }).click();
  await expect(page).toHaveURL(/tab=missed/);
  await expect(page.getByText(/may hold your biggest breakthrough/)).toBeVisible();

  await page.getByRole('link', { name: /Log a miss/ }).first().click();
  await expect(page.getByRole('heading', { name: 'Log a missed trade' })).toBeVisible();

  // Dante's category: a canceled order that would have LOST → protective.
  await page.getByRole('button', { name: 'Canceled a working order' }).click();
  await page.getByLabel('Instrument', { exact: true }).fill('NQ');
  await page.getByRole('button', { name: '+ pulled_on_spike' }).click();
  await page.getByLabel('Hypothetical R', { exact: true }).fill('-1.5');
  await page.getByRole('button', { name: 'Log the miss' }).click();

  // Back on the missed tab with the card + the opportunity-cost panel.
  await expect(page).toHaveURL(/\/journal\?tab=missed/);
  const card = page.getByTestId('missed-card').first();
  await expect(card).toBeVisible();
  await expect(card).toHaveAttribute('data-miss-type', 'canceled');
  await expect(card).toContainText('-1.50R');
  await expect(card).toContainText('pulled_on_spike');

  const panel = page.getByTestId('opportunity-cost');
  await expect(panel).toBeVisible();
  await expect(panel).toContainText('standing down was protective');
  await expect(panel).toContainText('-1.50R');

  // THE INVARIANT: a trade never taken changes nothing on /expectancy.
  expect(await expectancySnapshot(request, token)).toBe(before);
  await page.goto('/expectancy');
  await expect(page.locator('table')).toContainText('+2.00R');
});

test('a missed winner reads as forgone R and the log filters by miss type', async ({ page }) => {
  await page.goto('/journal?tab=missed');
  await page.getByRole('link', { name: /Log a miss/ }).first().click();
  await page.getByRole('button', { name: 'Hesitated at the trigger' }).click();
  await page.getByLabel('Instrument', { exact: true }).fill('ES');
  await page.getByLabel('Hypothetical R', { exact: true }).fill('3');
  await page.getByRole('button', { name: 'Log the miss' }).click();

  await expect(page.getByTestId('missed-card')).toHaveCount(2);
  const panel = page.getByTestId('opportunity-cost');
  await expect(panel).toContainText('hesitation is costing you'); // net +1.5R
  await expect(panel).toContainText('+1.50R');

  // Filter to the canceled ones only.
  await page.getByRole('combobox', { name: 'Filter by miss type' }).click();
  await page.getByRole('option', { name: 'Canceled a working order' }).click();
  await expect(page.getByTestId('missed-card')).toHaveCount(1);
  await expect(page.getByTestId('missed-card').first()).toContainText('NQ');
});

test('resolving a miss later updates the opportunity cost', async ({ page }) => {
  await page.goto('/journal?tab=missed');
  await page.getByRole('link', { name: /Log a miss/ }).first().click();
  await page.getByRole('button', { name: 'Almost took it' }).click();
  await page.getByLabel('Instrument', { exact: true }).fill('YM');
  await page.getByRole('button', { name: 'Log the miss' }).click();

  // Logged unresolved — counted, but not in the sums.
  const unresolved = page.getByTestId('missed-card').filter({ hasText: 'YM' }).first();
  await expect(unresolved).toContainText('unresolved');
  await expect(page.getByTestId('opportunity-cost')).toContainText('still to resolve');

  // Resolve it: +1R forgone → net moves from +1.50R to +2.50R.
  await unresolved.click();
  await expect(page.getByRole('heading', { name: 'Edit missed trade' })).toBeVisible();
  await page.getByLabel('Hypothetical R', { exact: true }).fill('1');
  await page.getByRole('button', { name: 'Save changes' }).click();
  await expect(page.getByTestId('opportunity-cost')).toContainText('+2.50R');
});

test('position size is recorded on a journal entry without moving expectancy', async ({
  page,
  request,
}) => {
  const before = await expectancySnapshot(request, token);

  await page.goto('/journal');
  await page.getByTestId('journal-card').first().click();
  await expect(page.getByRole('heading', { name: 'Edit entry' })).toBeVisible();
  await page.getByRole('tab', { name: /Execution/ }).click();
  await page.getByLabel('Position size', { exact: true }).fill('3');
  await page.getByRole('button', { name: 'Save changes' }).click();
  await expect(page).toHaveURL(/\/journal$/);

  // It round-trips…
  await page.getByTestId('journal-card').first().click();
  await page.getByRole('tab', { name: /Execution/ }).click();
  await expect(page.getByLabel('Position size', { exact: true })).toHaveValue('3');

  // …and expectancy is untouched (it stays R-based).
  expect(await expectancySnapshot(request, token)).toBe(before);
});

test('/expectancy states that untaken trades are excluded and links to the log', async ({ page }) => {
  await page.goto('/expectancy');
  await expect(page.getByText(/Trades you didn't take are excluded/)).toBeVisible();
  await page.getByRole('link', { name: /missed & canceled log/ }).click();
  await expect(page).toHaveURL(/tab=missed/);
  await expect(page.getByTestId('opportunity-cost')).toBeVisible();
});
