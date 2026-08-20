/**
 * Rendered-surface check for the Cloudflare-tunnel listener (2026-08-20).
 *
 * The curl matrix proves the gate and the /_api proxy answer correctly. It does
 * NOT prove the app paints: a bundle whose API calls 401 behind the scenes still
 * returns 200 for index.html. So this drives a real browser through the real
 * public hostname — Basic auth, debug login, then an authed page — and captures
 * screenshots.
 *
 *   node scripts/tunnel-render-check.mjs <https://…trycloudflare.com> <user> <pass>
 *
 * Screenshots land in api/docs/evidence/tunnel/.
 */
import { chromium } from '@playwright/test';
import { mkdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const [url, username, password] = process.argv.slice(2);
if (!url || !username || !password) {
  console.error('usage: node scripts/tunnel-render-check.mjs <url> <user> <pass>');
  process.exit(2);
}

const outDir = resolve(dirname(fileURLToPath(import.meta.url)), '../../api/docs/evidence/tunnel');
mkdirSync(outDir, { recursive: true });

const browser = await chromium.launch();
const context = await browser.newContext({
  httpCredentials: { username, password },
  viewport: { width: 1440, height: 900 },
});
const page = await context.newPage();

// Anything the SPA fails to load is the whole point of this check, so surface it
// rather than letting a blank panel pass as a render.
const failures = [];
page.on('console', (m) => m.type() === 'error' && failures.push(`console: ${m.text()}`));
page.on('requestfailed', (r) => failures.push(`request: ${r.url()} ${r.failure()?.errorText}`));
page.on('response', (r) => {
  if (r.url().includes('/_api/') && r.status() >= 400 && !r.url().includes('/auth/me')) {
    failures.push(`api: ${r.status()} ${r.url()}`);
  }
});

await page.goto(url, { waitUntil: 'networkidle' });
await page.screenshot({ path: `${outDir}/01-login.png` });
console.log('login page   :', await page.title(), '|', page.url());

await page.getByPlaceholder('Enter any Discord ID').fill('tunnel-smoke');
await page.getByRole('button', { name: /sign in|log in|debug/i }).last().click();
await page.waitForURL((u) => !u.pathname.startsWith('/login'), { timeout: 20_000 });
await page.waitForLoadState('networkidle');
await page.screenshot({ path: `${outDir}/02-after-login.png`, fullPage: true });
console.log('after login  :', page.url());

for (const [name, path] of [['03-path', '/path'], ['04-journal', '/journal'], ['05-gate', '/gate']]) {
  await page.goto(`${url}${path}`, { waitUntil: 'networkidle' });
  await page.screenshot({ path: `${outDir}/${name}.png`, fullPage: true });
  const body = (await page.textContent('body')) ?? '';
  console.log(`${path.padEnd(9)}: ${body.replace(/\s+/g, ' ').trim().slice(0, 90)}`);
}

console.log(failures.length ? `\nFAILURES (${failures.length}):` : '\nNo console errors, failed requests, or 4xx/5xx API calls.');
failures.forEach((f) => console.log('  -', f));

await browser.close();
process.exit(failures.length ? 1 : 0);
