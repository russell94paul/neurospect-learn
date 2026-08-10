import { useMemo, useState } from 'react';
import { AlertTriangle, CheckCircle2, ClipboardCheck, Hand, Loader2, Wrench } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { cn } from '@/lib/utils';
import { checkedKeys, latestSelfCheck, useSelfCheck } from '@/lib/rubrics';
import { RubricText } from '@/components/evidence/rubric-text';
import type { EvidenceAsset, Rubric, RubricItem } from '@/types/api';

/**
 * The SELF-CHECK — tier 2 of the design's three grading tiers, and the tier that
 * makes a rep "graded" (concepts/architecture/learning-enforcement.md §2).
 *
 * Every line of text here comes from the wiki. The component renders
 * `rubric.items[].text` verbatim (stripping only markdown emphasis for display);
 * it never phrases a criterion of its own, because a rubric authored in the app
 * would drift from the curriculum it exists to enforce.
 *
 * AN UNCHECKED CAPTURE STILL COUNTS ITS REPS. A self-check cannot retract one —
 * `reps` feeds the stage exit bars and the Gate, so retraction would make
 * progress non-monotonic. A partial check therefore records `flagged` plus the
 * specific unticked items, and the unchecked backlog is SURFACED (below) rather
 * than deducted.
 */

function VariantIcon({ variant }: { variant: RubricItem['variant'] }) {
  if (variant === 'hand') return <Hand className="h-3 w-3 shrink-0 text-muted-foreground" aria-label="Hand-marked" />;
  if (variant === 'tool') return <Wrench className="h-3 w-3 shrink-0 text-muted-foreground" aria-label="Tool-assisted" />;
  return null;
}

export function SelfCheck({
  asset,
  rubrics,
  className,
}: {
  asset: EvidenceAsset;
  rubrics: Rubric[];
  className?: string;
}) {
  const existing = latestSelfCheck(asset);
  const [open, setOpen] = useState(false);
  // A concept's bar is the union of its drills' bars, so more than one rubric can
  // apply. A grade records ONE `rubric_slug`, so the user picks which bar.
  const [slug, setSlug] = useState(() => existing?.rubric_slug ?? rubrics[0]?.slug ?? '');
  const rubric = rubrics.find((r) => r.slug === slug) ?? rubrics[0];
  const [checked, setChecked] = useState<Set<string>>(() => checkedKeys(asset));
  const submit = useSelfCheck();

  const items = rubric?.items ?? [];
  const met = useMemo(() => items.filter((i) => checked.has(i.item_key)).length, [items, checked]);

  if (!rubric || items.length === 0) return null;

  const staleVersion =
    existing?.rubric_version != null && existing.rubric_version !== rubric.version;

  function toggle(key: string) {
    setChecked((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  if (!open) {
    return (
      <div className={cn('flex flex-wrap items-center gap-2', className)}>
        <Button
          type="button"
          size="sm"
          variant={existing ? 'outline' : 'default'}
          className="h-7 text-xs"
          onClick={() => setOpen(true)}
          data-testid="self-check-open"
        >
          <ClipboardCheck className="mr-1.5 h-3.5 w-3.5" />
          {existing ? 'Review your check' : 'Check against the bar'}
        </Button>
        {existing ? (
          <span
            className={cn(
              'flex items-center gap-1 text-xs',
              existing.state === 'passed'
                ? 'text-emerald-600 dark:text-emerald-500'
                : 'text-amber-600 dark:text-amber-500'
            )}
            data-testid="self-check-state"
          >
            {existing.state === 'passed' ? (
              <CheckCircle2 className="h-3.5 w-3.5" />
            ) : (
              <AlertTriangle className="h-3.5 w-3.5" />
            )}
            {existing.state === 'passed' ? 'Meets the bar' : 'Partly met'}
            {existing.score != null && ` · ${Math.round(existing.score)}%`}
          </span>
        ) : (
          // Surfaced, never deducted: the reps already count.
          <span className="text-xs text-muted-foreground" data-testid="self-check-pending">
            not checked yet — the reps still count
          </span>
        )}
      </div>
    );
  }

  return (
    <div
      className={cn('space-y-2 rounded-md border bg-muted/30 p-2.5', className)}
      data-testid="self-check-panel"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-xs font-medium">
          {rubric.drill_ref}&rsquo;s own bar{' '}
          <span className="font-normal text-muted-foreground">
            · {met}/{items.length} met · v{rubric.version}
          </span>
        </span>
        {rubrics.length > 1 && (
          <select
            value={slug}
            onChange={(e) => {
              setSlug(e.target.value);
              setChecked(new Set());
            }}
            aria-label="Which drill's bar to check against"
            data-testid="self-check-rubric-select"
            className="h-6 rounded border bg-background px-1 text-xs"
          >
            {rubrics.map((r) => (
              <option key={r.slug} value={r.slug}>
                {r.drill_ref}
              </option>
            ))}
          </select>
        )}
      </div>

      {rubric.source_ref && (
        <p className="text-[11px] text-muted-foreground">
          {rubric.drill_ref} {rubric.source_ref} — from{' '}
          <span className="font-mono">{rubric.source_path}</span>
        </p>
      )}

      {staleVersion && (
        <p className="text-[11px] text-amber-600 dark:text-amber-500" data-testid="self-check-stale">
          Your last check was against v{existing?.rubric_version}; this bar is now v{rubric.version}.
        </p>
      )}

      <ul className="space-y-1.5">
        {items.map((item) => (
          <li key={item.item_key} className="flex items-start gap-2">
            <Checkbox
              id={`sc-${asset.id}-${item.item_key}`}
              checked={checked.has(item.item_key)}
              onCheckedChange={() => toggle(item.item_key)}
              className="mt-0.5"
              data-testid="self-check-item"
            />
            <label
              htmlFor={`sc-${asset.id}-${item.item_key}`}
              className="flex-1 cursor-pointer text-xs leading-snug"
            >
              <span className="mr-1 inline-flex align-middle">
                <VariantIcon variant={item.variant} />
              </span>
              <RubricText text={item.text} />
            </label>
          </li>
        ))}
      </ul>

      {submit.isError && (
        <p className="flex items-start gap-1.5 text-xs text-destructive" data-testid="self-check-error">
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          {(submit.error as Error).message}
        </p>
      )}

      <div className="flex items-center gap-2">
        <Button
          type="button"
          size="sm"
          className="h-7 text-xs"
          disabled={submit.isPending}
          data-testid="self-check-submit"
          onClick={() =>
            submit.mutate(
              {
                evidenceId: asset.id,
                rubricSlug: rubric.slug,
                checkedItemKeys: items.filter((i) => checked.has(i.item_key)).map((i) => i.item_key),
              },
              { onSuccess: () => setOpen(false) }
            )
          }
        >
          {submit.isPending && <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />}
          Record this check
        </Button>
        <Button
          type="button"
          size="sm"
          variant="ghost"
          className="h-7 text-xs"
          onClick={() => setOpen(false)}
        >
          Cancel
        </Button>
        <span className="text-[11px] text-muted-foreground">
          An honest partial is recorded as such — it never removes a rep.
        </span>
      </div>
    </div>
  );
}
