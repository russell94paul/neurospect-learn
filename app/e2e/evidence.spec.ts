import { expect, test, type APIRequestContext } from '@playwright/test';
import { chartPng, clearEvidence } from './evidence-helpers';

// Phase E2 — the evidence layer on the RENDERED surfaces: paste-first capture on
// a drill, the refusal reason shown inline, evidence moving the rep count, and
// the two inherited debts (journal + missed-trade screenshots) attaching to the
// same layer. These share one dedicated debug user, so they run SERIALLY.
test.describe.configure({ mode: 'serial' });

const API_URL = process.env.E2E_API_URL ?? 'http://localhost:8000';
const DISCORD_ID = 'e2e-evidence';

let tok = '';

async function mintToken(request: APIRequestContext): Promise<string> {
  const res = await request.post(`${API_URL}/auth/debug/token`, {
    data: { discord_id: DISCORD_ID },
  });
  return (await res.json()).access_token as string;
}

const authed = () => ({ headers: { Authorization: `Bearer ${tok}` } });

/** Point the browser at this spec's own user so it never races the shared one. */
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

// ---------------------------------------------------------------------------
// Paste-first capture (Paul's decision #4 — desktop TradingView, so Ctrl+V)
// ---------------------------------------------------------------------------

test('pasting a capture onto a drill card creates the rep', async ({ page, request }) => {
  await clearEvidence(request, API_URL, tok);
  await page.goto('/drills');

  const card = page.getByTestId('drill-card').first();
  await expect(card).toBeVisible();
  const zone = card.getByTestId('evidence-dropzone');
  await expect(zone).toBeVisible();
  await expect(zone).toContainText('Ctrl');

  const readReps = async () =>
    parseInt((await card.getByTestId('rep-count').innerText()).split('/')[0].trim(), 10);
  const before = await readReps();

  // Focus the zone, then fire a real paste carrying an image file — exactly what
  // Ctrl+V after a TradingView snapshot delivers. The handler is focus-scoped
  // (there is one zone per drill card, so a page-wide paste would be ambiguous),
  // hence the explicit focus() inside the evaluate rather than relying on the
  // click having landed.
  await zone.click();
  await zone.evaluate((el, b64) => {
    (el as HTMLElement).focus();
    const bytes = Uint8Array.from(atob(b64 as string), (ch) => ch.charCodeAt(0));
    const file = new File([bytes], 'snapshot.png', { type: 'image/png' });
    const dt = new DataTransfer();
    dt.items.add(file);
    el.dispatchEvent(new ClipboardEvent('paste', { clipboardData: dt, bubbles: true }));
  }, chartPng(9001).toString('base64'));

  await expect(card.getByTestId('evidence-thumb')).toHaveCount(1);
  await expect.poll(readReps).toBe(before + 1);

  // The thumbnail renders from the signed local URL — no bucket configured. And
  // it must ACTUALLY LOAD: asserting only the `src` attribute passed while the
  // image rendered broken, because the local backend's URL is app-relative and
  // resolved against the SPA origin instead of the API.
  const img = card.getByTestId('evidence-thumb').locator('img');
  const src = await img.getAttribute('src');
  expect(src).toContain('/api/evidence/file?token=');
  expect(src).toContain(API_URL);
  await expect
    .poll(() => img.evaluate((el) => (el as HTMLImageElement).naturalWidth))
    .toBeGreaterThan(0);
});

test('a capture can claim several reps at once', async ({ page, request }) => {
  await clearEvidence(request, API_URL, tok);
  await page.goto('/drills');
  const card = page.getByTestId('drill-card').first();
  const readReps = async () =>
    parseInt((await card.getByTestId('rep-count').innerText()).split('/')[0].trim(), 10);
  await expect(card.getByTestId('evidence-thumb')).toHaveCount(0);
  const before = await readReps();

  await card.getByTestId('reps-claimed').fill('10');
  await expect(card.getByTestId('reps-claimed')).toHaveValue('10');
  await card
    .getByTestId('evidence-file-input')
    .setInputFiles({ name: 'ten.png', mimeType: 'image/png', buffer: chartPng(9002) });

  await expect(card.getByTestId('evidence-thumb')).toHaveCount(1);
  await expect(card.getByTestId('evidence-rejection')).toHaveCount(0);
  await expect.poll(readReps).toBe(before + 10);
  await expect(card.getByTestId('evidence-count')).toContainText('10 reps');
});

test('a non-image upload is refused with the reason on screen', async ({ page, request }) => {
  await clearEvidence(request, API_URL, tok);
  await page.goto('/drills');
  const card = page.getByTestId('drill-card').first();
  await card.getByTestId('evidence-file-input').setInputFiles({
    name: 'notes.txt',
    mimeType: 'text/plain',
    buffer: Buffer.from('I definitely marked 50 ranges, trust me.'.repeat(40)),
  });
  await expect(card.getByTestId('evidence-rejection')).toContainText('not an image');
  // Refused means refused: nothing was recorded.
  await expect(card.getByTestId('evidence-thumb')).toHaveCount(0);
});

test('deleting the capture removes the rep it carried', async ({ page, request }) => {
  await clearEvidence(request, API_URL, tok);
  await page.goto('/drills');
  const card = page.getByTestId('drill-card').first();
  const readReps = async () =>
    parseInt((await card.getByTestId('rep-count').innerText()).split('/')[0].trim(), 10);
  await expect(card.getByTestId('evidence-thumb')).toHaveCount(0);
  const before = await readReps();

  await card.getByTestId('reps-claimed').fill('4');
  await card
    .getByTestId('evidence-file-input')
    .setInputFiles({ name: 'four.png', mimeType: 'image/png', buffer: chartPng(9003) });
  await expect(card.getByTestId('evidence-thumb')).toHaveCount(1);
  await expect.poll(readReps).toBe(before + 4);

  await card.getByTestId('evidence-thumb').first().getByTestId('evidence-delete').click();
  await expect(card.getByTestId('evidence-thumb')).toHaveCount(0);
  await expect.poll(readReps).toBe(before);
});

// ---------------------------------------------------------------------------
// The rep counter is no longer a control
// ---------------------------------------------------------------------------

test('the concept panel shows reps as derived, with no way to type one in', async ({ page }) => {
  await page.goto('/path/aura/A1');
  const panel = page.getByTestId('evidence-capture').first();
  await expect(panel).toBeVisible();
  // No +/- anywhere on the page any more.
  await expect(page.getByRole('button', { name: 'Increase reps' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Decrease reps' })).toHaveCount(0);
});

// ---------------------------------------------------------------------------
// The two inherited debts, closed on the same layer
// ---------------------------------------------------------------------------

test('journal screenshots attach to the evidence layer (5c debt closed)', async ({
  page,
  request,
}) => {
  const created = await request.post(`${API_URL}/api/journal`, {
    ...authed(),
    data: {
      entry_date: '2026-07-20',
      instrument: 'NQ',
      mode: 'backtest',
      entry_model: 'london',
    },
  });
  const entry = await created.json();

  await page.goto(`/journal/${entry.id}`);
  const capture = page.getByTestId('evidence-capture');
  await expect(capture).toBeVisible();
  // Journal evidence is a record, not a rep — no rep claim control here.
  await expect(capture.getByTestId('reps-claimed')).toHaveCount(0);

  await capture
    .getByTestId('evidence-file-input')
    .setInputFiles({ name: 'entry.png', mimeType: 'image/png', buffer: chartPng(9101) });
  await expect(capture.getByTestId('evidence-thumb')).toHaveCount(1);

  // Persisted against the entry, on the ONE polymorphic table.
  const listed = await request.get(
    `${API_URL}/api/evidence?subject_type=journal_entry&journal_entry_id=${entry.id}`,
    authed()
  );
  expect((await listed.json()).length).toBe(1);
});

test('missed-trade screenshots attach to the same layer (0008 omission closed)', async ({
  page,
  request,
}) => {
  const created = await request.post(`${API_URL}/api/missed-trades`, {
    ...authed(),
    data: {
      entry_date: '2026-07-20',
      instrument: 'NQ',
      entry_model: 'london',
      miss_type: 'canceled',
    },
  });
  const miss = await created.json();

  await page.goto(`/journal/missed/${miss.id}`);
  const capture = page.getByTestId('evidence-capture');
  await expect(capture).toBeVisible();
  await capture
    .getByTestId('evidence-file-input')
    .setInputFiles({ name: 'stood-down.png', mimeType: 'image/png', buffer: chartPng(9102) });
  await expect(capture.getByTestId('evidence-thumb')).toHaveCount(1);

  const listed = await request.get(
    `${API_URL}/api/evidence?subject_type=missed_trade&missed_trade_id=${miss.id}`,
    authed()
  );
  expect((await listed.json()).length).toBe(1);
});

// ---------------------------------------------------------------------------
// THE BYPASS, on the wire
// ---------------------------------------------------------------------------

test('no endpoint mints a rep without evidence', async ({ request }) => {
  const drills = await (await request.get(`${API_URL}/api/drills?track=aura`, authed())).json();
  const progress = await (await request.get(`${API_URL}/api/progress?track=aura`, authed())).json();

  const byDrill = await request.patch(`${API_URL}/api/drills`, {
    ...authed(),
    data: { drill_ref: drills[0].drill_ref, reps: 99 },
  });
  expect(byDrill.status()).toBe(422);
  expect(await byDrill.text()).toContain('evidence');

  const byProgress = await request.patch(`${API_URL}/api/progress`, {
    ...authed(),
    data: { concept_id: progress[0].concept_id, reps: 99 },
  });
  expect(byProgress.status()).toBe(422);
  expect(await byProgress.text()).toContain('/api/evidence');

  // …and the planner's mark-done, which used to increment the count.
  await request.put(`${API_URL}/api/preferences`, {
    ...authed(),
    data: {
      timezone: 'UTC',
      max_session_minutes: 60,
      active_track: 'aura',
      mon_minutes: 120,
      tue_minutes: 120,
      wed_minutes: 120,
      thu_minutes: 120,
      fri_minutes: 120,
      sat_minutes: 120,
      sun_minutes: 120,
    },
  });
  const today = await (await request.get(`${API_URL}/api/plan/today`, authed())).json();
  const item = today.items.find((i: { concept_id: string | null }) => i.concept_id);
  const marked = await request.patch(`${API_URL}/api/plan/items/${item.id}`, {
    ...authed(),
    data: { status: 'done', done_qty: 40 },
  });
  expect(marked.ok()).toBeTruthy();

  const after = await (await request.get(`${API_URL}/api/progress?track=aura`, authed())).json();
  const row = after.find((r: { concept_id: string }) => r.concept_id === item.concept_id);
  expect(row.reps_evidenced).toBe(0);
  expect(row.reps).toBe(row.reps_legacy);
  expect(row.last_practiced).not.toBeNull(); // practice recorded; rep not minted
});
