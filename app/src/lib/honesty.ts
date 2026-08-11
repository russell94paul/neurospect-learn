import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, apiErrorDetail } from '@/lib/api';
import type { HonestyStrip, RestDay } from '@/types/api';

// ============================================================
// Honesty signals + declared rest days (Phase E6).
//
// Read concepts/architecture/learning-enforcement.md §5 and §6 before changing
// anything here. Three rules govern this module:
//
// 1. **The strip is READ-ONLY, and there must be no mutation for it.** Nothing to
//    dismiss, acknowledge or clear — a signal a user can switch off is not a record
//    of anything. It is also served from its own endpoint rather than as a field on
//    `GateResponse`, so the gate's verdict has no honesty value in scope to read.
//    That is what makes "these gate nothing" structural rather than a promise.
//
// 2. **There is no update and no delete mutation for a rest day**, exactly as for a
//    prediction (E5). A rest day that can be moved could be slid onto a day you
//    later turn out to have missed; the backend makes it impossible (Alembic
//    `0012`: a trigger, and no `is_deleted` column) and this module offers no such
//    call so the UI cannot imply one exists.
//
// 3. **Nothing here is a score.** §6 (Deci, Koestner & Ryan 1999) forbids XP,
//    badges and points, and a signal with a target is a point. `count` is never
//    rendered as progress, and `NOT MEASURED` is never rendered as a zero.
// ============================================================

export const honestyKeys = {
  all: ['honesty'] as const,
  strip: () => [...honestyKeys.all, 'strip'] as const,
  restDays: () => [...honestyKeys.all, 'rest-days'] as const,
};

/** The five §5 signals, recomputed server-side on every read and stored nowhere. */
export function useHonesty() {
  return useQuery({
    queryKey: honestyKeys.strip(),
    queryFn: () => api.get('api/gate/honesty').json<HonestyStrip>(),
  });
}

export function useRestDays() {
  return useQuery({
    queryKey: honestyKeys.restDays(),
    queryFn: () => api.get('api/rest-days').json<RestDay[]>(),
  });
}

export interface DeclareRestDayVars {
  rest_date: string;
  reason?: string | null;
}

/** Book a day off, ahead of time.
 *
 * `declared_at` is deliberately absent — the server stamps it, and a date already
 * past is refused with a message that says why. That refusal is the mechanic, not
 * an error to swallow: a day off booked after you missed a day is a retroactive
 * streak freeze, which §6 rejects because it lets the number survive the behaviour
 * it is supposed to measure. So the detail is surfaced verbatim. */
export function useDeclareRestDay() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (vars: DeclareRestDayVars) => {
      try {
        return await api.post('api/rest-days', { json: vars }).json<RestDay>();
      } catch (e) {
        const detail = await apiErrorDetail(e);
        throw new Error(
          typeof detail === 'string'
            ? detail
            : detail
              ? JSON.stringify(detail)
              : 'Could not declare that rest day'
        );
      }
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: honestyKeys.all });
      // The evidence-backed streak reads rest days, so Today must refresh.
      void qc.invalidateQueries({ queryKey: ['planner'] });
    },
  });
}

// ============================================================
// Presentation helpers
// ============================================================

/** The earliest date a rest day may be declared for: tomorrow is always safe, and
 * today is accepted too (the trigger blocks only the past). Returned as the
 * `min` for a date input so the impossible case is not offered in the first place
 * — the refusal still exists beneath it, but friction on the honest path is a
 * north-star failure in its own right. */
export function earliestRestDate(now = new Date()): string {
  return now.toISOString().slice(0, 10);
}

/**
 * What a signal found, as a short phrase — or `null` when nothing was measured.
 *
 * NEVER returns "0" for an unmeasured signal. The caller must render the absence
 * instead: the distinction between "clean" and "not measured" is the only reason
 * this strip is worth reading, and collapsing it would turn a measurement gap into
 * a claim about the user.
 */
export function signalCount(signal: { status: string; count: number | null }): number | null {
  return signal.status === 'measured' ? (signal.count ?? 0) : null;
}
