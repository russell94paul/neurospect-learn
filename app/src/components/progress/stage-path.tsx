import { Link } from 'react-router-dom';
import { Check, Eye, Lock } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { StageRollup } from '@/types/api';

/** A small SVG progress ring (reached / total at ≥ Can-mark). */
function Ring({ value, met }: { value: number; met: boolean }) {
  const r = 18;
  const circ = 2 * Math.PI * r;
  const offset = circ * (1 - value / 100);
  return (
    <svg width="48" height="48" viewBox="0 0 48 48" className="shrink-0" aria-hidden>
      <circle cx="24" cy="24" r={r} fill="none" strokeWidth="4" className="stroke-muted" />
      <circle
        cx="24"
        cy="24"
        r={r}
        fill="none"
        strokeWidth="4"
        strokeLinecap="round"
        className={cn(met ? 'stroke-emerald-500' : 'stroke-primary')}
        strokeDasharray={circ}
        strokeDashoffset={offset}
        transform="rotate(-90 24 24)"
      />
      <text x="24" y="28" textAnchor="middle" className="fill-foreground text-[10px] font-medium">
        {Math.round(value)}%
      </text>
    </svg>
  );
}

export function StageNode({ stage }: { stage: StageRollup }) {
  const pct = stage.total ? (stage.reached / stage.total) * 100 : stage.met ? 100 : 0;
  return (
    <Link
      to={`/path/${stage.track}/${stage.stage_code}`}
      className={cn(
        'flex items-center gap-4 rounded-lg border p-4 transition-colors',
        stage.locked ? 'opacity-60 hover:opacity-100' : 'hover:bg-accent'
      )}
    >
      <Ring value={pct} met={stage.met} />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="font-mono text-xs text-muted-foreground">{stage.stage_code}</span>
          <span className="truncate font-semibold">{stage.title}</span>
          {stage.watch_only && (
            <span className="inline-flex items-center gap-1 text-xs text-amber-600 dark:text-amber-500">
              <Eye className="h-3 w-3" /> watch-only
            </span>
          )}
        </div>
        <div className="mt-1 flex flex-wrap items-center gap-x-2 text-xs">
          {stage.locked ? (
            <span className="inline-flex items-center gap-1 text-muted-foreground">
              <Lock className="h-3 w-3" /> Locked
            </span>
          ) : stage.met ? (
            <span className="inline-flex items-center gap-1 text-emerald-600 dark:text-emerald-400">
              <Check className="h-3 w-3" /> Exit bar met
            </span>
          ) : stage.total === 0 ? (
            // Concept-less stage (backtest / live / journal): 6a grades it on the
            // journal evidence or a /gate attestation, so "0/0 at Can-mark+" would
            // misdescribe it.
            <span className="text-muted-foreground">graded on your logged evidence</span>
          ) : (
            <span className="text-muted-foreground">
              {stage.reached}/{stage.total} at Can-mark+
            </span>
          )}
          {stage.attest_pending && !stage.locked && !stage.met && (
            <span className="text-amber-600 dark:text-amber-500">· attestation pending</span>
          )}
          {stage.never_gate_eligible && (
            <span className="text-muted-foreground">· never gate-eligible</span>
          )}
        </div>
      </div>
    </Link>
  );
}

/** A track's curriculum spine — the one-glance gated stage map. */
export function StagePath({ stages }: { stages: StageRollup[] }) {
  return (
    <div className="space-y-3">
      {stages.map((s) => (
        <StageNode key={`${s.track}-${s.stage_code}`} stage={s} />
      ))}
    </div>
  );
}
