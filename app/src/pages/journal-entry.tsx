import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, Loader2, Trash2 } from 'lucide-react';
import { useCreateEntry, useDeleteEntry, useJournalEntry, useUpdateEntry } from '@/lib/journal';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { JournalForm } from '@/components/journal/journal-form';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { EvidenceCapture } from '@/components/evidence/evidence-capture';
import type { JournalEntryIn } from '@/types/api';

/** /journal/new (create) + /journal/:id (edit) — one form, both flows.
 * `id` is undefined on the static /new route, present (a uuid) on /:id. */
export function JournalEntryPage() {
  const { id } = useParams();
  const editing = !!id;
  const navigate = useNavigate();

  const entryQuery = useJournalEntry(id);
  const create = useCreateEntry();
  const update = useUpdateEntry();
  const del = useDeleteEntry();
  const [confirmDelete, setConfirmDelete] = useState(false);

  const saving = create.isPending || update.isPending;
  const saveError = ((create.error || update.error) as Error | null)?.message ?? null;

  function handleSubmit(body: JournalEntryIn) {
    if (editing && id) {
      update.mutate({ id, body }, { onSuccess: () => navigate('/journal') });
    } else {
      create.mutate(body, { onSuccess: () => navigate('/journal') });
    }
  }

  function handleDelete() {
    if (!id) return;
    del.mutate(id, { onSuccess: () => navigate('/journal') });
  }

  const back = (
    <Button variant="ghost" size="sm" asChild className="-ml-2 w-fit">
      <Link to="/journal">
        <ArrowLeft className="mr-1.5 h-4 w-4" /> Journal
      </Link>
    </Button>
  );

  if (editing && entryQuery.isLoading) {
    return (
      <div className="mx-auto max-w-3xl space-y-6">
        {back}
        <Skeleton className="h-96 w-full" />
      </div>
    );
  }

  if (editing && entryQuery.isError) {
    return (
      <div className="mx-auto max-w-3xl space-y-6">
        {back}
        <Card>
          <CardContent className="py-10 text-center text-muted-foreground">Entry not found.</CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      {back}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">{editing ? 'Edit entry' : 'New entry'}</h1>
        {editing && (
          confirmDelete ? (
            <div className="flex items-center gap-2 text-sm">
              <span className="text-muted-foreground">Delete this entry?</span>
              <Button variant="destructive" size="sm" onClick={handleDelete} disabled={del.isPending}>
                {del.isPending ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> : null} Confirm
              </Button>
              <Button variant="ghost" size="sm" onClick={() => setConfirmDelete(false)}>
                Cancel
              </Button>
            </div>
          ) : (
            <Button variant="outline" size="sm" onClick={() => setConfirmDelete(true)}>
              <Trash2 className="mr-1.5 h-4 w-4" /> Delete
            </Button>
          )
        )}
      </div>

      <JournalForm
        defaults={editing ? entryQuery.data : undefined}
        onSubmit={handleSubmit}
        isSaving={saving}
        saveError={saveError}
        submitLabel={editing ? 'Save changes' : 'Create entry'}
      />

      {/* Screenshots were deferred at 5c because they are the SAME primitive
          verified drill grading needs. Phase E2 built that one evidence layer,
          so the journal attaches to it here — no second table, no duplication.
          Only available once the entry exists (evidence needs something to
          attach to). Journal evidence is a record, not a rep. */}
      {editing && id && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Screenshots</CardTitle>
          </CardHeader>
          <CardContent>
            <EvidenceCapture
              subject={{ subject_type: 'journal_entry', journal_entry_id: id }}
              label="Charts for this trade"
              hint="Entry, management and exit captures. These are a record — they do not count reps."
              showRepsClaimed={false}
            />
          </CardContent>
        </Card>
      )}
    </div>
  );
}
