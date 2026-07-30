import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, Loader2, Trash2 } from 'lucide-react';
import {
  useCreateMissedTrade,
  useDeleteMissedTrade,
  useMissedTrade,
  useUpdateMissedTrade,
} from '@/lib/missed-trades';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { MissedTradeForm } from '@/components/journal/missed-trade-form';
import { EvidenceCapture } from '@/components/evidence/evidence-capture';
import type { MissedTradeIn } from '@/types/api';

const BACK = '/journal?tab=missed';

/** /journal/missed/new (create) + /journal/missed/:id (edit) — one form, both
 * flows, mirroring journal-entry.tsx. Editing is how a miss gets RESOLVED: log it
 * in the moment, fill in what price did afterwards. */
export function MissedTradeEntryPage() {
  const { id } = useParams();
  const editing = !!id;
  const navigate = useNavigate();

  const missQuery = useMissedTrade(id);
  const create = useCreateMissedTrade();
  const update = useUpdateMissedTrade();
  const del = useDeleteMissedTrade();
  const [confirmDelete, setConfirmDelete] = useState(false);

  const saving = create.isPending || update.isPending;
  const saveError = ((create.error || update.error) as Error | null)?.message ?? null;

  function handleSubmit(body: MissedTradeIn) {
    if (editing && id) {
      update.mutate({ id, body }, { onSuccess: () => navigate(BACK) });
    } else {
      create.mutate(body, { onSuccess: () => navigate(BACK) });
    }
  }

  const back = (
    <Button variant="ghost" size="sm" asChild className="-ml-2 w-fit">
      <Link to={BACK}>
        <ArrowLeft className="mr-1.5 h-4 w-4" /> Journal
      </Link>
    </Button>
  );

  if (editing && missQuery.isLoading) {
    return (
      <div className="mx-auto max-w-3xl space-y-6">
        {back}
        <Skeleton className="h-96 w-full" />
      </div>
    );
  }

  if (editing && missQuery.isError) {
    return (
      <div className="mx-auto max-w-3xl space-y-6">
        {back}
        <Card>
          <CardContent className="py-10 text-center text-muted-foreground">
            Missed trade not found.
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      {back}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">{editing ? 'Edit missed trade' : 'Log a missed trade'}</h1>
          <p className="text-sm text-muted-foreground">
            Never taken — so it never touches expectancy or the Gate.
          </p>
        </div>
        {editing &&
          (confirmDelete ? (
            <div className="flex items-center gap-2 text-sm">
              <span className="text-muted-foreground">Delete this record?</span>
              <Button
                variant="destructive"
                size="sm"
                onClick={() => id && del.mutate(id, { onSuccess: () => navigate(BACK) })}
                disabled={del.isPending}
              >
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
          ))}
      </div>

      <MissedTradeForm
        defaults={editing ? missQuery.data : undefined}
        onSubmit={handleSubmit}
        isSaving={saving}
        saveError={saveError}
        submitLabel={editing ? 'Save changes' : 'Log the miss'}
      />

      {/* `missed_trade_screenshots` was deliberately OMITTED from Alembic 0008 —
          it is the same primitive as drill evidence, and half-building it would
          have pre-committed the shape. Phase E2's one polymorphic evidence layer
          closes it here, with no child table of its own. */}
      {editing && id && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Screenshots</CardTitle>
          </CardHeader>
          <CardContent>
            <EvidenceCapture
              subject={{ subject_type: 'missed_trade', missed_trade_id: id }}
              label="The setup you didn't take"
              hint="The chart at the moment you stood down, and what price did after."
              showRepsClaimed={false}
            />
          </CardContent>
        </Card>
      )}
    </div>
  );
}
