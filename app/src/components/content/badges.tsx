import { AlertTriangle, Eye } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import type { ConceptBadge } from '@/types/api';

/** Source tier of a frontier concept (e.g. "Tier 1", "Tier 2-3"). */
export function TierBadge({ tier, className }: { tier: string | null | undefined; className?: string }) {
  if (!tier) return null;
  return (
    <Badge variant="outline" className={cn('font-mono', className)}>
      {tier}
    </Badge>
  );
}

/**
 * Evidence label — ESTABLISHED / EMERGING / SPECULATIVE. Colour tracks the
 * gate risk: ESTABLISHED is safe (secondary), EMERGING/SPECULATIVE are
 * study-and-watch only (destructive) — they must never read as trade-ready.
 */
export function LabelBadge({ label, className }: { label: string | null | undefined; className?: string }) {
  if (!label) return null;
  const established = label.toUpperCase() === 'ESTABLISHED';
  return (
    <Badge variant={established ? 'secondary' : 'destructive'} className={className}>
      {label}
    </Badge>
  );
}

/** Study-and-watch marker for watch-only (frontier) concepts. */
export function WatchOnlyBadge({ className }: { className?: string }) {
  return (
    <Badge variant="outline" className={cn('gap-1 text-amber-600 dark:text-amber-500', className)}>
      <Eye className="h-3 w-3" />
      Study &amp; watch
    </Badge>
  );
}

/** The full badge row shown on a reader page, sourced from the referencing concept. */
export function ConceptBadgeRow({ badge }: { badge: ConceptBadge | null | undefined }) {
  if (!badge) return null;
  const speculative = badge.label && badge.label.toUpperCase() !== 'ESTABLISHED';
  return (
    <div className="flex flex-wrap items-center gap-2">
      {badge.code && (
        <Badge variant="default" className="font-mono">
          {badge.code}
        </Badge>
      )}
      <TierBadge tier={badge.tier} />
      <LabelBadge label={badge.label} />
      {badge.watch_only && <WatchOnlyBadge />}
      {speculative && (
        <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
          <AlertTriangle className="h-3 w-3" />
          Never gate-eligible
        </span>
      )}
    </div>
  );
}
