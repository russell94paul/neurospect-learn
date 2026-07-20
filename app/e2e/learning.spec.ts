import { expect, test } from '@playwright/test';

// Phase 5e-1 — progress foundation. These specs pin the UI wiring of the
// progress/stage/drill surfaces that was manually verified when 5e-1 shipped.
// They share the single 'e2e' debug user (see global-setup), so they run
// SERIALLY to avoid racing on that user's progress rows.
test.describe.configure({ mode: 'serial' });

const API_URL = process.env.E2E_API_URL ?? 'http://localhost:8000';

async function token(request: import('@playwright/test').APIRequestContext) {
  const res = await request.post(`${API_URL}/auth/debug/token`, {
    data: { discord_id: 'e2e' },
  });
  return (await res.json()).access_token as string;
}

async function conceptId(
  request: import('@playwright/test').APIRequestContext,
  tok: string,
  slug: string
) {
  const res = await request.get(`${API_URL}/api/progress`, {
    headers: { Authorization: `Bearer ${tok}` },
  });
  const rows = (await res.json()) as Array<{ slug: string; concept_id: string; rep_target_count: number | null }>;
  return rows.find((r) => r.slug === slug)!;
}

async function patchProgress(
  request: import('@playwright/test').APIRequestContext,
  tok: string,
  body: Record<string, unknown>
) {
  return request.patch(`${API_URL}/api/progress`, {
    headers: { Authorization: `Bearer ${tok}` },
    data: body,
  });
}

test('path renders the U0–U6 spine with stages + watch-only frontier', async ({ page }) => {
  await page.goto('/path');
  await expect(page.getByRole('heading', { name: 'The Path' })).toBeVisible();
  // The seven stage nodes link to their detail pages.
  for (const s of ['U0', 'U1', 'U2', 'U3', 'U4', 'U5', 'U6']) {
    await expect(page.locator(`a[href="/path/${s}"]`)).toBeVisible();
  }
  // U5 is the watch-only frontier stage.
  await expect(page.locator('a[href="/path/U5"]').getByText('watch-only')).toBeVisible();
});

test('editing progress on the reader persists across reload', async ({ page }) => {
  // u1-3 (double-qualified swing) → content page ict-market-structure; its rep
  // target is qualitative ("score by hand"), so Can-mark needs only confidence.
  await page.goto('/concepts/ict-market-structure');
  await expect(page.getByText('Track this')).toBeVisible();

  await page.getByLabel(/^Confidence 3/).click();
  await page.getByRole('button', { name: /2 · Can-mark/ }).click();
  await page.getByRole('button', { name: 'Save' }).click();
  await expect(page.getByText('Saved')).toBeVisible();

  await page.reload();
  // Confidence summary text is unambiguous (only rendered from persisted state).
  await expect(page.getByText('3 · usually right')).toBeVisible();
});

test('stage exit-bar flips with concept_progress', async ({ page, request }) => {
  const tok = await token(request);
  // Seed all five U1 primitives to Can-mark + conf 3 + reps ≥ target via the API
  // (rep floors up to 50 make clicking impractical), then assert the UI gate.
  const res = await request.get(`${API_URL}/api/progress`, {
    headers: { Authorization: `Bearer ${tok}` },
  });
  const rows = (await res.json()) as Array<{
    slug: string;
    concept_id: string;
    u_stage: string;
    is_core: boolean;
    rep_target_count: number | null;
  }>;
  const u1 = rows.filter((r) => r.u_stage === 'U1' && r.is_core);
  for (const c of u1) {
    await patchProgress(request, tok, {
      concept_id: c.concept_id,
      ladder_stage: 2,
      confidence: 3,
      reps: c.rep_target_count ?? 0,
    });
  }

  await page.goto('/path/U1');
  await expect(page.getByText('Exit bar met').first()).toBeVisible();

  // Drop one primitive back to Learned → the gate is no longer met.
  await patchProgress(request, tok, { concept_id: u1[0].concept_id, ladder_stage: 1 });
  await page.goto('/path/U1');
  await expect(page.getByText('Exit bar not met')).toBeVisible();
});

test('drill mark (reps) persists across reload', async ({ page }) => {
  await page.goto('/drills');
  const card = page.getByTestId('drill-card').first();
  await expect(card).toBeVisible();

  const readReps = async () => {
    const txt = await card.getByTestId('rep-count').innerText();
    return parseInt(txt.split('/')[0].trim(), 10);
  };
  const before = await readReps();
  await card.getByRole('button', { name: 'Increase reps' }).click();
  await expect(card.getByTestId('rep-count')).toContainText(String(before + 1));

  await page.reload();
  expect(await readReps()).toBe(before + 1);
});
