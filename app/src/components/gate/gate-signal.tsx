import { CheckCircle2, Lock, ShieldCheck, XCircle } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import { pct, rMultiple } from '@/lib/analytics';
import { ENTRY_MODEL_LABELS } from '@/lib/journal';
import type { EntryModel, ModelReadiness } from '@/types/api';

/** One source group's met/unmet pill (concepts · evidence · behaviour). */
function SourcePill({ label, met }: { label: string; met: boolean }) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium',
        met
          ? 'border-emerald-600/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400'
          : 'border-border bg-muted/40 text-muted-foreground'
      )}
    >
      {met ? <CheckCircle2 className="h-3 w-3" /> : <XCircle className="h-3 w-3" />}
      {label}
    </span>
  );
}

/**
 * GateSignal — one model's "cleared to live?" signal.
 *
 * The verdict is computed server-side and is NOT overridable: there is no control
 * here to mark a model cleared. A blocked model always says what is blocking it.
 */
export function GateSignal({
  model,
  selected,
  onSelect,
}: {
  model: ModelReadiness;
  selected?: boolean;
  onSelect?: () => void;
}) {
  const label = ENTRY_MODEL_LABELS[model.entry_model as EntryModel] ?? model.entry_model;
  const cleared = model.cleared;

  return (
    <Card
      data-testid="gate-signal"
      data-model={model.entry_model}
      data-cleared={cleared ? 'true' : 'false'}
      onClick={onSelect}
      className={cn(
        'cursor-pointer transition-colors',
        selected && 'ring-2 ring-ring',
        cleared
          ? 'border-emerald-600/40 bg-emerald-500/5'
          : 'hover:border-foreground/20'
      )}
    >
      <CardContent className="space-y-3 py-4">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <p className="truncate font-semibold">{label}</p>
            <p className="text-xs text-muted-foreground">
              {model.entry_model === 'unified'
                ? 'the unified decision flow — all seven models'
                : 'entry model'}
            </p>
          </div>
          {cleared ? (
            <Badge className="shrink-0 gap-1 border-transparent bg-emerald-600 text-white hover:bg-emerald-600">
              <ShieldCheck className="h-3.5 w-3.5" />
              Cleared
            </Badge>
          ) : (
            <Badge variant="outline" className="shrink-0 gap-1 text-muted-foreground">
              <Lock className="h-3.5 w-3.5" />
              Not cleared
            </Badge>
          )}
        </div>

        <div className="flex flex-wrap gap-1.5">
          <SourcePill label="Concepts" met={model.concepts_met} />
          <SourcePill label="Edge" met={model.evidence_met} />
          <SourcePill label="Discipline" met={model.behaviour_met} />
        </div>

        <div className="grid grid-cols-3 gap-2 text-xs">
          <div>
            <p className="text-muted-foreground">Backtests</p>
            <p
              className={cn(
                'font-medium tabular-nums',
                model.backtest_n >= model.sample_target
                  ? 'text-emerald-600 dark:text-emerald-400'
                  : 'text-amber-600 dark:text-amber-400'
              )}
            >
              {model.backtest_n}/{model.sample_target}
            </p>
          </div>
          <div>
            <p className="text-muted-foreground">Expectancy</p>
            <p
              className={cn(
                'font-medium tabular-nums',
                model.backtest_expectancy == null
                  ? 'text-muted-foreground'
                  : model.backtest_expectancy > 0
                    ? 'text-emerald-600 dark:text-emerald-400'
                    : 'text-destructive'
              )}
            >
              {rMultiple(model.backtest_expectancy)}
            </p>
          </div>
          <div>
            <p className="text-muted-foreground">Win / BE</p>
            <p className="font-medium tabular-nums">
              {pct(model.backtest_win_rate)}
              <span className="text-muted-foreground"> / {pct(model.backtest_break_even)}</span>
            </p>
          </div>
        </div>

        {!cleared && model.blocking.length > 0 && (
          <ul data-testid="gate-blocking" className="space-y-1 border-t pt-2 text-xs text-muted-foreground">
            {model.blocking.map((b) => (
              <li key={b} className="flex gap-1.5">
                <span aria-hidden className="text-destructive">•</span>
                <span>{b}</span>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
