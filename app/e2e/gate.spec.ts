import { expect, test, type APIRequestContext } from '@playwright/test';
import { clearEvidence, giveReps } from './evidence-helpers';

// Phase 5g — Readiness-to-Live Gate. These specs pin the north-star payoff: a
// FULLY satisfied model renders as cleared, an unsatisfied one renders as blocked
// WITH its reasons, ticking the behavioural boxes cannot clear a model on its own,
// and frontier concepts are shown as never gate-eligible.
//
// They run SERIALLY against their OWN isolated debug user (injected via
// addInitScript) so they never race with the other suites' shared users.
test.describe.configure({ mode: 'serial' });

// Phase E2: reps come from uploaded evidence, so the fixture produces the work.
const API_URL = process.env.E2E_API_URL ?? 'http://localhost:8000';
const TOKEN_KEY = 'neurospect_learn_token'; // must match app/src/lib/api.ts
const DISCORD_ID = 'e2e-gate-5g';

const MODEL = 'london';
const MODEL_CONCEPT = 'u3-2d-london'; // gate.ENTRY_MODEL_CONCEPTS['london']
const BACKTESTED = 3;
const LIVE_READY = 4;

let gateToken = '';
let coreSlugs: string[] = [];

function authed(tok: string) {
  return { headers: { Authorization: `Bearer ${tok}` } };
}

async function mintToken(request: APIRequestContext): Promise<string> {
  const res = await request.post(`${API_URL}/auth/debug/token`, { data: { discord_id: DISCORD_ID } });
  return (await res.json()).access_token as string;
}

/** Advance one concept's ladder through the real API (which enforces
 * reps ≥ target + confidence — so the fixture cannot cheat the ladder gate).
 *
 * Phase E2: `reps` is no longer a field on this PATCH, so clearing the rep floor
 * means UPLOADING EVIDENCE first. A seeded counter keeps every capture visually
 * distinct, since the deterministic tier refuses a duplicate. */
let evidenceSeed = 5000;

async function setLadder(
  request: APIRequestContext,
  conceptId: string,
  ladder: number
): Promise<void> {
  await giveReps(
    request, API_URL, gateToken,
    { subject_type: 'concept', concept_id: conceptId },
    200,
    evidenceSeed++
  );
  const res = await request.patch(`${API_URL}/api/progress`, {
    ...authed(gateToken),
    data: { concept_id: conceptId, ladder_stage: ladder, confidence: 5 },
  });
  expect(res.ok(), await res.text()).toBeTruthy();
}

async function attestAll(request: APIRequestContext, attested: boolean): Promise<void> {
  const items = ['risk_precommitted', 'sim_track_record', 'journaling_habit', 'circuit_breaker'];
  for (const item of items) {
    const res = await request.patch(`${API_URL}/api/gate/attestations`, {
      ...authed(gateToken),
      data: { item, attested },
    });
    expect(res.ok(), await res.text()).toBeTruthy();
  }
}

test.beforeAll(async ({ request }) => {
  gateToken = await mintToken(request);

  // Phase E2: the fixture uploads real evidence to clear the rep floors, and the
  // deterministic tier refuses a duplicate — so drop last run's captures first,
  // otherwise the second run of this spec 409s on its own images.
  await clearEvidence(request, API_URL, gateToken);

  // --- Build a FULLY satisfied London model for this user -----------------
  const concepts = await (
    await request.get(`${API_URL}/api/concepts?track=unified`, authed(gateToken))
  ).json();

  const cores = concepts.filter(
    (c: { is_core: boolean; watch_only: boolean; u_stage: string | null }) =>
      c.is_core && !c.watch_only && ['U1', 'U2', 'U3', 'U4'].includes(c.u_stage ?? '')
  );
  expect(cores.length).toBeGreaterThan(4);
  coreSlugs = cores.map((c: { slug: string }) => c.slug);

  for (const c of cores) await setLadder(request, c.id, BACKTESTED);

  const modelConcept = concepts.find((c: { slug: string }) => c.slug === MODEL_CONCEPT);
  expect(modelConcept, `seed concept ${MODEL_CONCEPT} must exist`).toBeTruthy();
  await setLadder(request, modelConcept.id, LIVE_READY);

  // 50 closed backtest trades: 60% at +2R / -1R, planned R:R 2 → +0.80R.
  const existing = await (
    await request.get(`${API_URL}/api/journal?mode=backtest&entry_model=${MODEL}`, authed(gateToken))
  ).json();
  for (let i = existing.length; i < 50; i++) {
    const win = i < 30;
    const res = await request.post(`${API_URL}/api/journal`, {
      ...authed(gateToken),
      data: {
        entry_date: '2026-07-20',
        instrument: 'NQ',
        mode: 'backtest',
        entry_model: MODEL,
        r_multiple: win ? 2.0 : -1.0,
        rr_planned: 2.0,
        outcome: win ? 'win' : 'loss',
      },
    });
    expect(res.ok(), await res.text()).toBeTruthy();
  }

  await attestAll(request, true);
});

test.beforeEach(async ({ page }) => {
  await page.addInitScript(
    ([k, v]) => window.localStorage.setItem(k as string, v as string),
    [TOKEN_KEY, gateToken]
  );
});

test('a fully satisfied model renders as CLEARED', async ({ page }) => {
  await page.goto('/gate');
  await expect(page.getByRole('heading', { name: 'Gate', level: 1 })).toBeVisible();

  const card = page.locator('[data-testid="gate-signal"][data-model="london"]');
  await expect(card).toBeVisible();
  await expect(card).toHaveAttribute('data-cleared', 'true');
  await expect(card.getByText('Cleared')).toBeVisible();
  await expect(card.getByText('50/50')).toBeVisible();
  await expect(card.getByText('+0.80R')).toBeVisible();

  // The overall banner reflects at least one cleared model.
  await expect(page.getByTestId('gate-overall')).not.toHaveAttribute('data-cleared-count', '0');
  await expect(page.getByText(/cleared to live\./)).toBeVisible();

  // Its checklist shows all three source groups fully met.
  await card.click();
  const checklist = page.getByTestId('gate-checklist');
  await expect(checklist).toHaveAttribute('data-model', 'london');
  await expect(checklist.getByText('london — Readiness-to-Live Gate', { exact: false })).toBeVisible();
  const unmet = checklist.locator('[data-testid="gate-requirement"][data-met="false"]');
  await expect(unmet).toHaveCount(0);
});

test('an unsatisfied model renders as BLOCKED with its reasons', async ({ page }) => {
  await page.goto('/gate');

  // consolidation shares the satisfied core ladder but its own entry-model
  // concept is untouched and it has no backtest sample.
  const card = page.locator('[data-testid="gate-signal"][data-model="consolidation"]');
  await expect(card).toHaveAttribute('data-cleared', 'false');
  await expect(card.getByText('Not cleared')).toBeVisible();
  await expect(card.getByText('0/50', { exact: true })).toBeVisible();

  const blocking = card.getByTestId('gate-blocking');
  await expect(blocking).toBeVisible();
  await expect(blocking).toContainText('0/50 closed backtest trades');
  await expect(blocking).toContainText(/concept requirement/);

  // Its checklist names the unmet load-bearing concept + the evidence gaps.
  await card.click();
  const checklist = page.getByTestId('gate-checklist');
  await expect(checklist).toHaveAttribute('data-model', 'consolidation');
  const unmet = checklist.locator('[data-testid="gate-requirement"][data-met="false"]');
  expect(await unmet.count()).toBeGreaterThan(0);
  await expect(checklist.getByText('Consolidation model — Live-ready')).toBeVisible();
});

test('revoking a behavioural attestation blocks the cleared model', async ({ page, request }) => {
  const res = await request.patch(`${API_URL}/api/gate/attestations`, {
    ...authed(gateToken),
    data: { item: 'circuit_breaker', attested: false },
  });
  expect(res.ok()).toBeTruthy();

  await page.goto('/gate');
  const card = page.locator('[data-testid="gate-signal"][data-model="london"]');
  await expect(card).toHaveAttribute('data-cleared', 'false');
  await expect(card.getByTestId('gate-blocking')).toContainText('not attested');

  // Re-tick it IN THE UI — the checkbox is the only writable control on the page.
  await card.click();
  const box = page.locator('[data-testid="gate-attestation"][data-item="circuit_breaker"]');
  // click(), not check(): the box is server-controlled — it flips only once the
  // PATCH lands and the gate refetches (no optimistic lie about an attestation).
  await box.getByRole('checkbox').click();
  await expect(box).toHaveAttribute('data-attested', 'true');
  // …and the verdict recomputes back to cleared.
  await expect(card).toHaveAttribute('data-cleared', 'true');
});

test('attesting cannot clear a model that lacks the evidence', async ({ page }) => {
  await page.goto('/gate');
  // All four behavioural items are attested (beforeAll), yet every other model
  // stays blocked — attestation is an input, never an override.
  const others = page.locator('[data-testid="gate-signal"][data-cleared="true"]');
  await expect(others).toHaveCount(1); // london only
  const attested = page.locator('[data-testid="gate-attestation"][data-attested="true"]');
  await expect(attested).toHaveCount(4);
});

test('frontier concepts are listed as never gate-eligible', async ({ page }) => {
  await page.goto('/gate');
  const frontier = page.getByTestId('gate-frontier');
  await expect(frontier).toBeVisible();
  await expect(frontier).toContainText('never count toward live-readiness');

  // No frontier concept appears as a requirement in any checklist.
  await page.locator('[data-testid="gate-signal"][data-model="london"]').click();
  const reqs = page.getByTestId('gate-requirement');
  await expect(reqs.first()).toBeVisible();
  await expect(page.getByTestId('gate-checklist')).not.toContainText('watch-only');
});

test('restricting the credit track only tightens the verdict', async ({ page }) => {
  await page.goto('/gate');
  await expect(page.locator('[data-testid="gate-signal"][data-model="london"]')).toHaveAttribute(
    'data-cleared',
    'true'
  );

  // The ladder above was earned on the unified track; crediting Aura only drops it.
  await page.getByLabel('Credit track').click();
  await page.getByRole('option', { name: /Aura only/ }).click();

  await expect(page.getByTestId('gate-overall')).toHaveAttribute('data-cleared-count', '0');
  await expect(page.locator('[data-testid="gate-signal"][data-model="london"]')).toHaveAttribute(
    'data-cleared',
    'false'
  );
  await expect(page.getByText(/only Aura progress may satisfy/)).toBeVisible();
});

test('core concept slugs used by the fixture match the seeded curriculum', async () => {
  // Guards the spec itself: if the seed's core set changes, the fixture (and the
  // gate's (a) source) must be revisited rather than silently passing.
  expect(coreSlugs.length).toBeGreaterThanOrEqual(5);
  expect(coreSlugs).toContain('u1-1-liquidity-draw');
});
