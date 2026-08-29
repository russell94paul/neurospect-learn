import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Eye, Lock, ShieldCheck } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { cn } from '@/lib/utils';
import { useGate } from '@/lib/gate';
import { TRACK_LABELS } from '@/lib/learning';
import { GateSignal } from '@/components/gate/gate-signal';
import { GateChecklist } from '@/components/gate/gate-checklist';
import { HonestyStripCard } from '@/components/gate/honesty-strip';

const ANY_TRACK = '__any__';

/**
 * /gate — the Readiness-to-Live Gate: the computed "cleared to live?" verdict per
 * entry model. The whole disciplined process pays off here.
 *
 * Nothing on this page can override the verdict. The server recomputes it from
 * (a) the concept ladder, (b) backtest expectancy in R, (c) four attestations;
 * the only input is ticking a behavioural item, which cannot clear a model whose
 * ladder or expectancy is short. Frontier (U5) concepts are listed as explicitly
 * never gate-eligible.
 */
export function GatePage() {
  const [creditTrack, setCreditTrack] = useState<string>(ANY_TRACK);
  const [selected, setSelected] = useState<string | null>(null);
  const gate = useGate(creditTrack === ANY_TRACK ? undefined : creditTrack);

  const models = gate.data?.models ?? [];
  const clearedCount = models.filter((m) => m.cleared).length;
  const active = models.find((m) => m.entry_model === selected) ?? models[0];

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Gate</h1>
        <p className="text-muted-foreground">
          Am I good enough to live-trade this model yet? Evidence-based, per model — your concept ladder, your
          backtest expectancy, and the behavioural checklist. The bar is{' '}
          <Link to="/concepts/mastery" className="underline underline-offset-2">
            the Readiness-to-Live Gate
          </Link>
          .
        </p>
      </div>

      {gate.isLoading ? (
        <div className="space-y-4">
          <Skeleton className="h-20 w-full" />
          <div className="grid gap-3 sm:grid-cols-2">
            <Skeleton className="h-44 w-full" />
            <Skeleton className="h-44 w-full" />
          </div>
        </div>
      ) : gate.isError ? (
        <Card>
          <CardContent className="py-8 text-center text-muted-foreground">
            Could not load the gate.
          </CardContent>
        </Card>
      ) : (
        <>
          <Card
            data-testid="gate-overall"
            data-cleared-count={clearedCount}
            className={cn(clearedCount > 0 && 'border-success-emphasis/40 bg-success-emphasis/5')}
          >
            <CardContent className="flex flex-wrap items-center gap-3 py-4">
              {clearedCount > 0 ? (
                <ShieldCheck className="h-6 w-6 text-success" />
              ) : (
                <Lock className="h-6 w-6 text-muted-foreground" />
              )}
              <div className="min-w-0 flex-1">
                <p className="font-semibold">
                  {clearedCount === 0
                    ? 'No model is cleared to live yet.'
                    : `${clearedCount} ${clearedCount === 1 ? 'model is' : 'models are'} cleared to live.`}
                </p>
                <p className="text-xs text-muted-foreground">
                  {clearedCount === 0
                    ? 'Every requirement below is earned, not declared — the gate cannot be overridden.'
                    : 'Start small: the gate certifies readiness to begin, not to size up.'}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs text-muted-foreground">Credit progress from</span>
                <Select value={creditTrack} onValueChange={setCreditTrack}>
                  <SelectTrigger className="h-8 w-[150px] text-xs" aria-label="Credit track">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={ANY_TRACK}>Any track</SelectItem>
                    {Object.entries(TRACK_LABELS).map(([key, label]) => (
                      <SelectItem key={key} value={key}>
                        {label} only
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </CardContent>
          </Card>

          {creditTrack !== ANY_TRACK && (
            <p className="text-xs text-muted-foreground">
              Showing a stricter view: only {TRACK_LABELS[creditTrack]} progress may satisfy a concept
              requirement. Restricting the credit track can only tighten the verdict, never loosen it.
            </p>
          )}

          <div className="grid gap-3 sm:grid-cols-2">
            {models.map((m) => (
              <GateSignal
                key={m.entry_model}
                model={m}
                selected={active?.entry_model === m.entry_model}
                onSelect={() => setSelected(m.entry_model)}
              />
            ))}
          </div>

          {active && gate.data && (
            <GateChecklist
              model={active}
              attestations={gate.data.attestations}
              corroboration={gate.data.corroboration}
            />
          )}

          {/* The E6 honesty strip, beside the attestations (§5). It is fetched
              SEPARATELY from the verdict on purpose — nothing in it reaches
              `compute_readiness`, so it cannot move the gate above even by
              accident. See components/gate/honesty-strip.tsx. */}
          <HonestyStripCard />

          {gate.data && gate.data.frontier.length > 0 && (
            <Card data-testid="gate-frontier">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Eye className="h-4 w-4" />
                  Frontier — never gate-eligible
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <p className="text-xs text-muted-foreground">
                  These {gate.data.frontier.length} concepts are study-and-watch only. They never count toward
                  live-readiness for any model, at any ladder position — and confluence tags logged against them
                  are study data, never evidence of edge.
                </p>
                <ul className="flex flex-wrap gap-1.5">
                  {gate.data.frontier.map((f) => (
                    <li key={f.slug}>
                      <Badge variant="outline" className="text-[11px] font-normal text-muted-foreground">
                        {f.title}
                        {f.label && <span className="ml-1 opacity-70">· {f.label}</span>}
                      </Badge>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}

          <p className="text-xs text-muted-foreground">
            The backtest sample bar is {gate.data?.sample_target} closed trades per model, with{' '}
            {gate.data?.sample_stretch} the ideal — the stretch figure is shown for context and is not part of
            the verdict. Expectancy and win rate come from{' '}
            <Link to="/expectancy" className="underline underline-offset-2">
              the expectancy dashboard
            </Link>{' '}
            and count backtest trades only; a losing live record is surfaced for honesty but never gates.
          </p>
        </>
      )}
    </div>
  );
}
