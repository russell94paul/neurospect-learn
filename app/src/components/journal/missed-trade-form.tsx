import { useState } from 'react';
import { Controller, useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Loader2, Plus, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { cn } from '@/lib/utils';
import { ENTRY_MODELS, ENTRY_MODEL_LABELS, SESSION_LABELS } from '@/lib/journal';
import {
  HESITATION_TAG_SUGGESTIONS,
  HYPOTHETICAL_OUTCOME_LABELS,
  MISS_TYPES,
  MISS_TYPE_LABELS,
} from '@/lib/missed-trades';
import type { MissedTrade, MissedTradeIn } from '@/types/api';

const NONE = '__none__';

const numStr = z
  .string()
  .optional()
  .refine((v) => !v || v.trim() === '' || !Number.isNaN(Number(v)), 'Must be a number');

const schema = z.object({
  entry_date: z.string().min(1, 'Date is required'),
  instrument: z.string().min(1, 'Instrument is required').max(20),
  entry_model: z.enum([
    'consolidation', 'expansion_retracement', 'reversal_raid_on_stops', 'london',
    'model_2022_ote', 'daily_bias', 'smt_confirmation', 'unified',
  ]),
  miss_type: z.enum(['almost_took', 'hesitated', 'canceled']),
  session: z.string().optional(),
  reason: z.string().optional(),
  planned_entry: numStr,
  planned_stop: numStr,
  planned_target: numStr,
  rr_planned: numStr,
  hypothetical_outcome: z.string().optional(),
  hypothetical_r: numStr,
  narrative: z.string().optional(),
  notes: z.string().optional(),
});

type FormValues = z.infer<typeof schema>;

const s = (n: number | null | undefined) => (n == null ? '' : String(n));
const e = (v: string | null | undefined) => v ?? NONE;

function toDefaults(d?: MissedTrade): FormValues {
  return {
    entry_date: d?.entry_date ?? new Date().toISOString().slice(0, 10),
    instrument: d?.instrument ?? '',
    entry_model: d?.entry_model ?? 'unified',
    miss_type: d?.miss_type ?? 'canceled',
    session: e(d?.session),
    reason: d?.reason ?? '',
    planned_entry: s(d?.planned_entry),
    planned_stop: s(d?.planned_stop),
    planned_target: s(d?.planned_target),
    rr_planned: s(d?.rr_planned),
    hypothetical_outcome: e(d?.hypothetical_outcome),
    hypothetical_r: s(d?.hypothetical_r),
    narrative: d?.narrative ?? '',
    notes: d?.notes ?? '',
  };
}

/** The missed / canceled trade form (Phase 6b). Lighter than the executed-trade
 * journal on purpose: what the setup was, why you didn't take it, and what it
 * would have done in R. */
export function MissedTradeForm({
  defaults,
  onSubmit,
  isSaving,
  saveError,
  submitLabel = 'Save',
}: {
  defaults?: MissedTrade;
  onSubmit: (body: MissedTradeIn) => void;
  isSaving?: boolean;
  saveError?: string | null;
  submitLabel?: string;
}) {
  const {
    register,
    handleSubmit,
    control,
    watch,
    setValue,
    formState: { errors },
  } = useForm<FormValues>({ resolver: zodResolver(schema), defaultValues: toDefaults(defaults) });

  const [tags, setTags] = useState<string[]>(defaults?.hesitation_tags ?? []);
  const missType = watch('miss_type');

  const num = (v?: string) => (v && v.trim() !== '' ? Number(v) : null);
  const enumOrNull = (v?: string) => (v && v !== NONE ? v : null);

  function submit(v: FormValues) {
    onSubmit({
      entry_date: v.entry_date,
      instrument: v.instrument,
      entry_model: v.entry_model,
      miss_type: v.miss_type,
      session: enumOrNull(v.session) as MissedTradeIn['session'],
      reason: v.reason?.trim() || null,
      hesitation_tags: tags.length ? tags : null,
      planned_entry: num(v.planned_entry),
      planned_stop: num(v.planned_stop),
      planned_target: num(v.planned_target),
      rr_planned: num(v.rr_planned),
      hypothetical_outcome: enumOrNull(
        v.hypothetical_outcome
      ) as MissedTradeIn['hypothetical_outcome'],
      hypothetical_r: num(v.hypothetical_r),
      narrative: v.narrative?.trim() || null,
      notes: v.notes?.trim() || null,
    });
  }

  return (
    <form onSubmit={handleSubmit(submit)} className="space-y-6" data-testid="missed-trade-form">
      {/* Miss type — the headline classification; `canceled` is Dante's category. */}
      <div className="space-y-1.5">
        <Label>What happened</Label>
        <div className="flex flex-wrap gap-0.5 rounded-md border p-0.5" role="group" aria-label="Miss type">
          {MISS_TYPES.map((m) => (
            <button
              key={m}
              type="button"
              aria-pressed={missType === m}
              onClick={() => setValue('miss_type', m, { shouldValidate: true })}
              className={cn(
                'rounded px-3 py-1.5 text-sm font-medium transition-colors',
                missType === m
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:text-foreground'
              )}
            >
              {MISS_TYPE_LABELS[m]}
            </button>
          ))}
        </div>
        <p className="text-xs text-muted-foreground">
          Logging the ones you didn't take is where the hidden edge is — a canceled order that would
          have lost is as useful a finding as a missed runner.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Date" error={errors.entry_date?.message}>
          <Input type="date" {...register('entry_date')} />
        </Field>
        <Field label="Instrument" error={errors.instrument?.message}>
          <Input placeholder="NQ, ES, EURUSD…" aria-label="Instrument" {...register('instrument')} />
        </Field>
        <SelectField
          control={control}
          name="entry_model"
          label="Entry model"
          placeholder="Select model"
          allowNone={false}
          options={ENTRY_MODELS.map((m) => [m, ENTRY_MODEL_LABELS[m]])}
        />
        <SelectField
          control={control}
          name="session"
          label="Session"
          placeholder="—"
          options={Object.entries(SESSION_LABELS)}
        />
      </div>

      <Field label="Why you didn't take it">
        <Input placeholder="e.g. pulled the order when price went vertical" {...register('reason')} />
      </Field>

      <TagField
        label="Hesitation tags"
        note="Structured so the recurring one surfaces in the opportunity-cost view."
        tags={tags}
        setTags={setTags}
        suggestions={HESITATION_TAG_SUGGESTIONS}
      />

      <div className="space-y-3">
        <p className="text-xs text-muted-foreground">
          The plan you didn't take, and what price actually did. Positive R = a missed winner;
          negative R = standing down protected you.
        </p>
        <div className="grid gap-4 sm:grid-cols-4">
          <NumField label="Planned entry" reg={register('planned_entry')} err={errors.planned_entry?.message} />
          <NumField label="Planned stop" reg={register('planned_stop')} err={errors.planned_stop?.message} />
          <NumField label="Planned target" reg={register('planned_target')} err={errors.planned_target?.message} />
          <NumField label="Planned R:R" reg={register('rr_planned')} err={errors.rr_planned?.message} />
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <SelectField
            control={control}
            name="hypothetical_outcome"
            label="Would have…"
            placeholder="—"
            options={Object.entries(HYPOTHETICAL_OUTCOME_LABELS)}
          />
          <NumField
            label="Hypothetical R"
            reg={register('hypothetical_r')}
            err={errors.hypothetical_r?.message}
          />
        </div>
      </div>

      <Field label="What you saw (the thesis you didn't act on)">
        <Textarea rows={3} placeholder="The read you had before you stood down…" {...register('narrative')} />
      </Field>
      <Field label="Notes">
        <Textarea rows={3} placeholder="Post-review reflection…" {...register('notes')} />
      </Field>

      {saveError && <p className="text-sm text-destructive">{saveError}</p>}

      <Button type="submit" disabled={isSaving}>
        {isSaving && <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />}
        {submitLabel}
      </Button>
    </form>
  );
}

// ---------------------------------------------------------------------------
// Field helpers (kept local, mirroring journal-form.tsx)
// ---------------------------------------------------------------------------

function Field({ label, error, children }: { label: string; error?: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <Label>{label}</Label>
      {children}
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  );
}

function NumField({
  label,
  reg,
  err,
}: {
  label: string;
  reg: ReturnType<ReturnType<typeof useForm>['register']>;
  err?: string;
}) {
  return (
    <div className="space-y-1.5">
      <Label>{label}</Label>
      <Input type="number" step="any" inputMode="decimal" className="tabular-nums" aria-label={label} {...reg} />
      {err && <p className="text-xs text-destructive">{err}</p>}
    </div>
  );
}

/* eslint-disable @typescript-eslint/no-explicit-any */
function SelectField({
  control, name, label, options, placeholder, allowNone = true,
}: {
  control: any; name: any; label: string; options: [string, string][]; placeholder?: string; allowNone?: boolean;
}) {
  return (
    <div className="space-y-1.5">
      <Label>{label}</Label>
      <Controller
        control={control}
        name={name}
        render={({ field }) => (
          <Select value={field.value ?? NONE} onValueChange={field.onChange}>
            <SelectTrigger aria-label={label}>
              <SelectValue placeholder={placeholder} />
            </SelectTrigger>
            <SelectContent>
              {allowNone && <SelectItem value={NONE}>—</SelectItem>}
              {options.map(([v, l]) => (
                <SelectItem key={v} value={v}>{l}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
      />
    </div>
  );
}
/* eslint-enable @typescript-eslint/no-explicit-any */

function TagField({
  label, note, tags, setTags, suggestions,
}: {
  label: string; note?: string; tags: string[]; setTags: (t: string[]) => void; suggestions?: string[];
}) {
  const [draft, setDraft] = useState('');
  const add = (value?: string) => {
    const t = (value ?? draft).trim();
    if (t && !tags.includes(t)) {
      setTags([...tags, t]);
      setDraft('');
    }
  };
  return (
    <div className="space-y-1.5">
      <Label>{label}</Label>
      {note && <p className="text-xs text-muted-foreground">{note}</p>}
      <div className="flex items-center gap-2">
        <Input
          value={draft}
          onChange={(ev) => setDraft(ev.target.value)}
          onKeyDown={(ev) => {
            if (ev.key === 'Enter') {
              ev.preventDefault();
              add();
            }
          }}
          placeholder="e.g. pulled_on_spike"
          className="max-w-xs"
          aria-label={`Add ${label}`}
        />
        <Button type="button" variant="outline" size="sm" onClick={() => add()} disabled={!draft.trim()}>
          <Plus className="mr-1 h-3.5 w-3.5" /> Add
        </Button>
      </div>
      {suggestions && suggestions.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {suggestions
            .filter((sug) => !tags.includes(sug))
            .map((sug) => (
              <button
                key={sug}
                type="button"
                onClick={() => add(sug)}
                className="rounded border border-dashed px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground hover:border-primary/40 hover:text-foreground"
              >
                + {sug}
              </button>
            ))}
        </div>
      )}
      {tags.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {tags.map((t) => (
            <span key={t} className="inline-flex items-center gap-1 rounded-md border bg-muted px-2 py-0.5 font-mono text-xs">
              {t}
              <button
                type="button"
                onClick={() => setTags(tags.filter((x) => x !== t))}
                aria-label={`Remove ${t}`}
                className="text-muted-foreground hover:text-destructive"
              >
                <X className="h-3 w-3" />
              </button>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
