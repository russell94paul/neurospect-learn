import { useMemo } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, BookOpen, Dumbbell, Lock, Target } from 'lucide-react';
import { useDrills, useProgress, useStages, TRACK_LABELS } from '@/lib/learning';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { ExitBarGate } from '@/components/progress/exit-bar-gate';
import { ConceptTrackPanel } from '@/components/progress/concept-track-panel';
import { DrillCard } from '@/components/drills/drill-card';

/**
 * /path/:track/:stage — the CURRICULUM UNIT for one track-stage:
 *   Read (content links) → Drill (the stage's drills) → Track (its concepts'
 *   progress) → the stage's Gate (exit bar + gate_text).
 */
export function StageDetailPage() {
  const { track = 'unified', stage } = useParams<{ track: string; stage: string }>();
  const stagesQuery = useStages(track);
  const progressQuery = useProgress(track);
  const drillsQuery = useDrills(track);

  const stageData = stagesQuery.data?.find((s) => s.stage_code === stage);

  const concepts = useMemo(
    () => (progressQuery.data ?? []).filter((r) => r.stage_code === stage),
    [progressQuery.data, stage]
  );

  // Read: unique content pages referenced by the stage's concepts.
  const readPages = useMemo(() => {
    const m = new Map<string, string[]>();
    for (const c of concepts) {
      if (!c.content_slug) continue;
      const titles = m.get(c.content_slug) ?? [];
      titles.push(c.title);
      m.set(c.content_slug, titles);
    }
    return Array.from(m.entries()).map(([slug, titles]) => ({ slug, titles }));
  }, [concepts]);

  // Drill: the drills referenced by the stage's concepts' drill_refs.
  const stageDrills = useMemo(() => {
    const refs = new Set<string>();
    for (const c of concepts) for (const r of c.drill_refs ?? []) refs.add(r);
    return (drillsQuery.data ?? []).filter((d) => refs.has(d.drill_ref));
  }, [concepts, drillsQuery.data]);

  const loading = stagesQuery.isLoading || progressQuery.isLoading;

  return (
    <div className="mx-auto max-w-3xl space-y-6">
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
            Unknown stage: <span className="font-mono">{track}/{stage}</span>
          </CardContent>
        </Card>
      )}

      {stageData && (
        <>
          <div>
            <div className="flex items-center gap-2">
              <span className="rounded bg-primary/10 px-1.5 py-0.5 text-xs font-medium text-primary">
                {TRACK_LABELS[track] ?? track}
              </span>
              <span className="font-mono text-sm text-muted-foreground">{stageData.stage_code}</span>
              <h1 className="text-2xl font-bold">{stageData.title}</h1>
            </div>
            {stageData.summary && (
              <p className="mt-1 text-sm text-muted-foreground">{stageData.summary}</p>
            )}
            {stageData.watch_only && (
              <p className="mt-1 text-sm text-warning">
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

          {/* ---- Read ---- */}
          <section className="space-y-3">
            <h2 className="flex items-center gap-2 text-sm font-semibold text-muted-foreground">
              <BookOpen className="h-4 w-4" /> Read
            </h2>
            {readPages.length > 0 ? (
              <div className="flex flex-col gap-2">
                {readPages.map((p) => (
                  <Link
                    key={p.slug}
                    to={`/concepts/${p.slug}`}
                    className="rounded-lg border p-3 text-sm transition-colors hover:bg-accent"
                  >
                    {p.titles.join(' · ')}
                  </Link>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                No linked reading for this stage (backtest / journal by reference).
              </p>
            )}
          </section>

          {/* ---- Drill ---- */}
          <section className="space-y-3">
            <h2 className="flex items-center gap-2 text-sm font-semibold text-muted-foreground">
              <Dumbbell className="h-4 w-4" /> Drill ({stageDrills.length})
            </h2>
            {stageDrills.length > 0 ? (
              <div className="space-y-3">
                {stageDrills.map((d) => (
                  <DrillCard key={d.id} drill={d} />
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                No mapped drills for this stage.
              </p>
            )}
          </section>

          {/* ---- Track ---- */}
          <section className="space-y-3">
            <h2 className="flex items-center gap-2 text-sm font-semibold text-muted-foreground">
              <Target className="h-4 w-4" /> Track your progress ({concepts.length})
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
          </section>

          {/* ---- Gate ---- */}
          <section className="space-y-3">
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base">Gate — exit bar</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {stageData.gate_text && (
                  <p className="text-sm text-muted-foreground">{stageData.gate_text}</p>
                )}
                <ExitBarGate stage={stageData} />
              </CardContent>
            </Card>
          </section>
        </>
      )}
    </div>
  );
}
