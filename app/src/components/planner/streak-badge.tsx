import { Flame } from 'lucide-react';
import { cn } from '@/lib/utils';

/**
 * Consecutive fully-cleared days ending today. Surfaced, not hideable
 * (north star — accountability by design). Cold (muted) at 0.
 */
export function StreakBadge({ streak }: { streak: number }) {
  const hot = streak > 0;
  return (
    <div
      data-testid="streak-badge"
      className={cn(
        'inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-sm font-medium',
        hot
          ? 'border-warning-emphasis/40 bg-warning-muted text-warning'
          : 'text-muted-foreground'
      )}
    >
      <Flame className={cn('h-4 w-4', !hot && 'opacity-50')} />
      <span className="tabular-nums">{streak}</span>
      <span className="text-xs font-normal">day{streak === 1 ? '' : 's'} streak</span>
    </div>
  );
}
