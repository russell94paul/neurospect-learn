import { Link } from 'react-router-dom';
import { TrendingUp } from 'lucide-react';
import { pct, rMultiple, useExpectancy, useRDistribution, useSummary } from '@/lib/analytics';
import { ENTRY_MODEL_LABELS } from '@/lib/journal';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import { ExpectancyChart } from '@/components/analytics/expectancy-chart';
import { BacktestVsLiveChart } from '@/components/analytics/backtest-vs-live-chart';
import { RDistributionChart } from '@/components/analytics/r-distribution-chart';
import type { EntryModel, ExpectancyGroup, ModeSummary } from '@/types/api';

const MODE_LABEL: Record<string, string> = { backtest: 'Backtest', live: 'Live' };

function SummaryTile({ summary }: { summary: ModeSummary }) {
  const isLive = summary.mode === 'live';
  return (
    <Card>
      <CardContent className="space-y-2 py-4">
        <div className="flex items-center gap-2">
          <span
            className="inline-block h-2.5 w-2.5 rounded-sm"
            style={{ backgroundColor: isLive ? 'var(--chart-live)' : 'var(--chart-backtest)' }}
          />
          <span className="text-sm font-semibold">{MODE_LABEL[summary.mode]}</span>
          <span className="ml-auto text-xs text-muted-foreground tabular-nums">
            {summary.n}/{summary.logged} closed
          </span>
        </div>
        <div className="flex items-baseline gap-2">
          <span
            className={cn(
              'text-2xl font-bold tabular-nums',
              summary.expectancy == null ? 'text-muted-foreground'
                : summary.expectancy > 0 ? 'text-emerald-600 dark:text-emerald-400'
                  : summary.expectancy < 0 ? 'text-destructive' : ''
            )}
          >
            {rMultiple(summary.expectancy)}
          </span>
          <span className="text-xs text-muted-foreground">expectancy / trade</span>
        </div>
        <div className="flex gap-4 text-xs text-muted-foreground">
          <span>win {pct(summary.win_rate)}</span>
          <span>total {rMultiple(summary.total_r)}</span>
        </div>
      </CardContent>
    </Card>
  );
}

function ExpectancyTable({ groups, sampleTarget }: { groups: ExpectancyGroup[]; sampleTarget: number }) {
  if (!groups.length) return null;
  const sorted = [...groups].sort(
    (a, b) => a.entry_model.localeCompare(b.entry_model) || a.mode.localeCompare(b.mode)
  );
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b text-left text-xs text-muted-foreground">
            <th className="py-2 pr-3 font-medium">Model</th>
            <th className="py-2 pr-3 font-medium">Mode</th>
            <th className="py-2 pr-3 text-right font-medium">n</th>
            <th className="py-2 pr-3 text-right font-medium">Win%</th>
            <th className="py-2 pr-3 text-right font-medium">Avg win</th>
            <th className="py-2 pr-3 text-right font-medium">Avg loss</th>
            <th className="py-2 pr-3 text-right font-medium">Expectancy</th>
            <th className="py-2 pr-3 text-right font-medium">Break-even</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((g) => (
            <tr key={`${g.entry_model}-${g.mode}`} className="border-b last:border-0">
              <td className="py-2 pr-3">{ENTRY_MODEL_LABELS[g.entry_model as EntryModel] ?? g.entry_model}</td>
              <td className="py-2 pr-3 capitalize text-muted-foreground">{g.mode}</td>
              <td className="py-2 pr-3 text-right tabular-nums">
                <span className={cn(!g.sample_met && 'text-amber-600 dark:text-amber-400')} title={`Reference sample: ${sampleTarget}`}>
                  {g.n}
                </span>
              </td>
              <td className="py-2 pr-3 text-right tabular-nums">{pct(g.win_rate)}</td>
              <td className="py-2 pr-3 text-right tabular-nums">{g.avg_win_r == null ? '—' : `${g.avg_win_r.toFixed(2)}R`}</td>
              <td className="py-2 pr-3 text-right tabular-nums">{g.avg_loss_r == null ? '—' : `${g.avg_loss_r.toFixed(2)}R`}</td>
              <td className={cn('py-2 pr-3 text-right font-medium tabular-nums',
                g.expectancy == null ? '' : g.expectancy > 0 ? 'text-emerald-600 dark:text-emerald-400' : g.expectancy < 0 ? 'text-destructive' : '')}>
                {rMultiple(g.expectancy)}
              </td>
              <td className="py-2 pr-3 text-right tabular-nums">
                {g.break_even == null ? '—' : (
                  <span className={cn(g.above_break_even ? 'text-emerald-600 dark:text-emerald-400' : 'text-muted-foreground')}>
                    {pct(g.break_even)}
                  </span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** /expectancy — the empirical proof-of-edge dashboard. Per-model expectancy +
 * win rate, backtest vs live (never conflated), with sample sizes visible so an
 * under-evidenced model reads as such. No "cleared to live" verdict here — that
 * is the Gate (Phase 5g); this is the VIEW the gate will read. */
export function ExpectancyPage() {
  const expectancy = useExpectancy();
  const summary = useSummary();
  const rDist = useRDistribution();

  const groups = expectancy.data?.groups ?? [];
  const sampleTarget = expectancy.data?.sample_target ?? 50;
  const modes = summary.data?.modes ?? [];
  const totalClosed = modes.reduce((s, m) => s + m.n, 0);
  const totalLogged = modes.reduce((s, m) => s + m.logged, 0);

  const loading = expectancy.isLoading || summary.isLoading;

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Expectancy</h1>
        <p className="text-muted-foreground">
          Per-model proof of edge in R — backtest and live kept separate. Expectancy is computed only over
          closed trades (a realized R).
        </p>
      </div>

      {loading ? (
        <div className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <Skeleton className="h-28 w-full" />
            <Skeleton className="h-28 w-full" />
          </div>
          <Skeleton className="h-72 w-full" />
        </div>
      ) : totalLogged === 0 ? (
        <Card>
          <CardContent className="space-y-3 py-10 text-center">
            <TrendingUp className="mx-auto h-8 w-8 text-muted-foreground" />
            <p className="text-muted-foreground">
              No journal entries yet. Log backtested setups and their outcomes, and your edge builds here.
            </p>
            <Button asChild>
              <Link to="/journal/new">Log a setup</Link>
            </Button>
          </CardContent>
        </Card>
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2">
            {modes.map((m) => (
              <SummaryTile key={m.mode} summary={m} />
            ))}
          </div>

          {totalClosed === 0 && (
            <p className="rounded-md border border-dashed p-3 text-sm text-muted-foreground">
              {totalLogged} {totalLogged === 1 ? 'entry' : 'entries'} logged, none closed yet — expectancy appears once
              trades carry a realized R.
            </p>
          )}

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Expectancy by model (R)</CardTitle>
            </CardHeader>
            <CardContent>
              <ExpectancyChart groups={groups} />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Win rate — backtest vs live</CardTitle>
            </CardHeader>
            <CardContent>
              <BacktestVsLiveChart groups={groups} />
            </CardContent>
          </Card>

          {rDist.data && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">R distribution</CardTitle>
              </CardHeader>
              <CardContent>
                <RDistributionChart buckets={rDist.data.buckets} />
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Per-model detail</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <ExpectancyTable groups={groups} sampleTarget={sampleTarget} />
              <p className="text-xs text-muted-foreground">
                Amber sample sizes are below the reference of {sampleTarget} closed trades — a guideline for
                statistical meaning, <span className="font-medium">not</span> the live-eligibility gate. Confluence
                (frontier) tags are study-only and never count toward going live. The Readiness-to-Live decision
                lives on the Gate.
              </p>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
