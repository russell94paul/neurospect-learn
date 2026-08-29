import { ChevronDown, Flag } from 'lucide-react';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { RuleChip, stripMarkdown } from '@/components/runner/rule-chip';
import { runnerData, type RunnerSection } from '@/lib/runner';
import { cn } from '@/lib/utils';

/**
 * The reference tabs — setup steps, chart markup, playbook mapping.
 *
 * These are projections of the three wiki pages authored in S1. They are read
 * material, not tick state: the runner's *state* is the checklist, and adding a
 * second set of checkboxes here would invent a second, competing record of what
 * you did.
 */
export function ReferenceSections({ sections }: { sections: RunnerSection[] }) {
  return (
    <div className="space-y-2">
      {sections.map((s, i) => (
        <SectionBlock key={s.title} section={s} defaultOpen={i <= 1} />
      ))}
    </div>
  );
}

function SectionBlock({ section, defaultOpen }: { section: RunnerSection; defaultOpen: boolean }) {
  const empty =
    section.items.length === 0 && section.tables.length === 0 && section.paras.length === 0;
  if (empty) return null;

  return (
    <Collapsible defaultOpen={defaultOpen}>
      <div className="rounded-lg border bg-card">
        <CollapsibleTrigger className="flex w-full items-center gap-2 p-2.5 text-left">
          <span className="min-w-0 flex-1 text-[13px] font-semibold leading-tight">
            {stripMarkdown(section.title)}
          </span>
          {section.items.length > 0 && (
            <span className="shrink-0 font-mono text-[10px] text-muted-foreground">
              {section.items.length}
            </span>
          )}
          <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" />
        </CollapsibleTrigger>
        <CollapsibleContent>
          <div className="space-y-2 border-t p-2.5">
            {section.paras.map((p, i) => (
              <p key={i} className="text-[12px] leading-snug text-muted-foreground">
                {stripMarkdown(p)}
              </p>
            ))}

            {section.items.length > 0 && (
              <ol className="space-y-1.5">
                {section.items.map((item, i) => (
                  <li key={i} className="flex gap-2">
                    <span className="mt-0.5 font-mono text-[10px] text-muted-foreground">
                      {String(i + 1).padStart(2, '0')}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block text-[12px] leading-snug">
                        {stripMarkdown(
                          item.text.replace(/\*\*\[[^\]]+\]\*\*/g, '').replace(/←\s*hard gate/i, '')
                        )}
                      </span>
                      <span className="mt-0.5 flex flex-wrap items-center gap-1">
                        {item.hardGate && (
                          <span className="rounded bg-warning-emphasis/20 px-1 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-warning">
                            hard gate
                          </span>
                        )}
                        {item.ruleRefs.map((r) => (
                          <RuleChip key={r} id={r} />
                        ))}
                      </span>
                    </span>
                  </li>
                ))}
              </ol>
            )}

            {/* Wide content scrolls inside its own box — the page body must never
                scroll horizontally at a third-of-a-screen width. */}
            {section.tables.map((t, i) => (
              <div key={i} className="-mx-1 overflow-x-auto">
                <table className="w-full min-w-[22rem] border-collapse text-[11px]">
                  <thead>
                    <tr>
                      {t.headers.map((h, j) => (
                        <th
                          key={j}
                          className="border-b px-1.5 py-1 text-left font-semibold text-muted-foreground"
                        >
                          {stripMarkdown(h)}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {t.rows.map((row, j) => (
                      <tr key={j} className="align-top">
                        {row.map((cell, k) => (
                          <td key={k} className="border-b border-border/50 px-1.5 py-1 leading-snug">
                            {cell.includes('`') ? (
                              <code className="rounded bg-muted px-1 py-0.5">
                                {stripMarkdown(cell)}
                              </code>
                            ) : (
                              stripMarkdown(cell)
                            )}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ))}
          </div>
        </CollapsibleContent>
      </div>
    </Collapsible>
  );
}

/**
 * rules.md §"Divergences & open flags (do not silently resolve)".
 *
 * These render as OPEN FLAGS, never resolved into a confident checkbox. The
 * workstream's stated worst-available failure is flattening a known divergence
 * to make a tick render, so they get their own always-visible surface.
 */
export function OpenFlags({ className }: { className?: string }) {
  return (
    <div className={cn('rounded-lg border border-warning-emphasis/40 bg-warning-emphasis/5 p-3', className)}>
      <div className="flex items-center gap-1.5">
        <Flag className="h-3.5 w-3.5 text-warning" />
        <h3 className="text-[13px] font-semibold">Open flags — do not silently resolve</h3>
      </div>
      <p className="mt-1 text-[11px] leading-snug text-muted-foreground">
        Live divergences in the model itself. The runner shows them; it does not pick a side to make
        a checkbox work.
      </p>
      <ul className="mt-2 space-y-1.5">
        {runnerData.divergences.map((d, i) => (
          <li key={i} className="text-[12px] leading-snug">
            {d.label && <span className="font-semibold">{d.label}: </span>}
            <span className="text-muted-foreground">{stripMarkdown(d.text)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
