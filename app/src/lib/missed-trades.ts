import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import type {
  HypotheticalOutcome,
  MissedFilterState,
  MissedTrade,
  MissedTradeIn,
  MissedTradeUpdate,
  MissType,
  OpportunityCostResponse,
} from '@/types/api';

// ============================================================
// Missed / canceled trade log (Phase 6b) — the trades you did NOT take.
//
// Deliberately its OWN query subtree, mirroring lib/journal.ts. A write here
// invalidates the missed log + its opportunity-cost summary and NOTHING else:
// missed trades never enter expectancy or the gate, so `analyticsKeys.all` is
// intentionally NOT invalidated (that would imply a dependency that must not
// exist).
// ============================================================

export const missedKeys = {
  all: ['missed-trades'] as const,
  list: (filters?: MissedFilterState) => [...missedKeys.all, 'list', filters ?? {}] as const,
  detail: (id: string) => [...missedKeys.all, 'detail', id] as const,
  summary: () => [...missedKeys.all, 'summary'] as const,
};

function toSearchParams(filters?: MissedFilterState): Record<string, string> | undefined {
  if (!filters) return undefined;
  const sp: Record<string, string> = {};
  if (filters.miss_type) sp.miss_type = filters.miss_type;
  if (filters.entry_model) sp.entry_model = filters.entry_model;
  if (filters.hypothetical_outcome) sp.hypothetical_outcome = filters.hypothetical_outcome;
  if (filters.instrument) sp.instrument = filters.instrument;
  return Object.keys(sp).length ? sp : undefined;
}

// ============================================================
// Queries
// ============================================================

export function useMissedTrades(filters?: MissedFilterState) {
  const sp = toSearchParams(filters);
  return useQuery({
    queryKey: missedKeys.list(filters),
    queryFn: () =>
      api.get('api/missed-trades', sp ? { searchParams: sp } : undefined).json<MissedTrade[]>(),
  });
}

export function useMissedTrade(id: string | undefined) {
  return useQuery({
    queryKey: missedKeys.detail(id ?? ''),
    queryFn: () => api.get(`api/missed-trades/${id}`).json<MissedTrade>(),
    enabled: !!id,
  });
}

/** "How much is hesitation costing you?" — in R. */
export function useOpportunityCost() {
  return useQuery({
    queryKey: missedKeys.summary(),
    queryFn: () => api.get('api/analytics/missed-summary').json<OpportunityCostResponse>(),
  });
}

// ============================================================
// Mutations
// ============================================================

function invalidateMissed(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: missedKeys.all });
}

export function useCreateMissedTrade() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: MissedTradeIn) =>
      api.post('api/missed-trades', { json: body }).json<MissedTrade>(),
    onSuccess: () => invalidateMissed(qc),
  });
}

export function useUpdateMissedTrade() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: MissedTradeUpdate }) =>
      api.patch(`api/missed-trades/${id}`, { json: body }).json<MissedTrade>(),
    onSuccess: (data) => {
      qc.setQueryData(missedKeys.detail(data.id), data);
      invalidateMissed(qc);
    },
  });
}

export function useDeleteMissedTrade() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete(`api/missed-trades/${id}`).then(() => id),
    onSuccess: () => invalidateMissed(qc),
  });
}

// ============================================================
// Display labels (mirror app/models/enums.py — labels only)
// ============================================================

export const MISS_TYPE_LABELS: Record<MissType, string> = {
  almost_took: 'Almost took it',
  hesitated: 'Hesitated at the trigger',
  canceled: 'Canceled a working order',
};

export const MISS_TYPES = Object.keys(MISS_TYPE_LABELS) as MissType[];

export const HYPOTHETICAL_OUTCOME_LABELS: Record<HypotheticalOutcome, string> = {
  would_win: 'Would have won',
  would_lose: 'Would have lost',
  would_breakeven: 'Would have broken even',
  unknown: 'Unresolved',
};

/** The hesitation vocabulary from concepts/architecture/trade-schema §Missed
 * Trades — suggestions for the tag input, never an enum (tags stay freeform). */
export const HESITATION_TAG_SUGGESTIONS = [
  'fear_of_loss',
  'unclear_bias',
  'distracted',
  'size_fear',
  'rules_freeze',
  'left_desk',
  'pulled_on_spike',
];
