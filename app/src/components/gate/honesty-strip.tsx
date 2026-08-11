import { ScrollText } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import { useHonesty } from '@/lib/honesty';
import type { HonestySignal } from '@/types/api';

/**
 * THE HONESTY STRIP — the record, shown in the face of the claim.
 *
 * concepts/architecture/learning-enforcement.md §5 names the five signals and the
 * idiom §5g established for them: "shown in the face of the record, gating nothing
 * on an invented rule." This component is that sentence rendered, and the design
 * problem is entirely in what it must NOT do:
 *
 * · **No verdict, no colour-coding, no tick.** A green "0 flags" badge is a point
 *   scored for not being caught, and §6 (Deci/Koestner/Ryan 1999) is explicit that
 *   rewarding activity over mastery would undermine the Gate this strip sits on.
 *   Nothing here is styled as good or bad — the numbers are muted facts.
 * · **"Not measured" is never rendered as a zero.** A fresh user must not be told
 *   they are clean by an instrument that has never been fed. This is E5's
 *   `accuracy: null` precedent (calibration-panel.tsx), owed five times over, and
 *   it is the only reason the strip is trustworthy at all.
 * · **Every threshold is printed.** Two of the five need one; both state it in
 *   `measured_what`, so a reader can discount the figure rather than take it on faith.
 * · **Every finding names its subjects.** "3 captures were back-dated" without
 *   saying which three is a scolding; informational feedback (§6) is actionable.
 * · **Nothing is dismissible.** There is no acknowledge control and no mutation
 *   behind this component — a signal you can switch off is not a record.
 *
 * It gates nothing, and says so. The Gate's verdict is computed from three inputs
 * (concept ladder · backtest expectancy · four attestations) and this is none of
 * them — it is served from its own endpoint precisely so that stays true.
 */
function SignalRow({ signal }: { signal: HonestySignal }) {
  const measured = signal.status === 'measured';
  const found = measured && (signal.count ?? 0) > 0;

  return (
    <li
      data-testid="honesty-signal"
      data-signal={signal.key}
      data-status={signal.status}
      data-count={signal.count === null ? 'null' : String(signal.count)}
      className="py-2.5 text-sm"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
        <span className="font-medium">{signal.label}</span>
        {measured ? (
          <span
            className={cn('text-xs tabular-nums', found ? 'text-foreground' : 'text-muted-foreground')}
            data-testid="honesty-value"
          >
            {signal.count} of {signal.population}
          </span>
        ) : (
          /* NOT a zero. The absence of a measurement is its own state and has to
             read as one, or the whole strip becomes a reassurance machine. */
          <span
            className="text-[11px] uppercase tracking-wide text-muted-foreground"
            data-testid="honesty-unmeasured"
          >
            not measured
          </span>
        )}
      </div>
      <p className="text-xs text-muted-foreground">{signal.detail}</p>
      <p className="text-[11px] text-muted-foreground/80">Measured: {signal.measured_what}.</p>
      {signal.subjects.length > 0 && (
        <p className="text-[11px] text-muted-foreground/80" data-testid="honesty-subjects">
          {signal.subjects.slice(0, 6).join(' · ')}
          {signal.subjects.length > 6 && ` +${signal.subjects.length - 6} more`}
        </p>
      )}
    </li>
  );
}

export function HonestyStripCard({ className }: { className?: string }) {
  const { data } = useHonesty();
  if (!data) return null;

  const measured = data.signals.filter((s) => s.status === 'measured').length;

  return (
    <Card className={cn('border-dashed', className)} data-testid="honesty-strip">
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-base">
          <ScrollText className="h-4 w-4 text-muted-foreground" />
          The record
        </CardTitle>
        <p className="text-xs text-muted-foreground">
          What your evidence actually looks like, computed fresh on every read and stored nowhere.{' '}
          <span className="font-medium">None of this gates anything</span> — the verdict above is
          built from your concept ladder, your backtest expectancy and the four attestations, and
          these numbers are not among its inputs. They are here so a self-attestation is made in
          the face of the record.
        </p>
      </CardHeader>
      <CardContent className="space-y-3">
        <ul className="divide-y">
          {data.signals.map((s) => (
            <SignalRow key={s.key} signal={s} />
          ))}
        </ul>

        {/* E2 froze `legacy_reps` and left it visible for exactly this phase: it is
            the one part of the rep count with no evidence behind it, and no
            re-derivation can ever give it any. Shown only when it exists. */}
        {data.reps_legacy > 0 && (
          <p className="text-xs text-muted-foreground" data-testid="honesty-legacy-reps">
            <span className="font-medium tabular-nums text-foreground">{data.reps_legacy}</span> of
            your reps were claimed before evidence was required (
            <span className="tabular-nums">{data.reps_evidenced}</span> are evidenced). Those
            pre-evidence reps still count and were never removed — but nothing can be shown for
            them now, so they are listed here rather than folded into a single number.
          </p>
        )}

        {/* THE SUMMARY LINE QUALIFIES A MEASUREMENT — so it may only appear when
            there has been one. Rendered unconditionally it printed "0 of 5 signals
            had something to measure, across 0 captures" directly beneath five
            careful "not measured" rows: every word true, and together a reassuring
            zero that undoes the exact distinction the strip exists to draw. A
            query-layer check passes here, because a `measured_count` of 0 is a
            perfectly correct count of an empty set. Caught by e2e/honesty.spec.ts
            on the rendered page — the same defect class as E5's calibration panel,
            and pinned the same way: no "0 of N" may appear on an empty record. */}
        {measured === 0 ? (
          <p className="border-t pt-3 text-[11px] text-muted-foreground">
            Nothing has been measured yet — none of these signals has been given anything to look
            at. That is not the same as a clean record, and it is deliberately not shown as one:
            capture some evidence and they will have something to report.
          </p>
        ) : (
          <p className="border-t pt-3 text-[11px] text-muted-foreground">
            {measured} of {data.signals.length} signals had something to measure, across{' '}
            {data.captures} {data.captures === 1 ? 'capture' : 'captures'}. A signal with nothing
            to look at reports <span className="font-medium">not measured</span> rather than zero
            — being unable to see is not the same as finding nothing.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
