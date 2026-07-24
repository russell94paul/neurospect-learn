import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { analyticsKeys } from '@/lib/analytics';
import type {
  EntryModel,
  JournalEntry,
  JournalEntryIn,
  JournalEntryUpdate,
  JournalFilterState,
} from '@/types/api';

// ============================================================
// TanStack Query keys — hierarchical under ['journal'], mirroring the
// learningKeys / plannerKeys convention.
// ============================================================

export const journalKeys = {
  all: ['journal'] as const,
  list: (filters?: JournalFilterState) =>
    [...journalKeys.all, 'list', filters ?? {}] as const,
  detail: (id: string) => [...journalKeys.all, 'detail', id] as const,
};

function toSearchParams(filters?: JournalFilterState): Record<string, string> | undefined {
  if (!filters) return undefined;
  const sp: Record<string, string> = {};
  if (filters.mode) sp.mode = filters.mode;
  if (filters.entry_model) sp.entry_model = filters.entry_model;
  if (filters.instrument) sp.instrument = filters.instrument;
  return Object.keys(sp).length ? sp : undefined;
}

// ============================================================
// Queries
// ============================================================

/** This user's entries, newest first, optionally filtered by mode/model/instrument. */
export function useJournalEntries(filters?: JournalFilterState) {
  const sp = toSearchParams(filters);
  return useQuery({
    queryKey: journalKeys.list(filters),
    queryFn: () => api.get('api/journal', sp ? { searchParams: sp } : undefined).json<JournalEntry[]>(),
  });
}

export function useJournalEntry(id: string | undefined) {
  return useQuery({
    queryKey: journalKeys.detail(id ?? ''),
    queryFn: () => api.get(`api/journal/${id}`).json<JournalEntry>(),
    enabled: !!id,
  });
}

// ============================================================
// Mutations — a write changes the entries AND the derived expectancy, so every
// mutation invalidates BOTH the journal lists and the whole analytics subtree.
// ============================================================

function invalidateJournalAndAnalytics(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: journalKeys.all });
  qc.invalidateQueries({ queryKey: analyticsKeys.all });
}

export function useCreateEntry() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: JournalEntryIn) => api.post('api/journal', { json: body }).json<JournalEntry>(),
    onSuccess: () => invalidateJournalAndAnalytics(qc),
  });
}

export function useUpdateEntry() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: JournalEntryUpdate }) =>
      api.patch(`api/journal/${id}`, { json: body }).json<JournalEntry>(),
    onSuccess: (data) => {
      qc.setQueryData(journalKeys.detail(data.id), data);
      invalidateJournalAndAnalytics(qc);
    },
  });
}

export function useDeleteEntry() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete(`api/journal/${id}`).then(() => id),
    onSuccess: () => invalidateJournalAndAnalytics(qc),
  });
}

// ============================================================
// Display labels for the journal enums (mirror concepts/entry-models/** +
// concepts/mastery — labels only, the content pages are canonical).
// ============================================================

export const ENTRY_MODEL_LABELS: Record<EntryModel, string> = {
  consolidation: 'Consolidation',
  expansion_retracement: 'Expansion / Retracement',
  reversal_raid_on_stops: 'Reversal (raid on stops)',
  london: 'London',
  model_2022_ote: '2022 Model (OTE)',
  daily_bias: 'Daily Bias',
  smt_confirmation: 'SMT Confirmation',
  unified: 'Unified',
};

export const ENTRY_MODELS = Object.keys(ENTRY_MODEL_LABELS) as EntryModel[];

export const SESSION_LABELS: Record<string, string> = {
  asia: 'Asia',
  london: 'London',
  ny_am: 'NY AM',
  ny_pm: 'NY PM',
};

export const RANGE_POSITION_LABELS: Record<string, string> = {
  discount: 'Discount',
  eq: 'Equilibrium',
  premium: 'Premium',
};

export const ENTRY_PDA_LABELS: Record<string, string> = {
  fvg: 'FVG',
  ifvg: 'iFVG',
  order_block: 'Order Block',
  breaker: 'Breaker',
  rejection_block: 'Rejection Block',
  ote_block: 'OTE Block',
};

export const OUTCOME_LABELS: Record<string, string> = {
  win: 'Win',
  loss: 'Loss',
  breakeven: 'Breakeven',
};

export const GRADE_LABELS: Record<string, string> = {
  a_plus: 'A+',
  a: 'A',
  b: 'B',
  c: 'C',
};
