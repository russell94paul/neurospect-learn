import { Link } from 'react-router-dom';
import {
  BookOpen,
  Check,
  Clock,
  Dumbbell,
  Eye,
  History,
  Loader2,
  Repeat,
  Rewind,
  SkipForward,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import { ACTIVITY_LABELS, useUpdatePlanItem } from '@/lib/planner';
import type { PlanActivity, PlanItem, PlanItemStatus } from '@/types/api';

const ACTIVITY_ICON: Record<PlanActivity, typeof BookOpen> = {
  learn: BookOpen,
  drill: Dumbbell,
  review: History,
  observe: Eye,
  habit: Repeat,
  backtest: Rewind,
};

const STATUS_STYLE: Record<PlanItemStatus, string> = {
  pending: '',
  done: 'border-emerald-500/40 bg-emerald-500/5',
  partial: 'border-amber-500/40 bg-amber-500/5',
  skipped: 'border-muted bg-muted/30 opacity-70',
};

/**
 * One prescribed task in the daily plan. Activity icon + title + target +
 * est-minutes, with done / partial / skip controls that PATCH the item (which
 * feeds concept/drill progress). Skipping is a LOGGED skip — it hurts adherence
 * and is never hidden. Computed future items (no `id`) render read-only.
 */
export function PlanItemCard({ item }: { item: PlanItem }) {
  const update = useUpdatePlanItem();
  const Icon = ACTIVITY_ICON[item.activity] ?? BookOpen;

  const title = item.concept_title ?? item.drill_title ?? item.drill_ref ?? 'Study task';
  const editable = !!item.id;

  const mark = (status: PlanItemStatus) => {
    if (!item.id) return;
    const body =
      status === 'done' && item.target_qty != null
        ? { status, done_qty: item.target_qty }
        : { status };
    update.mutate({ id: item.id, body });
  };

  // Read → its content page; Drill → the drills tracker.
  const href = item.content_slug
    ? `/concepts/${item.content_slug}`
    : item.activity === 'drill' || item.activity === 'review'
      ? '/drills'
      : null;

  return (
    <div
      data-testid="plan-item"
      data-status={item.status}
      data-activity={item.activity}
      className={cn('space-y-3 rounded-lg border bg-card p-3 transition-colors', STATUS_STYLE[item.status])}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-2.5">
          <span className="mt-0.5 rounded-md bg-accent p-1.5 text-accent-foreground">
            <Icon className="h-4 w-4" />
          </span>
          <div className="min-w-0 space-y-1">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="secondary" className="text-[10px] uppercase tracking-wide">
                {ACTIVITY_LABELS[item.activity] ?? item.activity}
              </Badge>
              {item.carried_over && (
                <Badge variant="outline" className="border-amber-500/50 text-[10px] text-amber-600 dark:text-amber-400">
                  carried over
                </Badge>
              )}
              {item.drill_ref && (
                <span className="font-mono text-[11px] text-muted-foreground">{item.drill_ref}</span>
              )}
            </div>
            <p className={cn('font-medium leading-tight', item.status === 'skipped' && 'line-through')}>
              {href ? (
                <Link to={href} className="hover:underline">
                  {title}
                </Link>
              ) : (
                title
              )}
            </p>
            <div className="flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs text-muted-foreground">
              {item.target_qty != null && (
                <span>
                  target: {item.target_qty}
                  {item.target_unit ? ` ${item.target_unit}` : ''}
                </span>
              )}
              <span className="flex items-center gap-1">
                <Clock className="h-3 w-3" /> ~{item.est_minutes} min
              </span>
            </div>
          </div>
        </div>
      </div>

      {editable && (
        <div className="flex items-center gap-2">
          <Button
            type="button"
            size="sm"
            variant={item.status === 'done' ? 'default' : 'outline'}
            className="h-7"
            disabled={update.isPending}
            onClick={() => mark('done')}
            aria-label="Mark done"
          >
            {update.isPending ? (
              <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />
            ) : (
              <Check className="mr-1 h-3.5 w-3.5" />
            )}
            Done
          </Button>
          <Button
            type="button"
            size="sm"
            variant={item.status === 'partial' ? 'default' : 'outline'}
            className="h-7"
            disabled={update.isPending}
            onClick={() => mark('partial')}
            aria-label="Mark partial"
          >
            Partial
          </Button>
          <Button
            type="button"
            size="sm"
            variant={item.status === 'skipped' ? 'default' : 'ghost'}
            className="h-7 text-muted-foreground"
            disabled={update.isPending}
            onClick={() => mark('skipped')}
            aria-label="Skip"
          >
            <SkipForward className="mr-1 h-3.5 w-3.5" /> Skip
          </Button>
        </div>
      )}
    </div>
  );
}
