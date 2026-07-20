import { useEffect, useState } from 'react';
import { AlertTriangle, Check, Eye, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { advanceBlocked, LADDER_LABELS, useUpdateProgress } from '@/lib/learning';
import type { ProgressRow } from '@/types/api';
import { LadderBadge } from './ladder-badge';
import { ConfidenceRating } from './confidence-rating';
import { RepCounter } from './rep-counter';

const CAN_MARK = 2;

/**
 * The "track this" panel — edit a concept's ladder / confidence / reps / notes,
 * PATCH /api/progress on save. Surfaces the ladder-advance gate (reps ≥ target
 * AND confidence set) and the frontier watch-only cap (Can-mark max).
 */
export function ConceptTrackPanel({ row }: { row: ProgressRow }) {
  const update = useUpdateProgress();

  const [ladder, setLadder] = useState<number | null>(row.ladder_stage);
  const [confidence, setConfidence] = useState<number | null>(row.confidence);
  const [reps, setReps] = useState<number>(row.reps);
  const [notes, setNotes] = useState<string>(row.notes ?? '');

  // Re-sync from the server row (e.g. after a save invalidates + refetches).
  useEffect(() => {
    setLadder(row.ladder_stage);
    setConfidence(row.confidence);
    setReps(row.reps);
    setNotes(row.notes ?? '');
  }, [row.ladder_stage, row.confidence, row.reps, row.notes]);

  const dirty =
    ladder !== row.ladder_stage ||
    confidence !== row.confidence ||
    reps !== row.reps ||
    (notes ?? '') !== (row.notes ?? '');

  const gateMsg = advanceBlocked(ladder ?? 0, reps, confidence, row.rep_target_count);
  const maxLadder = row.watch_only ? CAN_MARK : 4;

  function save() {
    update.mutate({
      concept_id: row.concept_id,
      ladder_stage: ladder,
      confidence: confidence,
      reps: reps,
      notes: notes.trim() ? notes.trim() : null,
      last_practiced: new Date().toISOString().slice(0, 10),
    });
  }

  return (
    <div className="space-y-4 rounded-lg border bg-card p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold">Track this</span>
          {row.code && <span className="font-mono text-xs text-muted-foreground">{row.code}</span>}
          <LadderBadge stage={row.ladder_stage} />
        </div>
        {row.watch_only && (
          <span className="inline-flex items-center gap-1 text-xs text-amber-600 dark:text-amber-500">
            <Eye className="h-3 w-3" /> watch-only · observe to Can-mark
          </span>
        )}
      </div>

      {/* Ladder selector */}
      <div className="space-y-1.5">
        <span className="text-xs font-medium text-muted-foreground">Ladder stage</span>
        <div className="flex flex-wrap gap-1.5">
          {[1, 2, 3, 4].map((n) => (
            <Button
              key={n}
              type="button"
              size="sm"
              variant={ladder === n ? 'default' : 'outline'}
              disabled={n > maxLadder}
              onClick={() => setLadder(ladder === n ? null : n)}
              className="h-7"
            >
              {n} · {LADDER_LABELS[n]}
            </Button>
          ))}
        </div>
      </div>

      {/* Confidence */}
      <div className="space-y-1.5">
        <span className="text-xs font-medium text-muted-foreground">Confidence</span>
        <ConfidenceRating value={confidence} onChange={setConfidence} />
      </div>

      {/* Reps */}
      <div className="space-y-1.5">
        <span className="text-xs font-medium text-muted-foreground">
          Reps{row.rep_target ? ` · target: ${row.rep_target}` : ''}
        </span>
        <RepCounter reps={reps} target={row.rep_target_count} onChange={setReps} />
      </div>

      {/* Notes */}
      <div className="space-y-1.5">
        <span className="text-xs font-medium text-muted-foreground">Notes</span>
        <Textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="Working notes…"
          rows={2}
          className="text-sm"
        />
      </div>

      {/* Gate message */}
      {gateMsg && (
        <p className="flex items-center gap-1.5 text-xs text-amber-600 dark:text-amber-500">
          <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
          {gateMsg}
        </p>
      )}
      {update.isError && (
        <p className="text-xs text-destructive">{(update.error as Error).message}</p>
      )}

      <div className="flex items-center gap-2">
        <Button size="sm" onClick={save} disabled={!dirty || !!gateMsg || update.isPending}>
          {update.isPending ? (
            <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />
          ) : update.isSuccess && !dirty ? (
            <Check className="mr-1 h-3.5 w-3.5" />
          ) : null}
          Save
        </Button>
        {update.isSuccess && !dirty && !update.isPending && (
          <span className="text-xs text-muted-foreground">Saved</span>
        )}
      </div>
    </div>
  );
}
