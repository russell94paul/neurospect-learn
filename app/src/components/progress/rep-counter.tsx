import { Progress } from '@/components/ui/progress';
import { cn } from '@/lib/utils';

/**
 * Rep count against the (parsed) freetext target. Reps are a *floor*, not the
 * finish line (concepts/mastery/README §reps).
 *
 * PHASE E2 — READ-ONLY. The +/− control is gone: a rep is no longer a number the
 * user types, it is what the evidence ledger says. `reps = legacy + evidenced`,
 * and the split is shown so the pre-evidence gap is visible rather than folded
 * into one figure. `target` is the parsed numeric floor (null = qualitative /
 * habit → no bar).
 */
export function RepCounter({
  reps,
  target,
  evidenced,
  legacy,
  className,
}: {
  reps: number;
  target: number | null;
  evidenced?: number;
  legacy?: number;
  className?: string;
}) {
  const pct = target ? Math.min(100, Math.round((reps / target) * 100)) : null;
  return (
    <div className={cn('space-y-1', className)}>
      <div className="flex flex-wrap items-center gap-2">
        <span className="tabular-nums text-sm font-medium" data-testid="rep-count">
          {reps}
          {target != null ? ` / ${target}` : ''}
        </span>
        <span className="text-xs text-muted-foreground">reps</span>
        {evidenced != null && (
          <span className="text-xs text-muted-foreground" data-testid="rep-split">
            · {evidenced} evidenced
            {legacy ? ` · ${legacy} pre-evidence` : ''}
          </span>
        )}
      </div>
      {pct != null && <Progress value={pct} className="h-1.5 max-w-[12rem]" />}
    </div>
  );
}
