import { Link } from 'react-router-dom';
import { Check, ChevronRight, Circle, Info } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import { GATE_SOURCES, useUpdateAttestation } from '@/lib/gate';
import { ENTRY_MODEL_LABELS } from '@/lib/journal';
import type {
  EntryModel,
  GateAttestation,
  GateCorroboration,
  GateRequirement,
  ModelReadiness,
} from '@/types/api';

function MetIcon({ met }: { met: boolean }) {
  return met ? (
    <Check className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600 dark:text-emerald-400" />
  ) : (
    <Circle className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
  );
}

/** A concept or evidence requirement row (read-only — these are earned, not ticked). */
function RequirementRow({ req }: { req: GateRequirement }) {
  const stageLink =
    req.concept_track && req.concept_stage
      ? `/path/${req.concept_track}/${req.concept_stage}`
      : null;
  return (
    <li
      data-testid="gate-requirement"
      data-source={req.source}
      data-met={req.met ? 'true' : 'false'}
      className="flex gap-2 py-1.5 text-sm"
    >
      <MetIcon met={req.met} />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-baseline gap-x-2">
          <span className={cn(!req.met && 'text-foreground')}>{req.label}</span>
          {req.concept_code && (
            <span className="text-[11px] text-muted-foreground tabular-nums">{req.concept_code}</span>
          )}
        </div>
        {req.detail && (
          <p className={cn('text-xs', req.met ? 'text-muted-foreground' : 'text-amber-600 dark:text-amber-400')}>
            {req.detail}
          </p>
        )}
      </div>
      {!req.met && stageLink && (
        <Link
          to={stageLink}
          className="shrink-0 self-center text-xs text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
        >
          work it <ChevronRight className="inline h-3 w-3" />
        </Link>
      )}
    </li>
  );
}

/** The (c) items — the only ticks on this page, and they can never clear the gate
 * on their own. Revocable; each records what it claims in plain language. */
function AttestationRow({ attestation }: { attestation: GateAttestation }) {
  const update = useUpdateAttestation();
  return (
    <li
      data-testid="gate-attestation"
      data-item={attestation.item}
      data-attested={attestation.attested ? 'true' : 'false'}
      className="flex gap-2 py-2 text-sm"
    >
      <Checkbox
        id={`attest-${attestation.item}`}
        checked={attestation.attested}
        disabled={update.isPending}
        onCheckedChange={(checked) =>
          update.mutate({ item: attestation.item, attested: checked === true })
        }
        className="mt-0.5"
      />
      <label htmlFor={`attest-${attestation.item}`} className="min-w-0 flex-1 cursor-pointer">
        <span>{attestation.label}</span>
        <span className="ml-2 text-[11px] uppercase tracking-wide text-muted-foreground">
          self-attested
        </span>
        {attestation.note && (
          <p className="text-xs text-muted-foreground">{attestation.note}</p>
        )}
      </label>
    </li>
  );
}

/** The objective journal record, shown next to the attestations so a self-attest
 * is made in the face of the facts. Deliberately not a gate. */
function CorroborationStrip({ corroboration }: { corroboration: GateCorroboration }) {
  const c = corroboration;
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1 rounded-md border border-dashed p-2.5 text-xs text-muted-foreground">
      <Info className="h-3.5 w-3.5" />
      <span>
        <span className="font-medium tabular-nums text-foreground">{c.entries_logged}</span>{' '}
        {c.entries_logged === 1 ? 'entry' : 'entries'} logged
      </span>
      <span>
        across <span className="font-medium tabular-nums text-foreground">{c.journaling_days}</span>{' '}
        {c.journaling_days === 1 ? 'day' : 'days'}
      </span>
      <span>
        <span className="font-medium tabular-nums text-foreground">{c.backtest_entries}</span> backtest /{' '}
        <span className="font-medium tabular-nums text-foreground">{c.live_entries}</span> live
      </span>
      <span>last: {c.last_entry_date ?? '—'}</span>
    </div>
  );
}

/**
 * GateChecklist — the Readiness-to-Live Gate for ONE model, grouped by its three
 * evidence sources. Concept + evidence rows are earned (read-only); only the four
 * behavioural items are tickable, and ticking them can never clear a model whose
 * ladder or expectancy is short.
 */
export function GateChecklist({
  model,
  attestations,
  corroboration,
}: {
  model: ModelReadiness;
  attestations: GateAttestation[];
  corroboration: GateCorroboration;
}) {
  const label = ENTRY_MODEL_LABELS[model.entry_model as EntryModel] ?? model.entry_model;

  return (
    <Card data-testid="gate-checklist" data-model={model.entry_model}>
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center gap-2 text-base">
          <span>{label} — Readiness-to-Live Gate</span>
          <Badge
            variant={model.cleared ? 'default' : 'outline'}
            className={cn(
              'text-[11px]',
              model.cleared && 'border-transparent bg-emerald-600 text-white hover:bg-emerald-600'
            )}
          >
            {model.cleared ? 'cleared' : 'blocked'}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-5">
        {GATE_SOURCES.map((source) => {
          const reqs = model.requirements.filter((r) => r.source === source.key);
          if (!reqs.length) return null;
          const met = reqs.every((r) => r.met);
          const metCount = reqs.filter((r) => r.met).length;
          return (
            <section key={source.key} data-testid="gate-group" data-group={source.key}>
              <div className="mb-1 flex items-baseline justify-between gap-2">
                <h3 className="text-sm font-semibold">{source.title}</h3>
                <span
                  className={cn(
                    'text-xs tabular-nums',
                    met ? 'text-emerald-600 dark:text-emerald-400' : 'text-muted-foreground'
                  )}
                >
                  {metCount}/{reqs.length}
                </span>
              </div>
              <p className="mb-2 text-xs text-muted-foreground">{source.blurb}</p>

              {source.key === 'behaviour' ? (
                <>
                  <CorroborationStrip corroboration={corroboration} />
                  <ul className="mt-1 divide-y">
                    {attestations.map((a) => (
                      <AttestationRow key={a.item} attestation={a} />
                    ))}
                  </ul>
                </>
              ) : (
                <ul className="divide-y">
                  {reqs.map((r) => (
                    <RequirementRow key={r.key} req={r} />
                  ))}
                </ul>
              )}
            </section>
          );
        })}

        <p className="border-t pt-3 text-xs text-muted-foreground">
          This verdict is computed on every read from your concept ladder, your backtest expectancy, and the
          four attestations — there is no way to mark a model cleared. Live trading starts{' '}
          <span className="font-medium">small</span> even after the gate clears: it certifies readiness to
          begin, not to size up.
        </p>
      </CardContent>
    </Card>
  );
}
