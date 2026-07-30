import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import type { GateAttestation, GateAttestationPatch, GateResponse } from '@/types/api';

// ============================================================
// TanStack Query keys — hierarchical under ['gate'], mirroring the
// learningKeys / analyticsKeys convention.
// ============================================================

export const gateKeys = {
  all: ['gate'] as const,
  verdict: (track?: string) => [...gateKeys.all, 'verdict', track ?? 'any'] as const,
  attestations: () => [...gateKeys.all, 'attestations'] as const,
};

/** The computed per-model "cleared to live?" verdict.
 *
 * `track` restricts which track's progress may satisfy a concept requirement —
 * it can only ever TIGHTEN the verdict (omit it to credit any track). There is
 * deliberately no mutation that sets `cleared`: the gate is recomputed
 * server-side from concept progress + backtest expectancy + attestations. */
export function useGate(track?: string) {
  return useQuery({
    queryKey: gateKeys.verdict(track),
    queryFn: () =>
      api.get('api/gate', { searchParams: track ? { track } : undefined }).json<GateResponse>(),
  });
}

/** The four behavioural checklist items and their attested state. */
export function useAttestations() {
  return useQuery({
    queryKey: gateKeys.attestations(),
    queryFn: () => api.get('api/gate/attestations').json<GateAttestation[]>(),
  });
}

/** Attest or revoke ONE behavioural item. Attesting is an input to the gate, not
 * an override — it can never satisfy the concept or expectancy requirements. */
export function useUpdateAttestation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: GateAttestationPatch) =>
      api.patch('api/gate/attestations', { json: body }).json<GateAttestation>(),
    onSuccess: () => {
      // The verdict reads attestations, so invalidate the whole gate subtree.
      qc.invalidateQueries({ queryKey: gateKeys.all });
    },
  });
}

// ============================================================
// Presentation helpers
// ============================================================

export const LADDER_NAMES: Record<number, string> = {
  1: 'Learned',
  2: 'Can-mark',
  3: 'Backtested',
  4: 'Live-ready',
};

export function ladderName(stage: number | null | undefined): string {
  return stage == null ? 'not started' : (LADDER_NAMES[stage] ?? String(stage));
}

/** The gate's three evidence sources, in the order the checklist presents them. */
export const GATE_SOURCES = [
  {
    key: 'concepts' as const,
    title: 'Concept ladder',
    blurb:
      'Every core concept at Backtested+, and the model’s load-bearing concept at Live-ready. Frontier (U5) concepts never count.',
  },
  {
    key: 'evidence' as const,
    title: 'Proof of edge',
    blurb:
      'A real backtest sample with positive expectancy in R, and a win rate that clears break-even for its planned R:R.',
  },
  {
    key: 'behaviour' as const,
    title: 'Behavioural discipline',
    blurb:
      'The four items no data can prove — self-attested, and never a substitute for the two above.',
  },
];
