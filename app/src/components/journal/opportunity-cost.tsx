import { AlertTriangle, ShieldCheck, TrendingDown } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import { rMultiple } from '@/lib/analytics';
import { ENTRY_MODEL_LABELS } from '@/lib/journal';
import { MISS_TYPE_LABELS, useOpportunityCost } from '@/lib/missed-trades';
import type { EntryModel, MissBucket, MissType } from '@/types/api';

/**
 * "How much is hesitation costing you?" — in R, over the missed-trade log.
 *
 * The two directions are given equal weight on purpose (concepts/aura/journaling-system):
 * forgone R is what not pulling the trigger cost, but a NEGATIVE net R is Dante's
 * finding — the orders you pulled would have lost, so standing down was protective.
 * This is NOT expectancy: these trades were never taken and never reach the Gate.
 */
export function OpportunityCost() {
  const query = useOpportunityCost();

  if (query.isLoading) return <Skeleton className="h-28 w-full" />;
  const data = query.data;
  if (!data || data.total.logged === 0) return null;

  const t = data.total;
  const net = t.net_r ?? 0;

  return (
    <Card data-testid="opportunity-cost">
      <CardContent className="space-y-4 py-4">
        <div className="grid gap-3 sm:grid-cols-3">
          <Tile
            icon={<TrendingDown className="h-4 w-4" />}
            label="Forgone"
            value={rMultiple(t.forgone_r)}
            note={`${t.would_win} would have won`}
            tone="warn"
          />
          <Tile
            icon={<ShieldCheck className="h-4 w-4" />}
            label="Saved by standing down"
            value={rMultiple(t.saved_r)}
            note={`${t.would_lose} would have lost`}
            tone="good"
          />
          <Tile
            icon={<AlertTriangle className="h-4 w-4" />}
            label="Net"
            value={rMultiple(t.net_r)}
            note={
              net > 0
                ? 'hesitation is costing you'
                : net < 0
                  ? 'standing down was protective'
                  : 'a wash so far'
            }
            tone={net > 0 ? 'warn' : net < 0 ? 'good' : 'muted'}
          />
        </div>

        <p className="text-xs text-muted-foreground">
          {t.logged} logged · {t.resolved} resolved
          {t.logged > t.resolved && ` · ${t.logged - t.resolved} still to resolve`}. Hypothetical R
          only — missed trades never enter expectancy or the Readiness-to-Live Gate.
        </p>

        {data.by_miss_type.length > 0 && (
          <BucketRow
            title="By miss type"
            buckets={data.by_miss_type}
            label={(k) => MISS_TYPE_LABELS[k as MissType] ?? k}
          />
        )}
        {data.by_hesitation_tag.length > 0 && (
          <BucketRow
            title="Recurring hesitations (attack the top one first)"
            buckets={data.by_hesitation_tag}
            label={(k) => k}
            mono
          />
        )}
        {data.by_entry_model.length > 1 && (
          <BucketRow
            title="By entry model"
            buckets={data.by_entry_model}
            label={(k) => ENTRY_MODEL_LABELS[k as EntryModel] ?? k}
          />
        )}
      </CardContent>
    </Card>
  );
}

function Tile({
  icon,
  label,
  value,
  note,
  tone,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  note: string;
  tone: 'warn' | 'good' | 'muted';
}) {
  const toneCls =
    tone === 'warn'
      ? 'text-warning'
      : tone === 'good'
        ? 'text-success'
        : 'text-muted-foreground';
  return (
    <div className="rounded-lg border p-3">
      <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
        {icon}
        {label}
      </div>
      <div className={cn('mt-1 text-2xl font-semibold tabular-nums', toneCls)}>{value}</div>
      <div className="text-xs text-muted-foreground">{note}</div>
    </div>
  );
}

function BucketRow({
  title,
  buckets,
  label,
  mono,
}: {
  title: string;
  buckets: MissBucket[];
  label: (key: string) => string;
  mono?: boolean;
}) {
  return (
    <div className="space-y-1">
      <p className="text-xs font-medium text-muted-foreground">{title}</p>
      <div className="flex flex-wrap gap-1.5">
        {buckets.map((b) => (
          <span
            key={b.key}
            className="inline-flex items-center gap-1.5 rounded-md border bg-muted/50 px-2 py-1 text-xs"
          >
            <span className={cn(mono && 'font-mono')}>{label(b.key)}</span>
            <span className="text-muted-foreground">×{b.logged}</span>
            <span
              className={cn(
                'font-medium tabular-nums',
                (b.net_r ?? 0) > 0
                  ? 'text-warning'
                  : (b.net_r ?? 0) < 0
                    ? 'text-success'
                    : 'text-muted-foreground'
              )}
            >
              {rMultiple(b.net_r)}
            </span>
          </span>
        ))}
      </div>
    </div>
  );
}
