import { Link } from 'react-router-dom';
import { format, parseISO } from 'date-fns';
import { CalendarDays, Settings } from 'lucide-react';
import { usePlanToday, usePreferences } from '@/lib/planner';
import { TRACK_LABELS } from '@/lib/learning';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { TodayList } from '@/components/planner/today-list';
import { StreakBadge } from '@/components/planner/streak-badge';
import { AdherenceMeter } from '@/components/planner/adherence-meter';
import { PaceProjection } from '@/components/planner/pace-projection';

/** /today — the prescriptive daily view (the platform's headline differentiator). */
export function TodayPage() {
  const prefsQuery = usePreferences();
  const todayQuery = usePlanToday();

  const configured = prefsQuery.data?.is_configured ?? false;
  const today = todayQuery.data;

  const heading = (
    <div className="flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl font-bold">Today</h1>
        <p className="flex items-center gap-1.5 text-muted-foreground">
          <CalendarDays className="h-4 w-4" />
          {today ? format(parseISO(today.date), 'EEEE, MMM d') : format(new Date(), 'EEEE, MMM d')}
          {today && (
            <span className="rounded bg-primary/10 px-1.5 py-0.5 text-xs font-medium text-primary">
              {TRACK_LABELS[today.active_track] ?? today.active_track}
            </span>
          )}
        </p>
      </div>
      <Button variant="outline" size="sm" asChild>
        <Link to="/plan/setup">
          <Settings className="mr-1.5 h-4 w-4" /> Availability
        </Link>
      </Button>
    </div>
  );

  if (prefsQuery.isLoading || todayQuery.isLoading) {
    return (
      <div className="mx-auto max-w-3xl space-y-6">
        {heading}
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  if (!configured) {
    return (
      <div className="mx-auto max-w-3xl space-y-6">
        {heading}
        <Card>
          <CardContent className="space-y-3 py-8 text-center">
            <p className="text-muted-foreground">
              Set your weekly availability and the planner will tell you exactly what to study each
              day — gated by your progress, never a menu.
            </p>
            <Button asChild>
              <Link to="/plan/setup">Set your availability</Link>
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      {heading}

      {today && (
        <>
          <div className="flex flex-wrap items-center gap-3">
            <StreakBadge streak={today.adherence.current_streak} />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <AdherenceMeter adherence={today.adherence} />
            <PaceProjection pace={today.pace} />
          </div>
          <div className="space-y-3">
            <h2 className="text-sm font-semibold text-muted-foreground">
              Do these, in order
            </h2>
            <TodayList items={today.items} />
          </div>
        </>
      )}

      {todayQuery.isError && (
        <Card>
          <CardContent className="py-8 text-center text-muted-foreground">
            Could not load today's plan.
          </CardContent>
        </Card>
      )}
    </div>
  );
}
