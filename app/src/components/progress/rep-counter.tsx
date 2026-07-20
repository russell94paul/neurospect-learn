import { Minus, Plus } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { cn } from '@/lib/utils';

/**
 * Rep count against the (parsed) freetext target. Reps are a *floor*, not the
 * finish line (concepts/mastery/README §reps). Editable when `onChange` given.
 * `target` is the parsed numeric floor (null = qualitative/habit → no bar).
 */
export function RepCounter({
  reps,
  target,
  onChange,
  className,
}: {
  reps: number;
  target: number | null;
  onChange?: (v: number) => void;
  className?: string;
}) {
  const editable = !!onChange;
  const pct = target ? Math.min(100, Math.round((reps / target) * 100)) : null;
  return (
    <div className={cn('space-y-1', className)}>
      <div className="flex items-center gap-2">
        {editable && (
          <Button
            type="button"
            variant="outline"
            size="icon"
            className="h-6 w-6"
            onClick={() => onChange(Math.max(0, reps - 1))}
            disabled={reps <= 0}
            aria-label="Decrease reps"
          >
            <Minus className="h-3 w-3" />
          </Button>
        )}
        <span className="tabular-nums text-sm font-medium" data-testid="rep-count">
          {reps}
          {target != null ? ` / ${target}` : ''}
        </span>
        {editable && (
          <Button
            type="button"
            variant="outline"
            size="icon"
            className="h-6 w-6"
            onClick={() => onChange(reps + 1)}
            aria-label="Increase reps"
          >
            <Plus className="h-3 w-3" />
          </Button>
        )}
        <span className="text-xs text-muted-foreground">reps</span>
      </div>
      {pct != null && <Progress value={pct} className="h-1.5 max-w-[12rem]" />}
    </div>
  );
}
