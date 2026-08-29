import { useCallback, useEffect, useRef, useState } from 'react';
import { Hammer, Loader2, RefreshCw, TriangleAlert } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

/**
 * Rebuild the Docker stack from the UI.
 *
 * WHY THIS IS SAFE TO PUT IN A PAGE THAT IS PUBLISHED THROUGH A TUNNEL
 * --------------------------------------------------------------------
 * It talks to a helper on `127.0.0.1:5199` that runs on the HOST, not in a
 * container (see scripts/dev-rebuild.mjs for why that distinction is the whole
 * security argument). Loaded through the tunnel, `127.0.0.1` resolves on the
 * VISITOR's machine — so a remote visitor's browser cannot address the helper at
 * all. The isolation is structural, not a permission check someone could talk
 * their way past.
 *
 * `isLocal()` below is therefore cosmetic: it hides a control that would not have
 * worked anyway, so a remote viewer is not offered a button that silently fails.
 * It is not the security boundary and must never be treated as one.
 */

const HELPER = 'http://127.0.0.1:5199';
const POLL_MS = 1500;

type State = 'idle' | 'running' | 'done' | 'error';

interface Status {
  ok: boolean;
  state: State;
  services: string[];
  exitCode: number | null;
  log: string[];
}

/** True only when this page is being served from this machine. */
function isLocal(): boolean {
  if (typeof location === 'undefined') return false;
  return ['localhost', '127.0.0.1', '[::1]'].includes(location.hostname);
}

/** The hashed bundle name in a given index.html — how we tell old from new. */
async function bundleHash(origin: string): Promise<string | null> {
  try {
    const html = await fetch(`${origin}/index.html?ts=${Date.now()}`, {
      cache: 'no-store',
    }).then((r) => r.text());
    return html.match(/assets\/index-([A-Za-z0-9_-]+)\.js/)?.[1] ?? null;
  } catch {
    return null;
  }
}

export function RebuildButton() {
  const [available, setAvailable] = useState<boolean | null>(null);
  const [status, setStatus] = useState<Status | null>(null);
  const [phase, setPhase] = useState<'idle' | 'building' | 'waiting' | 'error'>('idle');
  const [error, setError] = useState<string | null>(null);
  const beforeHash = useRef<string | null>(null);
  const logRef = useRef<HTMLPreElement>(null);

  // Is the helper running? Probing beats rendering a button that does nothing.
  useEffect(() => {
    if (!isLocal()) return;
    let cancelled = false;
    fetch(`${HELPER}/status`)
      .then((r) => r.json())
      .then((s: Status) => {
        if (cancelled) return;
        setAvailable(true);
        setStatus(s);
        if (s.state === 'running') setPhase('building');
      })
      .catch(() => !cancelled && setAvailable(false));
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight });
  }, [status?.log.length]);

  const start = useCallback(async () => {
    setError(null);
    // Record what we are serving now, so we can tell when the NEW bundle is live
    // instead of reloading into the old one.
    beforeHash.current = await bundleHash(location.origin);

    try {
      const res = await fetch(`${HELPER}/rebuild`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ services: ['app', 'api'] }),
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        throw new Error(b.error ?? `helper returned ${res.status}`);
      }
      setPhase('building');
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setPhase('error');
    }
  }, []);

  // Poll the helper while it builds.
  useEffect(() => {
    if (phase !== 'building') return;
    const id = setInterval(async () => {
      try {
        const s: Status = await fetch(`${HELPER}/status`).then((r) => r.json());
        setStatus(s);
        if (s.state === 'done') setPhase('waiting');
        if (s.state === 'error') {
          setError(`docker exited ${s.exitCode}`);
          setPhase('error');
        }
      } catch {
        /* the helper is on the host and survives the rebuild; a blip is fine */
      }
    }, POLL_MS);
    return () => clearInterval(id);
  }, [phase]);

  // The container we are served from has just been replaced. Wait for a bundle
  // whose hash differs from the one we loaded, then reload into it.
  useEffect(() => {
    if (phase !== 'waiting') return;
    const id = setInterval(async () => {
      const now = await bundleHash(location.origin);
      if (now && now !== beforeHash.current) {
        clearInterval(id);
        location.reload();
      }
    }, POLL_MS);
    return () => clearInterval(id);
  }, [phase]);

  if (!isLocal()) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Hammer className="h-4 w-4" /> Developer
          <Badge variant="info-subtle">Local only</Badge>
        </CardTitle>
        <CardDescription>
          Rebuilds the <code>app</code> and <code>api</code> containers and reloads
          once the new bundle is live. A restart is not enough — the frontend is
          baked into the image at build time.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {available === false && (
          <div className="flex gap-2 rounded-md border border-warning-emphasis/40 bg-warning-muted p-3">
            <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0 text-warning" />
            <div className="space-y-1 text-sm text-warning">
              <p>The rebuild helper is not running. Start it from the repo root:</p>
              <code className="block rounded bg-background/60 px-2 py-1 text-xs text-foreground">
                node scripts/dev-rebuild.mjs
              </code>
            </div>
          </div>
        )}

        {available && (
          <div className="flex flex-wrap items-center gap-3">
            <Button
              onClick={start}
              disabled={phase === 'building' || phase === 'waiting'}
              size="sm"
            >
              {phase === 'building' || phase === 'waiting' ? (
                <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
              ) : (
                <RefreshCw className="mr-1.5 h-4 w-4" />
              )}
              {phase === 'building'
                ? 'Rebuilding…'
                : phase === 'waiting'
                  ? 'Waiting for the new bundle…'
                  : 'Rebuild & reload'}
            </Button>
            {phase === 'building' && (
              <span className="text-sm text-muted-foreground">
                This takes a minute or two. The page will reload itself.
              </span>
            )}
          </div>
        )}

        {error && (
          <p className="text-sm text-destructive-ink">
            {error}
          </p>
        )}

        {status && status.log.length > 0 && (
          <pre
            ref={logRef}
            className="max-h-48 overflow-auto rounded-md border bg-muted/40 p-3 text-xs leading-relaxed text-muted-foreground"
          >
            {status.log.join('\n')}
          </pre>
        )}
      </CardContent>
    </Card>
  );
}
