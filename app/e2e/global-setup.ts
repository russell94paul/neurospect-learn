import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname } from 'node:path';

/**
 * Authenticate once for the whole suite: mint a debug JWT from the API and
 * write it into a Playwright storageState file as the app's localStorage token.
 * Runs before the frontend webServer, so it talks to the API directly (no
 * browser) — the API must be up with DEBUG=true.
 */
const API_URL = process.env.E2E_API_URL ?? 'http://localhost:8000';
const BASE_URL = process.env.E2E_BASE_URL ?? 'http://localhost:5173';
const STATE_PATH = './e2e/.auth/state.json';
const TOKEN_KEY = 'neurospect_learn_token'; // must match app/src/lib/api.ts

async function globalSetup() {
  const res = await fetch(`${API_URL}/auth/debug/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ discord_id: 'e2e' }),
  }).catch((e) => {
    throw new Error(
      `Could not reach the API at ${API_URL} to mint a debug token — is it running with DEBUG=true? (${e})`
    );
  });
  if (!res.ok) {
    throw new Error(`Debug token request failed: ${res.status} (DEBUG=true on the API?)`);
  }
  const { access_token } = (await res.json()) as { access_token: string };

  const state = {
    cookies: [],
    origins: [
      { origin: BASE_URL, localStorage: [{ name: TOKEN_KEY, value: access_token }] },
    ],
  };
  mkdirSync(dirname(STATE_PATH), { recursive: true });
  writeFileSync(STATE_PATH, JSON.stringify(state, null, 2));
}

export default globalSetup;
