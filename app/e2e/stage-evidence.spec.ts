import { expect, test, type APIRequestContext } from '@playwright/test';

// Phase 6a — the stage exit bars are wired to real evidence. These specs pin the
// rendered `/path/:track/:stage` surface: a row that could NEVER become met before
// 6a now reflects a tick made on /gate (one source of truth, no second checkbox
// here), and a derived row shows the numbers from the journal instead of the word
// "self-attested".
//
// Serial, against their OWN isolated debug user (injected via addInitScript).
test.describe.configure({ mode: 'serial' });

const API_URL = process.env.E2E_API_URL ?? 'http://localhost:8000';
const TOKEN_KEY = 'neurospect_learn_token'; // must match app/src/lib/api.ts
const DISCORD_ID = 'e2e-stage-evidence-6a';

let token = '';

function authed(tok: string) {
  return { headers: { Authorization: `Bearer ${tok}` } };
}

async function attest(request: APIRequestContext, item: string, attested: boolean) {
  const res = await request.patch(`${API_URL}/api/gate/attestations`, {
    ...authed(token),
    data: { item, attested },
  });
  expect(res.ok(), await res.text()).toBeTruthy();
}

/** The locked/auto_met signature of a track — must not move when attesting. */
async function lockSignature(request: APIRequestContext, track: string) {
  const stages = await (
    await request.get(`${API_URL}/api/stages?track=${track}`, authed(token))
  ).json();
  return JSON.stringify(
    stages.map((s: { stage_code: string; locked: boolean; auto_met: boolean }) => [
      s.stage_code,
      s.locked,
      s.auto_met,
    ])
  );
}

test.beforeAll(async ({ request }) => {
  const res = await request.post(`${API_URL}/auth/debug/token`, {
    data: { discord_id: DISCORD_ID },
  });
  token = (await res.json()).access_token as string;
  // Start from a clean slate: no attestations, no journal.
  for (const item of ['circuit_breaker', 'journaling_habit', 'risk_precommitted', 'sim_track_record']) {
    await attest(request, item, false);
  }
  const entries = await (await request.get(`${API_URL}/api/journal`, authed(token))).json();
  for (const e of entries as Array<{ id: string }>) {
    await request.delete(`${API_URL}/api/journal/${e.id}`, authed(token));
  }
});

test.beforeEach(async ({ page }) => {
  await page.addInitScript(
    ([k, v]) => window.localStorage.setItem(k as string, v as string),
    [TOKEN_KEY, token]
  );
});

test('a U0 behavioural row reflects the /gate tick instead of being permanently unmet', async ({
  page,
  request,
}) => {
  const before = await lockSignature(request, 'unified');

  await page.goto('/path/unified/U0');
  await expect(page.getByText(/circuit-breakers held/)).toBeVisible();
  // Before 6a every such row read "(self-attested)" and could never be met; now
  // it names where it is satisfied.
  await expect(page.getByText('attest it on the Gate once it is true').first()).toBeVisible();
  await expect(page.getByText(/attestation pending on the/)).toBeVisible();

  // Tick both items the U0 bar names, on /gate — the only place they can be set.
  await attest(request, 'circuit_breaker', true);
  await attest(request, 'journaling_habit', true);

  await page.goto('/path/unified/U0');
  await expect(page.getByText('attested on the Gate').first()).toBeVisible();
  await expect(page.getByText(/attestation pending on the/)).toHaveCount(0);

  // Revoking on /gate un-meets the /path row (one source of truth).
  await attest(request, 'circuit_breaker', false);
  await page.goto('/path/unified/U0');
  await expect(page.getByText(/attestation pending on the/)).toBeVisible();

  // And none of it moved the curriculum's lock chain.
  expect(await lockSignature(request, 'unified')).toBe(before);
});

test('the U4 expectancy row is earned from the journal, with the numbers shown', async ({
  page,
  request,
}) => {
  await page.goto('/path/unified/U4');
  const row = page.getByText(/Can compute a trade's expectancy contribution in R/);
  await expect(row).toBeVisible();
  await expect(page.getByText(/no closed backtest trade yet/)).toBeVisible();
  await expect(page.getByText('from your log').first()).toBeVisible();

  // Log one closed backtest trade — a LOSS, because U4's bar is computability,
  // not positivity (that is the A4/M7 bar).
  const res = await request.post(`${API_URL}/api/journal`, {
    ...authed(token),
    data: {
      entry_date: '2026-07-20', instrument: 'NQ', mode: 'backtest',
      entry_model: 'london', r_multiple: -0.5, rr_planned: 2.0,
    },
  });
  expect(res.ok(), await res.text()).toBeTruthy();

  await page.goto('/path/unified/U4');
  await expect(page.getByText(/expectancy -0\.50R over 1 closed backtest trade/)).toBeVisible();
  await expect(page.getByText('earned').first()).toBeVisible();
});

test('the aura backtest stage shows its ≥50-sample evidence bar, not a checkbox', async ({
  page,
}) => {
  await page.goto('/path/aura/A4');
  await expect(page.getByText(/≥50 backtest setups logged with positive expectancy/)).toBeVisible();
  // The sample progress is stated as a number against the shipped reference.
  await expect(page.getByText(/\/50 closed backtest trades/)).toBeVisible();
});

test('the unified readiness arc points at the computed per-model Gate verdict', async ({ page }) => {
  await page.goto('/path/unified/U6');
  await expect(
    page.getByText(/Readiness-to-Live Gate cleared for at least one entry model/)
  ).toBeVisible();
  await expect(page.getByText(/no entry model is cleared to live yet/)).toBeVisible();
});
