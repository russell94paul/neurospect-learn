import { useSyncExternalStore } from 'react';

/**
 * Display settings — the design-system layer.
 *
 * THREE THINGS WORTH THE COMMENT
 * ------------------------------
 * **localStorage, not the server.** The boot script must stamp the theme before
 * React mounts and before the JWT in `lib/auth.ts` is validated — anything that
 * waits on a fetch flashes. A server value could only ever be a mirror, never
 * the boot source. And the obvious server home is a trap: `PUT /api/preferences`
 * (`lib/planner.ts`) RECOMPUTES THE WHOLE STUDY PLAN on write, so routing a
 * theme toggle through it would regenerate the schedule. Display prefs are also
 * legitimately per-device. If server sync is ever added it needs its own table
 * and endpoint, with localStorage still the boot source.
 *
 * **`useSyncExternalStore`, not context.** This state is a single global that is
 * also written by a non-React boot script (index.html) and two matchMedia
 * listeners. Context would need an effect to bridge each. This way `main.tsx`
 * stays untouched and a theme change does not re-render through the
 * AuthProvider / QueryClientProvider boundary.
 *
 * **`apply()` is the only DOM writer.** Every axis lands on <html> as a class or
 * a data attribute; CSS does the rest. Keeping that in one function is what lets
 * the boot script be a dumb duplicate of it (see index.html) without drift.
 */

export type ThemeMode = 'light' | 'dark' | 'system';
export type BrandId = 'cyan' | 'violet' | 'emerald' | 'amber' | 'rose';
export type Density = 'comfortable' | 'compact';
export type FontId = 'inter' | 'system' | 'serif';
export type MotionPref = 'system' | 'full' | 'subtle' | 'none';

export interface Settings {
  version: 1;
  mode: ThemeMode;
  brand: BrandId;
  /** Corner radius in rem. 0 = square. */
  radius: number;
  density: Density;
  font: FontId;
  motion: MotionPref;
  updatedAt: string;
}

/** Must match the literal defaults on <html> in index.html. */
export const DEFAULTS: Settings = {
  version: 1,
  mode: 'dark', // dark-first, explicitly — not 'system'
  brand: 'cyan',
  radius: 0.5,
  density: 'comfortable',
  font: 'inter',
  motion: 'system',
  updatedAt: '',
};

/** Must match the key read by the boot script in index.html. */
const KEY = 'neurospect.learn.settings.v1';

export const BRANDS: { id: BrandId; label: string }[] = [
  { id: 'cyan', label: 'Cyan' },
  { id: 'violet', label: 'Violet' },
  { id: 'emerald', label: 'Emerald' },
  { id: 'amber', label: 'Amber' },
  { id: 'rose', label: 'Rose' },
];

export const RADII: { value: number; label: string }[] = [
  { value: 0, label: 'Square' },
  { value: 0.35, label: 'Soft' },
  { value: 0.5, label: 'Default' },
  { value: 0.85, label: 'Round' },
];

const BRAND_IDS = new Set<string>(BRANDS.map((b) => b.id));
const DENSITIES = new Set<string>(['comfortable', 'compact']);
const FONTS = new Set<string>(['inter', 'system', 'serif']);
const MODES = new Set<string>(['light', 'dark', 'system']);
const MOTIONS = new Set<string>(['system', 'full', 'subtle', 'none']);

/**
 * Resolve the two OS-dependent axes. Pure, so it is unit-testable and so the
 * boot script can mirror it without importing anything.
 *
 * An explicit motion choice wins in BOTH directions: someone whose OS asks for
 * reduced motion may still choose `full` and get it. That is why no CSS in this
 * app may contain a bare `@media (prefers-reduced-motion)` block — the media
 * query is consulted here, in JS, only to resolve `system`.
 */
export function resolve(
  s: Settings,
  os: { osDark: boolean; osReduce: boolean }
): { dark: boolean; motion: 'full' | 'subtle' | 'none' } {
  const dark = s.mode === 'system' ? os.osDark : s.mode === 'dark';
  const motion = s.motion === 'system' ? (os.osReduce ? 'none' : 'full') : s.motion;
  return { dark, motion };
}

function sanitize(raw: unknown): Settings {
  const p = (raw ?? {}) as Partial<Settings>;
  return {
    ...DEFAULTS,
    ...p,
    version: 1,
    mode: MODES.has(p.mode as string) ? (p.mode as ThemeMode) : DEFAULTS.mode,
    brand: BRAND_IDS.has(p.brand as string) ? (p.brand as BrandId) : DEFAULTS.brand,
    density: DENSITIES.has(p.density as string) ? (p.density as Density) : DEFAULTS.density,
    font: FONTS.has(p.font as string) ? (p.font as FontId) : DEFAULTS.font,
    motion: MOTIONS.has(p.motion as string) ? (p.motion as MotionPref) : DEFAULTS.motion,
    radius:
      typeof p.radius === 'number' && p.radius >= 0 && p.radius <= 2
        ? p.radius
        : DEFAULTS.radius,
  };
}

function load(): Settings {
  try {
    const s = localStorage.getItem(KEY);
    if (!s) return DEFAULTS;
    const parsed = JSON.parse(s) as Partial<Settings>;
    return parsed?.version === 1 ? sanitize(parsed) : DEFAULTS;
  } catch {
    return DEFAULTS;
  }
}

function save(s: Settings): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(s));
  } catch {
    /* quota or private mode — the app still works, it just forgets */
  }
}

const mqDark =
  typeof matchMedia === 'function' ? matchMedia('(prefers-color-scheme: dark)') : null;
const mqReduce =
  typeof matchMedia === 'function' ? matchMedia('(prefers-reduced-motion: reduce)') : null;

function osState() {
  return { osDark: mqDark?.matches ?? true, osReduce: mqReduce?.matches ?? false };
}

/** The single DOM writer. Everything else in the app reads CSS. */
function apply(s: Settings): void {
  if (typeof document === 'undefined') return;
  const el = document.documentElement;
  const r = resolve(s, osState());

  el.classList.toggle('dark', r.dark);
  el.dataset.brand = s.brand;
  el.dataset.density = s.density;
  el.dataset.font = s.font;
  el.dataset.motion = r.motion;
  el.style.setProperty('--radius', s.radius + 'rem');

  // Clear the free-hue escape hatch. A future arbitrary-colour picker writes
  // these three inline and wins on specificity with no new selectors; until
  // then they must never linger from a previous session.
  el.style.removeProperty('--brand-h');
  el.style.removeProperty('--brand-c');
  el.style.removeProperty('--brand-fg');
}

let current: Settings = load();
const listeners = new Set<() => void>();

function emit() {
  for (const l of listeners) l();
}

function commit(next: Settings) {
  current = next;
  save(next);
  apply(next);
  emit();
}

mqDark?.addEventListener('change', () => {
  apply(current);
  emit();
});
mqReduce?.addEventListener('change', () => {
  apply(current);
  emit();
});

if (typeof window !== 'undefined') {
  window.addEventListener('storage', (e) => {
    if (e.key !== KEY) return;
    current = load();
    apply(current);
    emit();
  });
}

export function subscribe(cb: () => void): () => void {
  listeners.add(cb);
  return () => {
    listeners.delete(cb);
  };
}

export function getSnapshot(): Settings {
  return current;
}

export function setSettings(patch: Partial<Settings>): void {
  commit(sanitize({ ...current, ...patch, updatedAt: new Date().toISOString() }));
}

export function resetSettings(): void {
  commit({ ...DEFAULTS, updatedAt: new Date().toISOString() });
}

/** True when the OS asks for reduced motion — for the override warning in Settings. */
export function osPrefersReducedMotion(): boolean {
  return mqReduce?.matches ?? false;
}

export function useSettings() {
  const settings = useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
  return { settings, set: setSettings, reset: resetSettings };
}

// The boot script in index.html has already stamped <html>. Re-apply once on
// import so a stored value that failed that dumber parse (or a sanitised field)
// is reconciled before first interaction.
apply(current);
