import { Check, ClipboardCheck, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { StageOut } from '@/types/api';

/**
 * The per-stage exit-bar checklist (computed by the backend stages service).
 * Self-attested requirements (U0 held-habit; U4 expectancy/risk precommit) are
 * surfaced honestly as pending until the 5f journal / 5g gate wire them.
 */
export function ExitBarGate({ stage }: { stage: StageOut }) {
  return (
    <div className="space-y-3">
      {/* The bar status reflects concept_progress regardless of lock state —
          the StageDetail page shows a separate "Locked" notice for ordering. */}
      <div className="flex flex-wrap items-center gap-2 text-sm font-medium">
        {stage.met ? (
          <span className="inline-flex items-center gap-1 text-emerald-600 dark:text-emerald-400">
            <Check className="h-4 w-4" /> Exit bar met
          </span>
        ) : (
          <span className="text-muted-foreground">Exit bar not met</span>
        )}
        {stage.attest_pending && !stage.met && (
          <span className="inline-flex items-center gap-1 text-xs text-amber-600 dark:text-amber-500">
            <ClipboardCheck className="h-3 w-3" /> self-attestation pending
          </span>
        )}
      </div>

      <ul className="space-y-1.5">
        {stage.requirements.map((r, i) => (
          <li key={i} className="flex items-start gap-2 text-sm">
            {r.met ? (
              <Check className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600 dark:text-emerald-400" />
            ) : r.attest ? (
              <ClipboardCheck className="mt-0.5 h-4 w-4 shrink-0 text-amber-600 dark:text-amber-500" />
            ) : (
              <X className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground/50" />
            )}
            <span className={cn(!r.met && 'text-muted-foreground')}>
              {r.concept_code && (
                <span className="mr-1 font-mono text-xs text-muted-foreground">{r.concept_code}</span>
              )}
              {r.label}
              {r.attest && !r.met && (
                <span className="ml-1 text-xs italic">(self-attested — Phase 5f/5g)</span>
              )}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
