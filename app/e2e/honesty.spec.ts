import { expect, test, type APIRequestContext } from '@playwright/test';
import { clearEvidence, uploadEvidence } from './evidence-helpers';

// Phase E6 — THE HONESTY STRIP + DECLARED REST DAYS on the RENDERED surface.
//
// The backend proofs live in api/tests/test_honesty_api.py (the gate stays
// byte-identical, the rest-day trigger, no PATCH/DELETE). What only this layer can
// prove is what the trader actually SEES — and E5's one real defect was exactly
// this class: two individually-correct API responses that read as a contradiction
// once painted. So the assertions here are about rendered text, not JSON:
//
//   * an unmeasured signal paints "not measured" and NEVER a zero — the single
//     property that makes the strip trustworthy, and one a query-layer check
//     cannot catch, because `count: null` is a perfectly correct response;
//   * no signal paints a tick, a target or a score (§6: a green "0 flags" badge is
//     a point scored for not being caught);
//   * the strip says, on screen, that it gates nothing;
//   * a rest day cannot be declared for a day that has passed, and the refusal is
//     shown verbatim rather than swallowed;
//   * the evidence-backed streak paints beside the marked one, not instead of it.
//
// Serial, against its own isolated debug user.
test.describe.configure({ mode: 'serial' });

const API_URL = process.env.E2E_API_URL ?? 'http://localhost:8000';
const TOKEN_KEY = 'neurospect_learn_token'; // must match app/src/lib/api.ts
const DISCORD_ID = 'e2e-honesty-e6';
const DRILL = 'aura D1-a';

let token = '';

function authed(tok: string) {
  return { headers: { Authorization: `Bearer ${tok}` } };
}

/** Every rest day this user has booked. There is no DELETE — by design — so specs
 * are written to be correct given whatever is already on the record. */
async function restDays(request: APIRequestContext) {
  const res = await request.get(`${API_URL}/api/rest-days`, authed(token));
  return (await res.json()) as Array<{ id: string; rest_date: string }>;
}

function isoDaysFromNow(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

test.beforeAll(async ({ request }) => {
  const res = await request.post(`${API_URL}/auth/debug/token`, {
    data: { discord_id: DISCORD_ID },
  });
  token = (await res.json()).access_token as string;
  await clearEvidence(request, API_URL, token);
});

test.beforeEach(async ({ page }) => {
  await page.addInitScript(
    ([k, v]) => window.localStorage.setItem(k as string, v as string),
    [TOKEN_KEY, token]
  );
});

// ---------------------------------------------------------------------------
// THE RULE THE STRIP EXISTS FOR — not measured is not zero, ON SCREEN
// ---------------------------------------------------------------------------

test('with no evidence, every signal paints "not measured" and no zero appears', async ({
  page,
  request,
}) => {
  await clearEvidence(request, API_URL, token);
  await page.goto('/gate');

  const strip = page.getByTestId('honesty-strip');
  await expect(strip).toBeVisible();

  const signals = strip.getByTestId('honesty-signal');
  await expect(signals).toHaveCount(5);

  // Every one unmeasured…
  await expect(strip.getByTestId('honesty-unmeasured')).toHaveCount(5);
  for (const s of await signals.all()) {
    await expect(s).toHaveAttribute('data-status', 'not_measured');
    await expect(s).toHaveAttribute('data-count', 'null');
  }

  // …and — the assertion a query-layer check cannot make — the rendered strip
  // contains NO count of any kind. A fresh user must not be told they are clean
  // by an instrument that has never been fed. (This is E5's calibration-panel
  // defect generalised: `count: null` was always correct in JSON; what mattered
  // was that the page did not paint a reassuring number from it.)
  await expect(strip.getByTestId('honesty-value')).toHaveCount(0);
  await expect(strip).not.toContainText(/\b0 of \d/);
  await expect(strip).not.toContainText(/\b0 captures\b/);
  // The summary line is a QUALIFIER ON A MEASUREMENT and must be absent entirely
  // when there has not been one — it printed "0 of 5 signals … across 0 captures"
  // beneath five "not measured" rows before this was pinned.
  await expect(strip).toContainText('Nothing has been measured yet');
});

test('the strip states on screen that it gates nothing', async ({ page }) => {
  await page.goto('/gate');
  const strip = page.getByTestId('honesty-strip');
  await expect(strip).toContainText('None of this gates anything');
  await expect(strip).toContainText('not measured');
});

test('no signal paints a tick, a target, a percentage or a score', async ({ page, request }) => {
  // §6 (Deci/Koestner/Ryan 1999): a reward for activity would undermine the very
  // gate this strip sits beneath. There is nothing here to fill up.
  await uploadEvidence(request, API_URL, token, { subject_type: 'drill', drill_ref: DRILL }, {
    seed: 6201,
    reps: 5,
  });
  await page.goto('/gate');
  const strip = page.getByTestId('honesty-strip');
  await expect(strip.getByTestId('honesty-signal').first()).toBeVisible();

  const text = (await strip.innerText()).toLowerCase();
  // Word-boundary matched, not substring: the strip legitimately says "backtest
  // expectancy" when naming what the gate IS built from, and a bare `includes('xp')`
  // reads that as an XP system.
  const banned = [/\bxp\b/, /\bbadges?\b/, /\bpoints?\b/, /\blevel\b/, /\btargets?\b/,
                  /\bscores?\b/, /\bstreaks?\b/, /\brank(ed|ing)?\b/];
  for (const pattern of banned) {
    expect(text, `the strip must not present ${pattern}`).not.toMatch(pattern);
  }
  // No progress bar and no percentage anywhere in the strip.
  await expect(strip.locator('[role="progressbar"]')).toHaveCount(0);
  expect(text).not.toMatch(/\d+\s?%/);
});

// ---------------------------------------------------------------------------
// A measured signal, and the gate that must not move
// ---------------------------------------------------------------------------

test('a measured signal paints its count, its rule and the subjects it implicates', async ({
  page,
  request,
}) => {
  await clearEvidence(request, API_URL, token);
  await uploadEvidence(request, API_URL, token, { subject_type: 'drill', drill_ref: DRILL }, {
    seed: 6210,
    reps: 14,
  });
  await page.goto('/gate');

  const bulk = page.getByTestId('honesty-signal').filter({ hasText: 'Reps claimed per capture' });
  await expect(bulk).toHaveAttribute('data-status', 'measured');
  await expect(bulk).toHaveAttribute('data-count', '1');
  await expect(bulk.getByTestId('honesty-value')).toContainText('1 of 1');
  // The rule is printed, so the figure can be discounted rather than taken on faith.
  await expect(bulk).toContainText('Measured:');
  // And it names what it found, so this is feedback rather than a scolding.
  await expect(bulk.getByTestId('honesty-subjects')).toContainText(DRILL);
});

test('the rendered gate verdict is unchanged by evidence that trips the signals', async ({
  page,
  request,
}) => {
  // The API-level proof is byte-for-byte in test_honesty_api.py. This is the
  // rendered counterpart: the cleared count and every requirement row must be
  // identical before and after the strip lights up.
  await clearEvidence(request, API_URL, token);
  await page.goto('/gate');
  const before = await page.getByTestId('gate-overall').getAttribute('data-cleared-count');
  const reqsBefore = await page.getByTestId('gate-requirement').count();
  const metBefore = await page
    .getByTestId('gate-requirement')
    .evaluateAll((els) => els.map((e) => e.getAttribute('data-met')).join(','));

  await uploadEvidence(request, API_URL, token, { subject_type: 'drill', drill_ref: DRILL }, {
    seed: 6220,
    reps: 40,
  });

  await page.goto('/gate');
  await expect(page.getByTestId('honesty-signal').first()).toBeVisible();
  expect(await page.getByTestId('gate-overall').getAttribute('data-cleared-count')).toBe(before);
  expect(await page.getByTestId('gate-requirement').count()).toBe(reqsBefore);
  expect(
    await page
      .getByTestId('gate-requirement')
      .evaluateAll((els) => els.map((e) => e.getAttribute('data-met')).join(','))
  ).toBe(metBefore);
});

// ---------------------------------------------------------------------------
// Declared rest days — in advance, or not at all
// ---------------------------------------------------------------------------

test('a past date cannot be declared from the form at all', async ({ page, request }) => {
  await page.goto('/plan/setup');
  const card = page.getByTestId('rest-days');
  await expect(card).toBeVisible();

  const input = card.getByLabel('Date');
  // The past is not offered: `min` is today.
  await expect(input).toHaveAttribute('min', isoDaysFromNow(0));

  const past = isoDaysFromNow(-3);
  const before = (await restDays(request)).length;

  // Type one anyway. The field becomes natively INVALID, so the browser refuses
  // the submit before a request is ever made — the outermost of three guards
  // (input `min` → the router's 422 → Alembic `0012`'s trigger). Nothing is
  // created, which is the property that matters; which layer said no is not.
  await input.fill(past);
  await expect(input).toHaveJSProperty('validity.rangeUnderflow', true);
  await card.getByRole('button', { name: 'Declare' }).click();

  await expect
    .poll(async () => (await restDays(request)).length, { timeout: 3000 })
    .toBe(before);
  expect((await restDays(request)).some((d) => d.rest_date === past)).toBe(false);
});

test('the SERVER refuses a back-dated rest day even when the form is bypassed', async ({
  request,
}) => {
  // The form's `min` is a courtesy, not the mechanic. Going straight at the API —
  // as any client could — must still be refused, and the reason must say why,
  // because §6's whole argument is that a repairable streak is not worth reading.
  const res = await request.post(`${API_URL}/api/rest-days`, {
    ...authed(token),
    data: { rest_date: isoDaysFromNow(-4) },
  });
  expect(res.status()).toBe(422);
  expect((await res.json()).detail).toContain('in advance');
});

test('a server refusal is shown verbatim rather than swallowed', async ({ page, request }) => {
  // The error surface has to actually render a server refusal. Exercised through
  // the 409 (a day already booked), since the back-dating case never reaches the
  // server from this form — ky v2 consumes the response body, and E2 found the
  // hard way that a mis-wired error path silently replaces every `detail` with a
  // generic status string.
  const day = isoDaysFromNow(14);
  if (!(await restDays(request)).some((d) => d.rest_date === day)) {
    const seed = await request.post(`${API_URL}/api/rest-days`, {
      ...authed(token),
      data: { rest_date: day },
    });
    expect(seed.ok(), await seed.text()).toBeTruthy();
  }

  await page.goto('/plan/setup');
  const card = page.getByTestId('rest-days');
  await card.getByLabel('Date').fill(day);
  await card.getByRole('button', { name: 'Declare' }).click();

  const error = card.getByTestId('rest-day-error');
  await expect(error).toContainText('already declared a rest day');
  // The server's own words, not a generic "Request failed with status code 409".
  await expect(error).not.toContainText('status code');
});

test('a rest day booked ahead renders frozen, with no edit or delete affordance', async ({
  page,
  request,
}) => {
  const day = isoDaysFromNow(9);
  const already = (await restDays(request)).some((d) => d.rest_date === day);
  if (!already) {
    const res = await request.post(`${API_URL}/api/rest-days`, {
      ...authed(token),
      data: { rest_date: day, reason: 'planned break' },
    });
    expect(res.ok(), await res.text()).toBeTruthy();
  }

  await page.goto('/plan/setup');
  const row = page.getByTestId('rest-day').filter({ hasText: day });
  await expect(row).toBeVisible();
  await expect(row).toContainText('declared');

  // No affordance to change or remove it — the record is the mechanic.
  await expect(row.getByRole('button')).toHaveCount(0);
  await expect(row.getByRole('link')).toHaveCount(0);
});

// ---------------------------------------------------------------------------
// The evidence-backed streak, beside the marked one
// ---------------------------------------------------------------------------

test('Today paints the evidence-backed streak BESIDE the marked figures', async ({
  page,
  request,
}) => {
  await uploadEvidence(request, API_URL, token, { subject_type: 'drill', drill_ref: DRILL }, {
    seed: 6230,
  });
  // The planner needs preferences before Today renders its meters.
  await request.put(`${API_URL}/api/preferences`, {
    ...authed(token),
    data: {
      timezone: 'UTC', mon_minutes: 60, tue_minutes: 60, wed_minutes: 60, thu_minutes: 60,
      fri_minutes: 60, sat_minutes: 60, sun_minutes: 60, max_session_minutes: 45,
      blackout_dates: [], target_go_live_date: null, active_track: 'aura',
    },
  });

  await page.goto('/today');
  const meter = page.getByTestId('adherence-meter');
  await expect(meter).toBeVisible();

  // BOTH are on screen: the shipped adherence % (a claim) and the evidence-backed
  // run (a record). E2's `reps` / `reps_evidenced` idiom — replacing one with the
  // other would read as the app having lost the user's work.
  await expect(meter).toContainText('Adherence');
  const backed = meter.getByTestId('evidence-backed-consistency');
  await expect(backed).toBeVisible();
  await expect(backed).toContainText('Backed by evidence');
  await expect(backed).toContainText('day with a capture');
});

test('declaring rest days does not raise the evidence-backed streak', async ({ page, request }) => {
  // THE SCORE-CHASE TEST, on the rendered surface. If booking days off could raise
  // the number, rest days would be the cheapest currency in the app.
  await page.goto('/today');
  const before = await page
    .getByTestId('evidence-backed-consistency')
    .getAttribute('data-evidence-streak');

  for (const n of [20, 21, 22, 23]) {
    const day = isoDaysFromNow(n);
    if ((await restDays(request)).some((d) => d.rest_date === day)) continue;
    const res = await request.post(`${API_URL}/api/rest-days`, {
      ...authed(token),
      data: { rest_date: day },
    });
    expect(res.ok(), await res.text()).toBeTruthy();
  }

  await page.goto('/today');
  const after = await page
    .getByTestId('evidence-backed-consistency')
    .getAttribute('data-evidence-streak');
  expect(after).toBe(before);
});
