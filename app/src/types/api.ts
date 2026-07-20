// ============================================================
// Auth (mirrors backend app/schemas/auth.py)
// ============================================================

export interface User {
  id: string;
  discord_id: string;
  discord_username: string | null;
  discord_avatar_url: string | null;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

// ============================================================
// Content API (mirrors backend app/schemas/content.py)
// ============================================================

export interface ContentPageSummary {
  slug: string;
  title: string;
  category: string | null;
  u_stage: string | null;
  tier: string | null;
  label: string | null;
  source_path: string | null;
}

export interface ConceptBadge {
  code: string | null;
  tier: string | null;
  label: string | null;
  watch_only: boolean;
}

export interface ContentPageDetail extends ContentPageSummary {
  body: string;
  tags: string[] | null;
  wikilink_targets: string[] | null;
  badge: ConceptBadge | null;
}

// ============================================================
// Learning API (mirrors backend app/schemas/learning.py)
// ============================================================

export interface ConceptOut {
  id: string;
  slug: string;
  code: string | null;
  u_stage: string;
  title: string;
  is_core: boolean;
  tier: string | null;
  label: string | null;
  axis: string | null;
  watch_only: boolean;
  rep_target: string | null;
  rep_target_kind: string;
  rep_target_count: number | null;
  content_slug: string | null;
  drill_refs: string[] | null;
  sort_order: number;
  notes: string | null;
}

/** One concept + this user's progress (null progress = untracked). */
export interface ProgressRow {
  concept_id: string;
  slug: string;
  code: string | null;
  u_stage: string;
  title: string;
  is_core: boolean;
  watch_only: boolean;
  content_slug: string | null;
  drill_refs: string[] | null;
  rep_target: string | null;
  rep_target_kind: string;
  rep_target_count: number | null;
  sort_order: number;
  ladder_stage: number | null;
  confidence: number | null;
  reps: number;
  last_practiced: string | null;
  notes: string | null;
}

/** PATCH /api/progress body — concept_id required, rest partial. */
export interface ProgressPatch {
  concept_id: string;
  ladder_stage?: number | null;
  confidence?: number | null;
  reps?: number | null;
  last_practiced?: string | null;
  notes?: string | null;
}

export interface Requirement {
  label: string;
  met: boolean;
  attest: boolean;
  concept_slug: string | null;
  concept_code: string | null;
}

export interface StageOut {
  u_stage: string;
  title: string;
  watch_only: boolean;
  never_gate_eligible: boolean;
  locked: boolean;
  met: boolean;
  auto_met: boolean;
  attest_pending: boolean;
  total: number;
  reached: number;
  requirements: Requirement[];
}

export interface DrillOut {
  id: string;
  drill_ref: string;
  track: string;
  stage_code: string | null;
  title: string;
  advances_to: string | null;
  rep_target: string | null;
  rep_target_count: number | null;
  concept_slugs: string[] | null;
  sort_order: number;
  reps: number;
  hand_done: boolean;
  tool_done: boolean;
  last_practiced: string | null;
  notes: string | null;
}

/** PATCH /api/drills body — drill_ref required, rest partial. */
export interface DrillPatch {
  drill_ref: string;
  reps?: number | null;
  hand_done?: boolean | null;
  tool_done?: boolean | null;
  last_practiced?: string | null;
  notes?: string | null;
}
