import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { lookupRule } from '@/lib/runner';
import { cn } from '@/lib/utils';

/**
 * An [R##] reference on a checklist item, opening the CANONICAL rule text.
 *
 * The text is projected verbatim from concepts/mastery/aura/rules.md — it is
 * never paraphrased here. dOoMeR's own hedges (`soft` / `flagged`) travel with
 * it, because hardening a stated preference into a confident instruction is
 * this workstream's worst available failure.
 */
export function RuleChip({ id }: { id: string }) {
  const rule = lookupRule(id);

  if (!rule) {
    // A reference the projection could not resolve renders inert, never as a
    // confident-looking chip that says nothing when tapped.
    return (
      <span className="rounded bg-muted px-1 py-0.5 font-mono text-[10px] text-muted-foreground">
        {id}
      </span>
    );
  }

  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          className={cn(
            'rounded px-1 py-0.5 font-mono text-[10px] transition-colors',
            'bg-primary/10 text-primary hover:bg-primary/20',
            (rule.soft || rule.flagged) && 'ring-1 ring-amber-500/50'
          )}
        >
          {id}
          {(rule.soft || rule.flagged) && <span className="ml-0.5">*</span>}
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-[min(22rem,calc(100vw-2rem))] text-sm" align="start">
        <p className="text-[10px] uppercase tracking-wide text-muted-foreground">
          {rule.group || rule.section}
        </p>
        <p className="mt-1 font-mono text-xs text-primary">{rule.id}</p>
        <p className="mt-1 leading-snug">{stripMarkdown(rule.text)}</p>
        {(rule.soft || rule.flagged) && (
          <p className="mt-2 rounded bg-amber-500/10 p-1.5 text-[11px] leading-snug text-amber-600 dark:text-amber-400">
            {rule.soft && rule.flagged
              ? 'dOoMeR states this as a preference AND flags his own uncertainty.'
              : rule.soft
                ? 'Stated as a preference, not a hard rule.'
                : 'dOoMeR flags his own uncertainty here.'}{' '}
            Preserved as stated — not hardened.
          </p>
        )}
      </PopoverContent>
    </Popover>
  );
}

/** Flatten the wiki's inline markdown for a compact popover (no link chrome). */
function stripMarkdown(s: string): string {
  return s
    .replace(/\[\[([^\]|]+)\|([^\]]+)\]\]/g, '$2')
    .replace(/\[\[([^\]]+)\]\]/g, (_m, t: string) => t.split('/').pop() ?? t)
    .replace(/\*\*(.+?)\*\*/g, '$1')
    .replace(/\*(.+?)\*/g, '$1')
    .replace(/`(.+?)`/g, '$1')
    .trim();
}

export { stripMarkdown };
