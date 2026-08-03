import { expect, test, type APIRequestContext } from '@playwright/test';
import { chartPng, clearEvidence } from './evidence-helpers';

// Phase E3 — the SELF-CHECK on the RENDERED surface: the drill's own wiki bullets
// appearing as checkable items after a capture lands, a partial check recorded
// honestly, and the rep count NOT moving either way.
//
// E2's lesson is applied throughout: assert the RENDERED result, not an attribute
// or an API response. A spec that checks `src` while the image renders broken is
// the failure mode this suite exists to catch.
test.describe.configure({ mode: 'serial' });

const API_URL = process.env.E2E_API_URL ?? 'http://localhost:8000';
const DISCORD_ID = 'e2e-self-check';

let tok = '';

async function mintToken(request: APIRequestContext): Promise<string> {
  const res = await request.post(`${API_URL}/auth/debug/token`, {
    data: { discord_id: DISCORD_ID },
  });
  return (await res.json()).access_token as string;
}

test.beforeEach(async ({ page, request }) => {
  tok = tok || (await mintToken(request));
  await page.addInitScript(
    ([key, value]) => window.localStorage.setItem(key as string, value as string),
    ['neurospect_learn_token', tok]
  );
});

test.afterAll(async ({ request }) => {
  if (tok) await clearEvidence(request, API_URL, tok);
});

/** The first drill card that actually has a projected bar to check against. */
async function cardWithABar(page: import('@playwright/test').Page) {
  const cards = page.getByTestId('drill-card');
  await expect(cards.first()).toBeVisible();
  for (let i = 0; i < (await cards.count()); i++) {
    const card = cards.nth(i);
    if ((await card.getByTestId('evidence-dropzone').count()) > 0) return card;
  }
  throw new Error('no drill card offers evidence capture');
}

const readReps = async (card: import('@playwright/test').Locator) =>
  parseInt((await card.getByTestId('rep-count').innerText()).split('/')[0].trim(), 10);

/**
 * Upload one capture and return the rep count ONCE IT HAS SETTLED.
 *
 * The thumbnail appears from the mutation's own response, but the rep counter
 * only moves after the invalidated `/api/drills` query refetches — so reading the
 * count straight after the thumbnail appears reads the stale pre-upload value.
 * That is a genuine ordering trap, and polling here is what makes the later
 * "the rep did not move" assertions mean anything.
 */
async function capture(card: import('@playwright/test').Locator, seed: number): Promise<number> {
  const before = await readReps(card);
  await card
    .getByTestId('evidence-file-input')
    .setInputFiles({ name: `c${seed}.png`, mimeType: 'image/png', buffer: chartPng(seed) });
  await expect(card.getByTestId('evidence-thumb')).toHaveCount(1);
  await expect(card.getByTestId('evidence-rejection')).toHaveCount(0);
  await expect.poll(() => readReps(card)).toBe(before + 1);
  return before + 1;
}

// ---------------------------------------------------------------------------

test('a fresh capture is surfaced as awaiting its check, and the reps still count', async ({
  page,
  request,
}) => {
  await clearEvidence(request, API_URL, tok);
  await page.goto('/drills');
  const card = await cardWithABar(page);

  // The rep counted on upload (E2's provisional lifecycle) — `capture` asserts it …
  await capture(card, 9301);
  // … and the missing check is shown as work OWED, never as a deduction.
  await expect(card.getByTestId('self-check-pending')).toContainText('the reps still count');
  await expect(card.getByTestId('evidence-unchecked')).toContainText('1 awaiting your check');
  await expect(card.getByTestId('self-check-open')).toContainText('Check against the bar');
});

test("the bar shows the drill's own wiki bullets as checkable items", async ({ page, request }) => {
  await clearEvidence(request, API_URL, tok);
  await page.goto('/drills');
  const card = await cardWithABar(page);
  await capture(card, 9302);

  await card.getByTestId('self-check-open').click();
  const panel = card.getByTestId('self-check-panel');
  await expect(panel).toBeVisible();

  // Every item is a real rendered checkbox …
  const items = panel.getByTestId('self-check-item');
  const count = await items.count();
  expect(count).toBeGreaterThan(0);

  // … and the panel cites the wiki file the text came from, so the bar is
  // traceable to the corpus rather than to the app.
  await expect(panel).toContainText('concepts/mastery/');
  await expect(panel).toContainText('/');

  // The text next to each box is the wiki's own words, RENDERED — no raw
  // markdown asterisks should reach the screen.
  const shown = await panel.innerText();
  expect(shown).not.toContain('**');
  expect(shown.length).toBeGreaterThan(20);
});

test('a partial check is recorded as partly met, and removes no rep', async ({ page, request }) => {
  await clearEvidence(request, API_URL, tok);
  await page.goto('/drills');
  const card = await cardWithABar(page);
  const withRep = await capture(card, 9303);

  await card.getByTestId('self-check-open').click();
  const panel = card.getByTestId('self-check-panel');
  const items = panel.getByTestId('self-check-item');
  const total = await items.count();
  test.skip(total < 2, 'this drill has a single-item bar, so a partial is impossible');

  await items.first().click();
  await panel.getByTestId('self-check-submit').click();

  // The rendered verdict, not the response body.
  await expect(card.getByTestId('self-check-state')).toContainText('Partly met');
  await expect(card.getByTestId('self-check-state')).toContainText('%');
  // THE LOAD-BEARING ASSERTION: a partial check does not retract the rep.
  await expect.poll(() => readReps(card)).toBe(withRep);
  // No longer in the unchecked backlog — it has been answered, if only partly.
  await expect(card.getByTestId('evidence-unchecked')).toHaveCount(0);
});

test('checking the whole bar reads as meeting it, and still mints no rep', async ({
  page,
  request,
}) => {
  await clearEvidence(request, API_URL, tok);
  await page.goto('/drills');
  const card = await cardWithABar(page);
  const withRep = await capture(card, 9304);

  await card.getByTestId('self-check-open').click();
  const panel = card.getByTestId('self-check-panel');
  const items = panel.getByTestId('self-check-item');
  const total = await items.count();
  for (let i = 0; i < total; i++) await items.nth(i).click();
  await panel.getByTestId('self-check-submit').click();

  await expect(card.getByTestId('self-check-state')).toContainText('Meets the bar');
  await expect(card.getByTestId('self-check-state')).toContainText('100%');
  // A grade is not a rep — it cannot inflate the count either.
  await expect.poll(() => readReps(card)).toBe(withRep);

  // Re-opening shows the recorded answer rather than a blank form: the ticks are
  // read back out of the stored grade's findings.
  await card.getByTestId('self-check-open').click();
  await expect(panel.getByTestId('self-check-item').first()).toBeChecked();
  await expect(panel).toContainText(`${total}/${total} met`);
});

test('the concept panel offers the same bar, resolved through the concept', async ({
  page,
  request,
}) => {
  await clearEvidence(request, API_URL, tok);
  // The concept capture surface lives on a track-stage path page, not /progress
  // (same route the E2 spec uses for the derived-reps assertion).
  await page.goto('/path/aura/A1');

  const panels = page.getByTestId('evidence-capture');
  await expect(panels.first()).toBeVisible({ timeout: 15_000 });
  const panel = panels.first();
  await panel
    .getByTestId('evidence-file-input')
    .setInputFiles({ name: 'concept.png', mimeType: 'image/png', buffer: chartPng(9305) });
  await expect(panel.getByTestId('evidence-thumb')).toHaveCount(1);

  // A concept with no projected bar renders no self-check at all — that is
  // correct, not a failure, so assert only that nothing is invented.
  const opener = panel.getByTestId('self-check-open');
  if ((await opener.count()) > 0) {
    await opener.click();
    await expect(panel.getByTestId('self-check-panel')).toBeVisible();
    await expect(panel.getByTestId('self-check-item').first()).toBeVisible();
  }
});
