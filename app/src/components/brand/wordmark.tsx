import { cn } from '@/lib/utils';
import { Logo } from '@/components/brand/logo';

/**
 * The name lockup.
 *
 * Set in the app's own font stack rather than a webfont: /runner is designed to
 * work with the backend down, and a render-blocking third-party font request at
 * the top of the critical path is exactly the wrong dependency to add. The
 * tracking and weight do the work a display face would.
 *
 * This is the single source of the product name — it replaced four hand-typed
 * copies (index.html, sidebar desktop, sidebar mobile, login).
 */
export function Wordmark({
  className,
  size = 'md',
  showMark = true,
}: {
  className?: string;
  size?: 'sm' | 'md' | 'lg';
  showMark?: boolean;
}) {
  const text =
    size === 'sm' ? 'text-sm' : size === 'lg' ? 'text-2xl sm:text-3xl' : 'text-base';

  return (
    <span className={cn('inline-flex items-center gap-2', className)}>
      {showMark && <Logo size={size} />}
      <span className={cn('font-semibold tracking-tight', text)}>
        <span className="text-foreground">NeuroSpect</span>
        <span className="text-primary"> Learn</span>
      </span>
    </span>
  );
}
