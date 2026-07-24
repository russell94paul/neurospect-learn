import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Plus, NotebookPen } from 'lucide-react';
import { useJournalEntries } from '@/lib/journal';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { JournalCard } from '@/components/journal/journal-card';
import { JournalFilters } from '@/components/journal/journal-filters';
import type { JournalFilterState } from '@/types/api';

/** /journal — the model-aligned trade log (backtest + live), newest first. */
export function JournalPage() {
  const [filters, setFilters] = useState<JournalFilterState>({});
  const query = useJournalEntries(filters);
  const entries = query.data ?? [];
  const filtered = !!(filters.mode || filters.entry_model || filters.instrument);

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Journal</h1>
          <p className="text-muted-foreground">
            Every setup — backtest and live — logged against the model-aligned decision flow.
          </p>
        </div>
        <Button asChild>
          <Link to="/journal/new">
            <Plus className="mr-1.5 h-4 w-4" /> New entry
          </Link>
        </Button>
      </div>

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
              {filtered ? 'No entries match these filters.' : 'No entries yet — log your first setup to start building expectancy.'}
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
    </div>
  );
}
