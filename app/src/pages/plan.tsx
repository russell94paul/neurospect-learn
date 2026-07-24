import { Link } from 'react-router-dom';
import { Settings } from 'lucide-react';
import { usePreferences } from '@/lib/planner';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { StudyCalendar } from '@/components/planner/study-calendar';

/** /plan — the study calendar (past frozen, today, future projected) + regenerate. */
export function PlanPage() {
  const prefsQuery = usePreferences();
  const configured = prefsQuery.data?.is_configured ?? false;

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Plan</h1>
          <p className="text-muted-foreground">
            Past days are frozen; future days are the projection at your current pace.
          </p>
        </div>
        <Button variant="outline" size="sm" asChild>
          <Link to="/plan/setup">
            <Settings className="mr-1.5 h-4 w-4" /> Availability
          </Link>
        </Button>
      </div>

      {!prefsQuery.isLoading && !configured ? (
        <Card>
          <CardContent className="space-y-3 py-8 text-center">
            <p className="text-muted-foreground">
              Set your availability first — the calendar is generated from your weekly budget.
            </p>
            <Button asChild>
              <Link to="/plan/setup">Set your availability</Link>
            </Button>
          </CardContent>
        </Card>
      ) : (
        <StudyCalendar />
      )}
    </div>
  );
}
