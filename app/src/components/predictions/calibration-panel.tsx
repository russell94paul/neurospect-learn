import { Target } from 'lucide-react';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import { pct, useCalibration } from '@/lib/predictions';

/**
 * CALIBRATION — how often your pre-committed call matched reality.
 *
 * This is the one genuinely new mechanic in the workstream
 * (concepts/architecture/learning-enforcement.md §6) and the whole design problem
 * is presenting it WITHOUT turning it into a currency. Deci, Koestner & Ryan
 * (1999), a meta-analysis of 128 experiments, find tangible performance-contingent
 * rewards undermine intrinsic motivation (d ≈ −0.34) while informational feedback
 * does not. So, deliberately:
 *
 * · **No target, no threshold, no ring, no streak, no "grade".** There is nothing to
 *   fill up and nothing to keep alive. A progress ring would silently assert that
 *   100% is the goal, and the goal is an accurate self-model — a trader who knows
 *   they read DOL at 40% is better off than one who thinks they read it at 90%.
 * · **Every figure carries its denominator.** "3 of 4" beside the percentage, so a
 *   small sample reads as a small sample.
 * · **A zero is never rendered for an empty record.** No resolved call means "not
 *   measured yet", not 0% — the distinction between a measurement and a missing
 *   instrument is exactly what makes this figure trustworthy.
 * · **The resolution rate is shown whenever calls are outstanding.** Scoring only
 *   the calls you got right is the one remaining way to flatter this number, and the
 *   app cannot force a resolution — so it publishes the gap instead of hiding it.
 * · **Nothing here gates anything.** M6's exit bar is derived from whether the calls
 *   were COMMITTED before the reveal and then scored, never from whether they were
 *   right. The copy says so, because a user who suspects accuracy gates the stage
 *   will stop writing down calls they might lose.
 */
export function CalibrationPanel({
  drillRef,
  className,
}: {
  drillRef?: string;
  className?: string;
}) {
  const { data } = useCalibration(drillRef);
  if (!data || data.committed === 0) return null;

  const overall = pct(data.accuracy);

  return (
    <Card className={cn('border-dashed', className)} data-testid="calibration-panel">
      <CardHeader className="pb-2">
        <div className="flex items-center gap-2">
          <Target className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm font-medium">Calibration</span>
        </div>
        <p className="text-xs text-muted-foreground">
          Your pre-committed calls against what actually happened. This gates nothing — the tape
          stage asks that you called it before the reveal and scored it honestly, not that you
          were right.
        </p>
      </CardHeader>
      <CardContent className="space-y-3">
        {overall === null ? (
          <p className="text-sm text-muted-foreground" data-testid="calibration-unmeasured">
            {data.committed} {data.committed === 1 ? 'call' : 'calls'} committed, none scored yet —
            so there is nothing to measure. (Not zero: no outcome has been recorded.)
          </p>
        ) : (
          <div className="flex flex-wrap items-baseline gap-x-2">
            <span className="text-2xl font-semibold tabular-nums" data-testid="calibration-overall">
              {overall}
            </span>
            <span className="text-xs text-muted-foreground">
              of {data.components.reduce((n, c) => n + c.resolved, 0)} judgements across{' '}
              {data.resolved} scored {data.resolved === 1 ? 'call' : 'calls'}
            </span>
          </div>
        )}

        <dl className="grid gap-1.5 sm:grid-cols-2">
          {data.components.map((c) => {
            const value = pct(c.accuracy);
            return (
              <div key={c.key} className="flex items-baseline justify-between gap-2 text-sm">
                <dt className="text-muted-foreground">{c.label}</dt>
                <dd className="tabular-nums">
                  {value === null ? (
                    <span className="text-xs text-muted-foreground">not scored yet</span>
                  ) : (
                    <>
                      {value}
                      <span className="ml-1 text-xs text-muted-foreground">
                        ({c.correct}/{c.resolved})
                      </span>
                    </>
                  )}
                </dd>
              </div>
            );
          })}
        </dl>

        {/* The backlog line QUALIFIES A SCORE — it only means anything when there is
            one. Rendered unconditionally it printed "0% of your calls have an
            outcome recorded" directly beneath "Not 0%: no outcome has been
            recorded": both true, but together they read as a contradiction and
            undo the very distinction the panel exists to make. Caught by
            e2e/predictions.spec.ts on the rendered page; a query-layer check would
            have passed, because `resolution_rate: 0.0` is a perfectly correct
            measurement of "0 of 1 resolved". */}
        {data.unresolved > 0 && data.resolved > 0 && (
          <p className="text-xs text-muted-foreground" data-testid="calibration-backlog">
            {data.unresolved} {data.unresolved === 1 ? 'call is' : 'calls are'} committed and not
            yet scored ({pct(data.resolution_rate)} of your calls have an outcome recorded).
            Scoring only the ones that went your way would flatter the numbers above, so the gap
            is shown here.
          </p>
        )}

        {!drillRef && (
          <p className="text-xs text-muted-foreground">
            Tape reads called before the reveal: {data.tape_drills_resolved}/
            {data.tape_drills_total} scored
            {data.tape_drills_committed > data.tape_drills_resolved &&
              ` · ${data.tape_drills_committed - data.tape_drills_resolved} awaiting an outcome`}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
