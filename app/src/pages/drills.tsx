import { useState } from 'react';
import { useDrills } from '@/lib/learning';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Card, CardContent } from '@/components/ui/card';
import { DrillCard } from '@/components/drills/drill-card';

const TRACKS: { key: string | undefined; label: string }[] = [
  { key: undefined, label: 'All' },
  { key: 'aura', label: 'Aura' },
  { key: 'ict_course', label: 'ICT-course' },
];

/** /drills — the exercise tracker (both drill libraries, ✋/🛠 + rep counters). */
export function DrillsPage() {
  const [track, setTrack] = useState<string | undefined>(undefined);
  const drillsQuery = useDrills(track);

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <div>
        <h1 className="text-2xl font-bold">Drills</h1>
        <p className="text-muted-foreground">
          The two exercise libraries — mark ✋ hand / 🛠 tool variants and log reps.
        </p>
      </div>

      <div className="flex gap-1.5">
        {TRACKS.map((t) => (
          <Button
            key={t.label}
            size="sm"
            variant={track === t.key ? 'default' : 'outline'}
            onClick={() => setTrack(t.key)}
          >
            {t.label}
          </Button>
        ))}
      </div>

      {drillsQuery.isLoading && (
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-40 w-full" />
          ))}
        </div>
      )}

      {drillsQuery.isError && (
        <Card>
          <CardContent className="py-8 text-center text-muted-foreground">
            Could not load drills.
          </CardContent>
        </Card>
      )}

      {drillsQuery.data && (
        <>
          <p className="text-xs text-muted-foreground">{drillsQuery.data.length} drills</p>
          <div className="space-y-3">
            {drillsQuery.data.map((d) => (
              <DrillCard key={d.id} drill={d} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
