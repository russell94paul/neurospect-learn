import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { learningKeys } from '@/lib/learning';
import type {
  PlanItem,
  PlanItemPatch,
  PlanRange,
  PreferencesIn,
  PreferencesOut,
  TodayPlan,
} from '@/types/api';

// ============================================================
// TanStack Query keys — hierarchical under ['planner'], mirroring the
// learningKeys / contentKeys convention.
// ============================================================

export const plannerKeys = {
  all: ['planner'] as const,
  preferences: () => [...plannerKeys.all, 'preferences'] as const,
  today: () => [...plannerKeys.all, 'today'] as const,
  range: (from: string, to: string) => [...plannerKeys.all, 'range', from, to] as const,
};

// ============================================================
// Queries
// ============================================================

/** The current user's active study preferences (or server defaults with
 * `is_configured=false` when unset). */
export function usePreferences() {
  return useQuery({
    queryKey: plannerKeys.preferences(),
    queryFn: () => api.get('api/preferences').json<PreferencesOut>(),
  });
}

/** Today's prescriptive plan — materialized server-side, idempotent. */
export function usePlanToday() {
  return useQuery({
    queryKey: plannerKeys.today(),
    queryFn: () => api.get('api/plan/today').json<TodayPlan>(),
  });
}

/** A date range for the calendar — past/today frozen, future computed/projected. */
export function usePlanRange(from: string, to: string) {
  return useQuery({
    queryKey: plannerKeys.range(from, to),
    queryFn: () => api.get('api/plan', { searchParams: { from, to } }).json<PlanRange>(),
    enabled: !!from && !!to,
  });
}

// ============================================================
// Mutations — a mark feeds concept_progress/drill_progress, so it must also
// invalidate the learning subtrees (progress / stages / tracks / drills) so
// /path and /drills reflect the fed reps. Prefs/regenerate recompute the plan.
// ============================================================

/** Upsert the active preferences (PUT). New prefs recompute the whole plan. */
export function useUpdatePreferences() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: PreferencesIn) =>
      api.put('api/preferences', { json: body }).json<PreferencesOut>(),
    onSuccess: (data) => {
      qc.setQueryData(plannerKeys.preferences(), data);
      qc.invalidateQueries({ queryKey: plannerKeys.all });
    },
  });
}

/** Mark a plan item done/partial/skipped. Feeds progress; never advances the
 * ladder (the gate stays owned by /api/progress). */
export function useUpdatePlanItem() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: PlanItemPatch }) =>
      api.patch(`api/plan/items/${id}`, { json: body }).json<PlanItem>(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: plannerKeys.all });
      qc.invalidateQueries({ queryKey: learningKeys.all });
    },
  });
}

/** Regenerate — bumps plan_version and recomputes; frozen done/partial/skipped
 * items are kept as the accountability record. */
export function useRegenerate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post('api/plan/regenerate').json<TodayPlan>(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: plannerKeys.all });
    },
  });
}

// ============================================================
// Display helpers for the plan_activity + status scales.
// ============================================================

export const ACTIVITY_LABELS: Record<string, string> = {
  learn: 'Read',
  drill: 'Drill',
  review: 'Review',
  observe: 'Observe',
  habit: 'Habit',
  backtest: 'Backtest',
};

export const WEEKDAYS: { key: keyof PreferencesIn; label: string }[] = [
  { key: 'mon_minutes', label: 'Mon' },
  { key: 'tue_minutes', label: 'Tue' },
  { key: 'wed_minutes', label: 'Wed' },
  { key: 'thu_minutes', label: 'Thu' },
  { key: 'fri_minutes', label: 'Fri' },
  { key: 'sat_minutes', label: 'Sat' },
  { key: 'sun_minutes', label: 'Sun' },
];
