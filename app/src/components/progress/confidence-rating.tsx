import { cn } from '@/lib/utils';
import { CONFIDENCE_LABELS } from '@/lib/learning';

/**
 * The 1–5 confidence scale (concepts/mastery/README §confidence). Editable when
 * `onChange` is supplied; read-only otherwise.
 */
export function ConfidenceRating({
  value,
  onChange,
  className,
}: {
  value: number | null | undefined;
  onChange?: (v: number) => void;
  className?: string;
}) {
  const readOnly = !onChange;
  return (
    <div className={cn('flex items-center gap-1', className)}>
      {[1, 2, 3, 4, 5].map((n) => (
        <button
          key={n}
          type="button"
          disabled={readOnly}
          onClick={() => onChange?.(n)}
          aria-label={`Confidence ${n} — ${CONFIDENCE_LABELS[n]}`}
          title={CONFIDENCE_LABELS[n]}
          className={cn(
            'h-4 w-4 rounded-full border transition-colors',
            value && n <= value
              ? 'border-primary bg-primary'
              : 'border-muted-foreground/40 bg-transparent',
            !readOnly && 'cursor-pointer hover:border-primary'
          )}
        />
      ))}
      <span className="ml-1 text-xs text-muted-foreground">
        {value ? `${value} · ${CONFIDENCE_LABELS[value]}` : '—'}
      </span>
    </div>
  );
}
