import { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { Plus, NotebookPen, CircleSlash } from 'lucide-react';
import { useJournalEntries } from '@/lib/journal';
import { useMissedTrades } from '@/lib/missed-trades';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { JournalCard } from '@/components/journal/journal-card';
import { JournalFilters } from '@/components/journal/journal-filters';
import { MissedTradeCard } from '@/components/journal/missed-trade-card';
import { MissedFilters } from '@/components/journal/missed-filters';
import { OpportunityCost } from '@/components/journal/opportunity-cost';
import type { JournalFilterState, MissedFilterState } from '@/types/api';

/**
 * /journal — the model-aligned trade log.
 *
 * Two tabs, because the north star says the journal covers EVERY trade including
 * the ones you didn't take (Phase 6b): executed entries, and the missed/canceled
 * log with its opportunity-cost view. They are separate tables and separate
 * analytics — a trade never taken must never dilute executed expectancy — but one
 * journaling surface, not a new top-level destination. `?tab=missed` is in the URL
 * so the view is linkable.
 */
export function JournalPage() {
  const [params, setParams] = useSearchParams();
  const tab = params.get('tab') === 'missed' ? 'missed' : 'trades';

  const [filters, setFilters] = useState<JournalFilterState>({});
  const [missedFilters, setMissedFilters] = useState<MissedFilterState>({});

  const query = useJournalEntries(filters);
  const missedQuery = useMissedTrades(missedFilters);

  const entries = query.data ?? [];
  const missed = missedQuery.data ?? [];
  const filtered = !!(filters.mode || filters.entry_model || filters.instrument);
  const missedFiltered = !!(
    missedFilters.miss_type ||
    missedFilters.entry_model ||
    missedFilters.hypothetical_outcome ||
    missedFilters.instrument
  );

  function selectTab(next: string) {
    const p = new URLSearchParams(params);
    if (next === 'missed') p.set('tab', 'missed');
    else p.delete('tab');
    setParams(p, { replace: true });
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Journal</h1>
          <p className="text-muted-foreground">
            Every setup — backtest, live, and the ones you didn't take — logged against the
            model-aligned decision flow.
          </p>
        </div>
        <Button asChild>
          <Link to={tab === 'missed' ? '/journal/missed/new' : '/journal/new'}>
            <Plus className="mr-1.5 h-4 w-4" /> {tab === 'missed' ? 'Log a miss' : 'New entry'}
          </Link>
        </Button>
      </div>

      <Tabs value={tab} onValueChange={selectTab}>
        <TabsList>
          <TabsTrigger value="trades">Trades taken</TabsTrigger>
          <TabsTrigger value="missed">Missed &amp; canceled</TabsTrigger>
        </TabsList>

        {/* ------------------------------------------------ executed trades */}
        <TabsContent value="trades" className="space-y-4 pt-3">
          <JournalFilters value={filters} onChange={setFilters} />

          {query.isLoading ? (
            <div className="space-y-2">
              <Skeleton className="h-16 w-full" />
              <Skeleton className="h-16 w-full" />
              <Skeleton className="h-16 w-full" />
            </div>
          ) : entries.length === 0 ? (
            <Card>
              <CardContent className="space-y-3 py-10 text-center">
                <NotebookPen className="mx-auto h-8 w-8 text-muted-foreground" />
                <p className="text-muted-foreground">
                  {filtered
                    ? 'No entries match these filters.'
                    : 'No entries yet — log your first setup to start building expectancy.'}
                </p>
                {!filtered && (
                  <Button asChild>
                    <Link to="/journal/new">Log a setup</Link>
                  </Button>
                )}
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-2" data-testid="journal-list">
              {entries.map((entry) => (
                <JournalCard key={entry.id} entry={entry} />
              ))}
            </div>
          )}
        </TabsContent>

        {/* -------------------------------------------- missed / canceled */}
        <TabsContent value="missed" className="space-y-4 pt-3">
          <OpportunityCost />

          <MissedFilters value={missedFilters} onChange={setMissedFilters} />

          {missedQuery.isLoading ? (
            <div className="space-y-2">
              <Skeleton className="h-16 w-full" />
              <Skeleton className="h-16 w-full" />
            </div>
          ) : missed.length === 0 ? (
            <Card>
              <CardContent className="space-y-3 py-10 text-center">
                <CircleSlash className="mx-auto h-8 w-8 text-muted-foreground" />
                <p className="mx-auto max-w-md text-muted-foreground">
                  {missedFiltered
                    ? 'No missed trades match these filters.'
                    : "Nothing logged yet. The trades you almost took, hesitated on, or canceled are the ones nobody records — and they may hold your biggest breakthrough."}
                </p>
                {!missedFiltered && (
                  <Button asChild>
                    <Link to="/journal/missed/new">Log a miss</Link>
                  </Button>
                )}
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-2" data-testid="missed-list">
              {missed.map((m) => (
                <MissedTradeCard key={m.id} miss={m} />
              ))}
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
