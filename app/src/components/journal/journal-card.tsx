import { Link } from 'react-router-dom';
import { format, parseISO } from 'date-fns';
import { CircleDot } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import { rMultiple } from '@/lib/analytics';
import { ENTRY_MODEL_LABELS, GRADE_LABELS, OUTCOME_LABELS } from '@/lib/journal';
import type { JournalEntry } from '@/types/api';

const OUTCOME_STYLE: Record<string, string> = {
  win: 'text-success',
  loss: 'text-destructive',
  breakeven: 'text-muted-foreground',
};

/** One journal entry, summarized. `mode` is a prominent, color-coded badge so
 * backtest and live never blur together in the list. Links to the editor. */
export function JournalCard({ entry }: { entry: JournalEntry }) {
  const closed = entry.r_multiple != null;
  return (
    <Link
      to={`/journal/${entry.id}`}
      data-testid="journal-card"
      data-mode={entry.mode}
      className="block rounded-lg border bg-card p-3 transition-colors hover:border-primary/40 hover:bg-accent/40"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <Badge
              variant="outline"
              className={cn(
                'text-[10px] uppercase tracking-wide',
                entry.mode === 'live'
                  ? 'border-chart-live text-chart-live'
                  : 'border-chart-backtest text-chart-backtest'
              )}
            >
              {entry.mode}
            </Badge>
            <span className="font-medium">{ENTRY_MODEL_LABELS[entry.entry_model] ?? entry.entry_model}</span>
            <span className="font-mono text-xs text-muted-foreground">{entry.instrument}</span>
          </div>
          <div className="flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs text-muted-foreground">
            <span>{format(parseISO(entry.entry_date), 'MMM d, yyyy')}</span>
            {entry.outcome && (
              <span className={cn('font-medium', OUTCOME_STYLE[entry.outcome])}>
                {OUTCOME_LABELS[entry.outcome]}
              </span>
            )}
            {entry.grade && <span>grade {GRADE_LABELS[entry.grade]}</span>}
            {entry.plan_followed === false && <span className="text-warning">off-plan</span>}
          </div>
        </div>
        <div className="shrink-0 text-right">
          {closed ? (
            <span
              className={cn(
                'font-semibold tabular-nums',
                entry.r_multiple! > 0 ? 'text-success'
                  : entry.r_multiple! < 0 ? 'text-destructive' : 'text-muted-foreground'
              )}
            >
              {rMultiple(entry.r_multiple)}
            </span>
          ) : (
            <span className="flex items-center gap-1 text-xs text-muted-foreground">
              <CircleDot className="h-3 w-3" /> open
            </span>
          )}
        </div>
      </div>
    </Link>
  );
}
