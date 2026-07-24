import { useMemo, useState } from 'react';
import {
  addMonths,
  eachDayOfInterval,
  endOfMonth,
  endOfWeek,
  format,
  isSameMonth,
  isToday,
  startOfMonth,
  startOfWeek,
  subMonths,
} from 'date-fns';
import { AlertTriangle, ChevronLeft, ChevronRight, Loader2, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import { usePlanRange, useRegenerate } from '@/lib/planner';
import type { PlanItem, PlanItemStatus } from '@/types/api';

const WEEK_HEADERS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

const DOT: Record<PlanItemStatus, string> = {
  done: 'bg-emerald-500',
  partial: 'bg-amber-500',
  skipped: 'bg-destructive',
  pending: 'bg-primary/60',
};

/**
 * A lightweight custom CSS-grid month calendar (date-fns only — NOT
 * react-day-picker: this is a content calendar, not a date picker). Past/today
 * cells are FROZEN (real statuses); future cells are the COMPUTED projection
 * (all pending, shown lighter). A Regenerate button recomputes the plan.
 */
export function StudyCalendar() {
  const [month, setMonth] = useState(() => startOfMonth(new Date()));
  const regenerate = useRegenerate();

  const gridStart = startOfWeek(startOfMonth(month), { weekStartsOn: 1 });
  const gridEnd = endOfWeek(endOfMonth(month), { weekStartsOn: 1 });
  const from = format(gridStart, 'yyyy-MM-dd');
  const to = format(gridEnd, 'yyyy-MM-dd');

  const rangeQuery = usePlanRange(from, to);

  const byDate = useMemo(() => {
    const m = new Map<string, PlanItem[]>();
    for (const it of rangeQuery.data?.items ?? []) {
      const arr = m.get(it.scheduled_date) ?? [];
      arr.push(it);
      m.set(it.scheduled_date, arr);
    }
    return m;
  }, [rangeQuery.data]);

  const days = eachDayOfInterval({ start: gridStart, end: gridEnd });
  const unplaced = rangeQuery.data?.unplaced ?? 0;

  return (
    <div data-testid="study-calendar" className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Button variant="outline" size="icon" className="h-8 w-8" onClick={() => setMonth((m) => subMonths(m, 1))} aria-label="Previous month">
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <span className="min-w-[9rem] text-center font-semibold">{format(month, 'MMMM yyyy')}</span>
          <Button variant="outline" size="icon" className="h-8 w-8" onClick={() => setMonth((m) => addMonths(m, 1))} aria-label="Next month">
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => regenerate.mutate()}
          disabled={regenerate.isPending}
        >
          {regenerate.isPending ? (
            <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
          ) : (
            <RefreshCw className="mr-1.5 h-3.5 w-3.5" />
          )}
          Regenerate
        </Button>
      </div>

      {rangeQuery.isLoading ? (
        <Skeleton className="h-72 w-full" />
      ) : (
        <div className="overflow-hidden rounded-lg border">
          {/* Weekday header */}
          <div className="grid grid-cols-7 border-b bg-muted/40 text-center text-xs font-medium text-muted-foreground">
            {WEEK_HEADERS.map((d) => (
              <div key={d} className="py-1.5">{d}</div>
            ))}
          </div>
          {/* Day grid */}
          <div className="grid grid-cols-7">
            {days.map((day) => {
              const key = format(day, 'yyyy-MM-dd');
              const items = byDate.get(key) ?? [];
              const inMonth = isSameMonth(day, month);
              const today = isToday(day);
              const projected = items.length > 0 && items.every((it) => it.id == null);
              return (
                <div
                  key={key}
                  data-testid={today ? 'calendar-today' : undefined}
                  className={cn(
                    'min-h-[4.5rem] border-b border-r p-1.5 text-xs [&:nth-child(7n)]:border-r-0',
                    !inMonth && 'bg-muted/20 text-muted-foreground/50',
                    today && 'bg-primary/5 ring-1 ring-inset ring-primary/40'
                  )}
                >
                  <div className={cn('mb-1 flex items-center justify-between', today && 'font-bold text-primary')}>
                    <span className="tabular-nums">{format(day, 'd')}</span>
                    {items.length > 0 && (
                      <span className={cn('tabular-nums', projected ? 'text-muted-foreground/70' : 'text-muted-foreground')}>
                        {items.length}
                      </span>
                    )}
                  </div>
                  <div className="flex flex-wrap gap-0.5">
                    {items.slice(0, 8).map((it, i) => (
                      <span
                        key={it.id ?? i}
                        title={`${it.activity}${it.concept_title ? ` · ${it.concept_title}` : ''} (${it.status})`}
                        className={cn('h-1.5 w-1.5 rounded-full', DOT[it.status], projected && 'opacity-50')}
                      />
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Legend + accountability */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
        <span className="flex items-center gap-1"><span className="h-1.5 w-1.5 rounded-full bg-emerald-500" /> done</span>
        <span className="flex items-center gap-1"><span className="h-1.5 w-1.5 rounded-full bg-amber-500" /> partial</span>
        <span className="flex items-center gap-1"><span className="h-1.5 w-1.5 rounded-full bg-destructive" /> skipped</span>
        <span className="flex items-center gap-1"><span className="h-1.5 w-1.5 rounded-full bg-primary/60" /> pending</span>
        <span className="flex items-center gap-1"><span className="h-1.5 w-1.5 rounded-full bg-primary/30" /> projected (future)</span>
      </div>

      {unplaced > 0 && (
        <p className="flex items-center gap-1.5 text-xs text-amber-600 dark:text-amber-500">
          <AlertTriangle className="h-3.5 w-3.5" />
          {unplaced} task{unplaced === 1 ? '' : 's'} couldn't fit the visible horizon — add availability to place them.
        </p>
      )}
    </div>
  );
}
