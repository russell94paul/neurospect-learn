import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import type {
  ExpectancyResponse,
  RDistributionResponse,
  SummaryResponse,
} from '@/types/api';

// ============================================================
// TanStack Query keys — hierarchical under ['analytics']. Journal writes
// invalidate `analyticsKeys.all` (see lib/journal.ts) so the expectancy view
// always reflects the current entries.
// ============================================================

export const analyticsKeys = {
  all: ['analytics'] as const,
  expectancy: () => [...analyticsKeys.all, 'expectancy'] as const,
  summary: () => [...analyticsKeys.all, 'summary'] as const,
  rDistribution: () => [...analyticsKeys.all, 'r-distribution'] as const,
};

/** Per entry_model × mode expectancy (the proof-of-edge grid). */
export function useExpectancy() {
  return useQuery({
    queryKey: analyticsKeys.expectancy(),
    queryFn: () => api.get('api/analytics/expectancy').json<ExpectancyResponse>(),
  });
}

/** Top-line per mode (backtest vs live). */
export function useSummary() {
  return useQuery({
    queryKey: analyticsKeys.summary(),
    queryFn: () => api.get('api/analytics/summary').json<SummaryResponse>(),
  });
}

/** Realized-R histogram, split by mode. */
export function useRDistribution() {
  return useQuery({
    queryKey: analyticsKeys.rDistribution(),
    queryFn: () => api.get('api/analytics/r-distribution').json<RDistributionResponse>(),
  });
}

// ============================================================
// Formatting helpers — win_rate / break_even arrive as FRACTIONS (0–1).
// ============================================================

/** A fraction 0–1 → a percent string (e.g. 0.4 → "40%"). */
export function pct(fraction: number | null | undefined, digits = 0): string {
  if (fraction == null) return '—';
  return `${(fraction * 100).toFixed(digits)}%`;
}

/** An R multiple → a signed string (e.g. 0.2 → "+0.20R", -1 → "-1.00R"). */
export function rMultiple(r: number | null | undefined, digits = 2): string {
  if (r == null) return '—';
  const sign = r > 0 ? '+' : '';
  return `${sign}${r.toFixed(digits)}R`;
}
