import { useState } from 'react';
import { useTracks, TRACKS } from '@/lib/learning';
import { StagePath } from '@/components/progress/stage-path';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Card, CardContent } from '@/components/ui/card';

const TRACK_KEY = 'neurospect_learn_track';

/** /path — the track switcher (Aura · AXL · Unified), each a gated stage spine. */
export function PathPage() {
  const tracksQuery = useTracks();
  const [track, setTrack] = useState<string>(
    () => localStorage.getItem(TRACK_KEY) ?? 'aura'
  );

  function selectTrack(key: string) {
    setTrack(key);
    localStorage.setItem(TRACK_KEY, key);
  }

  const current = tracksQuery.data?.find((t) => t.track === track) ?? tracksQuery.data?.[0];

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold">The Path</h1>
        <p className="text-muted-foreground">
          Three graded tracks. Each stage gates the next — hand-marking first, tools second.
        </p>
      </div>

      {/* Track switcher */}
      <div className="flex flex-wrap gap-1.5" role="tablist" aria-label="Learning track">
        {TRACKS.map((t) => (
          <Button
            key={t.key}
            role="tab"
            aria-selected={track === t.key}
            size="sm"
            variant={track === t.key ? 'default' : 'outline'}
            onClick={() => selectTrack(t.key)}
          >
            {t.label}
          </Button>
        ))}
      </div>

      {tracksQuery.isLoading && (
        <div className="space-y-3">
          {Array.from({ length: 7 }).map((_, i) => (
            <Skeleton key={i} className="h-20 w-full" />
          ))}
        </div>
      )}

      {tracksQuery.isError && (
        <Card>
          <CardContent className="py-8 text-center text-muted-foreground">
            Could not load the path.
          </CardContent>
        </Card>
      )}

      {current && <StagePath stages={current.stages} />}
    </div>
  );
}
