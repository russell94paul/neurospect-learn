import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { ENTRY_MODEL_LABELS } from '@/lib/journal';
import { rMultiple } from '@/lib/analytics';
import type { EntryModel, ExpectancyGroup } from '@/types/api';
import { AXIS, CHART_COLORS, ChartTooltip, EmptyChart, GRID, ZERO } from './chart-common';

/**
 * Per-model EXPECTANCY in R, backtest vs live (grouped bars). The headline
 * proof-of-edge chart: bars above the zero line are a positive edge, below it a
 * negative one. Backtest and live are separate series (never conflated) so an
 * edge that only exists in backtest is visible as a tall backtest bar with a
 * short/absent live bar. Only models with ≥1 closed trade in a mode get a bar.
 */
export function ExpectancyChart({ groups }: { groups: ExpectancyGroup[] }) {
  const byModel = new Map<string, { model: string; label: string; backtest: number | null; live: number | null }>();
  for (const g of groups) {
    const row = byModel.get(g.entry_model) ?? {
      model: g.entry_model,
      label: ENTRY_MODEL_LABELS[g.entry_model as EntryModel] ?? g.entry_model,
      backtest: null,
      live: null,
    };
    if (g.mode === 'backtest') row.backtest = g.expectancy;
    else if (g.mode === 'live') row.live = g.expectancy;
    byModel.set(g.entry_model, row);
  }
  const data = [...byModel.values()]
    .filter((r) => r.backtest != null || r.live != null)
    .sort((a, b) => a.label.localeCompare(b.label));

  if (!data.length) {
    return <EmptyChart>No closed trades yet — log entries with a realized R to see expectancy.</EmptyChart>;
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
          tick={{ fill: AXIS, fontSize: 11 }}
          tickLine={false}
          axisLine={{ stroke: ZERO }}
          label={{ value: 'Expectancy (R)', angle: -90, position: 'insideLeft', fill: AXIS, fontSize: 11, dy: 40 }}
        />
        <ReferenceLine y={0} stroke={ZERO} strokeWidth={1} />
        <Tooltip
          cursor={{ fill: 'var(--chart-grid)', fillOpacity: 0.3 }}
          content={<ChartTooltip render={(v) => rMultiple(typeof v === 'number' ? v : null)} />}
        />
        <Legend
          formatter={(value) => (value === 'backtest' ? 'Backtest' : 'Live')}
          wrapperStyle={{ fontSize: 12 }}
        />
        <Bar dataKey="backtest" name="backtest" fill={CHART_COLORS.backtest} radius={[3, 3, 0, 0]} />
        <Bar dataKey="live" name="live" fill={CHART_COLORS.live} radius={[3, 3, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
