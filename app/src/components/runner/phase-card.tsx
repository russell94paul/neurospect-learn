import { ChevronDown, Lock, Repeat } from 'lucide-react';
import { Checkbox } from '@/components/ui/checkbox';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { RuleChip, stripMarkdown } from '@/components/runner/rule-chip';
import { phaseProgress, tickKey, type RunnerPhase } from '@/lib/runner';
import { cn } from '@/lib/utils';

interface Props {
  phase: RunnerPhase;
  day: number;
  setup: number;
  ticks: Record<string, boolean>;
  onToggle: (key: string) => void;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const SCOPE_LABEL: Record<string, string> = {
  day: 'once per replayed day',
  setup: 'per setup',
  any: 'checkable any time',
};

/**
 * One checklist phase. Items are projected verbatim from
 * concepts/mastery/aura/checklist.md; a "hard gate" item is styled as a stop,
 * not as an ordinary tick, because a "no" there means no trade.
 */
export function PhaseCard({ phase, day, setup, ticks, onToggle, open, onOpenChange }: Props) {
  const { done, total, gatesOpen } = phaseProgress(phase, ticks, day, setup);
  const complete = done === total;

  return (
    <Collapsible open={open} onOpenChange={onOpenChange}>
      <div
        className={cn(
          'rounded-lg border bg-card',
          complete && 'border-success-emphasis/40',
          gatesOpen > 0 && !complete && 'border-warning-emphasis/40'
        )}
      >
        <CollapsibleTrigger className="flex w-full items-start gap-2 p-3 text-left">
          <span
            className={cn(
              'mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold',
              complete ? 'bg-success-emphasis text-success-on-emphasis' : 'bg-muted text-muted-foreground'
            )}
          >
            {phase.index}
          </span>
          <span className="min-w-0 flex-1">
            <span className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
              <span className="text-sm font-semibold leading-tight">{phase.title}</span>
              <span className="font-mono text-[11px] text-muted-foreground">
                {done}/{total}
              </span>
            </span>
            <span className="mt-1 flex flex-wrap items-center gap-1">
              <span className="inline-flex items-center gap-1 rounded bg-muted px-1 py-0.5 text-[10px] text-muted-foreground">
                {phase.scope === 'setup' ? (
                  <Repeat className="h-2.5 w-2.5" />
                ) : null}
                {SCOPE_LABEL[phase.scope]}
              </span>
              {gatesOpen > 0 && (
                <span className="inline-flex items-center gap-1 rounded bg-warning-emphasis/15 px-1 py-0.5 text-[10px] text-warning">
                  <Lock className="h-2.5 w-2.5" />
                  {gatesOpen} hard gate{gatesOpen > 1 ? 's' : ''} open
                </span>
              )}
            </span>
          </span>
          <ChevronDown
            className={cn('mt-1 h-4 w-4 shrink-0 text-muted-foreground transition-transform', open && 'rotate-180')}
          />
        </CollapsibleTrigger>

        <CollapsibleContent>
          {/* The phase heading's own [R##] refs. Rendered here, not in the
              trigger, because a button cannot nest inside a button — and
              dropped entirely they would take some rules (R54 among them) out
              of the runner's reach altogether. */}
          {phase.ruleRefs.length > 0 && (
            <div className="flex flex-wrap items-center gap-1 border-t px-3 pt-2">
              <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
                Phase rules
              </span>
              {phase.ruleRefs.map((r) => (
                <RuleChip key={r} id={r} />
              ))}
            </div>
          )}
          <ul className="space-y-1 px-3 py-2">
            {phase.items.map((item, i) => {
              const key = tickKey(phase.scope, day, setup, phase.index, i);
              const on = !!ticks[key];
              return (
                <li key={key}>
                  <label
                    className={cn(
                      'flex cursor-pointer items-start gap-2.5 rounded-md p-2 transition-colors hover:bg-accent/50',
                      item.hardGate && !on && 'bg-warning-emphasis/5'
                    )}
                  >
                    <Checkbox
                      checked={on}
                      onCheckedChange={() => onToggle(key)}
                      className="mt-0.5 h-5 w-5 shrink-0"
                    />
                    <span className="min-w-0 flex-1">
                      <span
                        className={cn(
                          'block text-[13px] leading-snug',
                          on && 'text-muted-foreground line-through decoration-1'
                        )}
                      >
                        {label(item.text)}
                      </span>
                      <span className="mt-1 flex flex-wrap items-center gap-1">
                        {item.hardGate && (
                          <span className="rounded bg-warning-emphasis/20 px-1 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-warning">
                            hard gate — a &ldquo;no&rdquo; means no trade
                          </span>
                        )}
                        {item.ruleRefs.map((r) => (
                          <RuleChip key={r} id={r} />
                        ))}
                      </span>
                    </span>
                  </label>
                </li>
              );
            })}
          </ul>
        </CollapsibleContent>
      </div>
    </Collapsible>
  );
}

/** Item text minus the trailing rule refs and the hard-gate marker (both shown as chips). */
function label(text: string): string {
  return stripMarkdown(
    text
      .replace(/\*\*\[[^\]]+\]\*\*/g, '')
      .replace(/←\s*hard gate/i, '')
  ).replace(/\s{2,}/g, ' ').trim();
}
