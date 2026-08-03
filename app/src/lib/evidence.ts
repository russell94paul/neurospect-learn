import { useMemo } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, API_BASE_URL, apiErrorDetail } from '@/lib/api';
import { learningKeys } from '@/lib/learning';
import { plannerKeys } from '@/lib/planner';
import type { EvidenceAsset, EvidenceKind, EvidenceSubjectRef } from '@/types/api';

// ============================================================
// Evidence layer (Phase E2) — capture, list, remove.
//
// An evidence write MOVES REPS (`reps` is derived from this ledger), so unlike
// `missedKeys` — which deliberately invalidates nothing else — a write here must
// invalidate the whole progress/drills/stages/tracks subtree AND the planner,
// since the schedule is computed from how many reps are still owed.
// ============================================================

export const evidenceKeys = {
  all: ['evidence'] as const,
  /** ONE key for all of this user's evidence — see `useEvidenceCatalog`. */
  catalog: () => [...evidenceKeys.all, 'catalog'] as const,
  detail: (id: string) => [...evidenceKeys.all, 'detail', id] as const,
};

/** Does this asset belong to that subject? Mirrors the server-side filters. */
function matchesSubject(asset: EvidenceAsset, subject: EvidenceSubjectRef): boolean {
  if (asset.subject_type !== subject.subject_type) return false;
  if (subject.drill_ref) return asset.subject_drill_ref === subject.drill_ref;
  if (subject.concept_id) return asset.concept_id === subject.concept_id;
  if (subject.journal_entry_id) return asset.journal_entry_id === subject.journal_entry_id;
  if (subject.missed_trade_id) return asset.missed_trade_id === subject.missed_trade_id;
  return false;
}

// ============================================================
// Queries
// ============================================================

/**
 * ALL of this user's evidence, fetched once.
 *
 * `/drills` mounts an `EvidenceCapture` per drill — 58 of them — and a
 * per-subject query key meant 58 near-identical `GET /api/evidence` calls on one
 * page load. That saturated the browser's 6-connection-per-origin limit, queued
 * the user's own upload behind the pile, and reset connections at the dev server
 * under load. A single shared key dedupes every caller into ONE request.
 *
 * A user's evidence set is small and every consumer needs only its own slice, so
 * filtering client-side is strictly cheaper than slicing server-side. The
 * `subject_type` / `drill_ref` / … filters on `GET /api/evidence` are unchanged
 * and still used by tests and any single-subject caller.
 */
export function useEvidenceCatalog() {
  return useQuery({
    queryKey: evidenceKeys.catalog(),
    queryFn: () => api.get('api/evidence').json<EvidenceAsset[]>(),
  });
}

export function useEvidence(subject?: EvidenceSubjectRef) {
  const query = useEvidenceCatalog();
  const all = query.data;
  // Keyed on the subject's identity rather than the object, which callers rebuild
  // inline on every render.
  const key = subject ? JSON.stringify(subject) : '';
  const data = useMemo(
    () => (subject && all ? all.filter((a) => matchesSubject(a, subject)) : undefined),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [all, key]
  );
  return { ...query, data };
}

// ============================================================
// Mutations
// ============================================================

/** The refusal reason from the deterministic tier. A silent refusal is the
 * failure mode this workstream exists to avoid, so the UI always shows this. */
export interface EvidenceRejection {
  code: string;
  message: string;
  duplicate_of?: string | null;
  distance?: number | null;
}

async function rejectionFrom(e: unknown): Promise<Error> {
  const detail = await apiErrorDetail(e);
  if (detail && typeof detail === 'object' && 'message' in detail) {
    const rejection = detail as EvidenceRejection;
    const err = new Error(rejection.message) as Error & { rejection: EvidenceRejection };
    err.rejection = rejection;
    return err;
  }
  if (typeof detail === 'string') return new Error(detail);
  if (Array.isArray(detail)) {
    const msgs = detail
      .map((d) => (d && typeof d === 'object' && 'msg' in d ? String((d as { msg: unknown }).msg) : null))
      .filter(Boolean);
    if (msgs.length) return new Error(msgs.join(' '));
  }
  if (detail) return new Error(JSON.stringify(detail));
  return e instanceof Error ? e : new Error('Upload failed');
}

export interface UploadEvidenceVars {
  file: File;
  subject: EvidenceSubjectRef;
  kind?: EvidenceKind;
  reps_claimed?: number;
  notes?: string;
}

export function useUploadEvidence() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ file, subject, kind, reps_claimed, notes }: UploadEvidenceVars) => {
      const body = new FormData();
      body.append('file', file, file.name || 'capture.png');
      body.append('subject_type', subject.subject_type);
      if (subject.drill_ref) body.append('drill_ref', subject.drill_ref);
      if (subject.concept_id) body.append('concept_id', subject.concept_id);
      if (subject.journal_entry_id) body.append('journal_entry_id', subject.journal_entry_id);
      if (subject.missed_trade_id) body.append('missed_trade_id', subject.missed_trade_id);
      if (kind) body.append('kind', kind);
      if (reps_claimed != null) body.append('reps_claimed', String(reps_claimed));
      if (notes) body.append('notes', notes);
      try {
        // No `json:` — ky must let the browser set the multipart boundary.
        return await api.post('api/evidence', { body }).json<EvidenceAsset>();
      } catch (e) {
        throw await rejectionFrom(e);
      }
    },
    onSuccess: invalidateAfterEvidenceWrite(qc),
  });
}

export function useDeleteEvidence() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete(`api/evidence/${id}`).then(() => id),
    onSuccess: invalidateAfterEvidenceWrite(qc),
  });
}

/** Evidence is where reps come from, so a write refreshes everything that reads
 * a rep count: the progress grid, the drill catalog, the derived stage exit bars,
 * the track rollups and the planner's "what is still owed" schedule. */
function invalidateAfterEvidenceWrite(qc: ReturnType<typeof useQueryClient>) {
  return () => {
    qc.invalidateQueries({ queryKey: evidenceKeys.all });
    qc.invalidateQueries({ queryKey: learningKeys.all });
    qc.invalidateQueries({ queryKey: plannerKeys.all });
  };
}

// ============================================================
// Display helpers
// ============================================================

export const EVIDENCE_KIND_LABELS: Record<EvidenceKind, string> = {
  chart_markup: 'Marked-up chart',
  written_artifact: 'Written artifact',
  computation: 'Computation',
  prediction: 'Pre-committed call',
  tape_read: 'Tape read',
};

/**
 * The renderable `src` for an evidence asset.
 *
 * R2 returns an ABSOLUTE presigned URL; the local backend returns an
 * APP-RELATIVE signed path (`/api/evidence/file?token=…`), which a browser would
 * otherwise resolve against the SPA origin (:5173) and 404 — the thumbnail
 * rendered broken until this was added. Resolve relative URLs against the API.
 */
export function evidenceSrc(url: string): string {
  return url.startsWith('/') ? `${API_BASE_URL}${url}` : url;
}

/** Pull an image File out of a paste or drop, or null if there isn't one. */
export function imageFileFrom(data: DataTransfer | null): File | null {
  if (!data) return null;
  const direct = Array.from(data.files).find((f) => f.type.startsWith('image/'));
  if (direct) return direct;
  for (const item of Array.from(data.items ?? [])) {
    if (item.kind === 'file' && item.type.startsWith('image/')) {
      const file = item.getAsFile();
      if (file) return file;
    }
  }
  return null;
}
