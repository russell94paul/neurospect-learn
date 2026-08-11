/**
 * E6 live walkthrough — reads the RENDERED surfaces and captures the evidence.
 *
 * Phase E4 and E5 ran this step through the claude-in-chrome extension. It was not
 * connected for the E6 session, so the same walk is driven through Playwright's
 * Chromium instead: the same rendering engine, the same real DOM, the same console
 * stream. What matters is not the driver but that a HUMAN-VISIBLE surface is read
 * rather than an API response — E5's only real defect ("0% of your calls have an
 * outcome recorded" printed under "no outcome has been recorded") was two correct
 * JSON responses that contradicted each other once painted, and E6 hit the same
 * class again ("0 of 5 signals had something to measure" under five "not measured"
 * rows). A query-layer check passes both times.
 *
 *   node scripts/e6-walkthrough.mjs
 *
 * Prereqs: API on :8000 with DEBUG=true, vite on :5173.
 * Writes screenshots + a console report to api/docs/evidence/e6/.
 */

import { mkdirSync, writeFileSync } from 'node:fs';
import { deflateSync } from 'node:zlib';
import { chromium } from '@playwright/test';

const API = process.env.E2E_API_URL ?? 'http://localhost:8000';
const BASE = process.env.E2E_BASE_URL ?? 'http://localhost:5173';
const TOKEN_KEY = 'neurospect_learn_token';
const DISCORD_ID = 'e6-walkthrough';
const OUT = new URL('../../api/docs/evidence/e6/', import.meta.url).pathname.replace(/^\//, '');
const DRILL = 'aura D1-a';

mkdirSync(OUT, { recursive: true });

const console_messages = [];
const results = [];

function record(step, ok, detail) {
  results.push({ step, ok, detail });
  console.log(`${ok ? '  OK ' : '  ✗  '} ${step}${detail ? ` — ${detail}` : ''}`);
}

const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
const page = await context.newPage();

page.on('console', (m) => console_messages.push({ type: m.type(), text: m.text() }));
page.on('pageerror', (e) => console_messages.push({ type: 'pageerror', text: String(e) }));

// --- auth + a clean slate for this throwaway user ---------------------------
const tokenRes = await context.request.post(`${API}/auth/debug/token`, {
  data: { discord_id: DISCORD_ID },
});
const token = (await tokenRes.json()).access_token;
const authed = { headers: { Authorization: `Bearer ${token}` } };

const existing = await (await context.request.get(`${API}/api/evidence`, authed)).json();
for (const a of existing) await context.request.delete(`${API}/api/evidence/${a.id}`, authed);

await context.addInitScript(
  ([k, v]) => window.localStorage.setItem(k, v),
  [TOKEN_KEY, token]
);

// ===========================================================================
// 1. The strip with NOTHING measured — the property the whole phase rests on
// ===========================================================================
await page.goto(`${BASE}/gate`);
await page.getByTestId('honesty-strip').waitFor();
const emptyText = await page.getByTestId('honesty-strip').innerText();

record(
  'empty strip: 5 signals, all "not measured"',
  (await page.getByTestId('honesty-unmeasured').count()) === 5,
  `${await page.getByTestId('honesty-signal').count()} signals`
);
record(
  'empty strip: NO count of any kind is painted',
  !/\b0 of \d/.test(emptyText) && !/\b0 captures\b/.test(emptyText),
  'no "0 of N", no "0 captures"'
);
record(
  'empty strip: says so in words',
  emptyText.includes('Nothing has been measured yet'),
  'the summary line is absent, replaced by an explicit absence'
);
record(
  'empty strip: states it gates nothing',
  emptyText.includes('None of this gates anything')
);
await page.screenshot({ path: `${OUT}e6-gate-page.png`, fullPage: true });
// Element-scoped too: a full-page shot of /gate is mostly the seven model cards,
// and the strip is the artifact worth reading.
await page.getByTestId('honesty-strip').screenshot({ path: `${OUT}e6-strip-not-measured.png` });

// The gate verdict, before anything is captured.
const clearedBefore = await page.getByTestId('gate-overall').getAttribute('data-cleared-count');
const metBefore = await page
  .getByTestId('gate-requirement')
  .evaluateAll((els) => els.map((e) => e.getAttribute('data-met')).join(','));

// ===========================================================================
// 2. Trip the signals, and prove the verdict above them does not move
// ===========================================================================
async function upload({ seed, reps = 1, capturedAt = null }) {
  const multipart = {
    file: { name: `c-${seed}.png`, mimeType: 'image/png', buffer: makePng(seed) },
    subject_type: 'drill',
    drill_ref: DRILL,
    reps_claimed: String(reps),
  };
  if (capturedAt) multipart.captured_at = capturedAt;
  const res = await context.request.post(`${API}/api/evidence`, { ...authed, multipart });
  if (!res.ok()) throw new Error(`upload ${seed}: ${res.status()} ${await res.text()}`);
}

// A minimal seeded PNG (same approach as e2e/evidence-helpers.ts, inlined so this
// script has no TS import step).
function makePng(seed) {
  const size = 128;
  const crcTable = (() => {
    const t = new Int32Array(256);
    for (let n = 0; n < 256; n++) {
      let c = n;
      for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
      t[n] = c;
    }
    return t;
  })();
  const crc32 = (buf) => {
    let c = -1;
    for (const b of buf) c = crcTable[(c ^ b) & 0xff] ^ (c >>> 8);
    return (c ^ -1) >>> 0;
  };
  const chunk = (type, data) => {
    const len = Buffer.alloc(4);
    len.writeUInt32BE(data.length);
    const body = Buffer.concat([Buffer.from(type, 'ascii'), data]);
    const crc = Buffer.alloc(4);
    crc.writeUInt32BE(crc32(body));
    return Buffer.concat([len, body, crc]);
  };
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(size, 0);
  ihdr.writeUInt32BE(size, 4);
  ihdr[8] = 8;
  ihdr[9] = 2;
  let state = (Math.abs(seed) * 2654435761) % 2147483647 || 1;
  const rand = () => (state = (state * 48271) % 2147483647) / 2147483647;
  const cells = 8;
  const cell = Math.ceil(size / cells);
  const grid = Array.from({ length: cells * cells }, () => Math.floor(rand() * 256));
  const raw = Buffer.alloc(size * (size * 3 + 1));
  let o = 0;
  for (let y = 0; y < size; y++) {
    raw[o++] = 0;
    for (let x = 0; x < size; x++) {
      const base = grid[Math.floor(y / cell) * cells + Math.floor(x / cell)];
      const v = Math.max(0, Math.min(255, base + Math.floor(rand() * 30) - 15));
      raw[o++] = v;
      raw[o++] = Math.floor(v * 0.75);
      raw[o++] = Math.floor(v * 0.5);
    }
  }
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk('IHDR', ihdr),
    chunk('IDAT', deflateSync(raw)),
    chunk('IEND', Buffer.alloc(0)),
  ]);
}

const backdated = new Date(Date.now() - 9 * 86400_000).toISOString();
await upload({ seed: 9001, reps: 25 });
await upload({ seed: 9002, reps: 9, capturedAt: backdated });

await page.goto(`${BASE}/gate`);
await page.getByTestId('honesty-strip').waitFor();
const litText = await page.getByTestId('honesty-strip').innerText();

record(
  'measured strip: bulk marking counts 2 of 2 captures',
  /Reps claimed per capture[\s\S]*?2 of 2/.test(litText)
);
record(
  'measured strip: pacing measured on 1 gap (the two uploads were seconds apart)',
  /Rep pacing[\s\S]*?1 of 1/.test(litText)
);
record(
  'measured strip: back-dating found the 9-day-old assertion',
  /Back-dated captures[\s\S]*?1 of 1/.test(litText)
);
record(
  'measured strip: every threshold is printed (60s, 24h)',
  litText.includes('under 60s') && litText.includes('more than 24h')
);
record(
  'measured strip: the implicated subject is named',
  litText.includes(DRILL)
);
record(
  'measured strip: still no percentage, no progress bar, no target',
  !/\d+\s?%/.test(litText) &&
    (await page.getByTestId('honesty-strip').locator('[role="progressbar"]').count()) === 0
);

// THE assertion: the verdict above the strip is untouched.
const clearedAfter = await page.getByTestId('gate-overall').getAttribute('data-cleared-count');
const metAfter = await page
  .getByTestId('gate-requirement')
  .evaluateAll((els) => els.map((e) => e.getAttribute('data-met')).join(','));
record(
  'the Readiness-to-Live Gate did NOT move while every signal lit up',
  clearedAfter === clearedBefore && metAfter === metBefore,
  `cleared ${clearedBefore} → ${clearedAfter}`
);
await page.getByTestId('honesty-strip').screenshot({ path: `${OUT}e6-strip-measured.png` });

// ===========================================================================
// 3. Declared rest days
// ===========================================================================
await context.request.put(`${API}/api/preferences`, {
  ...authed,
  data: {
    timezone: 'UTC', mon_minutes: 60, tue_minutes: 60, wed_minutes: 60, thu_minutes: 60,
    fri_minutes: 60, sat_minutes: 60, sun_minutes: 60, max_session_minutes: 45,
    blackout_dates: [], target_go_live_date: null, active_track: 'aura',
  },
});

const iso = (d) => new Date(Date.now() + d * 86400_000).toISOString().slice(0, 10);

await page.goto(`${BASE}/plan/setup`);
await page.getByTestId('rest-days').waitFor();
const card = page.getByTestId('rest-days');

record(
  'rest days: the past is not offered (min = today)',
  (await card.getByLabel('Date').getAttribute('min')) === iso(0)
);

const past = await context.request.post(`${API}/api/rest-days`, {
  ...authed,
  data: { rest_date: iso(-3) },
});
record(
  'rest days: the SERVER refuses a back-dated declaration (422)',
  past.status() === 422,
  (await past.json()).detail?.slice(0, 60)
);

const future = iso(5);
const seeded = await context.request.get(`${API}/api/rest-days`, authed);
if (!(await seeded.json()).some((d) => d.rest_date === future)) {
  await card.getByLabel('Date').fill(future);
  await card.getByLabel('Reason (optional)').fill('planned break');
  await card.getByRole('button', { name: 'Declare' }).click();
}
await card.getByTestId('rest-day').first().waitFor();
const restText = await card.innerText();
record(
  'rest days: a booked day renders with when it was declared',
  restText.includes(future) && /declared \d+ days? ahead/.test(restText)
);
record(
  'rest days: no edit or delete affordance on the row',
  (await card.getByTestId('rest-day').first().getByRole('button').count()) === 0
);
await card.screenshot({ path: `${OUT}e6-rest-days.png` });

// ===========================================================================
// 4. The evidence-backed streak, beside the marked one
// ===========================================================================
await page.goto(`${BASE}/today`);
await page.getByTestId('adherence-meter').waitFor();
const meter = page.getByTestId('adherence-meter');
const meterText = await meter.innerText();
const streakBefore = await page
  .getByTestId('evidence-backed-consistency')
  .getAttribute('data-evidence-streak');

record(
  'today: BOTH figures render — the marked adherence and the evidence-backed run',
  meterText.includes('Adherence') && meterText.includes('Backed by evidence'),
  meterText.replace(/\s+/g, ' ').slice(0, 120)
);

for (const n of [30, 31, 32]) {
  await context.request.post(`${API}/api/rest-days`, { ...authed, data: { rest_date: iso(n) } });
}
await page.goto(`${BASE}/today`);
await page.getByTestId('adherence-meter').waitFor();
const streakAfter = await page
  .getByTestId('evidence-backed-consistency')
  .getAttribute('data-evidence-streak');
record(
  'today: declaring 3 more rest days did NOT raise the evidence streak',
  streakAfter === streakBefore,
  `${streakBefore} → ${streakAfter}`
);
await page.getByTestId('adherence-meter').screenshot({
  path: `${OUT}e6-evidence-backed-streak.png`,
});

// ===========================================================================
// Console report
// ===========================================================================
const errors = console_messages.filter(
  (m) => m.type === 'error' || m.type === 'pageerror'
);
record(`console: ${errors.length} errors across the whole walk`, errors.length === 0,
  errors.map((e) => e.text).join(' | ').slice(0, 300));

writeFileSync(
  `${OUT}e6-walkthrough.json`,
  JSON.stringify({ results, console_messages }, null, 2) + '\n'
);

await browser.close();

const failed = results.filter((r) => !r.ok);
console.log(`\n${results.length - failed.length}/${results.length} checks passed`);
console.log(`console messages: ${console_messages.length} (${errors.length} errors)`);
process.exit(failed.length === 0 ? 0 : 1);
