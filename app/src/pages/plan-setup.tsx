import { Link, useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { usePreferences, useUpdatePreferences } from '@/lib/planner';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { AvailabilityForm } from '@/components/planner/availability-form';
import type { PreferencesIn } from '@/types/api';

/** /plan/setup — availability & preferences form. On save, recomputes the plan
 * and returns to Today. */
export function PlanSetupPage() {
  const prefsQuery = usePreferences();
  const update = useUpdatePreferences();
  const navigate = useNavigate();

  function save(body: PreferencesIn) {
    update.mutate(body, { onSuccess: () => navigate('/today') });
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <Button variant="ghost" size="sm" asChild>
        <Link to="/today">
          <ArrowLeft className="mr-1 h-4 w-4" /> Today
        </Link>
      </Button>

      <div>
        <h1 className="text-2xl font-bold">Availability &amp; preferences</h1>
        <p className="text-muted-foreground">
          The planner turns your weekly time budget into a concrete, gated daily routine.
        </p>
      </div>

      {prefsQuery.isLoading ? (
        <Skeleton className="h-96 w-full" />
      ) : (
        <AvailabilityForm
          defaults={prefsQuery.data}
          onSaved={save}
          isSaving={update.isPending}
          saveError={update.isError ? (update.error as Error).message : null}
        />
      )}
    </div>
  );
}
