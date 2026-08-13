import { useCallback, useEffect, useMemo, useState } from 'react';
import raw from '@/data/aura-runner.json';

// ============================================================
// The Aura session runner's data layer (Phase S1).
//
// TWO THINGS THIS DELIBERATELY IS NOT:
//
// 1. It is NOT an API client. The content is a build-time projection of the
//    wiki (api/scripts/project_aura_runner.py), imported straight into the
//    bundle, and rendering the protocol issues ZERO /api requests (asserted in
//    e2e/runner.spec.ts).
//
//    ⚠️ That does NOT make the runner usable offline, and S1 measured this
//    rather than assuming it: the page sits behind ProtectedLayout, and
//    lib/auth.ts:50-53 clears the stored token on ANY `auth/me` failure —
//    network errors included — so an unreachable API bounces you to /login and
//    discards the session. Pre-existing, wider than this phase, and left
//    unchanged here on purpose.
// 2. It writes NOTHING to the database. Step state lives in `localStorage`
//    (the tracker's open question Q2, answered explicitly). See the honesty
//    note on `declaredAt` below for what that costs.
// ============================================================

export type PhaseScope = 'day' | 'setup' | 'any';

export interface RunnerItem {
  text: string;
  ruleRefs: string[];
  hardGate: boolean;
}

export interface RunnerPhase {
  index: number;
  title: string;
  ruleRefs: string[];
  scope: PhaseScope;
  items: RunnerItem[];
}

export interface Rule {
  id: string;
  n: number;
  section: string;
  group: string;
  text: string;
  soft: boolean;
  flagged: boolean;
}

export interface Divergence {
  label: string;
  text: string;
}

export interface RunnerTable {
  headers: string[];
  rows: string[][];
}

export interface RunnerSection {
  title: string;
  items: RunnerItem[];
  tables: RunnerTable[];
  paras: string[];
}

export interface RunnerData {
  generated: { sources: string[]; note: string };
  checklist: { phases: RunnerPhase[]; perTradeCard: string };
  rules: Rule[];
  divergences: Divergence[];
  setup: { sections: RunnerSection[] };
  mapping: { sections: RunnerSection[] };
  markup: { sections: RunnerSection[] };
}

export const runnerData = raw as unknown as RunnerData;

const RULES_BY_ID = new Map(runnerData.rules.map((r) => [r.id, r]));

export function lookupRule(id: string): Rule | undefined {
  return RULES_BY_ID.get(id);
}

// ============================================================
// The declared replay span — the counting basis, in code.
//
// A session is one sitting over a DECLARED span; the counted unit is the
// replayed DAY. See concepts/mastery/aura/tradezella-setup.md §The counting
// basis for why the day and not the session (short version: a day you
// correctly stood aside still counts, and R51 says that IS discipline).
// ============================================================

export const SPANS = [
  { key: '1w', label: '1 week', days: 7, tradingDays: 5 },
  { key: '1m', label: '1 month', days: 30, tradingDays: 21 },
  { key: '3m', label: '3 months', days: 91, tradingDays: 63 },
  { key: '6m', label: '6 months', days: 182, tradingDays: 126 },
  { key: '1y', label: '1 year', days: 365, tradingDays: 252 },
] as const;

export type SpanKey = (typeof SPANS)[number]['key'];

export function spanOf(key: SpanKey) {
  return SPANS.find((s) => s.key === key) ?? SPANS[0];
}

/** End date implied by a start date + span, as `yyyy-mm-dd`. */
export function endDateFor(start: string, key: SpanKey): string {
  const d = new Date(`${start}T00:00:00`);
  if (Number.isNaN(d.getTime())) return '';
  d.setDate(d.getDate() + spanOf(key).days);
  return d.toISOString().slice(0, 10);
}

/** `MM/DD/YYYY hh:mm:ss` — the format Tradezella's create-session form takes. */
export function toTradezellaDate(iso: string, endOfDay = false): string {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(iso)) return '';
  const [y, m, d] = iso.split('-');
  return `${m}/${d}/${y} ${endOfDay ? '23:59:59' : '00:00:00'}`;
}

/** The session-name convention, so sessions sort and compare. */
export function sessionName(start: string, key: SpanKey): string {
  const end = endDateFor(start, key);
  return start && end ? `AURA · NQ · ${start}→${end} · ${key}` : '';
}

// ============================================================
// Session state — localStorage only
// ============================================================

const KEY = 'neurospect.aura-runner.v1';

export interface RunnerState {
  version: 1;
  span: SpanKey;
  startDate: string;
  /** Pre-commitment (R48): what am I looking for, where, what makes me stand aside. */
  precommit: string;
  /**
   * When `precommit` was first written, by the BROWSER's clock.
   *
   * ⚠️ This is self-reported and NOT trustworthy ordering evidence — the
   * device clock is user-controlled and nothing stamps it server-side. A
   * pre-commitment whose ordering can actually be trusted is E5's frozen
   * ledger, which S1 deliberately does not write to. S2 owns that, and owns
   * the two-clock decision that comes with it.
   */
  declaredAt: string | null;
  /** Zero-based index of the replayed day within the declared span. */
  day: number;
  /** Per-day count of setups worked (index 0..setups-1). */
  setups: Record<number, number>;
  activeSetup: number;
  /** Days marked complete, as `yyyy-mm-dd` of the replayed date. */
  daysDone: string[];
  /** Days explicitly recorded as stood-aside — R51 discipline, not absence. */
  daysStoodAside: string[];
  ticks: Record<string, boolean>;
}

function freshState(): RunnerState {
  return {
    version: 1,
    span: '1w',
    startDate: '',
    precommit: '',
    declaredAt: null,
    day: 0,
    setups: {},
    activeSetup: 0,
    daysDone: [],
    daysStoodAside: [],
    ticks: {},
  };
}

function load(): RunnerState {
  try {
    const s = localStorage.getItem(KEY);
    if (!s) return freshState();
    const parsed = JSON.parse(s) as RunnerState;
    return parsed?.version === 1 ? { ...freshState(), ...parsed } : freshState();
  } catch {
    return freshState();
  }
}

/** Tick key. Setup-scoped phases repeat per setup; day-scoped ones do not. */
export function tickKey(scope: PhaseScope, day: number, setup: number, phase: number, item: number) {
  return scope === 'setup'
    ? `d${day}:s${setup}:p${phase}:i${item}`
    : `d${day}:p${phase}:i${item}`;
}

export function useRunnerState() {
  const [state, setState] = useState<RunnerState>(load);

  useEffect(() => {
    try {
      localStorage.setItem(KEY, JSON.stringify(state));
    } catch {
      /* quota or private mode — the runner still works, it just forgets */
    }
  }, [state]);

  const patch = useCallback((p: Partial<RunnerState>) => {
    setState((s) => ({ ...s, ...p }));
  }, []);

  const toggle = useCallback((key: string) => {
    setState((s) => ({ ...s, ticks: { ...s.ticks, [key]: !s.ticks[key] } }));
  }, []);

  const setupCount = state.setups[state.day] ?? 1;

  const addSetup = useCallback(() => {
    setState((s) => {
      const n = (s.setups[s.day] ?? 1) + 1;
      return { ...s, setups: { ...s.setups, [s.day]: n }, activeSetup: n - 1 };
    });
  }, []);

  /** The replayed date implied by the declared start + day offset. */
  const dayDate = useMemo(() => {
    if (!state.startDate) return '';
    const d = new Date(`${state.startDate}T00:00:00`);
    if (Number.isNaN(d.getTime())) return '';
    d.setDate(d.getDate() + state.day);
    return d.toISOString().slice(0, 10);
  }, [state.startDate, state.day]);

  const reset = useCallback(() => setState(freshState()), []);

  return { state, patch, toggle, setupCount, addSetup, dayDate, reset };
}

// ============================================================
// Progress — computed per read, never stored (the stages.py/gate.py convention)
// ============================================================

export interface PhaseProgress {
  done: number;
  total: number;
  gatesOpen: number;
}

export function phaseProgress(
  phase: RunnerPhase,
  ticks: Record<string, boolean>,
  day: number,
  setup: number
): PhaseProgress {
  let done = 0;
  let gatesOpen = 0;
  phase.items.forEach((item, i) => {
    const on = !!ticks[tickKey(phase.scope, day, setup, phase.index, i)];
    if (on) done += 1;
    else if (item.hardGate) gatesOpen += 1;
  });
  return { done, total: phase.items.length, gatesOpen };
}
