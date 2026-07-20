import { useMemo } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, Lock } from 'lucide-react';
import { useProgress, useStages } from '@/lib/learning';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { ExitBarGate } from '@/components/progress/exit-bar-gate';
import { ConceptTrackPanel } from '@/components/progress/concept-track-panel';

/** /path/:stage — a stage's concepts + the derived exit-bar gate. */
export function StageDetailPage() {
  const { stage } = useParams<{ stage: string }>();
  const stagesQuery = useStages();
  const progressQuery = useProgress();

  const stageData = stagesQuery.data?.find((s) => s.u_stage === stage);
  const concepts = useMemo(
    () => (progressQuery.data ?? []).filter((r) => r.u_stage === stage),
    [progressQuery.data, stage]
  );

  const loading = stagesQuery.isLoading || progressQuery.isLoading;

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <Button variant="ghost" size="sm" asChild>
        <Link to="/path">
          <ArrowLeft className="mr-1 h-4 w-4" /> Path
        </Link>
      </Button>

      {loading && (
        <div className="space-y-3">
          <Skeleton className="h-8 w-1/2" />
          <Skeleton className="h-40 w-full" />
        </div>
      )}

      {!loading && !stageData && (
        <Card>
          <CardContent className="py-8 text-center text-muted-foreground">
            Unknown stage: <span className="font-mono">{stage}</span>
          </CardContent>
        </Card>
      )}

      {stageData && (
        <>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-mono text-sm text-muted-foreground">{stageData.u_stage}</span>
              <h1 className="text-2xl font-bold">{stageData.title}</h1>
            </div>
            {stageData.watch_only && (
              <p className="mt-1 text-sm text-amber-600 dark:text-amber-500">
                Frontier — study &amp; watch only; never gate-eligible.
              </p>
            )}
          </div>

          {stageData.locked && (
            <Card className="border-dashed">
              <CardContent className="flex items-center gap-2 py-4 text-sm text-muted-foreground">
                <Lock className="h-4 w-4" /> This stage is locked until the earlier stages'
                exit bars are met — but you can review what it requires below.
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Exit bar</CardTitle>
            </CardHeader>
            <CardContent>
              <ExitBarGate stage={stageData} />
            </CardContent>
          </Card>

          <div className="space-y-3">
            <h2 className="text-sm font-semibold text-muted-foreground">
              Concepts ({concepts.length})
            </h2>
            {concepts.map((row) => (
              <div key={row.concept_id} className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="font-medium">{row.title}</span>
                  {row.is_core && (
                    <span className="rounded bg-primary/10 px-1.5 py-0.5 text-xs text-primary">
                      core
                    </span>
                  )}
                </div>
                <ConceptTrackPanel row={row} />
              </div>
            ))}
            {concepts.length === 0 && (
              <p className="text-sm text-muted-foreground">
                No gradable concepts in this stage (handled by reference in a later phase).
              </p>
            )}
          </div>
        </>
      )}
    </div>
  );
}
