import { Link } from 'react-router-dom';
import { format, parseISO } from 'date-fns';
import { CircleDashed } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import { rMultiple } from '@/lib/analytics';
import { ENTRY_MODEL_LABELS } from '@/lib/journal';
import { HYPOTHETICAL_OUTCOME_LABELS, MISS_TYPE_LABELS } from '@/lib/missed-trades';
import type { MissedTrade } from '@/types/api';

/** One missed / canceled setup, summarized. The R shown is HYPOTHETICAL: positive
 * = a missed winner (hesitation cost you), negative = standing down was
 * protective. It is never part of expectancy. */
export function MissedTradeCard({ miss }: { miss: MissedTrade }) {
  const resolved = miss.hypothetical_r != null;
  return (
    <Link
      to={`/journal/missed/${miss.id}`}
      data-testid="missed-card"
      data-miss-type={miss.miss_type}
      className="block rounded-lg border border-dashed bg-card p-3 transition-colors hover:border-primary/40 hover:bg-accent/40"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline" className="text-[10px] uppercase tracking-wide">
              {MISS_TYPE_LABELS[miss.miss_type]}
            </Badge>
            <span className="font-medium">
              {ENTRY_MODEL_LABELS[miss.entry_model] ?? miss.entry_model}
            </span>
            <span className="font-mono text-xs text-muted-foreground">{miss.instrument}</span>
          </div>
          <div className="flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs text-muted-foreground">
            <span>{format(parseISO(miss.entry_date), 'MMM d, yyyy')}</span>
            {miss.hypothetical_outcome && (
              <span>{HYPOTHETICAL_OUTCOME_LABELS[miss.hypothetical_outcome]}</span>
            )}
            {miss.reason && <span className="truncate">{miss.reason}</span>}
          </div>
          {miss.hesitation_tags && miss.hesitation_tags.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {miss.hesitation_tags.map((t) => (
                <span key={t} className="rounded border bg-muted px-1.5 py-0.5 font-mono text-[10px]">
                  {t}
                </span>
              ))}
            </div>
          )}
        </div>
        <div className="shrink-0 text-right">
          {resolved ? (
            <>
              <span
                className={cn(
                  'font-semibold tabular-nums',
                  miss.hypothetical_r! > 0
                    ? 'text-warning'
                    : miss.hypothetical_r! < 0
                      ? 'text-success'
                      : 'text-muted-foreground'
                )}
              >
                {rMultiple(miss.hypothetical_r)}
              </span>
              <span className="block text-[10px] uppercase tracking-wide text-muted-foreground">
                {miss.hypothetical_r! > 0 ? 'forgone' : miss.hypothetical_r! < 0 ? 'saved' : 'flat'}
              </span>
            </>
          ) : (
            <span className="flex items-center gap-1 text-xs text-muted-foreground">
              <CircleDashed className="h-3 w-3" /> unresolved
            </span>
          )}
        </div>
      </div>
    </Link>
  );
}
