import { format, parseISO } from 'date-fns';
import { CalendarDays, TrendingUp } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { Pace } from '@/types/api';

function fmt(d: string | null): string {
  if (!d) return '—';
  try {
    return format(parseISO(d), 'MMM d, yyyy');
  } catch {
    return d;
  }
}

/**
 * ETA projection — PACING-ONLY. It shows when each future gate is projected to
 * clear at the current pace, and (if a target go-live date is set) an
 * on-pace / behind flag. It NEVER advances a gate or unlocks a stage — the
 * Readiness-to-Live Gate stays evidence-based.
 */
export function PaceProjection({ pace }: { pace: Pace }) {
  const stages = Object.entries(pace.projected_clear).sort(([a], [b]) => a.localeCompare(b));
  const hasTarget = !!pace.target_go_live_date;

  if (!hasTarget && stages.length === 0 && !pace.projected_go_live) {
    return null;
  }

  return (
    <div data-testid="pace-projection" className="space-y-3 rounded-lg border bg-card p-4">
      <div className="flex items-center justify-between">
        <span className="flex items-center gap-1.5 text-sm font-semibold">
          <TrendingUp className="h-4 w-4" /> Pace
        </span>
        <span className="text-[11px] uppercase tracking-wide text-muted-foreground">
          projection only · never gates
        </span>
      </div>

      {hasTarget && (
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
          <span className="flex items-center gap-1.5 text-muted-foreground">
            <CalendarDays className="h-4 w-4" /> Target go-live:
            <span className="font-medium text-foreground">{fmt(pace.target_go_live_date)}</span>
          </span>
          {pace.on_pace != null && (
            <span
              className={cn(
                'rounded px-1.5 py-0.5 text-xs font-medium',
                pace.on_pace
                  ? 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400'
                  : 'bg-destructive/15 text-destructive'
              )}
            >
              {pace.on_pace ? 'on pace' : 'behind'}
            </span>
          )}
        </div>
      )}

      {pace.projected_go_live && (
        <p className="text-sm text-muted-foreground">
          Projected go-live at current pace:{' '}
          <span className="font-medium text-foreground">{fmt(pace.projected_go_live)}</span>
        </p>
      )}

      {stages.length > 0 && (
        <div className="space-y-1">
          <span className="text-xs font-medium text-muted-foreground">Projected gate clears</span>
          <ul className="divide-y rounded-md border text-sm">
            {stages.map(([stage, date]) => (
              <li key={stage} className="flex items-center justify-between px-3 py-1.5">
                <span className="font-mono text-xs text-muted-foreground">{stage}</span>
                <span className="tabular-nums">{fmt(date)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
