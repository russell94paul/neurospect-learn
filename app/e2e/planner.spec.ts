import { expect, test, type APIRequestContext } from '@playwright/test';

// Phase 5e-3 — Study Planner UI. These specs pin the prescriptive Today view,
// the mark-done → progress feed, the logged skip, the calendar, and regenerate.
// They run SERIALLY and against their OWN isolated debug user (injected via
// addInitScript) so they never race with learning.spec on the shared 'e2e' user.
test.describe.configure({ mode: 'serial' });

const API_URL = process.env.E2E_API_URL ?? 'http://localhost:8000';
const TOKEN_KEY = 'neurospect_learn_token'; // must match app/src/lib/api.ts
const DISCORD_ID = 'e2e-planner-5e3';

let plannerToken = '';

async function mintToken(request: APIRequestContext): Promise<string> {
  const res = await request.post(`${API_URL}/auth/debug/token`, { data: { discord_id: DISCORD_ID } });
  return (await res.json()).access_token as string;
}

function authed(tok: string) {
  return { headers: { Authorization: `Bearer ${tok}` } };
}

test.beforeAll(async ({ request }) => {
  plannerToken = await mintToken(request);
});

test.beforeEach(async ({ page }) => {
  // Override the shared storageState token with this suite's isolated user.
  await page.addInitScript(
    ([k, v]) => window.localStorage.setItem(k as string, v as string),
    [TOKEN_KEY, plannerToken]
  );
});

test('setup form saves prefs → Today renders a prescriptive ordered plan', async ({ page }) => {
  await page.goto('/plan/setup');
  await expect(page.getByRole('heading', { name: /Availability/ })).toBeVisible();

  // Defaults are pre-filled, but they are WEEKDAY minutes — the form ships
  // `sun_minutes: 0` ("0 = a day off"). A plan for a zero-capacity day is
  // correctly EMPTY, so relying on the defaults made this spec fail every Sunday.
  // Give TODAY explicit capacity so the assertion below is date-independent.
  const todayKey = ['sun', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat'][new Date().getDay()];
  await page.locator(`#${todayKey}_minutes`).fill('45');

  await page.getByRole('button', { name: 'Save & generate plan' }).click();

  // Lands on Today with an ordered, non-empty plan.
  await expect(page).toHaveURL(/\/today$/);
  await expect(page.getByRole('heading', { name: 'Today' })).toBeVisible();
  await expect(page.getByText('Do these, in order')).toBeVisible();
  const items = page.getByTestId('plan-item');
  await expect(items.first()).toBeVisible();
  expect(await items.count()).toBeGreaterThan(0);
});

test('marking an item done updates adherence AND feeds progress', async ({ page, request }) => {
  await page.goto('/today');
  const first = page.getByTestId('plan-item').first();
  await expect(first).toBeVisible();

  await first.getByRole('button', { name: 'Mark done' }).click();
  // The card reflects the done status (invalidate → refetch).
  await expect(first).toHaveAttribute('data-status', 'done');

  // Adherence surfaces at least one done item.
  const meter = page.getByTestId('adherence-meter');
  await expect(meter).toContainText('done');

  // Progress fed: the done item wrote last_practiced onto its concept row.
  const res = await request.get(`${API_URL}/api/progress?track=aura`, authed(plannerToken));
  const rows = (await res.json()) as Array<{ last_practiced: string | null; reps: number }>;
  expect(rows.some((r) => r.last_practiced != null || r.reps > 0)).toBeTruthy();
});

test('skipping an item logs a SKIP (adherence, never hidden)', async ({ page }) => {
  await page.goto('/today');
  // Skip a still-pending item (the done one from the prior test is excluded).
  const pending = page.getByTestId('plan-item').filter({ has: page.locator('[data-status="pending"]') });
  const target = (await pending.count()) > 0 ? pending.first() : page.getByTestId('plan-item').nth(1);
  await target.getByRole('button', { name: 'Skip' }).click();
  await expect(target).toHaveAttribute('data-status', 'skipped');

  await expect(page.getByTestId('adherence-meter')).toContainText('skipped');
});

test('calendar shows today with its scheduled items', async ({ page }) => {
  await page.goto('/plan');
  await expect(page.getByTestId('study-calendar')).toBeVisible();
  const todayCell = page.getByTestId('calendar-today');
  await expect(todayCell).toBeVisible();
  // Today has materialized items → a count + at least one status dot.
  await expect(todayCell.locator('span.rounded-full').first()).toBeVisible();
});

test('regenerate bumps plan_version', async ({ page, request }) => {
  const before = (await (await request.get(`${API_URL}/api/plan/today`, authed(plannerToken))).json())
    .plan_version as number;

  await page.goto('/plan');
  await page.getByRole('button', { name: 'Regenerate' }).click();

  await expect(async () => {
    const after = (await (await request.get(`${API_URL}/api/plan/today`, authed(plannerToken))).json())
      .plan_version as number;
    expect(after).toBeGreaterThan(before);
  }).toPass();
});
