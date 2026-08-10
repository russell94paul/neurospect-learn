import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, apiErrorDetail } from '@/lib/api';
import { learningKeys } from '@/lib/learning';
import type { Calibration, EntryModel, Prediction, PredictionBias } from '@/types/api';

// ============================================================
// Pre-commitment + calibration (Phase E5).
//
// Read concepts/architecture/learning-enforcement.md §9 and §6 before changing
// anything here. Two rules govern this whole module:
//
// 1. **There is no update and no delete mutation, and there must not be one.**
//    A call that can be edited after the reveal proves nothing, and a call that can
//    be deleted lets a ratio be inflated by dropping failures. The backend makes
//    both structurally impossible (Alembic `0011`: a freeze trigger, and no
//    `is_deleted` column); this module simply offers no such call so the UI cannot
//    imply one exists.
//
// 2. **Calibration is INFORMATIONAL FEEDBACK, never a currency** (§6, on Deci,
//    Koestner & Ryan 1999). Nothing in the app gates on it. In particular M6's exit
//    bar grades COMMITMENT, not correctness — so this module must never present the
//    accuracy as progress, a target, a streak or a thing to raise.
//
// Unlike a self-check, committing or resolving a call DOES move a stage bar (M6's
// row is derived from this ledger), so these mutations invalidate `learningKeys`.
// It moves no REP — a prediction is not evidence of markings.
// ============================================================

export const predictionKeys = {
  all: ['predictions'] as const,
  list: (drillRef?: string) => [...predictionKeys.all, 'list', drillRef ?? 'all'] as const,
  calibration: (drillRef?: string) =>
    [...predictionKeys.all, 'calibration', drillRef ?? 'all'] as const,
};

/** The 14 tape drills M6's bar names. Mirrors `stages.TAPE_STUDY_DRILLS`. */
export const TAPE_STUDY_DRILLS: readonly string[] = Array.from(
  { length: 14 },
  (_, i) => `ict-course T-${String(i + 1).padStart(2, '0')}`
);

export function isTapeStudyDrill(drillRef: string): boolean {
  return TAPE_STUDY_DRILLS.includes(drillRef);
}

export function usePredictions(drillRef?: string) {
  return useQuery({
    queryKey: predictionKeys.list(drillRef),
    queryFn: () =>
      api
        .get('api/predictions', { searchParams: drillRef ? { drill_ref: drillRef } : {} })
        .json<Prediction[]>(),
  });
}

export function useCalibration(drillRef?: string) {
  return useQuery({
    queryKey: predictionKeys.calibration(drillRef),
    queryFn: () =>
      api
        .get('api/calibration', { searchParams: drillRef ? { drill_ref: drillRef } : {} })
        .json<Calibration>(),
  });
}

export interface CommitVars {
  drill_ref: string;
  session_label: string;
  instrument?: string | null;
  bias: PredictionBias;
  dol: string;
  entry_model: EntryModel;
  target: string;
  evidence_id?: string | null;
}

/** Commit the call. `committed_at` is deliberately absent — the server stamps it,
 * and sending one is a 422 that says why. */
export function useCommitPrediction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (vars: CommitVars) => {
      try {
        return await api.post('api/predictions', { json: vars }).json<Prediction>();
      } catch (e) {
        const detail = await apiErrorDetail(e);
        throw new Error(
          typeof detail === 'string'
            ? detail
            : detail
              ? JSON.stringify(detail)
              : 'Could not commit that call'
        );
      }
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: predictionKeys.all });
      // M6's stage row is derived from this ledger, so the bar must refresh.
      void qc.invalidateQueries({ queryKey: learningKeys.all });
    },
  });
}

export interface ResolveVars {
  id: string;
  outcome_bias: PredictionBias;
  dol_hit: boolean;
  model_played_out: boolean;
  target_hit: boolean;
  resolution_notes?: string | null;
}

/** Record the reveal. Accepted exactly once — a second attempt is a 409 whose
 * message is shown verbatim, because "you already answered this" is the whole
 * point rather than an error to swallow. */
export function useResolvePrediction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, ...body }: ResolveVars) => {
      try {
        return await api.post(`api/predictions/${id}/resolve`, { json: body }).json<Prediction>();
      } catch (e) {
        const detail = await apiErrorDetail(e);
        throw new Error(
          typeof detail === 'string'
            ? detail
            : detail
              ? JSON.stringify(detail)
              : 'Could not record that outcome'
        );
      }
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: predictionKeys.all });
      void qc.invalidateQueries({ queryKey: learningKeys.all });
    },
  });
}

// ============================================================
// Labels + formatting
// ============================================================

export const BIAS_LABELS: Record<PredictionBias, string> = {
  long: 'Long',
  short: 'Short',
  // Not "unsure" — standing aside is a real call, and it is scored like one.
  neutral: 'Neutral / stand aside',
};

/**
 * A percentage, or null when nothing has resolved.
 *
 * NEVER returns "0%" for an empty record. A zero from an instrument that has seen
 * nothing is not a measurement, and rendering one would be a claim about the trader
 * that the data does not support — callers must render the absence instead.
 */
export function pct(value: number | null | undefined): string | null {
  if (value === null || value === undefined) return null;
  return `${Math.round(value * 100)}%`;
}

/** How long the call stood before the outcome was recorded. Surfaced, not judged:
 * the app cannot see a TradingView replay, so it reports the interval in its own
 * record and claims nothing more. */
export function revealGap(seconds: number | null | undefined): string | null {
  if (seconds === null || seconds === undefined) return null;
  if (seconds < 90) return `${seconds}s later`;
  const mins = Math.round(seconds / 60);
  if (mins < 90) return `${mins} min later`;
  const hours = Math.round(mins / 60);
  if (hours < 48) return `${hours}h later`;
  return `${Math.round(hours / 24)} days later`;
}
