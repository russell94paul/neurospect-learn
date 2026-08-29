import { cn } from '@/lib/utils';

/**
 * "Powered by the NeuroSpect Suite".
 *
 * A BRAND statement, not an integration claim. This backend is deliberately
 * standalone — it mints its own JWTs against its own users table and has no
 * runtime dependency on neurospect-api — so nothing here should imply that data
 * moves between products. Landing footer and Settings → About only; never in the
 * app chrome.
 */
export function SuiteLockup({ className }: { className?: string }) {
  return (
    <p className={cn('text-xs tracking-wide text-muted-foreground', className)}>
      Powered by the{' '}
      <span className="font-medium text-foreground">NeuroSpect Suite</span>
    </p>
  );
}
