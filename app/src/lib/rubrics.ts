import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, apiErrorDetail } from '@/lib/api';
import { evidenceKeys } from '@/lib/evidence';
import type { EvidenceAsset, EvidenceGrade, EvidenceSubjectRef, Rubric, SelfCheckFinding } from '@/types/api';

// ============================================================
// Rubric layer (Phase E3) — the drill's own bar + the self-check against it.
//
// Rubrics are SEED CONTENT projected from the wiki, so there is no create/update
// mutation here: the only write is the self-check, which appends a grade to an
// evidence asset.
//
// Unlike an evidence write, a self-check MOVES NO REPS — it cannot, by design
// (see routers/evidence.py::create_self_check). So it invalidates only the
// evidence subtree, NOT `learningKeys` / `plannerKeys`: nothing in the progress
// grid, the stage bars or the planner reads a grade. Over-invalidating would
// imply a coupling that deliberately does not exist.
// ============================================================

export const rubricKeys = {
  all: ['rubrics'] as const,
  /** ONE key for the whole catalog — see `useRubricCatalog`. */
  catalog: () => [...rubricKeys.all, 'catalog'] as const,
};

/**
 * The WHOLE rubric catalog, fetched once per session.
 *
 * Deliberately not one query per subject. `/drills` mounts an `EvidenceCapture`
 * for every drill — 58 of them — so a per-subject query fired 58 near-identical
 * requests on a single page load, saturating the browser's 6-connection limit and
 * queueing the user's own upload behind them. Because every caller uses the SAME
 * query key, TanStack Query dedupes all of them into ONE request.
 *
 * The whole catalog is small (44 rubrics / 104 items) and is SEED CONTENT that
 * only changes on a re-seed, so caching it wholesale is strictly better than
 * slicing it server-side. The `drill_ref` / `concept_id` filters on
 * `GET /api/rubrics` remain available for callers that want one.
 */
export function useRubricCatalog() {
  return useQuery({
    queryKey: rubricKeys.catalog(),
    queryFn: () => api.get('api/rubrics').json<Rubric[]>(),
    staleTime: 10 * 60 * 1000,
    gcTime: 30 * 60 * 1000,
  });
}

/** The bar(s) that apply to a capture subject, resolved from the cached catalog.
 *
 * A drill resolves to exactly one bar. A CONCEPT resolves to the union of the
 * bars of the drills that advance it (`concepts.drill_refs`, which `ProgressRow`
 * already carries) — 10 of the 74 seeded concepts have 2–3. Journal and
 * missed-trade evidence has no bar, so this returns `[]` and nothing renders.
 */
export function useRubrics(subject?: EvidenceSubjectRef, drillRefs?: string[] | null) {
  const { data } = useRubricCatalog();
  const all = data ?? [];
  if (subject?.drill_ref) return all.filter((r) => r.drill_ref === subject.drill_ref);
  if (subject?.concept_id && drillRefs?.length) {
    const wanted = new Set(drillRefs);
    return all.filter((r) => wanted.has(r.drill_ref));
  }
  return [];
}

export interface SelfCheckVars {
  evidenceId: string;
  rubricSlug: string;
  checkedItemKeys: string[];
}

export function useSelfCheck() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ evidenceId, rubricSlug, checkedItemKeys }: SelfCheckVars) => {
      try {
        return await api
          .post(`api/evidence/${evidenceId}/self-check`, {
            json: { rubric_slug: rubricSlug, checked_item_keys: checkedItemKeys },
          })
          .json<EvidenceAsset>();
      } catch (e) {
        const detail = await apiErrorDetail(e);
        throw new Error(
          typeof detail === 'string' ? detail : detail ? JSON.stringify(detail) : 'Self-check failed'
        );
      }
    },
    // A grade write must refresh whatever displays grading state — and only that.
    onSuccess: () => qc.invalidateQueries({ queryKey: evidenceKeys.all }),
  });
}

// ============================================================
// Grading-state helpers
// ============================================================

export const RUBRIC_VARIANT_LABELS: Record<string, string> = {
  hand: 'Hand-marked',
  tool: 'Tool-assisted',
  either: 'Either',
};

/** The most recent `self_check` grade on an asset, or null if never checked.
 * `grades` arrives ordered `graded_at DESC`, and a re-check APPENDS a row rather
 * than mutating one, so the first match is the current answer. */
export function latestSelfCheck(asset: EvidenceAsset): EvidenceGrade | null {
  return asset.grades.find((g) => g.grader === 'self_check') ?? null;
}

export function selfCheckFindings(grade: EvidenceGrade | null): SelfCheckFinding[] {
  return Array.isArray(grade?.findings) ? (grade.findings as SelfCheckFinding[]) : [];
}

/** Which item keys were ticked in the asset's current self-check. */
export function checkedKeys(asset: EvidenceAsset): Set<string> {
  return new Set(
    selfCheckFindings(latestSelfCheck(asset))
      .filter((f) => f.checked)
      .map((f) => f.item_key)
  );
}

/**
 * The honest backlog: captures whose bar has NOT been checked yet.
 *
 * An unchecked rep still COUNTS — a self-check can never un-count one, because
 * `reps` feeds the stage bars and the Gate and progress must stay monotonic. So
 * "not yet checked" is surfaced as work owed, never deducted from a total.
 */
export function ungradedCount(assets: EvidenceAsset[]): number {
  return assets.filter((a) => latestSelfCheck(a) === null).length;
}
