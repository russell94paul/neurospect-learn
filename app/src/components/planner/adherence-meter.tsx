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
  const con = adherence.consistency;

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

      {/* THE SAME CONSISTENCY, DERIVED FROM EVIDENCE (Phase E6, design §6).
          Everything above this line is written by clicking "done"; everything
          below it is derived from captures that exist. Both are shown — E2's
          `reps` / `reps_evidenced` / `reps_legacy` idiom — because a user whose
          marked figure is 12 and whose evidenced figure is 3 has learned
          something true, while being silently shown only the 3 would read as the
          app having lost their work. No new currency is minted here: §6 forbids
          points, so there is no target, no ring and nothing to fill. */}
      <div
        className="space-y-1 border-t pt-2 text-xs text-muted-foreground"
        data-testid="evidence-backed-consistency"
        data-evidence-streak={con.evidence_streak}
        data-rest-days-in-streak={con.rest_days_in_streak}
      >
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <span className="font-medium text-foreground">Backed by evidence</span>
          <span>
            <span className="font-medium tabular-nums text-foreground">
              {con.evidence_streak}
            </span>{' '}
            day{con.evidence_streak === 1 ? '' : 's'} in a row
          </span>
          <span>
            · <span className="tabular-nums">{con.evidenced_days}</span> day
            {con.evidenced_days === 1 ? '' : 's'} with a capture
          </span>
        </div>

        {/* The one thing rest days cannot be prevented from doing, surfaced (§5).
            A streak held up mostly by booked days off must read as one. */}
        {con.rest_days_in_streak > 0 && (
          <p data-testid="rest-days-in-streak">
            {con.rest_days_in_streak} of those day{con.rest_days_in_streak === 1 ? '' : 's'}{' '}
            {con.rest_days_in_streak === 1 ? 'was' : 'were'} declared a rest day in advance —
            neutral, so {con.rest_days_in_streak === 1 ? 'it' : 'they'} neither broke the run nor
            counted toward it.
          </p>
        )}

        {/* The gap between the claim and the record. Surfaced, never deducted:
            nothing here reduces a rep or a stage (§5, "surface the rest"). */}
        {con.days_marked_without_evidence > 0 && (
          <p data-testid="marked-without-evidence">
            <span className="tabular-nums">{con.days_marked_without_evidence}</span> day
            {con.days_marked_without_evidence === 1 ? '' : 's'} marked done carry no evidence at
            all. Nothing is deducted for that — it is shown because the figure above it is a
            record and the one at the top is a claim.
          </p>
        )}
      </div>
    </div>
  );
}
