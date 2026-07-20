import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { HTTPError } from 'ky';
import { api } from '@/lib/api';
import type {
  ConceptOut,
  DrillOut,
  DrillPatch,
  ProgressPatch,
  ProgressRow,
  StageOut,
} from '@/types/api';

// ============================================================
// TanStack Query keys — hierarchical under ['learning'], mirroring the
// contentKeys convention in lib/content.ts.
// ============================================================

export const learningKeys = {
  all: ['learning'] as const,
  concepts: (stage?: string) => [...learningKeys.all, 'concepts', stage ?? 'all'] as const,
  progress: () => [...learningKeys.all, 'progress'] as const,
  stages: () => [...learningKeys.all, 'stages'] as const,
  drills: (track?: string, stage?: string) =>
    [...learningKeys.all, 'drills', track ?? 'all', stage ?? 'all'] as const,
};

// ============================================================
// Queries
// ============================================================

export function useConcepts(stage?: string) {
  return useQuery({
    queryKey: learningKeys.concepts(stage),
    queryFn: () =>
      api
        .get('api/concepts', stage ? { searchParams: { stage } } : undefined)
        .json<ConceptOut[]>(),
    staleTime: 5 * 60_000, // seed data
  });
}

export function useProgress() {
  return useQuery({
    queryKey: learningKeys.progress(),
    queryFn: () => api.get('api/progress').json<ProgressRow[]>(),
  });
}

export function useStages() {
  return useQuery({
    queryKey: learningKeys.stages(),
    queryFn: () => api.get('api/stages').json<StageOut[]>(),
  });
}

export function useDrills(track?: string, stage?: string) {
  return useQuery({
    queryKey: learningKeys.drills(track, stage),
    queryFn: () => {
      const searchParams: Record<string, string> = {};
      if (track) searchParams.track = track;
      if (stage) searchParams.stage = stage;
      return api
        .get('api/drills', Object.keys(searchParams).length ? { searchParams } : undefined)
        .json<DrillOut[]>();
    },
  });
}

// ============================================================
// Mutations — the FIRST useMutation in this codebase (5b–5d were read-only).
// Pattern: PATCH → on success invalidate the affected query subtrees so the
// grid, the derived stages, and any drill views refetch. Progress edits feed
// the exit-bar derivation, so a progress write must also refresh stages.
// ============================================================

/** Extract a FastAPI `detail` message from a ky HTTPError (e.g. the 422 gate
 * rejection) so the UI can show why an advance was blocked. */
async function apiErrorMessage(e: unknown): Promise<string> {
  if (e instanceof HTTPError) {
    try {
      const body = (await e.response.json()) as { detail?: unknown };
      if (body?.detail) {
        return typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail);
      }
    } catch {
      /* fall through */
    }
  }
  return e instanceof Error ? e.message : 'Request failed';
}

/** Upsert one concept's progress. Throws (with the server message) on the
 * ladder-advance gate (422) — the caller surfaces `error` to the user. */
export function useUpdateProgress() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: ProgressPatch) => {
      try {
        return await api.patch('api/progress', { json: body }).json<ProgressRow>();
      } catch (e) {
        throw new Error(await apiErrorMessage(e));
      }
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: learningKeys.progress() });
      qc.invalidateQueries({ queryKey: learningKeys.stages() });
    },
  });
}

/** Upsert one drill's progress (reps / hand_done / tool_done). */
export function useUpdateDrill() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: DrillPatch) =>
      api.patch('api/drills', { json: body }).json<DrillOut>(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [...learningKeys.all, 'drills'] });
    },
  });
}

// ============================================================
// Shared display helpers for the ladder / confidence scales
// (concepts/mastery/README §ladder + §confidence — reused, not restated).
// ============================================================

export const LADDER_LABELS: Record<number, string> = {
  1: 'Learned',
  2: 'Can-mark',
  3: 'Backtested',
  4: 'Live-ready',
};

export const CONFIDENCE_LABELS: Record<number, string> = {
  1: 'no feel',
  2: 'shaky',
  3: 'usually right',
  4: 'reliable',
  5: 'automatic',
};

export const CAN_MARK = 2;

/** Does a ladder advance to Can-mark+ pass the client-side gate preview?
 * (The server is authoritative; this mirrors it to disable the control.) */
export function advanceBlocked(
  targetLadder: number,
  reps: number,
  confidence: number | null,
  repTargetCount: number | null
): string | null {
  if (targetLadder < CAN_MARK) return null;
  if (confidence == null) return 'Set a confidence rating first.';
  if (repTargetCount != null && reps < repTargetCount)
    return `Reps ${reps}/${repTargetCount} — reach the target first.`;
  return null;
}
