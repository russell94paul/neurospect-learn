import { useState } from 'react';
import { Controller, useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Loader2, Plus, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Checkbox } from '@/components/ui/checkbox';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { cn } from '@/lib/utils';
import {
  ENTRY_MODELS,
  ENTRY_MODEL_LABELS,
  ENTRY_PDA_LABELS,
  GRADE_LABELS,
  OUTCOME_LABELS,
  RANGE_POSITION_LABELS,
  SESSION_LABELS,
} from '@/lib/journal';
import type { JournalEntry, JournalEntryIn } from '@/types/api';

const NONE = '__none__';

const numStr = z
  .string()
  .optional()
  .refine((v) => !v || v.trim() === '' || !Number.isNaN(Number(v)), 'Must be a number');

const schema = z.object({
  // Context (required identity + axis + model)
  entry_date: z.string().min(1, 'Date is required'),
  instrument: z.string().min(1, 'Instrument is required').max(20),
  mode: z.enum(['backtest', 'live']),
  entry_model: z.enum([
    'consolidation', 'expansion_retracement', 'reversal_raid_on_stops', 'london',
    'model_2022_ote', 'daily_bias', 'smt_confirmation', 'unified',
  ]),
  session: z.string().optional(),
  // Decision flow
  draw_on_liquidity: z.string().optional(),
  range_position: z.string().optional(),
  swing_qualification: z.string().optional(),
  seq_smt_confirmed: z.boolean().optional(),
  triad_smt_confirmed: z.boolean().optional(),
  aura_asset_leg: z.boolean().optional(),
  time_window_valid: z.boolean().optional(),
  entry_pda: z.string(),
  // Execution / risk
  entry_price: numStr, stop_price: numStr, target_price: numStr,
  rr_planned: numStr, risk_pct: numStr, exit_price: numStr, r_multiple: numStr,
  outcome: z.string().optional(),
  mae: numStr, mfe: numStr,
  // Review
  plan_followed: z.boolean().optional(),
  grade: z.string().optional(),
  notes: z.string().optional(),
});

type FormValues = z.infer<typeof schema>;

const s = (n: number | null | undefined) => (n == null ? '' : String(n));
const e = (v: string | null | undefined) => v ?? NONE;

function toDefaults(d?: JournalEntry): FormValues {
  return {
    entry_date: d?.entry_date ?? new Date().toISOString().slice(0, 10),
    instrument: d?.instrument ?? '',
    mode: d?.mode ?? 'backtest',
    entry_model: d?.entry_model ?? 'unified',
    session: e(d?.session),
    draw_on_liquidity: d?.draw_on_liquidity ?? '',
    range_position: e(d?.range_position),
    swing_qualification: d?.swing_qualification == null ? NONE : String(d.swing_qualification),
    seq_smt_confirmed: d?.seq_smt_confirmed ?? false,
    triad_smt_confirmed: d?.triad_smt_confirmed ?? false,
    aura_asset_leg: d?.aura_asset_leg ?? false,
    time_window_valid: d?.time_window_valid ?? false,
    entry_pda: d?.entry_pda ?? 'fvg',
    entry_price: s(d?.entry_price), stop_price: s(d?.stop_price), target_price: s(d?.target_price),
    rr_planned: s(d?.rr_planned), risk_pct: s(d?.risk_pct), exit_price: s(d?.exit_price),
    r_multiple: s(d?.r_multiple), mae: s(d?.mae), mfe: s(d?.mfe),
    outcome: e(d?.outcome),
    plan_followed: d?.plan_followed ?? true,
    grade: e(d?.grade),
    notes: d?.notes ?? '',
  };
}

const opts = (labels: Record<string, string>) => Object.entries(labels);

/** The model-aligned journal form (Phase 5f). A prominent backtest|live toggle
 * drives both axes; fields are grouped into tabs that trace to the Unified
 * Playbook decision flow. Frontier `confluence_tags` are explicitly study-only. */
export function JournalForm({
  defaults,
  onSubmit,
  isSaving,
  saveError,
  submitLabel = 'Save entry',
}: {
  defaults?: JournalEntry;
  onSubmit: (body: JournalEntryIn) => void;
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

  const [confluenceTags, setConfluenceTags] = useState<string[]>(defaults?.confluence_tags ?? []);
  const [mistakeTags, setMistakeTags] = useState<string[]>(defaults?.mistake_tags ?? []);

  const mode = watch('mode');

  const num = (v?: string) => (v && v.trim() !== '' ? Number(v) : null);
  const enumOrNull = (v?: string) => (v && v !== NONE ? v : null);

  function submit(v: FormValues) {
    onSubmit({
      entry_date: v.entry_date,
      instrument: v.instrument,
      mode: v.mode,
      entry_model: v.entry_model,
      session: enumOrNull(v.session) as JournalEntryIn['session'],
      draw_on_liquidity: v.draw_on_liquidity?.trim() || null,
      range_position: enumOrNull(v.range_position) as JournalEntryIn['range_position'],
      swing_qualification: v.swing_qualification && v.swing_qualification !== NONE ? Number(v.swing_qualification) : null,
      seq_smt_confirmed: !!v.seq_smt_confirmed,
      triad_smt_confirmed: !!v.triad_smt_confirmed,
      aura_asset_leg: !!v.aura_asset_leg,
      time_window_valid: !!v.time_window_valid,
      entry_pda: (v.entry_pda || 'fvg') as JournalEntryIn['entry_pda'],
      entry_price: num(v.entry_price), stop_price: num(v.stop_price), target_price: num(v.target_price),
      rr_planned: num(v.rr_planned), risk_pct: num(v.risk_pct), exit_price: num(v.exit_price),
      r_multiple: num(v.r_multiple), mae: num(v.mae), mfe: num(v.mfe),
      outcome: enumOrNull(v.outcome) as JournalEntryIn['outcome'],
      confluence_tags: confluenceTags.length ? confluenceTags : null,
      plan_followed: !!v.plan_followed,
      mistake_tags: mistakeTags.length ? mistakeTags : null,
      grade: enumOrNull(v.grade) as JournalEntryIn['grade'],
      notes: v.notes?.trim() || null,
    });
  }

  return (
    <form onSubmit={handleSubmit(submit)} className="space-y-6" data-testid="journal-form">
      {/* Mode toggle — drives both axes; always visible above the tabs. */}
      <div className="space-y-1.5">
        <Label>Mode</Label>
        <div className="inline-flex rounded-md border p-0.5" role="group" aria-label="Mode">
          {(['backtest', 'live'] as const).map((m) => (
            <button
              key={m}
              type="button"
              aria-pressed={mode === m}
              onClick={() => setValue('mode', m, { shouldValidate: true })}
              className={cn(
                'rounded px-4 py-1.5 text-sm font-medium capitalize transition-colors',
                mode === m
                  ? m === 'live'
                    ? 'bg-[color:var(--chart-live)] text-white'
                    : 'bg-[color:var(--chart-backtest)] text-white'
                  : 'text-muted-foreground hover:text-foreground'
              )}
            >
              {m}
            </button>
          ))}
        </div>
        <p className="text-xs text-muted-foreground">
          Backtest and live are kept separate everywhere — expectancy is never conflated across the two.
        </p>
      </div>

      <Tabs defaultValue="context">
        <TabsList className="flex-wrap">
          <TabsTrigger value="context">Context</TabsTrigger>
          <TabsTrigger value="flow">Decision flow</TabsTrigger>
          <TabsTrigger value="exec">Execution &amp; risk</TabsTrigger>
          <TabsTrigger value="review">Review</TabsTrigger>
        </TabsList>

        {/* -------------------------------------------------- Context */}
        <TabsContent value="context" className="space-y-4 pt-2">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Date" error={errors.entry_date?.message}>
              <Input type="date" {...register('entry_date')} />
            </Field>
            <Field label="Instrument" error={errors.instrument?.message}>
              <Input placeholder="NQ, ES, EURUSD…" aria-label="Instrument" {...register('instrument')} />
            </Field>
            <SelectField control={control} name="entry_model" label="Entry model"
              placeholder="Select model" allowNone={false}
              options={ENTRY_MODELS.map((m) => [m, ENTRY_MODEL_LABELS[m]])} />
            <SelectField control={control} name="session" label="Session"
              placeholder="—" options={opts(SESSION_LABELS)} />
          </div>
        </TabsContent>

        {/* -------------------------------------------------- Decision flow */}
        <TabsContent value="flow" className="space-y-4 pt-2">
          <Field label="Draw on liquidity (DOL)">
            <Input placeholder="e.g. prior day high / weekly liquidity" {...register('draw_on_liquidity')} />
          </Field>
          <div className="grid gap-4 sm:grid-cols-3">
            <SelectField control={control} name="range_position" label="Range position"
              placeholder="—" options={opts(RANGE_POSITION_LABELS)} />
            <SelectField control={control} name="swing_qualification" label="Swing qualification (R2)"
              placeholder="—" options={[['0', '0 — none'], ['1', '1 — single'], ['2', '2 — double']]} />
            <SelectField control={control} name="entry_pda" label="Entry PDA (R4)"
              placeholder="FVG" allowNone={false} options={opts(ENTRY_PDA_LABELS)} />
          </div>
          <div className="grid gap-2 sm:grid-cols-2">
            <CheckField control={control} name="seq_smt_confirmed" label="Sequential SMT confirmed (HTF)" />
            <CheckField control={control} name="triad_smt_confirmed" label="Triad SMT confirmed (LTF)" />
            <CheckField control={control} name="time_window_valid" label="Entry inside a valid time window" />
            <CheckField control={control} name="aura_asset_leg" label="Aura asset leg (optional 6S · R7)" />
          </div>
        </TabsContent>

        {/* -------------------------------------------------- Execution / risk */}
        <TabsContent value="exec" className="space-y-4 pt-2">
          <p className="text-xs text-muted-foreground">
            Risk is expressed in R (no dollar sizing). A trade counts toward expectancy once it has a realized
            <span className="font-medium"> R multiple</span>.
          </p>
          <div className="grid gap-4 sm:grid-cols-3">
            <NumField label="Entry price" reg={register('entry_price')} err={errors.entry_price?.message} />
            <NumField label="Stop price" reg={register('stop_price')} err={errors.stop_price?.message} />
            <NumField label="Target price" reg={register('target_price')} err={errors.target_price?.message} />
            <NumField label="Planned R:R" reg={register('rr_planned')} err={errors.rr_planned?.message} />
            <NumField label="Risk %" reg={register('risk_pct')} err={errors.risk_pct?.message} />
            <NumField label="Exit price" reg={register('exit_price')} err={errors.exit_price?.message} />
            <NumField label="Realized R" reg={register('r_multiple')} err={errors.r_multiple?.message} />
            <NumField label="MAE" reg={register('mae')} err={errors.mae?.message} />
            <NumField label="MFE" reg={register('mfe')} err={errors.mfe?.message} />
          </div>
          <div className="max-w-xs">
            <SelectField control={control} name="outcome" label="Outcome" placeholder="—" options={opts(OUTCOME_LABELS)} />
          </div>
        </TabsContent>

        {/* -------------------------------------------------- Review */}
        <TabsContent value="review" className="space-y-4 pt-2">
          <TagField
            label="Confluence tags"
            note="Frontier stack (WHERE / WHEN / DIRECTION / CONFIRM). Study-only — never counts toward live eligibility."
            tags={confluenceTags}
            setTags={setConfluenceTags}
            placeholder="e.g. weekly-DOL, macro-window"
          />
          <div className="grid gap-4 sm:grid-cols-2">
            <SelectField control={control} name="grade" label="Execution grade" placeholder="—" options={opts(GRADE_LABELS)} />
            <div className="flex items-end pb-1">
              <CheckField control={control} name="plan_followed" label="Followed the plan" />
            </div>
          </div>
          <TagField
            label="Mistake tags"
            tags={mistakeTags}
            setTags={setMistakeTags}
            placeholder="e.g. early-entry, moved-stop"
          />
          <Field label="Notes">
            <Textarea rows={4} placeholder="What happened, what to repeat / fix…" {...register('notes')} />
          </Field>
        </TabsContent>
      </Tabs>

      {saveError && <p className="text-sm text-destructive">{saveError}</p>}

      <Button type="submit" disabled={isSaving}>
        {isSaving && <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />}
        {submitLabel}
      </Button>
    </form>
  );
}

// ---------------------------------------------------------------------------
// Small field helpers (kept local to the form)
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

function NumField({ label, reg, err }: { label: string; reg: ReturnType<ReturnType<typeof useForm>['register']>; err?: string }) {
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

function CheckField({ control, name, label }: { control: any; name: any; label: string }) {
  return (
    <Controller
      control={control}
      name={name}
      render={({ field }) => (
        <label className="flex items-center gap-2 text-sm">
          <Checkbox checked={!!field.value} onCheckedChange={field.onChange} aria-label={label} />
          {label}
        </label>
      )}
    />
  );
}
/* eslint-enable @typescript-eslint/no-explicit-any */

function TagField({
  label, note, tags, setTags, placeholder,
}: {
  label: string; note?: string; tags: string[]; setTags: (t: string[]) => void; placeholder?: string;
}) {
  const [draft, setDraft] = useState('');
  const add = () => {
    const t = draft.trim();
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
          placeholder={placeholder}
          className="max-w-xs"
          aria-label={`Add ${label}`}
        />
        <Button type="button" variant="outline" size="sm" onClick={add} disabled={!draft.trim()}>
          <Plus className="mr-1 h-3.5 w-3.5" /> Add
        </Button>
      </div>
      {tags.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {tags.map((t) => (
            <span key={t} className="inline-flex items-center gap-1 rounded-md border bg-muted px-2 py-0.5 text-xs">
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
