import { expect, test, type Page } from '@playwright/test';
import { mkdirSync } from 'node:fs';

// Phase S1 — THE AURA SESSION RUNNER on the RENDERED surface, at the width it
// will actually be used at.
//
// The runner's ONE job is to be followable in a window docked beside Tradezella
// — roughly a third of a screen. A component that only works maximised has
// failed that job, and no query-layer or type check can catch it: the build
// passes, the route resolves, and the page still overflows off the side.
//
// So the load-bearing assertion here is NOT "the text is present" but
// "the page body does not scroll horizontally at 400px". Everything else is
// interaction evidence — recorded per the estate rule that a silent no-op is a
// finding, never an acceptable default.
//
// Prereqs: the local stack (docker compose) on :8001 API / :5174 app, or the
// dev pair on :8000/:5173. Run:
//   E2E_BASE_URL=http://localhost:5174 E2E_API_URL=http://localhost:8001 \
//     npx playwright test e2e/runner.spec.ts

test.describe.configure({ mode: 'serial' });

const SHOTS = '../api/docs/evidence/s1';

/** The runner's primary target: a narrow docked column. 1280 is the control. */
const WIDTHS = [
  { w: 400, label: 'narrow-400' },
  { w: 620, label: 'docked-620' },
  { w: 1280, label: 'wide-1280' },
] as const;

test.beforeAll(() => {
  mkdirSync(SHOTS, { recursive: true });
});

/**
 * The property that matters. `documentElement.scrollWidth > clientWidth` means
 * the page body itself scrolls sideways — the failure this phase is most likely
 * to ship, because it looks fine at 1568px in every screenshot.
 */
async function horizontalOverflow(page: Page): Promise<number> {
  return page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth
  );
}

/**
 * Screenshot with animations frozen.
 *
 * `page.screenshot()` defaults to `animations: 'allow'`, and TabsTrigger carries
 * `transition-all` — so the first run's artifacts caught the tab highlight
 * mid-transition and showed the PREVIOUS tab as active while the new tab's
 * content was already painted. The DOM was correct throughout (aria-selected is
 * asserted below); the evidence was not. An artifact that misrepresents the
 * product is worse than no artifact, so every capture freezes animations.
 */
async function shot(page: Page, name: string) {
  await page.screenshot({ path: `${SHOTS}/${name}.png`, fullPage: true, animations: 'disabled' });
}

async function gotoRunner(page: Page, width: number) {
  await page.setViewportSize({ width, height: 1000 });
  await page.goto('/runner');
  await expect(page.getByRole('heading', { name: 'Runner', level: 1 })).toBeVisible();
}

/** Declare a session so the Run tab switches from the panel to the protocol. */
async function declare(page: Page, spanLabel = '1 week', start = '2025-06-02') {
  await page.getByRole('button', { name: spanLabel }).click();
  await page.getByLabel('Start date').fill(start);
}

test('renders at every width without the body scrolling sideways', async ({ page }) => {
  for (const { w, label } of WIDTHS) {
    await gotoRunner(page, w);

    // The declaration panel is the entry state — nothing is declared yet.
    await expect(page.getByText('Declare the session')).toBeVisible();
    await expect(page.getByRole('button', { name: '1 week' })).toBeVisible();

    expect(
      await horizontalOverflow(page),
      `body overflows horizontally at ${w}px`
    ).toBeLessThanOrEqual(0);

    await shot(page, `01-declare-${label}`);
  }
});

test('declaring a span produces the Tradezella paste block, incl. the symbol correction', async ({
  page,
}) => {
  await gotoRunner(page, 400);

  await page.getByRole('button', { name: '1 month' }).click();
  await expect(page.getByText(/≈ 21 replayed days/)).toBeVisible();

  await page.getByLabel('Start date').fill('2025-06-02');

  // The counting basis, made operational: name + both dates in Tradezella's own
  // format, so the create-session form can be filled without re-deriving them.
  await expect(page.getByText('AURA · NQ · 2025-06-02→2025-07-02 · 1m')).toBeVisible();
  await expect(page.getByText('06/02/2025 00:00:00')).toBeVisible();
  await expect(page.getByText('07/02/2025 23:59:59')).toBeVisible();
  await expect(page.getByText('NQ, ES, YM, 6S')).toBeVisible();

  // The finding from the probe, surfaced where it can change behaviour.
  await expect(page.getByText(/micro contracts of NQ and ES/)).toBeVisible();

  expect(await horizontalOverflow(page)).toBeLessThanOrEqual(0);
  await shot(page, '02-declared-narrow-400');
});

test('the working surface: 8 phases, per-setup scoping, hard gates, rule popovers', async ({
  page,
}) => {
  await gotoRunner(page, 400);
  await declare(page);

  await expect(page.getByText('Replayed day 1')).toBeVisible();
  // exact — the paste block legitimately shows the same date inside the session name
  await expect(page.getByText('2025-06-02', { exact: true })).toBeVisible();

  // All eight checklist phases project.
  for (const title of [
    'Pre-market — readiness',
    'HTF framing — top-down cascade',
    'Confirmation — Sequential SMT',
    'Entry',
    'In-trade management',
    'Exit',
    'Circuit-breaker checkpoints (any time)',
    'Post-market review',
  ]) {
    await expect(page.getByText(title, { exact: true })).toBeVisible();
  }

  // Scope is declared on the face of each phase (open question Q5's answer).
  await expect(page.getByText('per setup').first()).toBeVisible();
  await expect(page.getByText('once per replayed day').first()).toBeVisible();

  // Phase 0 is open by default; tick its first item and watch the counter move.
  const phase0 = page
    .locator('div.rounded-lg.border', { hasText: 'Pre-market — readiness' })
    .first();
  await expect(phase0.getByText('0/5')).toBeVisible();
  await phase0.getByRole('checkbox').first().click();
  await expect(phase0.getByText('1/5')).toBeVisible();

  expect(await horizontalOverflow(page)).toBeLessThanOrEqual(0);
  await shot(page, '03-phases-ticked-narrow-400');
});

test('a rule chip opens the CANONICAL wiki text, hedges intact', async ({ page }) => {
  await gotoRunner(page, 400);
  await declare(page);

  // R54 is one of the rules dOoMeR states softly, and it is reachable ONLY via
  // the phase-level refs — the first render walk dropped those entirely, which
  // took R54 out of the runner altogether without any test noticing.
  await page.getByRole('button', { name: /^R54/ }).first().click();
  await expect(page.getByText(/Environment & health are performance inputs/)).toBeVisible();
  await expect(page.getByText(/Preserved as stated — not hardened/)).toBeVisible();

  await shot(page, '04-rule-popover-narrow-400');
});

test('open flags render as flags — never resolved into a checkbox', async ({ page }) => {
  await gotoRunner(page, 400);
  await declare(page);

  const flags = page.locator('div', { hasText: 'Open flags — do not silently resolve' }).last();
  await expect(page.getByText('Open flags — do not silently resolve')).toBeVisible();
  await expect(page.getByText(/Aura uses discount\/EQ\/premium only/)).toBeVisible();
  await expect(page.getByText(/Aura rejects the term/)).toBeVisible();

  // The load-bearing negative: the flags panel contains NO tickable control.
  expect(await flags.getByRole('checkbox').count()).toBe(0);

  await shot(page, '05-open-flags-narrow-400');
});

test('a stood-aside day still counts — R51', async ({ page }) => {
  await gotoRunner(page, 400);
  await declare(page);

  await expect(page.getByText(/0 replayed days counted/)).toBeVisible();
  await page.getByRole('button', { name: /Stood aside/ }).click();
  await expect(page.getByText(/1 replayed day counted/)).toBeVisible();
  await expect(page.getByText(/1 stood aside/)).toBeVisible();

  await shot(page, '06-stood-aside-narrow-400');
});

test('reference tabs project the three authored pages, wide tables scrolling in-box', async ({
  page,
}) => {
  await gotoRunner(page, 400);

  for (const [tab, needle, name] of [
    ['Setup', 'The counting basis', '07-tab-setup'],
    ['Markup', 'The probe', '08-tab-markup'],
    ['Rules', 'What the instrument actually is', '09-tab-playbook'],
    ['Card', 'Per-trade card', '10-tab-card'],
  ] as const) {
    await page.getByRole('tab', { name: tab }).click();
    await expect(page.getByText(new RegExp(needle)).first()).toBeVisible();
    // The tab the user sees selected must be the tab whose content is showing.
    await expect(page.getByRole('tab', { name: tab })).toHaveAttribute('aria-selected', 'true');

    // Tables and the per-trade card are wide by nature; they must scroll inside
    // their own box, never push the page body sideways.
    expect(
      await horizontalOverflow(page),
      `the ${tab} tab pushes the body sideways at 400px`
    ).toBeLessThanOrEqual(0);

    await shot(page, `${name}-narrow-400`);
  }
});

test('prose is joined into paragraphs, not one fragment per source line', async ({ page }) => {
  // The wiki hard-wraps at ~100 columns. The first projection emitted one
  // paragraph per PHYSICAL line, which rendered the reference tabs as a column
  // of orphaned half-sentences at 400px — legible in a diff, unreadable on the
  // surface. Guarded here because only the rendered width exposes it.
  await gotoRunner(page, 400);
  await page.getByRole('tab', { name: 'Markup' }).click();

  const paras = await page
    .locator('p.text-\\[12px\\]')
    .filter({ hasText: /\w{4,}/ })
    .allInnerTexts();
  expect(paras.length, 'expected some prose on the markup tab').toBeGreaterThan(3);

  // A hard-wrapped source line is ~100 chars; joined paragraphs run longer.
  const longest = Math.max(...paras.map((p) => p.length));
  expect(longest, 'paragraphs look split per source line').toBeGreaterThan(160);
});

test('the runner CONTENT needs no API — but the app shell still logs you out', async ({ page }) => {
  // Two separable claims, and only one of them holds. Written as one test
  // because asserting the good half while staying silent about the bad half is
  // how a half-true "renders offline" claim would have shipped.
  //
  //  (a) TRUE  — the protocol content is a bundled wiki projection, so /api is
  //              never touched to render it.
  //  (b) FALSE — the runner is behind ProtectedLayout, and lib/auth.ts:50-53
  //              clears the stored token on ANY `auth/me` failure, network
  //              errors included. So an unreachable API does not just degrade
  //              the runner, it BOUNCES YOU TO /login and discards the session.
  //
  // (b) is a pre-existing defect in the auth shell, wider than this phase and
  // security-adjacent, so S1 documents it rather than changing it. Fixing it
  // means distinguishing 401/403 (token really is bad → clear it) from a
  // transport failure (→ keep it). Flagged in the tracker for approval.

  // (a) — no /api traffic is needed to paint the protocol.
  const apiCalls: string[] = [];
  page.on('request', (r) => {
    if (r.url().includes('/api/')) apiCalls.push(r.url());
  });
  await gotoRunner(page, 400);
  await declare(page);
  await expect(page.getByText('Confirmation — Sequential SMT')).toBeVisible();
  await expect(page.getByText('Open flags — do not silently resolve')).toBeVisible();
  expect(apiCalls, 'the runner should not need /api to render').toEqual([]);
  await shot(page, '11-no-api-traffic-narrow-400');

  // (b) — the honest negative, asserted so a future "it works offline" claim fails here.
  await page.route('**/auth/**', (route) => route.abort());
  await page.goto('/runner');
  await expect(page).toHaveURL(/\/login$/);
  expect(
    await page.evaluate(() => localStorage.getItem('neurospect_learn_token')),
    'auth.ts discards the token on a transport failure — see the note above'
  ).toBeNull();
  await shot(page, '12-auth-shell-logs-you-out');
});
