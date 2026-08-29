import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import { LADDER_LABELS } from '@/lib/learning';

// Colour climbs with the ladder (concepts/mastery/README §ladder): grey Learned
// → blue Can-mark → amber Backtested → green Live-ready.
//
// No `dark:` variants: the ladder tokens already carry their own dark step, so
// the mode is handled once in index.css rather than at every use site.
const LADDER_STYLES: Record<number, string> = {
  1: 'bg-ladder-1-muted text-ladder-1',
  2: 'bg-ladder-2-muted text-ladder-2',
  3: 'bg-ladder-3-muted text-ladder-3',
  4: 'bg-ladder-4-muted text-ladder-4',
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
