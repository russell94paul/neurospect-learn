import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, apiErrorMessage } from '@/lib/api';
import { useMemo } from 'react';
import type {
  ConceptOut,
  DrillOut,
  DrillPatch,
  ProgressPatch,
  ProgressRow,
  StageOut,
  TrackOut,
} from '@/types/api';

// ============================================================
// TanStack Query keys — hierarchical under ['learning'], mirroring the
// contentKeys convention in lib/content.ts.
// ============================================================

export const learningKeys = {
  all: ['learning'] as const,
  concepts: (track?: string, stage?: string) =>
    [...learningKeys.all, 'concepts', track ?? 'all', stage ?? 'all'] as const,
  progress: (track?: string) => [...learningKeys.all, 'progress', track ?? 'all'] as const,
  tracks: () => [...learningKeys.all, 'tracks'] as const,
  stages: (track?: string) => [...learningKeys.all, 'stages', track ?? 'unified'] as const,
  drills: (track?: string, stage?: string) =>
    [...learningKeys.all, 'drills', track ?? 'all', stage ?? 'all'] as const,
};

/** The three graded tracks (5e-1b) in display order + their labels. */
export const TRACKS: { key: string; label: string }[] = [
  { key: 'aura', label: 'Aura' },
  { key: 'ict_course', label: 'AXL' },
  { key: 'unified', label: 'Unified' },
];

export const TRACK_LABELS: Record<string, string> = {
  aura: 'Aura',
  ict_course: 'AXL / MrWitness',
  unified: 'Unified',
};

// ============================================================
// Queries
// ============================================================

export function useConcepts(track?: string, stage?: string) {
  return useQuery({
    queryKey: learningKeys.concepts(track, stage),
    queryFn: () => {
      const searchParams: Record<string, string> = {};
      if (track) searchParams.track = track;
      if (stage) searchParams.stage = stage;
      return api
        .get('api/concepts', Object.keys(searchParams).length ? { searchParams } : undefined)
        .json<ConceptOut[]>();
    },
    staleTime: 5 * 60_000, // seed data
  });
}

/** A slug → concept index across ALL tracks, for resolving cross_refs
 * ("Also taught in …") to their track + stage. Cached seed data. */
export function useConceptIndex() {
  const q = useConcepts();
  const index = useMemo(() => {
    const m = new Map<string, ConceptOut>();
    for (const c of q.data ?? []) m.set(c.slug, c);
    return m;
  }, [q.data]);
  return index;
}

export function useProgress(track?: string) {
  return useQuery({
    queryKey: learningKeys.progress(track),
    queryFn: () =>
      api
        .get('api/progress', track ? { searchParams: { track } } : undefined)
        .json<ProgressRow[]>(),
  });
}

/** The three graded tracks + their stage rollups (the /path switcher/spine). */
export function useTracks() {
  return useQuery({
    queryKey: learningKeys.tracks(),
    queryFn: () => api.get('api/tracks').json<TrackOut[]>(),
  });
}

export function useStages(track = 'unified') {
  return useQuery({
    queryKey: learningKeys.stages(track),
    queryFn: () => api.get('api/stages', { searchParams: { track } }).json<StageOut[]>(),
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
      // A progress write feeds the derived stages + track rollups; invalidate
      // the whole progress/stages/tracks subtrees (track-scoped keys included).
      qc.invalidateQueries({ queryKey: [...learningKeys.all, 'progress'] });
      qc.invalidateQueries({ queryKey: [...learningKeys.all, 'stages'] });
      qc.invalidateQueries({ queryKey: learningKeys.tracks() });
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
