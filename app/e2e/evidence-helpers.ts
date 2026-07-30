import { deflateSync } from 'node:zlib';
import type { APIRequestContext } from '@playwright/test';

/**
 * Evidence helpers for the e2e suite (Phase E2).
 *
 * Since E2 a rep exists only as evidence of the work, so any spec that needs a
 * concept or drill AT its rep target has to upload a capture, exactly as the user
 * would — the API bypass the old fixtures used (`reps: N` on PATCH) no longer
 * exists. That is the point of the phase.
 *
 * `chartPng` writes a real PNG with no image library: a seeded low-frequency
 * block pattern (so two seeds are never perceptual near-duplicates) over noise
 * (so the file compresses poorly and clears the minimum-size check).
 */

const CRC_TABLE = (() => {
  const table = new Int32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    table[n] = c;
  }
  return table;
})();

function crc32(buf: Buffer): number {
  let c = -1;
  for (const byte of buf) c = CRC_TABLE[(c ^ byte) & 0xff] ^ (c >>> 8);
  return (c ^ -1) >>> 0;
}

function chunk(type: string, data: Buffer): Buffer {
  const len = Buffer.alloc(4);
  len.writeUInt32BE(data.length);
  const body = Buffer.concat([Buffer.from(type, 'ascii'), data]);
  const crc = Buffer.alloc(4);
  crc.writeUInt32BE(crc32(body));
  return Buffer.concat([len, body, crc]);
}

/** A deterministic, visually distinct fake chart capture as PNG bytes. */
export function chartPng(seed: number, size = 128): Buffer {
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(size, 0);
  ihdr.writeUInt32BE(size, 4);
  ihdr[8] = 8; // bit depth
  ihdr[9] = 2; // truecolour RGB
  // 10..12 = compression / filter / interlace, all 0

  // A tiny LCG so the image is reproducible per seed.
  let state = (Math.abs(seed) * 2654435761) % 2147483647 || 1;
  const rand = () => (state = (state * 48271) % 2147483647) / 2147483647;

  // The BLOCK GRID must itself be seed-driven, not a shifted periodic pattern:
  // a perceptual hash reads low-frequency structure, and a phase-shifted
  // periodic pattern hashes identically (measured: distance 0 across seeds).
  const cells = 8;
  const cell = Math.ceil(size / cells);
  const grid = Array.from({ length: cells * cells }, () => Math.floor(rand() * 256));

  const raw = Buffer.alloc(size * (size * 3 + 1));
  let o = 0;
  for (let y = 0; y < size; y++) {
    raw[o++] = 0; // filter: none
    for (let x = 0; x < size; x++) {
      const base = grid[Math.floor(y / cell) * cells + Math.floor(x / cell)];
      // Noise on top so the file does not compress below the size floor.
      const noise = Math.floor(rand() * 30) - 15;
      const v = Math.max(0, Math.min(255, base + noise));
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

export interface EvidenceSubject {
  subject_type: 'drill' | 'concept' | 'journal_entry' | 'missed_trade';
  drill_ref?: string;
  concept_id?: string;
  journal_entry_id?: string;
  missed_trade_id?: string;
}

/** POST one evidence asset through the real endpoint. */
export async function uploadEvidence(
  request: APIRequestContext,
  apiUrl: string,
  tok: string,
  subject: EvidenceSubject,
  { seed, reps = 1 }: { seed: number; reps?: number }
) {
  const multipart: Record<string, string | { name: string; mimeType: string; buffer: Buffer }> = {
    file: { name: `chart-${seed}.png`, mimeType: 'image/png', buffer: chartPng(seed) },
    reps_claimed: String(reps),
  };
  for (const [k, v] of Object.entries(subject)) if (v) multipart[k] = v;

  return request.post(`${apiUrl}/api/evidence`, {
    headers: { Authorization: `Bearer ${tok}` },
    multipart,
  });
}

/** Give a subject `reps` reps, splitting across assets (one claims ≤ 100). */
export async function giveReps(
  request: APIRequestContext,
  apiUrl: string,
  tok: string,
  subject: EvidenceSubject,
  reps: number,
  seedBase: number
) {
  let remaining = Math.max(1, reps);
  let i = 0;
  while (remaining > 0) {
    const claim = Math.min(100, remaining);
    const res = await uploadEvidence(request, apiUrl, tok, subject, {
      seed: seedBase * 100 + i,
      reps: claim,
    });
    if (!res.ok()) throw new Error(`evidence upload failed: ${res.status()} ${await res.text()}`);
    remaining -= claim;
    i++;
  }
}

/** Remove every evidence asset the debug user owns — keeps specs re-runnable,
 * since the deterministic tier refuses a duplicate image. */
export async function clearEvidence(request: APIRequestContext, apiUrl: string, tok: string) {
  const res = await request.get(`${apiUrl}/api/evidence`, {
    headers: { Authorization: `Bearer ${tok}` },
  });
  for (const asset of (await res.json()) as Array<{ id: string }>) {
    await request.delete(`${apiUrl}/api/evidence/${asset.id}`, {
      headers: { Authorization: `Bearer ${tok}` },
    });
  }
}
