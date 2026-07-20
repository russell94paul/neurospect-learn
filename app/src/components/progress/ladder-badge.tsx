import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import { LADDER_LABELS } from '@/lib/learning';

// Colour climbs with the ladder (concepts/mastery/README §ladder): grey Learned
// → blue Can-mark → amber Backtested → green Live-ready.
const LADDER_STYLES: Record<number, string> = {
  1: 'bg-slate-200 text-slate-800 dark:bg-slate-700 dark:text-slate-100',
  2: 'bg-blue-200 text-blue-900 dark:bg-blue-900 dark:text-blue-100',
  3: 'bg-amber-200 text-amber-900 dark:bg-amber-900 dark:text-amber-100',
  4: 'bg-emerald-200 text-emerald-900 dark:bg-emerald-900 dark:text-emerald-100',
};

/** The 4-stage mastery ladder position (1 Learned → 4 Live-ready). */
export function LadderBadge({
  stage,
  className,
}: {
  stage: number | null | undefined;
  className?: string;
}) {
  if (!stage) {
    return (
      <Badge variant="outline" className={cn('text-muted-foreground', className)}>
        Untracked
      </Badge>
    );
  }
  return (
    <Badge className={cn('border-transparent', LADDER_STYLES[stage], className)}>
      {stage} · {LADDER_LABELS[stage]}
    </Badge>
  );
}
