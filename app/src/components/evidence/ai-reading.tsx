import { useState } from 'react';
import { ChevronDown, Eye, Loader2, ScanLine } from 'lucide-react';
import { cn } from '@/lib/utils';
import { checkedKeys, latestSelfCheck } from '@/lib/rubrics';
import { RubricText } from '@/components/evidence/rubric-text';
import {
  ITEM_EVIDENCE_LABELS,
  OBSERVATION_LABELS,
  SUBJECT_MATTER_LABELS,
  aiDisagreements,
  aiErrorReason,
  aiFindings,
  aiItems,
  latestAiGrade,
} from '@/lib/ai-grade';
import type { EvidenceAsset } from '@/types/api';

/**
 * The AI vision SECOND READER — tier 3 (learning-enforcement.md §2).
 *
 * This component is under a constraint the other two tiers are not: it must be
 * prevented from *looking* authoritative. The deterministic tier blocks and the
 * self-check sets the rep's bar; this one does neither, so every affordance here
 * is deliberately quieter than `SelfCheck`'s — muted text, no verdict colour, no
 * pass/fail word, and an explicit "advisory" label on the face of it.
 *
 * WHY NO PERCENTAGE. The grade carries an advisory `score`, and rendering it as
 * "75%" beside the self-check's own "75%" would read as a competing mark on the
 * work. Counts ("could see 3 of 4") say the same thing without impersonating a
 * grade. Invariant 7 — the advisory score never writes `confidence` or
 * `ladder_stage` — is enforced server-side; not showing it as a score is the
 * same commitment kept at the surface.
 *
 * WHAT IT MAY SAY. Only visibility, never correctness: MeasureBench puts
 * frontier vision models at ~19-30% on reading precise values off a chart axis,
 * so "is this swing at the right price" is a question this reader is not asked
 * and the schema gives it nowhere to answer.
 */
export function AiReading({ asset, className }: { asset: EvidenceAsset; className?: string }) {
  const [open, setOpen] = useState(false);
  const grade = latestAiGrade(asset);

  // No row at all — grading is switched off, or this subject has no bar to read
  // against. Silence is right: an empty panel would imply something is missing.
  if (!grade) return null;

  if (grade.state === 'pending') {
    return (
      <p
        className={cn('flex items-center gap-1.5 text-[11px] text-muted-foreground', className)}
        data-testid="ai-reading-pending"
      >
        <Loader2 className="h-3 w-3 animate-spin" />
        Second reader is looking at this…
      </p>
    );
  }

  if (grade.state === 'ungraded') {
    // Honest about its own failure. An unread capture is NOT a mark against the
    // work, and the reps were never in question either way.
    const reason = aiErrorReason(grade);
    return (
      <p
        className={cn('text-[11px] text-muted-foreground', className)}
        data-testid="ai-reading-ungraded"
      >
        Second reader couldn&rsquo;t read this one — your reps are unaffected.
        {reason && <span className="ml-1 opacity-70">({reason})</span>}
      </p>
    );
  }

  const findings = aiFindings(grade);
  const items = aiItems(grade);
  if (!findings || items.length === 0) return null;

  const seen = items.filter((i) => i.visible_evidence === 'clearly_present').length;
  const checked = checkedKeys(asset);
  const hasSelfCheck = latestSelfCheck(asset) !== null;
  const disagreements = aiDisagreements(grade, checked, hasSelfCheck);
  const observations = findings.observations ?? [];

  return (
    <div className={cn('space-y-1', className)} data-testid="ai-reading">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1.5 text-[11px] text-muted-foreground hover:text-foreground"
        data-testid="ai-reading-toggle"
        aria-expanded={open}
      >
        <ScanLine className="h-3 w-3 shrink-0" />
        <span>
          Second reader (advisory) · could see {seen} of {items.length}
        </span>
        {disagreements.length > 0 && (
          <span className="text-warning" data-testid="ai-reading-disagree-count">
            · {disagreements.length} differ{disagreements.length === 1 ? 's' : ''} from your check
          </span>
        )}
        <ChevronDown className={cn('h-3 w-3 shrink-0 transition-transform', open && 'rotate-180')} />
      </button>

      {open && (
        <div
          className="space-y-2 rounded-md border border-dashed bg-muted/20 p-2.5"
          data-testid="ai-reading-panel"
        >
          <p className="text-[11px] text-muted-foreground">
            An AI read this capture as a second opinion. It reports only what it could{' '}
            <em>see</em>, never whether your work is right — and it cannot change your reps,
            your confidence or your stage.
          </p>

          {findings.subject_matter && (
            <p className="text-[11px] text-muted-foreground" data-testid="ai-reading-subject">
              Read as {SUBJECT_MATTER_LABELS[findings.subject_matter] ?? findings.subject_matter}
              {findings.annotation_density && ` · ${findings.annotation_density} marking`}
            </p>
          )}

          <ul className="space-y-1">
            {items.map((item) => {
              const ticked = checked.has(item.item_key);
              const differs =
                hasSelfCheck &&
                ((ticked && item.visible_evidence === 'not_visible') ||
                  (!ticked && item.visible_evidence === 'clearly_present'));
              return (
                <li
                  key={item.item_key}
                  className="flex items-start gap-2 text-[11px] leading-snug"
                  data-testid="ai-reading-item"
                >
                  <Eye
                    className={cn(
                      'mt-0.5 h-3 w-3 shrink-0',
                      item.visible_evidence === 'clearly_present'
                        ? 'text-muted-foreground'
                        : 'text-muted-foreground/40'
                    )}
                  />
                  <span className="min-w-0 flex-1 text-muted-foreground">
                    <span className={cn(differs && 'text-warning')}>
                      {ITEM_EVIDENCE_LABELS[item.visible_evidence]}
                    </span>
                    {' — '}
                    {/* The wiki's own emphasis, rendered as emphasis. The corpus
                        carries `*actual*` and `**two**`; printing item.text raw
                        showed the user asterisks in their own course notes. */}
                    <RubricText text={item.text} />
                  </span>
                </li>
              );
            })}
          </ul>

          {observations.length > 0 && (
            <p className="text-[11px] text-muted-foreground" data-testid="ai-reading-observations">
              Notes: {observations.map((o) => OBSERVATION_LABELS[o] ?? o).join(' · ')}
            </p>
          )}

          {disagreements.length > 0 && (
            <div
              className="space-y-1 border-t pt-2 text-[11px]"
              data-testid="ai-reading-disagreements"
            >
              <p className="font-medium text-warning">
                Worth a look — you and the reader saw this differently
              </p>
              {disagreements.map((d) => (
                <p key={d.item_key} className="text-muted-foreground">
                  {d.kind === 'unseen' ? (
                    <>
                      You ticked it; the reader couldn&rsquo;t see it. Often the capture just
                      doesn&rsquo;t show it —{' '}
                    </>
                  ) : (
                    <>The reader saw it clearly; you didn&rsquo;t tick it — </>
                  )}
                  <span className="italic">
                    <RubricText text={d.text} />
                  </span>
                </p>
              ))}
              <p className="text-muted-foreground/80">
                Neither of you is scored on this. Your check is what counts.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
