import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { ENTRY_MODEL_LABELS } from '@/lib/journal';
import { pct } from '@/lib/analytics';
import type { EntryModel, ExpectancyGroup } from '@/types/api';
import { AXIS, CHART_COLORS, ChartTooltip, EmptyChart, GRID, ZERO } from './chart-common';

/**
 * Per-model WIN RATE %, backtest vs live (grouped bars) — the honesty view.
 * A backtest win rate that collapses in live is unmistakable here: the live bar
 * sits well below its backtest twin. Win rate arrives as a fraction (0–1); the
 * axis + tooltip format it as %. Only models with ≥1 closed trade in a mode get
 * a bar.
 */
export function BacktestVsLiveChart({ groups }: { groups: ExpectancyGroup[] }) {
  const byModel = new Map<string, { model: string; label: string; backtest: number | null; live: number | null }>();
  for (const g of groups) {
    const row = byModel.get(g.entry_model) ?? {
      model: g.entry_model,
      label: ENTRY_MODEL_LABELS[g.entry_model as EntryModel] ?? g.entry_model,
      backtest: null,
      live: null,
    };
    // Store as a percentage 0–100 for the axis; format back with pct() in the tooltip.
    if (g.mode === 'backtest') row.backtest = g.win_rate != null ? g.win_rate * 100 : null;
    else if (g.mode === 'live') row.live = g.win_rate != null ? g.win_rate * 100 : null;
    byModel.set(g.entry_model, row);
  }
  const data = [...byModel.values()]
    .filter((r) => r.backtest != null || r.live != null)
    .sort((a, b) => a.label.localeCompare(b.label));

  if (!data.length) {
    return <EmptyChart>No closed trades yet — win rate appears once entries carry a realized R.</EmptyChart>;
  }

  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={data} margin={{ top: 8, right: 12, bottom: 40, left: 4 }} barGap={2} barCategoryGap="24%">
        <CartesianGrid vertical={false} stroke={GRID} />
        <XAxis
          dataKey="label"
          tick={{ fill: AXIS, fontSize: 11 }}
          angle={-20}
          textAnchor="end"
          height={50}
          interval={0}
          tickLine={false}
          axisLine={{ stroke: ZERO }}
        />
        <YAxis
          domain={[0, 100]}
          tick={{ fill: AXIS, fontSize: 11 }}
          tickFormatter={(v) => `${v}%`}
          tickLine={false}
          axisLine={{ stroke: ZERO }}
          label={{ value: 'Win rate', angle: -90, position: 'insideLeft', fill: AXIS, fontSize: 11, dy: 24 }}
        />
        <Tooltip
          cursor={{ fill: 'var(--chart-grid)', fillOpacity: 0.3 }}
          content={<ChartTooltip render={(v) => pct(typeof v === 'number' ? v / 100 : null)} />}
        />
        <Legend formatter={(value) => (value === 'backtest' ? 'Backtest' : 'Live')} wrapperStyle={{ fontSize: 12 }} />
        <Bar dataKey="backtest" name="backtest" fill={CHART_COLORS.backtest} radius={[3, 3, 0, 0]} />
        <Bar dataKey="live" name="live" fill={CHART_COLORS.live} radius={[3, 3, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
