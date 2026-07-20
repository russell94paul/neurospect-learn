import { useStages } from '@/lib/learning';
import { StagePath } from '@/components/progress/stage-path';
import { Skeleton } from '@/components/ui/skeleton';
import { Card, CardContent } from '@/components/ui/card';

/** /path — the U0→U6 curriculum spine (the one-glance gated stage map). */
export function PathPage() {
  const stagesQuery = useStages();

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold">The Path</h1>
        <p className="text-muted-foreground">
          U0 → U6 — each stage gates the next. Hand-marking first, tools second.
        </p>
      </div>

      {stagesQuery.isLoading && (
        <div className="space-y-3">
          {Array.from({ length: 7 }).map((_, i) => (
            <Skeleton key={i} className="h-20 w-full" />
          ))}
        </div>
      )}

      {stagesQuery.isError && (
        <Card>
          <CardContent className="py-8 text-center text-muted-foreground">
            Could not load the path.
          </CardContent>
        </Card>
      )}

      {stagesQuery.data && <StagePath stages={stagesQuery.data} />}
    </div>
  );
}
