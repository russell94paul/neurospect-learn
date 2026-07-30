import { useCallback, useEffect, useRef, useState } from 'react';
import { AlertTriangle, ClipboardPaste, Loader2, Trash2, Upload } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import {
  evidenceSrc,
  imageFileFrom,
  useDeleteEvidence,
  useEvidence,
  useUploadEvidence,
} from '@/lib/evidence';
import type { EvidenceKind, EvidenceSubjectRef } from '@/types/api';

/**
 * Evidence capture — PASTE FIRST (Phase E2).
 *
 * Every drill's stated tooling is desktop TradingView bar-replay, so the
 * high-leverage affordance is `Ctrl+V` straight from a snapshot: the capture
 * never becomes a file the user has to find, name and browse to. Drag-and-drop
 * and a file input are the fallbacks, not the primary path.
 *
 * Clicking the zone focuses it, so a subsequent Ctrl+V lands here rather than in
 * whatever the browser last focused; a window-level paste listener also fires
 * while the zone is focused-within, which is what makes the flow one keystroke.
 */
export function EvidenceCapture({
  subject,
  kind = 'chart_markup',
  label = 'Evidence',
  hint,
  showRepsClaimed = true,
  className,
}: {
  subject: EvidenceSubjectRef;
  kind?: EvidenceKind;
  label?: string;
  hint?: string;
  /** Drill/concept evidence counts reps; journal + missed-trade evidence does not. */
  showRepsClaimed?: boolean;
  className?: string;
}) {
  const list = useEvidence(subject);
  const upload = useUploadEvidence();
  const remove = useDeleteEvidence();
  const zoneRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [repsClaimed, setRepsClaimed] = useState(1);

  const send = useCallback(
    (file: File) => {
      upload.mutate({ file, subject, kind, reps_claimed: showRepsClaimed ? repsClaimed : 1 });
    },
    [upload, subject, kind, repsClaimed, showRepsClaimed]
  );

  // Ctrl+V anywhere while this zone holds focus.
  useEffect(() => {
    function onPaste(e: ClipboardEvent) {
      const zone = zoneRef.current;
      if (!zone || !zone.contains(document.activeElement)) return;
      const file = imageFileFrom(e.clipboardData);
      if (!file) return;
      e.preventDefault();
      send(file);
    }
    window.addEventListener('paste', onPaste);
    return () => window.removeEventListener('paste', onPaste);
  }, [send]);

  const assets = list.data ?? [];
  const evidencedReps = assets.reduce((n, a) => n + a.reps_claimed, 0);
  const rejection = upload.isError ? (upload.error as Error).message : null;

  return (
    <div className={cn('space-y-2', className)} data-testid="evidence-capture">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-xs font-medium text-muted-foreground">
          {label}
          {assets.length > 0 && (
            <span data-testid="evidence-count">
              {' '}
              · {assets.length} captured{showRepsClaimed ? ` · ${evidencedReps} reps` : ''}
            </span>
          )}
        </span>
        {showRepsClaimed && (
          <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
            this capture counts
            <input
              type="number"
              min={1}
              max={100}
              value={repsClaimed}
              onChange={(e) => setRepsClaimed(Math.max(1, Math.min(100, +e.target.value || 1)))}
              className="h-6 w-14 rounded border bg-background px-1.5 text-right tabular-nums"
              aria-label="Reps this capture counts for"
              data-testid="reps-claimed"
            />
            reps
          </label>
        )}
      </div>

      <div
        ref={zoneRef}
        tabIndex={0}
        role="button"
        aria-label="Paste, drop or choose a capture as evidence"
        data-testid="evidence-dropzone"
        onClick={() => zoneRef.current?.focus()}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          const file = imageFileFrom(e.dataTransfer);
          if (file) send(file);
        }}
        className={cn(
          'flex flex-col items-center gap-1 rounded-md border border-dashed px-3 py-4 text-center text-xs transition-colors',
          'focus:outline-none focus-visible:ring-2 focus-visible:ring-ring',
          dragging ? 'border-primary bg-accent' : 'border-muted-foreground/30'
        )}
      >
        {upload.isPending ? (
          <span className="flex items-center gap-1.5 text-muted-foreground">
            <Loader2 className="h-3.5 w-3.5 animate-spin" /> Uploading…
          </span>
        ) : (
          <>
            <span className="flex items-center gap-1.5 font-medium">
              <ClipboardPaste className="h-4 w-4" /> Click, then <kbd className="rounded border px-1">Ctrl</kbd>
              +<kbd className="rounded border px-1">V</kbd> your capture
            </span>
            <span className="text-muted-foreground">
              or drop an image here ·{' '}
              <button
                type="button"
                className="underline underline-offset-2"
                onClick={(e) => {
                  e.stopPropagation();
                  inputRef.current?.click();
                }}
              >
                choose a file
              </button>
            </span>
            {hint && <span className="text-muted-foreground/80">{hint}</span>}
          </>
        )}
        <input
          ref={inputRef}
          type="file"
          accept="image/*"
          className="hidden"
          data-testid="evidence-file-input"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) send(file);
            e.target.value = '';
          }}
        />
      </div>

      {/* A refusal ALWAYS says why (design §5) — a silent refusal is the failure
          mode this layer exists to avoid. */}
      {rejection && (
        <p
          className="flex items-start gap-1.5 text-xs text-destructive"
          data-testid="evidence-rejection"
        >
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          {rejection}
        </p>
      )}

      {assets.length > 0 && (
        <ul className="flex flex-wrap gap-2">
          {assets.map((asset) => {
            const flagged = asset.grades.some((g) => g.state === 'flagged');
            return (
              <li key={asset.id} className="group relative" data-testid="evidence-thumb">
                <img
                  src={evidenceSrc(asset.url)}
                  alt={asset.original_filename ?? 'Captured evidence'}
                  className={cn(
                    'h-16 w-24 rounded border object-cover',
                    flagged && 'border-amber-500'
                  )}
                />
                {/* Only drill/concept evidence counts reps — labelling a journal
                    screenshot "1 rep" contradicts the panel's own hint. */}
                {showRepsClaimed && (
                  <span className="absolute bottom-0 left-0 rounded-tr bg-background/85 px-1 text-[10px] tabular-nums">
                    {asset.reps_claimed} rep{asset.reps_claimed === 1 ? '' : 's'}
                  </span>
                )}
                <button
                  type="button"
                  aria-label="Remove this evidence"
                  data-testid="evidence-delete"
                  onClick={() => remove.mutate(asset.id)}
                  className="absolute right-0 top-0 rounded-bl bg-background/85 p-0.5 opacity-0 transition-opacity group-hover:opacity-100 focus:opacity-100"
                >
                  <Trash2 className="h-3 w-3 text-destructive" />
                </button>
                {flagged && (
                  <span className="absolute right-0 bottom-0 rounded-tl bg-background/85 px-1 text-[10px] text-amber-600 dark:text-amber-500">
                    flagged
                  </span>
                )}
              </li>
            );
          })}
        </ul>
      )}

      {/* Flags are SURFACED, never a refusal. */}
      {assets.some((a) => a.grades.some((g) => g.state === 'flagged')) && (
        <p className="text-xs text-amber-600 dark:text-amber-500" data-testid="evidence-flag">
          {assets
            .flatMap((a) => a.grades)
            .filter((g) => g.state === 'flagged')
            .flatMap((g) => (Array.isArray(g.findings) ? g.findings : []))
            .map((f) => (f as { message?: string }).message)
            .filter(Boolean)
            .join(' ')}
        </p>
      )}
    </div>
  );
}

/** The button that opens the file picker without the full zone — used where
 * space is tight. Exported for reuse; the zone is the default affordance. */
export function EvidenceUploadButton({ onFile }: { onFile: (f: File) => void }) {
  const ref = useRef<HTMLInputElement>(null);
  return (
    <>
      <Button type="button" variant="outline" size="sm" onClick={() => ref.current?.click()}>
        <Upload className="mr-1.5 h-3.5 w-3.5" /> Add evidence
      </Button>
      <input
        ref={ref}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) onFile(file);
          e.target.value = '';
        }}
      />
    </>
  );
}
