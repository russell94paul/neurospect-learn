/**
 * Consumer-layer render walk.
 *
 * The Playwright suite proves structure and is BLIND to colour — it holds zero
 * toHaveClass/toHaveCSS assertions. This script covers what it cannot: that every
 * route actually PAINTS, in both modes, with no console errors and no unstyled
 * or collapsed content. Screenshots land in api/docs/evidence/ui/ alongside the
 * repo's existing evidence convention.
 *
 *   node scripts/render-walk.mjs
 */
import { chromium } from '@playwright/test';
import { mkdirSync, existsSync } from 'node:fs';
import { readFileSync } from 'node:fs';

const BASE = process.env.E2E_BASE_URL ?? 'http://localhost:5173';
const OUT = '../api/docs/evidence/ui';
const STATE = './e2e/.auth/state.json';

const ROUTES = [
  ['landing', '/', false],
  ['login', '/login', false],
  ['today', '/today', true],
  ['runner', '/runner', true],
  ['path', '/path', true],
  ['library', '/library', true],
  ['drills', '/drills', true],
  ['plan', '/plan', true],
  ['journal', '/journal', true],
  ['expectancy', '/expectancy', true],
  ['gate', '/gate', true],
  ['settings', '/settings', true],
  ['plan-setup', '/plan/setup', true],
  ['concept', '/concepts/quarterly-theory', true],
];

const KEY = 'neurospect.learn.settings.v1';

mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch();
const results = [];

for (const mode of ['dark', 'light']) {
 for (const signedIn of [true, false]) {
  // The public routes must be walked SIGNED OUT — with a session, `/` correctly
  // redirects into the app and the landing page is never seen.
  const routes = ROUTES.filter(([, , needsAuth]) => (signedIn ? needsAuth : !needsAuth));
  if (routes.length === 0) continue;
  const ctx = await browser.newContext({
    storageState: signedIn && existsSync(STATE) ? STATE : undefined,
    viewport: { width: 1280, height: 900 },
  });
  // Stamp the theme before any app code runs, exactly as a real visitor would
  // have it stored.
  await ctx.addInitScript(
    ([k, v]) => window.localStorage.setItem(k, v),
    [KEY, JSON.stringify({ version: 1, mode, brand: 'cyan', radius: 0.5, density: 'comfortable', font: 'inter', motion: 'none', updatedAt: '' })]
  );

  for (const [name, path] of routes) {
    const page = await ctx.newPage();
    const errors = [];
    page.on('console', (m) => {
      if (m.type() === 'error') errors.push(m.text());
    });
    page.on('pageerror', (e) => errors.push(String(e)));

    try {
      await page.goto(BASE + path, { waitUntil: 'networkidle', timeout: 20000 });
      await page.waitForTimeout(350);

      // Did it actually paint? Measure rendered text and the resolved background.
      const probe = await page.evaluate(() => {
        const el = document.querySelector('main') ?? document.body;
        const cs = getComputedStyle(document.body);
        return {
          text: (el.innerText || '').trim().length,
          bg: cs.backgroundColor,
          fg: cs.color,
          dark: document.documentElement.classList.contains('dark'),
          brand: document.documentElement.dataset.brand,
          scrollX: document.documentElement.scrollWidth > document.documentElement.clientWidth,
        };
      });

      await page.screenshot({ path: `${OUT}/${mode}-${name}.png`, fullPage: name === 'landing' });

      const painted = probe.text > 40;
      results.push({
        mode,
        name: signedIn ? name : name + '*',
        painted,
        chars: probe.text,
        darkClass: probe.dark,
        bg: probe.bg,
        sideScroll: probe.scrollX,
        errors: errors.filter((e) => !/favicon|ERR_/i.test(e)),
      });
    } catch (e) {
      results.push({ mode, name: signedIn ? name : name + '*', painted: false, error: String(e).slice(0, 120), errors });
    }
    await page.close();
  }
  await ctx.close();
 }
}

await browser.close();

let bad = 0;
console.log('\nmode  route          painted  chars  dark  sideScroll  bg                       errors');
console.log('-'.repeat(100));
for (const r of results) {
  const ok = r.painted && (r.errors?.length ?? 0) === 0 && !r.sideScroll;
  if (!ok) bad++;
  console.log(
    `${r.mode.padEnd(5)} ${r.name.padEnd(14)} ${String(r.painted).padEnd(8)} ${String(r.chars ?? '-').padEnd(6)} ${String(r.darkClass ?? '-').padEnd(5)} ${String(r.sideScroll ?? '-').padEnd(11)} ${String(r.bg ?? '-').padEnd(24)} ${(r.errors ?? []).slice(0, 1).join('') || (r.error ?? '')}`
  );
}
console.log('-'.repeat(100));
console.log(bad === 0 ? `render-walk: OK — ${results.length} renders clean.` : `render-walk: ${bad} of ${results.length} need attention.`);
process.exit(bad === 0 ? 0 : 1);
