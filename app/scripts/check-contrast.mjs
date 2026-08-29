/**
 * Contrast gate.
 *
 * The status tokens carry MEANING — pass, pending, fail. If a re-hue or a new
 * accent preset drops one of them below AA, the app still renders, every test
 * still passes, and the only symptom is that a user cannot tell "cleared" from
 * "short". Nothing else in this repo checks that.
 *
 * This is also what makes the fixed-preset decision defensible: five presets is
 * a countable number of assertions. An arbitrary hue picker would be untestable.
 *
 * Reads the COMPUTED values out of a real browser, so it tests what the cascade
 * actually produces rather than what the CSS appears to say.
 *
 *   node scripts/check-contrast.mjs
 */
import { chromium } from '@playwright/test';

const BASE = process.env.E2E_BASE_URL ?? 'http://localhost:5173';
const BRANDS = ['cyan', 'violet', 'emerald', 'amber', 'rose'];
const AA = 4.5;
const AA_LARGE = 3.0;

/** Ink tokens, each tested against both surfaces it can sit on. */
const INK = ['success', 'warning', 'info', 'destructive-ink', 'foreground', 'muted-foreground',
  'ladder-1', 'ladder-2', 'ladder-3', 'ladder-4'];
/** [fill, ink-on-fill] pairs. */
const PAIRS = [
  ['success-emphasis', 'success-on-emphasis'],
  ['warning-emphasis', 'warning-on-emphasis'],
  ['info-emphasis', 'info-on-emphasis'],
  ['primary', 'primary-foreground'],
  ['destructive', 'destructive-foreground'],
];

const browser = await chromium.launch();
const page = await browser.newPage();
await page.goto(BASE + '/login', { waitUntil: 'domcontentloaded' });

const failures = [];
const checked = [];

for (const mode of ['light', 'dark']) {
  for (const brand of BRANDS) {
    const readings = await page.evaluate(
      ({ mode, brand, INK, PAIRS }) => {
        const el = document.documentElement;
        el.classList.toggle('dark', mode === 'dark');
        el.dataset.brand = brand;

        // Resolve a token to real sRGB by painting it and reading it back —
        // getComputedStyle on a custom property returns the raw text, which for
        // oklch()/color-mix() is not something we can do arithmetic on.
        const probe = document.createElement('div');
        probe.style.position = 'fixed';
        probe.style.left = '-9999px';
        document.body.appendChild(probe);

        // Chromium returns modern color syntax VERBATIM from getComputedStyle —
        // `oklch(0.52 0.13 155)`, not rgb. Parsing those three numbers as RGB is
        // silently wrong (it made every pair look like it failed). Paint the
        // colour to a canvas and read the pixel back instead: that forces a real
        // sRGB conversion and handles oklch() and color-mix() alike.
        const cv = document.createElement('canvas');
        cv.width = cv.height = 1;
        const ctx = cv.getContext('2d', { willReadFrequently: true });
        const resolve = (token) => {
          probe.style.color = '';
          probe.style.color = `var(--${token})`;
          const str = getComputedStyle(probe).color;
          ctx.clearRect(0, 0, 1, 1);
          // White underlay, so a translucent token composites the way it would
          // on the page rather than reading back as near-black.
          ctx.fillStyle = '#ffffff';
          ctx.fillRect(0, 0, 1, 1);
          ctx.fillStyle = str;
          ctx.fillRect(0, 0, 1, 1);
          const d = ctx.getImageData(0, 0, 1, 1).data;
          return [d[0], d[1], d[2]];
        };
        const out = { ink: {}, fill: {}, surface: {} };
        for (const t of INK) out.ink[t] = resolve(t);
        for (const [f, i] of PAIRS) {
          out.fill[f] = resolve(f);
          out.fill[i] = resolve(i);
        }
        out.surface.background = resolve('background');
        out.surface.card = resolve('card');
        probe.remove();
        return out;
      },
      { mode, brand, INK, PAIRS }
    );

    const parse = (v) => (Array.isArray(v) && v.length === 3 ? v : null);
    const lum = (rgb) => {
      const c = rgb.map((v) => {
        const x = v / 255;
        return x <= 0.03928 ? x / 12.92 : Math.pow((x + 0.055) / 1.055, 2.4);
      });
      return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
    };
    const ratio = (a, b) => {
      const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p);
      return (x + 0.05) / (y + 0.05);
    };

    for (const [token, val] of Object.entries(readings.ink)) {
      for (const [sName, sVal] of Object.entries(readings.surface)) {
        const fg = parse(val);
        const bg = parse(sVal);
        if (!fg || !bg) continue;
        const r = ratio(fg, bg);
        checked.push(1);
        if (r < AA) failures.push(`${mode}/${brand}: --${token} on --${sName} = ${r.toFixed(2)}:1 (need ${AA})`);
      }
    }
    for (const [f, i] of PAIRS) {
      const bg = parse(readings.fill[f]);
      const fg = parse(readings.fill[i]);
      if (!fg || !bg) continue;
      const r = ratio(fg, bg);
      checked.push(1);
      // Fills carry short, bold labels — AA-large is the honest bar here.
      if (r < AA_LARGE) failures.push(`${mode}/${brand}: --${i} on --${f} = ${r.toFixed(2)}:1 (need ${AA_LARGE})`);
    }
  }
}

await browser.close();

if (failures.length) {
  console.error(`check-contrast: FAIL — ${failures.length} of ${checked.length} pairs below the bar:\n`);
  for (const f of failures) console.error('  - ' + f);
  process.exit(1);
}
console.log(`check-contrast: OK — ${checked.length} pairs pass across ${BRANDS.length} brands x 2 modes.`);
