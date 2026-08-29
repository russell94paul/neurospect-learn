/**
 * Dev rebuild helper — the thing the Settings → Developer button talks to.
 *
 * WHY THIS RUNS ON THE HOST AND NOT IN A CONTAINER
 * ------------------------------------------------
 * The obvious implementation is an endpoint on the FastAPI app that shells out
 * to `docker compose`. Do not do that. A container can only drive Docker if you
 * mount `/var/run/docker.sock` into it, and that socket is root on the host —
 * so it would hand full host control to a service that (a) is published through
 * a Cloudflare tunnel, (b) runs with DEBUG=true, and (c) therefore accepts
 * `POST /auth/debug/token` from anyone who gets past one Basic-auth password.
 * That trade is never worth a convenience button.
 *
 * This process runs on the host instead, so no socket is mounted anywhere, and
 * the API keeps having no ability to execute anything.
 *
 * WHY THE TUNNEL CANNOT REACH IT
 * ------------------------------
 * Three independent reasons, in order of how hard they are to defeat:
 *
 *  1. STRUCTURAL. The button fetches `http://127.0.0.1:5199` *from the browser*.
 *     Loaded through the tunnel, that address resolves on the VISITOR's machine,
 *     not on this one. A remote visitor cannot address this process at all — not
 *     because a check refuses them, but because the packets never leave their
 *     laptop. This is the one that actually matters.
 *  2. NETWORK. The listener binds 127.0.0.1 explicitly, so nothing off-box can
 *     open a socket to it even on the LAN.
 *  3. PROXY. `app/nginx-common.conf` proxies only `/_api/` and static assets.
 *     Nothing here is exposed through nginx, so the tunnel has no path to it.
 *     KEEP IT THAT WAY — adding a location for this would defeat 1 and 3 at once.
 *
 * And against a malicious website in your own browser: every mutating route
 * requires `Content-Type: application/json`, which forces a CORS preflight. An
 * unknown Origin fails the preflight, so the browser never sends the POST. The
 * Host header is checked too, which is what stops DNS rebinding from turning a
 * attacker-controlled name into 127.0.0.1.
 *
 *   node scripts/dev-rebuild.mjs          (or: npm run dev:rebuild -- from app/)
 */
import { createServer } from 'node:http';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { dirname, resolve as resolvePath } from 'node:path';

const PORT = Number(process.env.DEV_REBUILD_PORT ?? 5199);
const HOST = '127.0.0.1';
const REPO_ROOT = resolvePath(dirname(fileURLToPath(import.meta.url)), '..');

/** Only these may be rebuilt, and the list is not caller-extensible. */
const ALLOWED_SERVICES = ['app', 'api'];
/** Where the button may legitimately be served from. */
const ALLOWED_ORIGINS = new Set([
  'http://localhost:5174',
  'http://127.0.0.1:5174',
  'http://localhost:5173',
  'http://127.0.0.1:5173',
]);
const ALLOWED_HOSTS = new Set([`127.0.0.1:${PORT}`, `localhost:${PORT}`]);

const MAX_LOG_LINES = 300;
const TIMEOUT_MS = 10 * 60_000;

/** @type {{state:'idle'|'running'|'done'|'error', services:string[], startedAt:string|null, finishedAt:string|null, exitCode:number|null, log:string[]}} */
const status = {
  state: 'idle',
  services: [],
  startedAt: null,
  finishedAt: null,
  exitCode: null,
  log: [],
};
let child = null;

function push(line) {
  for (const l of String(line).split(/\r?\n/)) {
    if (!l.trim()) continue;
    status.log.push(l);
  }
  if (status.log.length > MAX_LOG_LINES) {
    status.log.splice(0, status.log.length - MAX_LOG_LINES);
  }
}

function startRebuild(services) {
  status.state = 'running';
  status.services = services;
  status.startedAt = new Date().toISOString();
  status.finishedAt = null;
  status.exitCode = null;
  status.log = [];

  // `up -d --build` rather than `restart`: the frontend bundle is baked into the
  // image at build time (app/Dockerfile runs `npm run build` then copies dist/
  // into nginx) and there is NO source bind mount, so a restart would re-serve
  // the byte-identical old files.
  const args = ['compose', 'up', '-d', '--build', ...services];
  push(`$ docker ${args.join(' ')}`);

  // shell:false — no string is ever handed to a shell, and `services` is
  // filtered against ALLOWED_SERVICES before we get here.
  child = spawn('docker', args, { cwd: REPO_ROOT, shell: false });

  const timer = setTimeout(() => {
    push(`! timed out after ${TIMEOUT_MS / 60000} min — killing`);
    child?.kill();
  }, TIMEOUT_MS);

  child.stdout.on('data', (d) => push(d.toString()));
  child.stderr.on('data', (d) => push(d.toString())); // compose reports progress on stderr
  child.on('error', (err) => {
    clearTimeout(timer);
    push(`! failed to start docker: ${err.message}`);
    status.state = 'error';
    status.exitCode = -1;
    status.finishedAt = new Date().toISOString();
    child = null;
  });
  child.on('close', (code) => {
    clearTimeout(timer);
    status.exitCode = code;
    status.state = code === 0 ? 'done' : 'error';
    status.finishedAt = new Date().toISOString();
    push(code === 0 ? '✓ rebuild complete' : `✗ docker exited ${code}`);
    child = null;
  });
}

function cors(req, res) {
  const origin = req.headers.origin;
  if (origin && ALLOWED_ORIGINS.has(origin)) {
    res.setHeader('Access-Control-Allow-Origin', origin);
    res.setHeader('Vary', 'Origin');
    res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
    res.setHeader('Access-Control-Max-Age', '600');
    return true;
  }
  return false;
}

function json(res, code, body) {
  res.writeHead(code, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify(body));
}

const server = createServer((req, res) => {
  // DNS-rebinding guard: a hostile name resolving to 127.0.0.1 arrives with its
  // own Host header, not ours.
  if (!ALLOWED_HOSTS.has(req.headers.host ?? '')) {
    res.writeHead(403).end('bad host');
    return;
  }

  const originOk = cors(req, res);

  if (req.method === 'OPTIONS') {
    // Unknown origin → no CORS headers → the browser never sends the real request.
    res.writeHead(originOk ? 204 : 403).end();
    return;
  }

  const url = new URL(req.url ?? '/', `http://${HOST}:${PORT}`);

  if (req.method === 'GET' && url.pathname === '/status') {
    json(res, 200, { ok: true, ...status, services: ALLOWED_SERVICES });
    return;
  }

  if (req.method === 'POST' && url.pathname === '/rebuild') {
    if (!originOk) {
      json(res, 403, { ok: false, error: 'origin not allowed' });
      return;
    }
    // Requiring JSON is what forces the preflight above to happen at all.
    if (!(req.headers['content-type'] ?? '').includes('application/json')) {
      json(res, 415, { ok: false, error: 'content-type must be application/json' });
      return;
    }
    if (status.state === 'running') {
      json(res, 409, { ok: false, error: 'a rebuild is already running' });
      return;
    }

    let body = '';
    req.on('data', (c) => {
      body += c;
      if (body.length > 4096) req.destroy();
    });
    req.on('end', () => {
      let requested = ALLOWED_SERVICES;
      try {
        const parsed = JSON.parse(body || '{}');
        if (Array.isArray(parsed.services) && parsed.services.length) {
          requested = parsed.services.filter((s) => ALLOWED_SERVICES.includes(s));
        }
      } catch {
        /* empty or malformed body → rebuild everything */
      }
      if (!requested.length) {
        json(res, 400, { ok: false, error: 'no valid services' });
        return;
      }
      startRebuild(requested);
      json(res, 202, { ok: true, state: status.state, services: requested });
    });
    return;
  }

  json(res, 404, { ok: false, error: 'not found' });
});

server.listen(PORT, HOST, () => {
  console.log(`dev-rebuild listening on http://${HOST}:${PORT}`);
  console.log(`  repo:     ${REPO_ROOT}`);
  console.log(`  services: ${ALLOWED_SERVICES.join(', ')}`);
  console.log('  The Settings → Developer button in the app talks to this.');
  console.log('  Bound to 127.0.0.1 and never proxied by nginx — the tunnel cannot reach it.');
});
