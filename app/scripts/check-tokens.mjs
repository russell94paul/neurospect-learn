/**
 * Token-emission gate.
 *
 * THE FAILURE MODE THIS EXISTS FOR: if a semantic token class is misspelled, or
 * its `@theme inline` entry is missing, Tailwind simply does not generate the
 * class. The element renders transparent, nothing throws, and the whole
 * Playwright suite still passes — it selects by role and text and asserts
 * nothing about colour. This is the only automated check that catches it.
 *
 * Two independent assertions, because they fail differently:
 *   1. Every semantic token class USED in src/ was emitted into the bundle.
 *      (Tailwind is JIT, so an unused class is legitimately absent — only the
 *      used ones can be checked, and only they matter.)
 *   2. Every semantic custom property is DEFINED in both modes. A token whose
 *      value is missing makes color-mix() invalid, which silently drops the
 *      entire declaration — so `bg-success/10` disappears rather than degrades.
 *
 * Run after `vite build`.
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';

const DIST = 'dist/assets';
const SRC = 'src';

/** The semantic families this design system owns. */
const FAMILIES = [
  'success',
  'success-emphasis',
  'success-on-emphasis',
  'success-muted',
  'warning',
  'warning-emphasis',
  'warning-on-emphasis',
  'warning-muted',
  'info',
  'info-emphasis',
  'info-on-emphasis',
  'info-muted',
  'destructive-ink',
  'destructive-muted',
  'ladder-1',
  'ladder-2',
  'ladder-3',
  'ladder-4',
  'ladder-1-muted',
  'ladder-2-muted',
  'ladder-3-muted',
  'ladder-4-muted',
  'overlay',
  'brand-2',
  'chart-backtest',
  'chart-live',
];

/** Custom properties that must resolve in BOTH :root and .dark. */
const MUST_DEFINE = FAMILIES.filter((f) => f !== 'brand-2' && !f.startsWith('chart-'));

function walk(dir) {
  const out = [];
  for (const e of readdirSync(dir)) {
    const p = join(dir, e);
    if (statSync(p).isDirectory()) out.push(...walk(p));
    else if (/\.(tsx|ts)$/.test(p)) out.push(p);
  }
  return out;
}

const cssFiles = readdirSync(DIST).filter((f) => f.endsWith('.css'));
if (cssFiles.length === 0) {
  console.error(`check-tokens: no CSS in ${DIST} — run \`npm run build\` first.`);
  process.exit(1);
}
const css = cssFiles.map((f) => readFileSync(join(DIST, f), 'utf8')).join('\n');
const source = walk(SRC)
  .map((f) => readFileSync(f, 'utf8'))
  .join('\n');

// ---- 1. used-but-not-emitted -------------------------------------------
const prefixes = '(?:bg|text|border|ring|fill|stroke|from|to|via|divide|outline)';
const used = new Set();
for (const fam of FAMILIES) {
  const re = new RegExp(`\\b${prefixes}-${fam}(\\/\\d{1,3})?\\b`, 'g');
  for (const m of source.matchAll(re)) used.add(m[0]);
}

// Tailwind escapes the `/` of an opacity modifier with a single backslash.
const BACKSLASH = String.fromCharCode(92);
const escape = (c) => c.split('/').join(BACKSLASH + '/');
const notEmitted = [...used].filter((c) => !css.includes(`.${escape(c)}`) && !css.includes(`.${c}`));

// ---- 2. tokens that must be defined in both modes ------------------------
const rootBlock = css.match(/:root\s*\{[\s\S]*?\}/)?.[0] ?? '';
const darkBlock = css.match(/\.dark\s*\{[\s\S]*?\}/)?.[0] ?? '';
const undefinedIn = [];
for (const t of MUST_DEFINE) {
  if (!rootBlock.includes(`--${t}:`)) undefinedIn.push(`--${t} (light)`);
  if (!darkBlock.includes(`--${t}:`)) undefinedIn.push(`--${t} (dark)`);
}

let failed = false;
if (notEmitted.length) {
  failed = true;
  console.error(`check-tokens: FAIL — ${notEmitted.length} class(es) used in src/ but NOT emitted:`);
  for (const m of notEmitted) console.error(`  - .${m}`);
  console.error('\nAn unemitted class renders as nothing. Check the spelling at the use');
  console.error('site and the matching --color-* entry in the @theme inline block.');
}
if (undefinedIn.length) {
  failed = true;
  console.error(`\ncheck-tokens: FAIL — ${undefinedIn.length} token(s) undefined:`);
  for (const m of undefinedIn) console.error(`  - ${m}`);
  console.error('\nAn undefined token makes color-mix() invalid, which drops the WHOLE');
  console.error('declaration — the utility disappears rather than falling back.');
}
if (failed) process.exit(1);

console.log(
  `check-tokens: OK — ${used.size} token classes emitted, ${MUST_DEFINE.length} tokens defined in both modes.`
);
