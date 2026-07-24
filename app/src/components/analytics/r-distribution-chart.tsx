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
import type { RDistributionBucket } from '@/types/api';
import { AXIS, CHART_COLORS, ChartTooltip, EmptyChart, GRID, ZERO } from './chart-common';

/**
 * Realized-R distribution (histogram) over closed trades, backtest vs live.
 * Fixed half-open R buckets from the API. Grouped (not stacked) so each mode's
 * shape reads on its own — the point is to SEE the R distribution, not conflate
 * the axes. An addition to the two named 5f charts; shares their validated
 * palette + chrome.
 */
export function RDistributionChart({ buckets }: { buckets: RDistributionBucket[] }) {
  const total = buckets.reduce((s, b) => s + b.backtest + b.live, 0);
  if (!total) {
    return <EmptyChart>No closed trades yet — the R distribution fills in as trades close.</EmptyChart>;
  }

  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart data={buckets} margin={{ top: 8, right: 12, bottom: 30, left: 4 }} barGap={2} barCategoryGap="20%">
        <CartesianGrid vertical={false} stroke={GRID} />
        <XAxis
          dataKey="label"
          tick={{ fill: AXIS, fontSize: 11 }}
          height={40}
          interval={0}
          tickLine={false}
          axisLine={{ stroke: ZERO }}
        />
        <YAxis
          allowDecimals={false}
          tick={{ fill: AXIS, fontSize: 11 }}
          tickLine={false}
          axisLine={{ stroke: ZERO }}
          label={{ value: 'Trades', angle: -90, position: 'insideLeft', fill: AXIS, fontSize: 11, dy: 20 }}
        />
        <Tooltip cursor={{ fill: 'var(--chart-grid)', fillOpacity: 0.3 }} content={<ChartTooltip />} />
        <Legend formatter={(value) => (value === 'backtest' ? 'Backtest' : 'Live')} wrapperStyle={{ fontSize: 12 }} />
        <Bar dataKey="backtest" name="backtest" fill={CHART_COLORS.backtest} radius={[3, 3, 0, 0]} />
        <Bar dataKey="live" name="live" fill={CHART_COLORS.live} radius={[3, 3, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
