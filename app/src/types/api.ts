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
