import { expect, test, type APIRequestContext, type Page } from '@playwright/test';

// Phase E5 — PRE-COMMITMENT + CALIBRATION on the RENDERED surface.
//
// The backend proofs live in api/tests/test_predictions.py (the freeze trigger, the
// ordering CHECK, the 409 on a second reveal). What only this layer can prove is
// what the trader actually SEES:
//
//   * the two-step shape holds on screen — the outcome fields do not exist until
//     the call is committed, which is the whole anti-cheat;
//   * a committed call renders as FROZEN, with no edit and no delete affordance
//     anywhere on the card;
//   * M6's stage row, which could NEVER be met before E5, becomes met from the
//     ledger — and is met on calls that were WRONG;
//   * calibration renders an absence as an absence. E2's lesson applied: an empty
//     record must not paint "0%", and a spec that only checked the API would never
//     catch it painting one.
//
// Serial, against its own isolated debug user.
test.describe.configure({ mode: 'serial' });

const API_URL = process.env.E2E_API_URL ?? 'http://localhost:8000';
const TOKEN_KEY = 'neurospect_learn_token'; // must match app/src/lib/api.ts
const DISCORD_ID = 'e2e-predictions-e5';
const T01 = 'ict-course T-01';
const TAPE_DRILLS = Array.from({ length: 14 }, (_, i) => `ict-course T-${String(i + 1).padStart(2, '0')}`);

let token = '';

function authed(tok: string) {
  return { headers: { Authorization: `Bearer ${tok}` } };
}

/** Commit a call through the API — used to set up state the UI then reads. */
async function commit(request: APIRequestContext, drillRef: string, over: object = {}) {
  const res = await request.post(`${API_URL}/api/predictions`, {
    ...authed(token),
    data: {
      drill_ref: drillRef,
      session_label: 'comparable no-news Monday',
      instrument: 'NQ',
      bias: 'long',
      dol: 'PDH 20134.50',
      entry_model: 'consolidation',
      target: '20180.00',
      ...over,
    },
  });
  expect(res.ok(), await res.text()).toBeTruthy();
  return (await res.json()) as { id: string };
}

async function resolve(request: APIRequestContext, id: string, over: object = {}) {
  const res = await request.post(`${API_URL}/api/predictions/${id}/resolve`, {
    ...authed(token),
    data: {
      outcome_bias: 'long',
      dol_hit: true,
      model_played_out: true,
      target_hit: true,
      ...over,
    },
  });
  expect(res.ok(), await res.text()).toBeTruthy();
}

/** The locked/auto_met signature of the track — must not move on this evidence. */
async function lockSignature(request: APIRequestContext) {
  const stages = await (
    await request.get(`${API_URL}/api/stages?track=ict_course`, authed(token))
  ).json();
  return JSON.stringify(
    stages.map((s: { stage_code: string; locked: boolean; auto_met: boolean }) => [
      s.stage_code,
      s.locked,
      s.auto_met,
    ])
  );
}

async function wipe(request: APIRequestContext) {
  // There is no DELETE for a prediction — by design. So the fixture cannot clean up
  // through the API, and each spec below is written to be correct given whatever
  // this user has already committed. (The DB row is harmless: it is scoped to this
  // throwaway debug user.)
  const res = await request.get(`${API_URL}/api/predictions`, authed(token));
  return (await res.json()) as Array<{ id: string; drill_ref: string; resolved: boolean }>;
}

async function tapeCard(page: Page) {
  const card = page.getByTestId('drill-card').filter({ hasText: T01 });
  await expect(card).toBeVisible();
  return card;
}

test.beforeAll(async ({ request }) => {
  const res = await request.post(`${API_URL}/auth/debug/token`, {
    data: { discord_id: DISCORD_ID },
  });
  token = (await res.json()).access_token as string;
});

test.beforeEach(async ({ page }) => {
  await page.addInitScript(
    ([k, v]) => window.localStorage.setItem(k as string, v as string),
    [TOKEN_KEY, token]
  );
});

// ---------------------------------------------------------------------------

test('the ledger appears only on the tape drills, whose bar actually needs it', async ({ page }) => {
  await page.goto('/drills');
  const tape = await tapeCard(page);
  await expect(tape.getByTestId('prediction-commit')).toBeVisible();

  // A non-tape drill must NOT grow a prediction form: its bar is markings, not a
  // call, and offering one would invent a requirement the wiki never stated.
  const d1a = page.getByTestId('drill-card').filter({ hasText: 'ict-course D1-a' });
  await expect(d1a).toBeVisible();
  await expect(d1a.getByTestId('prediction-commit')).toHaveCount(0);
});

test('the outcome cannot be recorded until the call is committed (the two-step shape)', async ({
  page,
}) => {
  await page.goto('/drills');
  const card = await tapeCard(page);

  await card.getByRole('button', { name: 'Commit a call' }).click();
  // While committing, NOTHING about the outcome is on screen — if both halves were
  // visible at once, nothing would stop them being filled in together after the
  // fact, and the ordering that makes this evidence would be gone.
  await expect(card.getByText('Which way did it actually go?')).toHaveCount(0);
  await expect(card.getByRole('button', { name: 'Record the outcome' })).toHaveCount(0);
  await expect(card.getByText('Frozen once committed.')).toBeVisible();

  await card.getByLabel('Session you are calling').fill('comparable no-news Monday');
  await card.getByLabel('Draw on liquidity').fill('PDH 20134.50');
  await card.getByLabel('Target').fill('20180.00');
  await card.getByRole('button', { name: 'Commit this call' }).click();

  const committed = card.getByTestId('committed-call').first();
  await expect(committed).toBeVisible();
  await expect(committed.getByText('Committed — awaiting its outcome. Nothing is scored yet.')).toBeVisible();
  // Only NOW does the reveal step exist.
  await expect(committed.getByRole('button', { name: 'Score it against what happened' })).toBeVisible();
});

test('a committed call is frozen: no edit and no delete anywhere on it', async ({ page, request }) => {
  const existing = await wipe(request);
  if (!existing.some((p) => p.drill_ref === T01)) await commit(request, T01);

  await page.goto('/drills');
  const committed = (await tapeCard(page)).getByTestId('committed-call').first();
  await expect(committed).toBeVisible();

  // The UI must not even hint that the call is provisional.
  for (const name of [/edit/i, /delete/i, /remove/i, /change/i, /undo/i]) {
    await expect(committed.getByRole('button', { name })).toHaveCount(0);
  }
  await expect(committed.getByLabel('Frozen')).toBeVisible();
});

test('scoring a call renders the per-component verdict and the interval it stood', async ({
  page,
  request,
}) => {
  const target = await commit(request, 'ict-course T-02', { bias: 'short' });
  // Wrong on bias and target, right on DOL and model — a mixed result, so the
  // per-component rendering is actually discriminating.
  await resolve(request, target.id, { outcome_bias: 'long', target_hit: false });

  await page.goto('/drills');
  const card = page.getByTestId('drill-card').filter({ hasText: 'ict-course T-02' });
  const scored = card.getByTestId('committed-call').first();
  await expect(scored).toBeVisible();
  await expect(scored.getByText(/Bias — Long/)).toBeVisible();
  await expect(scored.getByText('DOL', { exact: true })).toBeVisible();
  await expect(scored.getByText(/could not change in between/)).toBeVisible();
  // The reveal step is gone — it is a record now, not a draft.
  await expect(scored.getByRole('button', { name: 'Record the outcome' })).toHaveCount(0);
});

test('calibration renders an absence as an absence, never as 0%', async ({ page, request }) => {
  // A user with committed-but-unscored calls only. The panel must say there is
  // nothing to measure rather than paint a zero — a zero from an instrument that
  // has seen nothing is not a measurement.
  const res = await request.post(`${API_URL}/auth/debug/token`, {
    data: { discord_id: 'e2e-predictions-e5-unscored' },
  });
  const freshTok = (await res.json()).access_token as string;
  const before = await request.get(`${API_URL}/api/predictions`, authed(freshTok));
  if (((await before.json()) as unknown[]).length === 0) {
    await request.post(`${API_URL}/api/predictions`, {
      ...authed(freshTok),
      data: {
        drill_ref: T01, session_label: 's', bias: 'long',
        dol: 'PDH', entry_model: 'consolidation', target: '1',
      },
    });
  }

  await page.addInitScript(
    ([k, v]) => window.localStorage.setItem(k as string, v as string),
    [TOKEN_KEY, freshTok]
  );
  await page.goto('/drills');
  const panel = page.getByTestId('calibration-panel');
  await expect(panel).toBeVisible();
  await expect(panel.getByTestId('calibration-unmeasured')).toBeVisible();
  await expect(panel.getByText(/Not zero: no outcome has been recorded/)).toBeVisible();
  await expect(panel.getByTestId('calibration-overall')).toHaveCount(0);
  // THE ASSERTION THAT FOUND A REAL DEFECT: the panel used to print "0% of your
  // calls have an outcome recorded" one line under "no outcome has been recorded".
  // No percentage of any kind belongs on a record with nothing scored.
  await expect(panel.getByText('%')).toHaveCount(0);
  await expect(panel.getByTestId('calibration-backlog')).toHaveCount(0);
});

test('calibration publishes the unresolved gap beside the score', async ({ page, request }) => {
  await page.goto('/drills');
  const panel = page.getByTestId('calibration-panel');
  await expect(panel).toBeVisible();
  await expect(panel.getByTestId('calibration-overall')).toBeVisible();
  // Every figure carries its denominator, and the backlog is stated — scoring only
  // your winners is the one remaining way to flatter this, so the gap is shown.
  await expect(panel.getByText(/of \d+ judgements across \d+ scored/)).toBeVisible();
  await expect(panel.getByTestId('calibration-backlog')).toBeVisible();
  await expect(panel.getByText(/Directional bias/)).toBeVisible();
  await expect(panel.getByText(/gates nothing/)).toBeVisible();
});

// ---------------------------------------------------------------------------
// E1's acceptance test, on the rendered surface
// ---------------------------------------------------------------------------

test('M6 was a dead checkbox and is now earned from the ledger', async ({ page, request }) => {
  const lockBefore = await lockSignature(request);

  await page.goto('/path/ict_course/M6');
  await expect(
    page.getByText(/13 tape studies \(T-01…T-13\) \+ a blind live read \(T-14\)/)
  ).toBeVisible();
  // Before E5 this row read "no gate attestation covers this bar" and could never
  // be met. It is now DERIVED — it says how many were called, and which are left.
  await expect(page.getByText(/no gate attestation covers this bar/)).toHaveCount(0);
  await expect(page.getByText(/called before the reveal, then scored/)).toBeVisible();
  await expect(page.getByText('earned').first()).toBeVisible();

  // Commit + score all 14 — deliberately ALL WRONG. The bar is that the call
  // preceded the reveal and was scored honestly, never that it was right (§6).
  const existing = await wipe(request);
  const byDrill = new Map(existing.map((p) => [p.drill_ref, p]));
  for (const ref of TAPE_DRILLS) {
    let row = byDrill.get(ref);
    if (!row) row = { ...(await commit(request, ref, { bias: 'long' })), drill_ref: ref, resolved: false };
    if (!row.resolved) {
      await resolve(request, row.id, {
        outcome_bias: 'short', dol_hit: false, model_played_out: false, target_hit: false,
      });
    }
  }

  await page.goto('/path/ict_course/M6');
  await expect(page.getByText(/14\/14 called before the reveal, then scored/)).toBeVisible();

  // …and the curriculum's lock chain has not moved an inch (invariant 6).
  expect(await lockSignature(request)).toBe(lockBefore);
});
