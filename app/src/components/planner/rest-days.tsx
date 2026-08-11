import { useState } from 'react';
import { CalendarOff, Lock } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { earliestRestDate, useDeclareRestDay, useRestDays } from '@/lib/honesty';

/**
 * DECLARED REST DAYS — a day off you booked before it happened.
 *
 * concepts/architecture/learning-enforcement.md §6 asks for rest days "declared
 * *in advance*, unlike a retroactive streak freeze, which keeps the streak
 * honest." The entire mechanic is in those three words, so this surface is built
 * around one refusal and one disclosure:
 *
 * · **The past cannot be selected.** The date input's `min` is today, the API
 *   refuses an earlier date, and Alembic `0012`'s trigger refuses it again beneath
 *   that. Three layers, because a rest day that can be added after a day you
 *   missed is a streak freeze with extra steps — and §6 rejects streak freezes
 *   precisely because they let a number survive the behaviour it measures.
 * · **There is no edit and no delete**, exactly as for a committed prediction (E5).
 *   A rest day that can be moved could be slid onto a day you later turn out to
 *   have missed. The UI offers no such control because the backend has no such
 *   route and no `is_deleted` column.
 * · **When it was booked is shown.** The trigger blocks the past outright; how far
 *   ahead of that is judgement, and §5's rule for judgement-shaped things is to
 *   show them rather than gate on them. A same-day declaration reads as one.
 *
 * A rest day is NEUTRAL in the evidence-backed streak: it does not break the run
 * and does not count toward it. Booking ten of them raises nothing.
 */
export function RestDays() {
  const { data: restDays } = useRestDays();
  const declare = useDeclareRestDay();
  const [restDate, setRestDate] = useState('');
  const [reason, setReason] = useState('');

  const today = earliestRestDate();
  const upcoming = (restDays ?? []).filter((d) => d.rest_date >= today);
  const past = (restDays ?? []).filter((d) => d.rest_date < today);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!restDate) return;
    declare.mutate(
      { rest_date: restDate, reason: reason.trim() || null },
      { onSuccess: () => { setRestDate(''); setReason(''); } }
    );
  }

  return (
    <Card data-testid="rest-days">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <CalendarOff className="h-4 w-4 text-muted-foreground" />
          Rest days
        </CardTitle>
        <p className="text-xs text-muted-foreground">
          Book a day off <span className="font-medium">before it happens</span>. A declared rest day
          is neutral in your evidence-backed streak — it will not break the run, and it does not
          count toward it either. You cannot declare one for a day that has already passed: a day
          off booked after the fact would only be a way to repair the number.
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        <form onSubmit={submit} className="flex flex-wrap items-end gap-2">
          <div className="space-y-1">
            <label htmlFor="rest-date" className="text-xs text-muted-foreground">
              Date
            </label>
            <Input
              id="rest-date"
              type="date"
              /* The past is not offered in the first place. The refusal still
                 exists beneath this, but friction on the honest path is a
                 north-star failure in its own right. */
              min={today}
              value={restDate}
              onChange={(e) => setRestDate(e.target.value)}
              className="h-9 w-[170px]"
            />
          </div>
          <div className="min-w-[180px] flex-1 space-y-1">
            <label htmlFor="rest-reason" className="text-xs text-muted-foreground">
              Reason (optional)
            </label>
            <Input
              id="rest-reason"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="travelling, family, planned break…"
              className="h-9"
              maxLength={500}
            />
          </div>
          <Button type="submit" size="sm" disabled={!restDate || declare.isPending}>
            {declare.isPending ? 'Booking…' : 'Declare'}
          </Button>
        </form>

        {/* The refusal is shown VERBATIM rather than swallowed — it is the mechanic
            explaining itself, not an error to hide. */}
        {declare.isError && (
          <p className="text-xs text-destructive" data-testid="rest-day-error">
            {declare.error.message}
          </p>
        )}

        {upcoming.length > 0 && (
          <div className="space-y-1">
            <h4 className="text-xs font-semibold text-muted-foreground">Booked</h4>
            <ul className="divide-y text-sm">
              {upcoming.map((d) => (
                <li
                  key={d.id}
                  data-testid="rest-day"
                  data-rest-date={d.rest_date}
                  className="flex flex-wrap items-baseline gap-x-2 py-1.5"
                >
                  <Lock className="h-3 w-3 shrink-0 self-center text-muted-foreground" />
                  <span className="tabular-nums">{d.rest_date}</span>
                  {d.reason && <span className="text-xs text-muted-foreground">{d.reason}</span>}
                  <span className="ml-auto text-[11px] text-muted-foreground">
                    {d.days_declared_ahead > 0
                      ? `declared ${d.days_declared_ahead} day${d.days_declared_ahead === 1 ? '' : 's'} ahead`
                      : 'declared same day'}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {past.length > 0 && (
          <p className="text-xs text-muted-foreground" data-testid="rest-days-taken">
            {past.length} rest day{past.length === 1 ? '' : 's'} already taken. They stay on the
            record — a booked day off is not editable or removable, which is what makes the streak
            beside it worth reading.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
