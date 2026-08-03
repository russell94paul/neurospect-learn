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
  track: string;
  stage_code: string | null;
  stage_order: number | null;
  cross_refs: string[] | null;
  u_stage: string | null;
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
  track: string;
  stage_code: string | null;
  stage_order: number | null;
  cross_refs: string[] | null;
  u_stage: string | null;
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
  /** DERIVED (Phase E2) = reps_legacy + reps_evidenced. Read-only. */
  reps: number;
  /** Σ reps_claimed over this concept's live evidence — the proven part. */
  reps_evidenced: number;
  /** Claimed before the evidence layer existed (Alembic 0009 froze it). */
  reps_legacy: number;
  last_practiced: string | null;
  notes: string | null;
}

/** PATCH /api/progress body — concept_id required, rest partial.
 * `reps` is deliberately absent: since Phase E2 a rep counts only when there is
 * evidence of the work, so the count comes from POST /api/evidence and the API
 * rejects a `reps` key with a 422. */
export interface ProgressPatch {
  concept_id: string;
  ladder_stage?: number | null;
  confidence?: number | null;
  last_practiced?: string | null;
  notes?: string | null;
}

/** One exit-bar row. Phase 6a wiring fields: `derived` = objectively EARNED from
 * logged evidence (journal expectancy / the gate verdict); `attest` + `attest_item`
 * = REFLECTS a /gate attestation (never a second checkbox here); `detail` = the
 * evidence in numbers; `link` = where the row is satisfied. */
export interface Requirement {
  label: string;
  met: boolean;
  attest: boolean;
  concept_slug: string | null;
  concept_code: string | null;
  derived: boolean;
  detail: string | null;
  attest_item: string | null;
  link: string | null;
}

export interface StageRollup {
  track: string;
  stage_code: string;
  stage_order: number;
  title: string;
  summary: string | null;
  gate_text: string | null;
  watch_only: boolean;
  never_gate_eligible: boolean;
  locked: boolean;
  met: boolean;
  auto_met: boolean;
  attest_pending: boolean;
  total: number;
  reached: number;
}

export interface StageOut extends StageRollup {
  requirements: Requirement[];
}

export interface TrackOut {
  track: string;
  label: string;
  stages: StageRollup[];
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
  /** DERIVED (Phase E2) = reps_legacy + reps_evidenced. Read-only. */
  reps: number;
  reps_evidenced: number;
  reps_legacy: number;
  hand_done: boolean;
  tool_done: boolean;
  last_practiced: string | null;
  notes: string | null;
}

/** PATCH /api/drills body — drill_ref required, rest partial. `reps` is absent
 * for the same reason as on ProgressPatch: evidence is the only source. */
export interface DrillPatch {
  drill_ref: string;
  hand_done?: boolean | null;
  tool_done?: boolean | null;
  last_practiced?: string | null;
  notes?: string | null;
}

// ============================================================
// Planner API (mirrors backend app/schemas/planner.py — 5e-2)
// ============================================================

export type PlanActivity = 'learn' | 'drill' | 'review' | 'observe' | 'habit' | 'backtest';
export type PlanItemStatus = 'pending' | 'done' | 'partial' | 'skipped';

/** PUT /api/preferences body — availability + pacing.
 * `target_go_live_date` is PACING-ONLY (never gates). */
export interface PreferencesIn {
  timezone: string;
  mon_minutes: number;
  tue_minutes: number;
  wed_minutes: number;
  thu_minutes: number;
  fri_minutes: number;
  sat_minutes: number;
  sun_minutes: number;
  max_session_minutes: number;
  blackout_dates: string[];
  target_go_live_date: string | null;
  active_track: string;
}

/** GET/PUT /api/preferences response — the active prefs, or server defaults
 * (with `is_configured=false`) when the user has none yet. */
export interface PreferencesOut extends PreferencesIn {
  id: string | null;
  plan_version: number;
  generated_at: string | null;
  is_configured: boolean;
}

/** One prescribed task. `id` is null for COMPUTED (future, not-yet-frozen)
 * items; present for FROZEN (past/today) items materialized in the DB. */
export interface PlanItem {
  id: string | null;
  plan_version: number;
  scheduled_date: string;
  activity: PlanActivity;
  concept_id: string | null;
  concept_slug: string | null;
  concept_title: string | null;
  content_slug: string | null;
  drill_ref: string | null;
  drill_title: string | null;
  drill_variant: string | null;
  target_qty: number | null;
  target_unit: string | null;
  est_minutes: number;
  status: PlanItemStatus;
  done_qty: number;
  completed_at: string | null;
  sort_order: number;
  carried_over: boolean;
  frozen: boolean;
}

/** PATCH /api/plan/items/{id} body. `done_qty` feeds concept/drill progress
 * reps + last_practiced when done/partial. */
export interface PlanItemPatch {
  status: PlanItemStatus;
  done_qty?: number | null;
}

/** Accountability — surfaced, never hidden (north star). */
export interface Adherence {
  total: number;
  done: number;
  partial: number;
  skipped: number;
  pending: number;
  adherence_pct: number | null; // 0–100 percentage: 100·(done + 0.5·partial) / total
  current_streak: number; // consecutive fully-cleared days ending today
  days_behind: number; // distinct past dates with pending items
  carried_over: number; // past pending items re-queued today
}

/** ETA projection — PACING-ONLY (never advances a gate). */
export interface Pace {
  target_go_live_date: string | null;
  projected_go_live: string | null;
  on_pace: boolean | null;
  projected_clear: Record<string, string>; // stage_code → date
}

/** GET /api/plan/today */
export interface TodayPlan {
  date: string;
  active_track: string;
  plan_version: number;
  items: PlanItem[];
  adherence: Adherence;
  pace: Pace;
}

/** GET /api/plan?from=&to= — past/today frozen (id set), future computed (id null). */
export interface PlanRange {
  date_from: string;
  date_to: string;
  active_track: string;
  plan_version: number;
  items: PlanItem[];
  pace: Pace;
  unplaced: number;
}

// ============================================================
// Journal API (mirrors backend app/schemas/journal.py — 5f)
// ============================================================

/** The 7 journal enums (mirror app/models/enums.py). `mode` is the axis
 * discriminator; `entry_model` is the expectancy-grouping key. */
export type JournalMode = 'backtest' | 'live';
export type EntryModel =
  | 'consolidation'
  | 'expansion_retracement'
  | 'reversal_raid_on_stops'
  | 'london'
  | 'model_2022_ote'
  | 'daily_bias'
  | 'smt_confirmation'
  | 'unified';
export type RangePosition = 'discount' | 'eq' | 'premium';
export type SessionType = 'asia' | 'london' | 'ny_am' | 'ny_pm';
export type EntryPDA = 'fvg' | 'ifvg' | 'order_block' | 'breaker' | 'rejection_block' | 'ote_block';
export type Outcome = 'win' | 'loss' | 'breakeven';
export type Grade = 'a_plus' | 'a' | 'b' | 'c';

/** One journal row. A row is "closed" (counts toward expectancy) iff
 * `r_multiple != null`. Expectancy is in R — there is no dollar sizing. */
export interface JournalEntry {
  id: string;
  entry_date: string;
  instrument: string;
  session: SessionType | null;
  mode: JournalMode;
  entry_model: EntryModel;
  draw_on_liquidity: string | null;
  range_position: RangePosition | null;
  swing_qualification: number | null;
  seq_smt_confirmed: boolean | null;
  triad_smt_confirmed: boolean | null;
  aura_asset_leg: boolean | null;
  time_window_valid: boolean | null;
  entry_pda: EntryPDA | null;
  entry_price: number | null;
  stop_price: number | null;
  target_price: number | null;
  rr_planned: number | null;
  risk_pct: number | null;
  position_size: number | null; // contracts/lots — record-keeping only (6c)
  exit_price: number | null;
  r_multiple: number | null;
  outcome: Outcome | null;
  mae: number | null;
  mfe: number | null;
  confluence_tags: string[] | null;
  plan_followed: boolean | null;
  mistake_tags: string[] | null;
  grade: Grade | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

/** POST /api/journal body — `mode` + `entry_model` + `entry_date` + `instrument`
 * required; everything else optional. `entry_pda` defaults to fvg (R4). */
export interface JournalEntryIn {
  entry_date: string;
  instrument: string;
  session?: SessionType | null;
  mode: JournalMode;
  entry_model: EntryModel;
  draw_on_liquidity?: string | null;
  range_position?: RangePosition | null;
  swing_qualification?: number | null;
  seq_smt_confirmed?: boolean | null;
  triad_smt_confirmed?: boolean | null;
  aura_asset_leg?: boolean | null;
  time_window_valid?: boolean | null;
  entry_pda?: EntryPDA;
  entry_price?: number | null;
  stop_price?: number | null;
  target_price?: number | null;
  rr_planned?: number | null;
  risk_pct?: number | null;
  position_size?: number | null; // contracts/lots — record-keeping only (6c)
  exit_price?: number | null;
  r_multiple?: number | null;
  outcome?: Outcome | null;
  mae?: number | null;
  mfe?: number | null;
  confluence_tags?: string[] | null;
  plan_followed?: boolean | null;
  mistake_tags?: string[] | null;
  grade?: Grade | null;
  notes?: string | null;
}

/** PATCH /api/journal/{id} — partial; only supplied fields are written. */
export type JournalEntryUpdate = Partial<JournalEntryIn>;

/** Filters for GET /api/journal. */
export interface JournalFilterState {
  mode?: JournalMode;
  entry_model?: EntryModel;
  instrument?: string;
}

// ============================================================
// Missed-trade log (mirrors backend app/schemas/missed_trade.py — 6b)
// ============================================================

/** How the setup came to be missed. `canceled` is Dante's category — you had a
 * working order and pulled it (concepts/aura/journaling-system). */
export type MissType = 'almost_took' | 'hesitated' | 'canceled';
export type HypotheticalOutcome = 'would_win' | 'would_lose' | 'would_breakeven' | 'unknown';

/** One setup you did NOT take. A row is "resolved" (and enters the
 * opportunity-cost sums) iff it carries a `hypothetical_r`. NOTHING here enters
 * expectancy or the Readiness-to-Live Gate — these trades were never taken. */
export interface MissedTrade {
  id: string;
  entry_date: string;
  instrument: string;
  session: SessionType | null;
  entry_model: EntryModel;
  miss_type: MissType;
  reason: string | null;
  hesitation_tags: string[] | null;
  planned_entry: number | null;
  planned_stop: number | null;
  planned_target: number | null;
  rr_planned: number | null;
  hypothetical_outcome: HypotheticalOutcome | null;
  hypothetical_r: number | null;
  narrative: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

/** POST /api/missed-trades body — date + instrument + model + miss type required. */
export interface MissedTradeIn {
  entry_date: string;
  instrument: string;
  session?: SessionType | null;
  entry_model: EntryModel;
  miss_type: MissType;
  reason?: string | null;
  hesitation_tags?: string[] | null;
  planned_entry?: number | null;
  planned_stop?: number | null;
  planned_target?: number | null;
  rr_planned?: number | null;
  hypothetical_outcome?: HypotheticalOutcome | null;
  hypothetical_r?: number | null;
  narrative?: string | null;
  notes?: string | null;
}

export type MissedTradeUpdate = Partial<MissedTradeIn>;

/** Filters for GET /api/missed-trades. */
export interface MissedFilterState {
  miss_type?: MissType;
  entry_model?: EntryModel;
  hypothetical_outcome?: HypotheticalOutcome;
  instrument?: string;
}

/** One slice of the missed log. A NEGATIVE `net_r` means standing down was
 * PROTECTIVE — the sign carries the whole insight. */
export interface MissBucket {
  key: string;
  logged: number;
  resolved: number;
  would_win: number;
  would_lose: number;
  would_breakeven: number;
  forgone_r: number | null;
  saved_r: number | null;
  net_r: number | null;
  avg_r: number | null;
}

/** GET /api/analytics/missed-summary — opportunity cost in R. NOT expectancy. */
export interface OpportunityCostResponse {
  total: MissBucket;
  by_miss_type: MissBucket[];
  by_hesitation_tag: MissBucket[];
  by_entry_model: MissBucket[];
}

// ============================================================
// Analytics API (mirrors backend app/schemas/analytics.py — 5f)
// ============================================================

/** One entry_model × mode expectancy cell. `win_rate`/`break_even` are FRACTIONS
 * (0–1); the UI formats them as %. Backtest and live never conflate. */
export interface ExpectancyGroup {
  entry_model: string;
  mode: JournalMode;
  logged: number;
  n: number;
  wins: number;
  losses: number;
  breakevens: number;
  win_rate: number | null;
  avg_win_r: number | null;
  avg_loss_r: number | null;
  expectancy: number | null;
  avg_rr_planned: number | null;
  break_even: number | null;
  above_break_even: boolean | null;
  sample_target: number;
  sample_met: boolean;
}

export interface ExpectancyResponse {
  sample_target: number;
  groups: ExpectancyGroup[];
}

export interface ModeSummary {
  mode: JournalMode;
  logged: number;
  n: number;
  wins: number;
  losses: number;
  breakevens: number;
  win_rate: number | null;
  expectancy: number | null;
  total_r: number | null;
}

export interface SummaryResponse {
  modes: ModeSummary[];
}

export interface RDistributionBucket {
  label: string;
  lo: number | null;
  hi: number | null;
  backtest: number;
  live: number;
}

export interface RDistributionResponse {
  buckets: RDistributionBucket[];
}

// ============================================================
// Gate API (mirrors backend app/schemas/gate.py — 5g)
// ============================================================

/** One checkable gate requirement. `source` says which of the gate's three
 * evidence sources it comes from: `concepts` (a) · `evidence` (b) · `behaviour` (c). */
export interface GateRequirement {
  key: string;
  source: 'concepts' | 'evidence' | 'behaviour';
  label: string;
  met: boolean;
  detail: string | null;
  attest: boolean;
  concept_slug: string | null;
  concept_code: string | null;
  concept_track: string | null;   // link target: /path/:track/:stage
  concept_stage: string | null;
  required_ladder: number | null;
  actual_ladder: number | null;
  credited_slug: string | null;
  credited_track: string | null;
}

/** One entry_model's verdict. `cleared` is COMPUTED server-side from
 * (a) ∧ (b) ∧ (c) on every read — there is no way to set it. */
export interface ModelReadiness {
  entry_model: EntryModel;
  cleared: boolean;
  concepts_met: boolean;
  evidence_met: boolean;
  behaviour_met: boolean;
  requirements: GateRequirement[];
  blocking: string[];
  backtest_logged: number;
  backtest_n: number;
  backtest_expectancy: number | null;
  backtest_win_rate: number | null;   // FRACTION 0–1
  backtest_break_even: number | null; // FRACTION 0–1
  backtest_avg_rr: number | null;
  sample_target: number;
  sample_stretch: number;             // "ideally ≥100" — surfaced, NOT gating
  stretch_met: boolean;
  live_n: number;
  live_expectancy: number | null;
}

export interface GateFrontierConcept {
  slug: string;
  title: string;
  u_stage: string | null;
  tier: string | null;
  label: string | null;
}

export interface GateAttestation {
  item: string;
  label: string;
  attested: boolean;
  note: string | null;
}

export interface GateCorroboration {
  entries_logged: number;
  entries_closed: number;
  journaling_days: number;
  live_entries: number;
  backtest_entries: number;
  last_entry_date: string | null;
}

export interface GateResponse {
  anchor_track: string;
  credit_track: string | null;
  sample_target: number;
  sample_stretch: number;
  any_cleared: boolean;
  models: ModelReadiness[];
  attestations: GateAttestation[];
  corroboration: GateCorroboration;
  frontier: GateFrontierConcept[];
}

export interface GateAttestationPatch {
  item: string;
  attested: boolean;
  note?: string | null;
}

// ============================================================
// Evidence layer (Phase E2) — the ONLY way a rep is created
// ============================================================

export type EvidenceSubject = 'drill' | 'concept' | 'journal_entry' | 'missed_trade';

export type EvidenceKind =
  | 'chart_markup'
  | 'written_artifact'
  | 'computation'
  | 'prediction'
  | 'tape_read';

export type EvidenceGrader = 'deterministic' | 'self_check' | 'ai_vision';

export type EvidenceGradeState = 'ungraded' | 'pending' | 'passed' | 'flagged' | 'failed';

/** One grading pass. E2 only emits `deterministic`; the score is always advisory
 * and never writes confidence or ladder_stage. */
export interface EvidenceGrade {
  id: string;
  grader: EvidenceGrader;
  state: EvidenceGradeState;
  score: number | null;
  rubric_slug: string | null;
  rubric_version: number | null;
  findings: unknown;
  model: string | null;
  graded_at: string;
}

export interface EvidenceAsset {
  id: string;
  subject_type: EvidenceSubject;
  subject_drill_ref: string | null;
  concept_id: string | null;
  journal_entry_id: string | null;
  missed_trade_id: string | null;
  kind: EvidenceKind;
  content_type: string;
  original_filename: string | null;
  byte_size: number;
  sha256: string;
  perceptual_hash: string | null;
  captured_at: string | null;
  reps_claimed: number;
  notes: string | null;
  created_at: string;
  /** Presigned (R2) or signed local URL — renderable directly in an <img>. */
  url: string;
  grades: EvidenceGrade[];
}

/** Which subject a capture attaches to — exactly one id is set. */
export interface EvidenceSubjectRef {
  subject_type: EvidenceSubject;
  drill_ref?: string;
  concept_id?: string;
  journal_entry_id?: string;
  missed_trade_id?: string;
}

// ============================================================
// Rubric layer (Phase E3) — the drill's own bar, projected from the wiki
// ============================================================

/** ✋ hand-marking · 🛠 tool-assisted · `either` = the wiki bullet carries no
 * glyph (a computation, a written artifact, a procedure) — not a fallback. */
export type RubricVariant = 'hand' | 'tool' | 'either';

/** One checkable assertion. `text` is VERBATIM wiki markdown — no rubric text is
 * authored in the app, so the UI renders it rather than restating it. */
export interface RubricItem {
  item_key: string;
  ordinal: number;
  bullet_ordinal: number;
  variant: RubricVariant;
  text: string;
  rule_refs: string[] | null;
}

export interface Rubric {
  id: string;
  slug: string;
  drill_ref: string;
  track: string;
  /** Bumps when the projected wiki text changes, so a historical grade's
   * `rubric_version` names the exact bar it was judged against. */
  version: number;
  source_path: string;
  source_ref: string | null;
  items: RubricItem[];
}

/** One row of a `self_check` grade's `findings` — the whole bar plus what was
 * ticked, stored with the item text so the grade stays legible after a re-seed. */
export interface SelfCheckFinding {
  item_key: string;
  ordinal: number;
  variant: RubricVariant;
  text: string;
  checked: boolean;
}
