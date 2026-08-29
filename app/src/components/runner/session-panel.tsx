import { useState } from 'react';
import { Check, Copy, TriangleAlert } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  SPANS,
  endDateFor,
  sessionName,
  spanOf,
  toTradezellaDate,
  type RunnerState,
  type SpanKey,
} from '@/lib/runner';

interface Props {
  state: RunnerState;
  patch: (p: Partial<RunnerState>) => void;
}

/**
 * Declare the session before the replay is advanced.
 *
 * The span is configurable (Paul's requirement) but the COUNTED UNIT is the
 * replayed day — see concepts/mastery/aura/tradezella-setup.md §The counting
 * basis. This panel makes the basis visible rather than implied.
 */
export function SessionPanel({ state, patch }: Props) {
  const span = spanOf(state.span);

  return (
    <div className="space-y-3 rounded-lg border bg-card p-3">
      <div>
        <h2 className="text-sm font-semibold">Declare the session</h2>
        <p className="mt-0.5 text-[11px] leading-snug text-muted-foreground">
          Before the replay is advanced. The span is yours to choose; the counted unit is the{' '}
          <strong className="text-foreground">replayed day</strong>.
        </p>
      </div>

      <div className="space-y-1.5">
        <Label className="text-xs">Replay span</Label>
        <div className="flex flex-wrap gap-1">
          {SPANS.map((s) => (
            <Button
              key={s.key}
              size="sm"
              variant={state.span === s.key ? 'default' : 'outline'}
              className="h-7 px-2 text-xs"
              onClick={() => patch({ span: s.key as SpanKey })}
            >
              {s.label}
            </Button>
          ))}
        </div>
        <p className="text-[11px] text-muted-foreground">
          ≈ {span.tradingDays} replayed days — B2&rsquo;s ~20 is{' '}
          {Math.max(1, Math.ceil(20 / span.tradingDays))} sitting
          {Math.ceil(20 / span.tradingDays) > 1 ? 's' : ''} at this span.
        </p>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="runner-start" className="text-xs">
          Start date
        </Label>
        <Input
          id="runner-start"
          type="date"
          value={state.startDate}
          onChange={(e) => patch({ startDate: e.target.value, day: 0 })}
          className="h-8 text-sm"
        />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="runner-precommit" className="text-xs">
          Pre-commitment — R48&rsquo;s three questions
        </Label>
        <Textarea
          id="runner-precommit"
          rows={3}
          placeholder={'What am I looking for?\nWhere?\nWhat would make me stand aside?'}
          value={state.precommit}
          onChange={(e) =>
            patch({
              precommit: e.target.value,
              declaredAt: state.declaredAt ?? new Date().toISOString(),
            })
          }
          className="text-sm"
        />
        {/* An honest limit, stated in the face of the record — the E6 idiom. */}
        <p className="flex items-start gap-1.5 rounded bg-warning-emphasis/10 p-1.5 text-[11px] leading-snug text-warning">
          <TriangleAlert className="mt-0.5 h-3 w-3 shrink-0" />
          <span>
            This is stored in your browser and timestamped by{' '}
            <strong>your own device clock</strong>, so it is a note, not evidence of ordering.
            Paste it into the Tradezella session <strong>Description</strong> as well — that at
            least ties it to the session. A pre-commitment whose ordering can be trusted is the
            frozen ledger, which this screen deliberately does not write to.
          </span>
        </p>
      </div>

    </div>
  );
}

/**
 * The values to type into Tradezella's create-session form, in its own formats.
 *
 * Rendered SEPARATELY from the declaration panel because of a defect the render
 * walk caught: entering the start date switched the Run tab out of the panel and
 * into the protocol, which collapsed this block into a `<details>` at exactly
 * the moment it is needed. You declare the span and then immediately go and
 * create the session — so this has to stay on screen across that transition.
 */
export function TradezellaPaste({ state }: { state: RunnerState }) {
  const end = endDateFor(state.startDate, state.span);
  return (
    <div className="space-y-1.5 rounded-md bg-muted/50 p-2">
      <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
        Paste into Tradezella
      </p>
      <CopyRow label="Session name" value={sessionName(state.startDate, state.span)} />
      <CopyRow label="Start date" value={toTradezellaDate(state.startDate)} />
      <CopyRow label="End date" value={toTradezellaDate(end, true)} />
      <CopyRow label="Symbols" value="NQ, ES, YM, CHFUSD" />
      <p className="pt-0.5 text-[11px] leading-snug text-muted-foreground">
        The indices triad (R16) — three of the five slots allowed.{' '}
        <strong className="text-foreground">Not</strong> MNQ or MES: they are micro contracts of NQ
        and ES, so their divergences carry no information (measured — one divergence in 56, at a
        margin of zero) and the confirmation engine has nothing to read.
      </p>
      <p className="pt-0.5 text-[11px] leading-snug text-muted-foreground">
        <code>CHFUSD</code> stands in for <strong className="text-foreground">6S</strong>, the Aura
        Asset — a <em>flagged</em> 4th leg (R17), added <em>alongside</em> the triad, never replacing
        YM. 6S is quoted USD-per-CHF, and CHFUSD prints ~1.21 (a franc costs $1.21), so it matches;{' '}
        <code>USDCHF</code> prints ~0.82 and is <strong>inverted</strong> — it would reverse every
        divergence read.
      </p>
    </div>
  );
}

function CopyRow({ label, value }: { label: string; value: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="flex items-center gap-1.5">
      <span className="w-20 shrink-0 text-[11px] text-muted-foreground">{label}</span>
      <code className="min-w-0 flex-1 truncate rounded bg-background px-1.5 py-0.5 text-[11px]">
        {value}
      </code>
      <Button
        size="icon"
        variant="ghost"
        className="h-6 w-6 shrink-0"
        onClick={() => {
          navigator.clipboard?.writeText(value).then(
            () => {
              setCopied(true);
              setTimeout(() => setCopied(false), 1200);
            },
            () => undefined
          );
        }}
      >
        {copied ? <Check className="h-3 w-3 text-success" /> : <Copy className="h-3 w-3" />}
        <span className="sr-only">Copy {label}</span>
      </Button>
    </div>
  );
}
