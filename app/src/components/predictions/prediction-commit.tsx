import { useState } from 'react';
import { AlertTriangle, Check, Loader2, Lock, X } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';
import {
  BIAS_LABELS,
  revealGap,
  useCommitPrediction,
  usePredictions,
  useResolvePrediction,
} from '@/lib/predictions';
// Reused, not redeclared — the journal already owns the model vocabulary, and a
// second copy would be free to drift from the `entry_model` enum.
import { ENTRY_MODEL_LABELS, ENTRY_MODELS } from '@/lib/journal';
import type { EntryModel, Prediction, PredictionBias } from '@/types/api';

/**
 * PRE-COMMITMENT — the one primitive the other three grading tiers cannot supply
 * (concepts/architecture/learning-enforcement.md §9).
 *
 * The wiki's method for every tape study is: "read the transcript's live read →
 * note bias call, DOL, the model used, entry/target → find a matching session →
 * run the full pre-market routine blind → compare your read to the mentor's". T-14
 * says it outright: "call the read (bias, DOL, model, target) BEFORE IT RESOLVES;
 * grade after." So this surface is two steps that must not collapse into one.
 *
 * WHAT THIS UI MUST NEVER DO, and why:
 *
 * · **Never offer an edit or a delete.** Once committed, a call is frozen (the
 *   backend enforces it in a DB trigger, and the table has no soft-delete). Showing
 *   a disabled edit control would still imply the call is provisional, so there is
 *   none at all — the lock icon says what happened instead.
 * · **Never show the outcome fields before the call is committed.** The two-step
 *   shape IS the anti-cheat: if both halves were on screen at once, nothing would
 *   stop them being filled in together after the fact.
 * · **Never present being right as the goal.** M6's bar is that the call was made
 *   before the reveal and then scored honestly. A wrong call, committed and owned,
 *   is the exercise (§6) — so a miss renders as information, not as failure.
 */

const BIASES: PredictionBias[] = ['long', 'short', 'neutral'];

function Verdict({ ok, label }: { ok: boolean | null; label: string }) {
  if (ok === null) {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
        {label}
      </span>
    );
  }
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-xs',
        ok ? 'bg-emerald-500/10 text-emerald-600' : 'bg-muted text-muted-foreground'
      )}
    >
      {ok ? <Check className="h-3 w-3" /> : <X className="h-3 w-3" />}
      {label}
    </span>
  );
}

/** A committed call, and either its reveal or the form to record one. */
function CommittedCall({ call }: { call: Prediction }) {
  const resolve = useResolvePrediction();
  const [open, setOpen] = useState(false);
  const [outcome, setOutcome] = useState<PredictionBias>(call.bias);
  const [dolHit, setDolHit] = useState(false);
  const [played, setPlayed] = useState(false);
  const [targetHit, setTargetHit] = useState(false);
  const [notes, setNotes] = useState('');

  return (
    <div className="rounded-md border p-2.5 text-sm" data-testid="committed-call">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <Lock className="h-3.5 w-3.5 shrink-0 text-muted-foreground" aria-label="Frozen" />
        <Badge variant="outline">{BIAS_LABELS[call.bias]}</Badge>
        <span className="text-muted-foreground">·</span>
        <span>{ENTRY_MODEL_LABELS[call.entry_model] ?? call.entry_model}</span>
        <span className="text-muted-foreground">· DOL {call.dol}</span>
        <span className="text-muted-foreground">· target {call.target}</span>
      </div>
      <div className="mt-1 text-xs text-muted-foreground">
        {call.session_label}
        {call.instrument ? ` · ${call.instrument}` : ''} · committed{' '}
        {new Date(call.committed_at).toLocaleString()}
      </div>

      {call.resolved ? (
        <div className="mt-2 space-y-1">
          <div className="flex flex-wrap items-center gap-1.5">
            <Verdict ok={call.bias_correct} label={`Bias — ${BIAS_LABELS[call.outcome_bias!]}`} />
            <Verdict ok={call.dol_correct} label="DOL" />
            <Verdict ok={call.entry_model_correct} label="Model" />
            <Verdict ok={call.target_correct} label="Target" />
          </div>
          <p className="text-xs text-muted-foreground">
            Scored {revealGap(call.seconds_to_reveal)} — the call above could not change in
            between.
          </p>
          {call.resolution_notes && <p className="text-xs italic">{call.resolution_notes}</p>}
        </div>
      ) : open ? (
        <div className="mt-2 space-y-2 border-t pt-2">
          <p className="text-xs text-muted-foreground">
            What actually happened. Recorded once — it becomes part of the record, not a draft.
          </p>
          <div className="space-y-1">
            <Label className="text-xs">Which way did it actually go?</Label>
            <div className="flex flex-wrap gap-1.5">
              {BIASES.map((b) => (
                <Button
                  key={b}
                  type="button"
                  size="sm"
                  variant={outcome === b ? 'default' : 'outline'}
                  className="h-7"
                  onClick={() => setOutcome(b)}
                >
                  {BIAS_LABELS[b]}
                </Button>
              ))}
            </div>
          </div>
          {(
            [
              ['Your DOL got taken', dolHit, setDolHit],
              ['The model played out', played, setPlayed],
              ['Your target was hit', targetHit, setTargetHit],
            ] as const
          ).map(([label, value, set]) => (
            <label key={label} className="flex items-center gap-2 text-xs">
              <input
                type="checkbox"
                checked={value}
                onChange={(e) => set(e.target.checked)}
                className="h-3.5 w-3.5"
              />
              {label}
            </label>
          ))}
          <Textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="How your read differed from the mentor's (optional)"
            className="min-h-[52px] text-xs"
          />
          {resolve.isError && (
            <p className="flex items-start gap-1.5 text-xs text-destructive">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              {resolve.error.message}
            </p>
          )}
          <div className="flex gap-2">
            <Button
              type="button"
              size="sm"
              className="h-7"
              disabled={resolve.isPending}
              onClick={() =>
                resolve.mutate({
                  id: call.id,
                  outcome_bias: outcome,
                  dol_hit: dolHit,
                  model_played_out: played,
                  target_hit: targetHit,
                  resolution_notes: notes.trim() || null,
                })
              }
            >
              {resolve.isPending && <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />}
              Record the outcome
            </Button>
            <Button
              type="button"
              size="sm"
              variant="ghost"
              className="h-7"
              onClick={() => setOpen(false)}
            >
              Not yet
            </Button>
          </div>
        </div>
      ) : (
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <Button type="button" size="sm" variant="outline" className="h-7" onClick={() => setOpen(true)}>
            Score it against what happened
          </Button>
          <span className="text-xs text-muted-foreground">
            Committed — awaiting its outcome. Nothing is scored yet.
          </span>
        </div>
      )}
    </div>
  );
}

export function PredictionCommit({ drillRef, className }: { drillRef: string; className?: string }) {
  const { data: calls } = usePredictions(drillRef);
  const commit = useCommitPrediction();
  const [open, setOpen] = useState(false);
  const [session, setSession] = useState('');
  const [instrument, setInstrument] = useState('');
  const [bias, setBias] = useState<PredictionBias>('long');
  const [dol, setDol] = useState('');
  const [model, setModel] = useState<EntryModel>('consolidation');
  const [target, setTarget] = useState('');

  const ready = session.trim() && dol.trim() && target.trim();
  const list = calls ?? [];

  function submit() {
    commit.mutate(
      {
        drill_ref: drillRef,
        session_label: session.trim(),
        instrument: instrument.trim() || null,
        bias,
        dol: dol.trim(),
        entry_model: model,
        target: target.trim(),
      },
      {
        onSuccess: () => {
          setOpen(false);
          setSession('');
          setInstrument('');
          setDol('');
          setTarget('');
        },
      }
    );
  }

  return (
    <div className={cn('space-y-2', className)} data-testid="prediction-commit">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="text-sm font-medium">Your call, before the reveal</div>
        {list.length > 0 && (
          <span className="text-xs text-muted-foreground">
            {list.filter((c) => c.resolved).length} scored · {list.length} committed
          </span>
        )}
      </div>

      {list.length === 0 && !open && (
        <p className="text-xs text-muted-foreground">
          Call bias, DOL, model and target <em>before</em> you step the replay forward. Once
          committed it is frozen — that ordering is the only thing that makes this evidence.
        </p>
      )}

      {list.map((call) => (
        <CommittedCall key={call.id} call={call} />
      ))}

      {open ? (
        <div className="space-y-2 rounded-md border p-2.5">
          <div className="grid gap-2 sm:grid-cols-2">
            <div className="space-y-1">
              <Label htmlFor={`sess-${drillRef}`} className="text-xs">
                Session you are calling
              </Label>
              <Input
                id={`sess-${drillRef}`}
                value={session}
                onChange={(e) => setSession(e.target.value)}
                placeholder="comparable no-news Monday"
                className="h-8 text-sm"
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor={`inst-${drillRef}`} className="text-xs">
                Instrument (optional)
              </Label>
              <Input
                id={`inst-${drillRef}`}
                value={instrument}
                onChange={(e) => setInstrument(e.target.value)}
                placeholder="NQ"
                className="h-8 text-sm"
              />
            </div>
          </div>

          <div className="space-y-1">
            <Label className="text-xs">Bias</Label>
            <div className="flex flex-wrap gap-1.5">
              {BIASES.map((b) => (
                <Button
                  key={b}
                  type="button"
                  size="sm"
                  variant={bias === b ? 'default' : 'outline'}
                  className="h-7"
                  onClick={() => setBias(b)}
                >
                  {BIAS_LABELS[b]}
                </Button>
              ))}
            </div>
          </div>

          <div className="grid gap-2 sm:grid-cols-2">
            <div className="space-y-1">
              <Label htmlFor={`dol-${drillRef}`} className="text-xs">
                Draw on liquidity
              </Label>
              <Input
                id={`dol-${drillRef}`}
                value={dol}
                onChange={(e) => setDol(e.target.value)}
                placeholder="PDH 20134.50"
                className="h-8 text-sm"
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor={`tgt-${drillRef}`} className="text-xs">
                Target
              </Label>
              <Input
                id={`tgt-${drillRef}`}
                value={target}
                onChange={(e) => setTarget(e.target.value)}
                placeholder="20180.00"
                className="h-8 text-sm"
              />
            </div>
          </div>

          <div className="space-y-1">
            <Label htmlFor={`model-${drillRef}`} className="text-xs">
              Model
            </Label>
            <select
              id={`model-${drillRef}`}
              value={model}
              onChange={(e) => setModel(e.target.value as EntryModel)}
              className="h-8 w-full rounded-md border bg-background px-2 text-sm"
            >
              {ENTRY_MODELS.map((m) => (
                <option key={m} value={m}>
                  {ENTRY_MODEL_LABELS[m] ?? m}
                </option>
              ))}
            </select>
          </div>

          {commit.isError && (
            <p className="flex items-start gap-1.5 text-xs text-destructive">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              {commit.error.message}
            </p>
          )}

          <div className="flex items-center gap-2">
            <Button type="button" size="sm" className="h-7" disabled={!ready || commit.isPending} onClick={submit}>
              {commit.isPending && <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />}
              Commit this call
            </Button>
            <Button type="button" size="sm" variant="ghost" className="h-7" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <span className="text-xs text-muted-foreground">Frozen once committed.</span>
          </div>
        </div>
      ) : (
        <Button type="button" size="sm" variant="outline" className="h-7" onClick={() => setOpen(true)}>
          Commit a call
        </Button>
      )}
    </div>
  );
}
