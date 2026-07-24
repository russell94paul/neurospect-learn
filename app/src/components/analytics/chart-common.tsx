import type { ReactNode } from 'react';

/**
 * Shared chart chrome for the expectancy dashboard (Phase 5f).
 *
 * The two journal axes map to two VALIDATED categorical hues (dataviz skill):
 * backtest = slot-1 blue, live = slot-2 orange. The pair clears all six checks
 * in both light and dark (CVD ΔE 24.7 / 26.8, ≥8 target). Colors are CSS vars
 * (`--chart-*` in index.css) so light/dark swap in one place; identity is never
 * carried by color alone — a legend is always present and the table view on the
 * page lists exact numbers.
 */

export const CHART_COLORS = {
  backtest: 'var(--chart-backtest)',
  live: 'var(--chart-live)',
} as const;

export const MODE_LABELS: Record<string, string> = {
  backtest: 'Backtest',
  live: 'Live',
};

export const AXIS = 'var(--chart-axis)';
export const GRID = 'var(--chart-grid)';
export const ZERO = 'var(--chart-zero)';

/** A theme-aware Recharts tooltip using the shadcn popover tokens (the default
 * white tooltip is unreadable in dark mode). `render` formats each datum. */
export function ChartTooltip({
  active,
  payload,
  label,
  render,
}: {
  active?: boolean;
  payload?: Array<{ name?: string; value?: number | string; color?: string; dataKey?: string | number }>;
  label?: string | number;
  render?: (value: number | string | undefined, name: string | undefined) => ReactNode;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-md border bg-popover px-3 py-2 text-xs text-popover-foreground shadow-md">
      {label != null && <p className="mb-1 font-medium">{label}</p>}
      <ul className="space-y-0.5">
        {payload.map((p, i) => (
          <li key={i} className="flex items-center gap-2">
            <span className="inline-block h-2 w-2 rounded-sm" style={{ backgroundColor: p.color }} />
            <span className="text-muted-foreground">{MODE_LABELS[String(p.name)] ?? p.name}:</span>
            <span className="font-medium tabular-nums">
              {render ? render(p.value, String(p.name)) : p.value}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** A muted empty-state panel for a chart with no data yet. */
export function EmptyChart({ children }: { children: ReactNode }) {
  return (
    <div className="flex h-64 items-center justify-center rounded-lg border border-dashed text-center text-sm text-muted-foreground">
      {children}
    </div>
  );
}
