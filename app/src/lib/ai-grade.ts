import type { EvidenceAsset, EvidenceGrade } from '@/types/api';

// ============================================================
// AI vision — tier 3, the ADVISORY SECOND READER (Phase E4).
//
// Read concepts/architecture/learning-enforcement.md §2 tier 3 before changing
// anything here. This tier NEVER blocks and NEVER retracts: nothing in this file
// may feed a rep count, a stage bar, a ladder stage or the Gate. It is
// INFORMATIONAL FEEDBACK (§6, on Deci/Koestner/Ryan 1999) — the specific
// per-item finding IS the reward, which is also why it is delivered in seconds
// rather than through the Batch API.
//
// Everything the reader may say is a closed vocabulary, mirrored below. The
// backend's `VERDICT_SCHEMA` has no free-text and no numeric field anywhere, so
// there is no value here that could carry a price, a level or a count — and this
// module must not invent one either.
// ============================================================

/** Per rubric item: is the work VISIBLY EVIDENCED? Never whether it is CORRECT. */
export type ItemEvidence = 'clearly_present' | 'possibly_present' | 'not_visible';

export interface AiItemFinding {
  item_key: string;
  visible_evidence: ItemEvidence;
  /** Carried alongside the key so a re-seed of `rubric_items` cannot orphan it. */
  text: string;
}

export interface AiFindings {
  subject_matter?: string;
  annotation_density?: string;
  observations?: string[];
  items?: AiItemFinding[];
}

/** What the reader could observe, as a closed set. Each is a coarse
 * presence/structure question — the band vision models are reliable in. */
export const OBSERVATION_LABELS: Record<string, string> = {
  no_chart_detected: 'No chart detected',
  no_annotations_visible: 'No annotations visible',
  drawing_tools_visible: 'Drawing tools visible',
  text_labels_visible: 'Text labels visible',
  multiple_timeframes_shown: 'More than one timeframe shown',
  single_timeframe_only: 'Single timeframe only',
  price_axis_not_legible: 'Price axis not legible',
  time_axis_not_legible: 'Time axis not legible',
  image_low_resolution: 'Low resolution',
  image_appears_cropped: 'Appears cropped',
  chart_mostly_obscured_by_markings: 'Chart mostly obscured by markings',
};

export const SUBJECT_MATTER_LABELS: Record<string, string> = {
  annotated_price_chart: 'an annotated price chart',
  plain_price_chart: 'a plain price chart',
  written_document: 'a written document',
  table_or_computation: 'a table or computation',
  other: 'something else',
  unclear: 'unclear',
};

export const ITEM_EVIDENCE_LABELS: Record<ItemEvidence, string> = {
  clearly_present: 'Could see it',
  possibly_present: 'Not sure',
  not_visible: "Couldn't see it",
};

/** The most recent `ai_vision` grade, or null if none was ever queued.
 * `grades` arrives ordered `graded_at DESC` and a re-grade APPENDS a row, so the
 * first match is the current answer — same contract as `latestSelfCheck`. */
export function latestAiGrade(asset: EvidenceAsset): EvidenceGrade | null {
  return asset.grades.find((g) => g.grader === 'ai_vision') ?? null;
}

/**
 * The verdict, when there is one.
 *
 * `findings` is a UNION on the wire: an object on a completed read, but a LIST
 * (`[{error: …}]`) on an ungraded one, and null while pending. Narrowing on
 * "is a non-array object" is what keeps an error row from rendering as an empty
 * verdict panel.
 */
export function aiFindings(grade: EvidenceGrade | null): AiFindings | null {
  const f = grade?.findings;
  if (!f || typeof f !== 'object' || Array.isArray(f)) return null;
  return f as AiFindings;
}

/** Why a read produced nothing, when the backend recorded a reason. */
export function aiErrorReason(grade: EvidenceGrade | null): string | null {
  const f = grade?.findings;
  if (!Array.isArray(f)) return null;
  const first = f[0];
  if (first && typeof first === 'object' && 'error' in first) {
    return String((first as { error: unknown }).error);
  }
  return null;
}

export function aiItems(grade: EvidenceGrade | null): AiItemFinding[] {
  return aiFindings(grade)?.items ?? [];
}

/** Is any capture still waiting on its second reader? Drives the poll below. */
export function hasPendingAiGrade(assets: EvidenceAsset[] | undefined): boolean {
  return (assets ?? []).some((a) => latestAiGrade(a)?.state === 'pending');
}

// ============================================================
// Disagreement — the genuinely useful signal
// ============================================================

/**
 * Where the reader and the trader's own check DISAGREE.
 *
 * This is the point of the tier. Agreement tells you nothing you did not already
 * believe; a divergence is worth a second look — in EITHER direction, and
 * neither direction is a verdict:
 *
 *  · `unseen`  — you ticked it, the reader could not see it. Often the capture
 *                simply does not show it (one image rarely shows everything a
 *                drill asks for), which is worth knowing about your EVIDENCE
 *                rather than about your work.
 *  · `unclaimed` — the reader saw it clearly and you did not tick it. Usually you
 *                being stricter with yourself than the reader is, which is the
 *                honest direction to err in.
 *
 * `possibly_present` is deliberately never a disagreement: it is the reader
 * hedging, and a hedge is not evidence of anything.
 */
export type DisagreementKind = 'unseen' | 'unclaimed';

export interface Disagreement {
  item_key: string;
  text: string;
  kind: DisagreementKind;
}

export function aiDisagreements(
  grade: EvidenceGrade | null,
  checked: Set<string>,
  /** Null when the trader has not checked yet — then there is nothing to
   * disagree WITH, and showing "disagreements" would be inventing a conflict. */
  hasSelfCheck: boolean
): Disagreement[] {
  if (!hasSelfCheck) return [];
  const out: Disagreement[] = [];
  for (const item of aiItems(grade)) {
    const ticked = checked.has(item.item_key);
    if (ticked && item.visible_evidence === 'not_visible') {
      out.push({ item_key: item.item_key, text: item.text, kind: 'unseen' });
    } else if (!ticked && item.visible_evidence === 'clearly_present') {
      out.push({ item_key: item.item_key, text: item.text, kind: 'unclaimed' });
    }
  }
  return out;
}
