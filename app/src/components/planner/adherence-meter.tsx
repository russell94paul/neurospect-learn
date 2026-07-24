import { AlertTriangle, Gauge } from 'lucide-react';
import { Progress } from '@/components/ui/progress';
import { cn } from '@/lib/utils';
import type { Adherence } from '@/types/api';

/**
 * Adherence %, days-behind, and carried-over items — all visible, none
 * hideable (north star). `adherence_pct` = (done + 0.5·partial) / total over
 * items scheduled on/before today.
 */
export function AdherenceMeter({ adherence }: { adherence: Adherence }) {
  // adherence_pct is already a 0–100 percentage from the backend
  // (planner.py: round(100 * (done + 0.5·partial) / total, 1)).
  const pct = adherence.adherence_pct == null ? null : Math.round(adherence.adherence_pct);
  const behind = adherence.days_behind > 0;

  return (
    <div data-testid="adherence-meter" className="space-y-2 rounded-lg border bg-card p-4">
      <div className="flex items-center justify-between">
        <span className="flex items-center gap-1.5 text-sm font-semibold">
          <Gauge className="h-4 w-4" /> Adherence
        </span>
        <span className="tabular-nums text-sm font-medium">
          {pct == null ? '—' : `${pct}%`}
        </span>
      </div>

      <Progress value={pct ?? 0} className="h-2" />

      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
        <span>
          <span className="font-medium text-foreground">{adherence.done}</span> done
        </span>
        {adherence.partial > 0 && <span>· {adherence.partial} partial</span>}
        {adherence.skipped > 0 && (
          <span className="text-destructive">· {adherence.skipped} skipped</span>
        )}
        {adherence.pending > 0 && <span>· {adherence.pending} pending</span>}
        <span>· of {adherence.total}</span>
      </div>

      {(behind || adherence.carried_over > 0) && (
        <div
          className={cn(
            'flex flex-wrap items-center gap-x-3 gap-y-1 rounded-md px-2 py-1.5 text-xs',
            'bg-destructive/10 text-destructive'
          )}
        >
          <span className="flex items-center gap-1 font-medium">
            <AlertTriangle className="h-3.5 w-3.5" />
            {behind ? `${adherence.days_behind} day${adherence.days_behind === 1 ? '' : 's'} behind` : 'Carry-over'}
          </span>
          {adherence.carried_over > 0 && (
            <span>{adherence.carried_over} item{adherence.carried_over === 1 ? '' : 's'} carried into today</span>
          )}
        </div>
      )}
    </div>
  );
}
