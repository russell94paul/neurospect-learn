import { Link } from 'react-router-dom';
import { Check, ClipboardCheck, Sigma, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { Requirement, StageOut } from '@/types/api';

/**
 * The per-stage exit-bar checklist (computed by the backend stages service).
 *
 * Phase 6a: rows are no longer uniformly "(self-attested)". Three kinds now read
 * differently, because they are graded differently:
 *   • concept rows — from concept_progress (unchanged);
 *   • DERIVED rows — objectively EARNED from the shipped journal expectancy or the
 *     Gate verdict; they carry the numbers and never say "self-attested";
 *   • ATTESTED rows — they REFLECT a tick made on /gate (one source of truth), so
 *     they link there instead of offering a second checkbox here.
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
            <ClipboardCheck className="h-3 w-3" /> attestation pending on the{' '}
            <Link to="/gate" className="underline decoration-dotted hover:text-foreground">
              Gate
            </Link>
          </span>
        )}
      </div>

      <ul className="space-y-1.5">
        {stage.requirements.map((r, i) => (
          <RequirementRow key={i} req={r} />
        ))}
      </ul>
    </div>
  );
}

function RequirementRow({ req: r }: { req: Requirement }) {
  return (
    <li className="flex items-start gap-2 text-sm">
      <Icon req={r} />
      <span className={cn('min-w-0', !r.met && 'text-muted-foreground')}>
        {r.concept_code && (
          <span className="mr-1 font-mono text-xs text-muted-foreground">{r.concept_code}</span>
        )}
        {r.label}
        {r.derived && (
          <span className="ml-1.5 align-middle text-[10px] uppercase tracking-wide text-muted-foreground">
            {r.met ? 'earned' : 'from your log'}
          </span>
        )}
        {/* The evidence itself — the numbers for a derived row, or where an
            attestation is made. This is what stops a row reading as theatre. */}
        {r.detail && (
          <span className="block text-xs text-muted-foreground">
            {r.link ? (
              <Link to={r.link} className="underline decoration-dotted hover:text-foreground">
                {r.detail}
              </Link>
            ) : (
              r.detail
            )}
          </span>
        )}
      </span>
    </li>
  );
}

function Icon({ req: r }: { req: Requirement }) {
  const cls = 'mt-0.5 h-4 w-4 shrink-0';
  if (r.met) {
    return <Check className={cn(cls, 'text-emerald-600 dark:text-emerald-400')} />;
  }
  if (r.derived) {
    // Objectively unmet, not "pending a declaration" — show the evidence glyph.
    return <Sigma className={cn(cls, 'text-muted-foreground/60')} />;
  }
  if (r.attest) {
    return <ClipboardCheck className={cn(cls, 'text-amber-600 dark:text-amber-500')} />;
  }
  return <X className={cn(cls, 'text-muted-foreground/50')} />;
}
