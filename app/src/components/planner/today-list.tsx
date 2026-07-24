import { useMemo } from 'react';
import { PlanItemCard } from './plan-item-card';
import type { PlanItem } from '@/types/api';

/**
 * The prescriptive, ORDERED daily card list — not a menu. Items render in the
 * scheduler's `sort_order` (habits → due reviews → curriculum backlog). The
 * order is the plan; the user works top-down.
 */
export function TodayList({ items }: { items: PlanItem[] }) {
  const ordered = useMemo(
    () => [...items].sort((a, b) => a.sort_order - b.sort_order),
    [items]
  );

  if (ordered.length === 0) {
    return (
      <div className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">
        Nothing scheduled for today. If this isn't a planned rest day, check your availability in{' '}
        <span className="font-medium">Plan → Setup</span>.
      </div>
    );
  }

  return (
    <ol data-testid="today-list" className="space-y-3">
      {ordered.map((item, i) => (
        <li key={item.id ?? `${item.activity}-${item.concept_slug ?? item.drill_ref ?? i}`}>
          <PlanItemCard item={item} />
        </li>
      ))}
    </ol>
  );
}
