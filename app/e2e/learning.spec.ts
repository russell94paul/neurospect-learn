import { expect, test } from '@playwright/test';

// Phase 5e-1b — multi-track curriculum. These specs pin the UI wiring of the
// track switcher, the per-track curriculum unit (Read → Drill → Track → Gate),
// per-track progress isolation, and the cross-track "Also taught in" links.
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

test('track switcher shows each track its own gated spine', async ({ page }) => {
  await page.goto('/path');
  await expect(page.getByRole('heading', { name: 'The Path' })).toBeVisible();

  // Default track = Aura → A0…A6 stage nodes.
  await expect(page.locator('a[href="/path/aura/A0"]')).toBeVisible();

  // Switch to AXL → its M0…M8 spine.
  await page.getByRole('tab', { name: 'AXL' }).click();
  await expect(page.locator('a[href="/path/ict_course/M0"]')).toBeVisible();
  await expect(page.locator('a[href="/path/ict_course/M8"]')).toBeVisible();

  // Switch to Unified → U0…U6 with the watch-only frontier (U5).
  await page.getByRole('tab', { name: 'Unified' }).click();
  await expect(page.locator('a[href="/path/unified/U0"]')).toBeVisible();
  await expect(page.locator('a[href="/path/unified/U5"]').getByText('watch-only')).toBeVisible();
});

test('curriculum unit renders Read → Drill → Track → Gate', async ({ page }) => {
  await page.goto('/path/aura/A1');
  await expect(page.getByRole('heading', { name: 'The three structural primitives' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Read' })).toBeVisible();
  await expect(page.getByRole('heading', { name: /^Drill/ })).toBeVisible();
  await expect(page.getByRole('heading', { name: /Track your progress/ })).toBeVisible();
  await expect(page.getByText('Gate — exit bar')).toBeVisible();
  // Read links resolve to a content page; the Track section has concept panels.
  await expect(page.locator('a[href="/concepts/swing-points"]')).toBeVisible();
  await expect(page.getByText('Track this').first()).toBeVisible();
});

test('editing progress on the reader persists across reload', async ({ page }) => {
  // u1-3 (double-qualified swing) → content page ict-market-structure; its rep
  // target is qualitative ("score by hand"), so Can-mark needs only confidence.
  await page.goto('/concepts/ict-market-structure');
  await expect(page.getByText('Track this').first()).toBeVisible();

  await page.getByLabel(/^Confidence 3/).click();
  await page.getByRole('button', { name: /2 · Can-mark/ }).click();
  await page.getByRole('button', { name: 'Save' }).click();
  await expect(page.getByText('Saved')).toBeVisible();

  await page.reload();
  await expect(page.getByText('3 · usually right')).toBeVisible();
});

test('stage exit-bar flips with concept_progress (per-track isolation)', async ({ page, request }) => {
  const tok = await token(request);
  const res = await request.get(`${API_URL}/api/progress?track=unified`, {
    headers: { Authorization: `Bearer ${tok}` },
  });
  const rows = (await res.json()) as Array<{
    slug: string;
    concept_id: string;
    stage_code: string | null;
    is_core: boolean;
    rep_target_count: number | null;
  }>;
  const u1 = rows.filter((r) => r.stage_code === 'U1' && r.is_core);
  for (const c of u1) {
    await patchProgress(request, tok, {
      concept_id: c.concept_id,
      ladder_stage: 2,
      confidence: 3,
      reps: c.rep_target_count ?? 0,
    });
  }

  await page.goto('/path/unified/U1');
  await expect(page.getByText('Exit bar met').first()).toBeVisible();

  // The equivalent Aura stage (A1) must be UNAFFECTED — separate progress rows.
  await page.goto('/path/aura/A1');
  await expect(page.getByText('Exit bar not met')).toBeVisible();

  // Drop one unified primitive back to Learned → the U1 gate is no longer met.
  await patchProgress(request, tok, { concept_id: u1[0].concept_id, ladder_stage: 1 });
  await page.goto('/path/unified/U1');
  await expect(page.getByText('Exit bar not met')).toBeVisible();
});

test('cross-track "Also taught in" link jumps to the other track', async ({ page }) => {
  await page.goto('/path/unified/U1');
  // u1-1 liquidity/draw cross-links to the Aura swing-points concept (A1).
  const link = page.locator('a[href="/path/aura/A1"]', { hasText: 'Aura' }).first();
  await expect(link).toBeVisible();
  await link.click();
  await expect(page).toHaveURL(/\/path\/aura\/A1$/);
  await expect(page.getByRole('heading', { name: 'The three structural primitives' })).toBeVisible();
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
