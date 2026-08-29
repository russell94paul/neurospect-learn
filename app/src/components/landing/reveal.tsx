import { useEffect, useRef, useState, type ReactNode } from 'react';
import { cn } from '@/lib/utils';
import { resolve, useSettings } from '@/lib/settings';

/**
 * Scroll reveal, ported from the NeuroSpect marketing site's `.reveal`.
 *
 * Two properties that matter more than the effect:
 *  - It starts VISIBLE and only hides itself once the observer is wired. With no
 *    JS, or if IntersectionObserver is missing, the content is simply there.
 *  - When motion is off it NEVER hides. Hiding content behind an animation the
 *    user has switched off is how a reduced-motion setting turns into a blank
 *    page — an off-screen element would sit at opacity 0 with nothing left to
 *    reveal it. Caught by scripts/render-walk.mjs, which screenshotted exactly
 *    that: a landing page blank below the fold.
 */
export function Reveal({
  children,
  delay = 0,
  className,
}: {
  children: ReactNode;
  delay?: number;
  className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [shown, setShown] = useState(true);
  const [armed, setArmed] = useState(false);
  const { settings } = useSettings();

  const still =
    resolve(settings, {
      osDark: false,
      osReduce:
        typeof matchMedia === 'function' &&
        matchMedia('(prefers-reduced-motion: reduce)').matches,
    }).motion === 'none';

  useEffect(() => {
    if (still) return;
    if (typeof IntersectionObserver !== 'function') return;
    const el = ref.current;
    if (!el) return;

    setArmed(true);
    setShown(false);

    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting) {
            setShown(true);
            io.disconnect();
          }
        }
      },
      { rootMargin: '0px 0px -10% 0px', threshold: 0.05 }
    );
    io.observe(el);
    return () => io.disconnect();
  }, [still]);

  return (
    <div
      ref={ref}
      style={armed ? { transitionDelay: `${delay}ms` } : undefined}
      className={cn(
        armed && 'transition-[opacity,transform] duration-700 ease-out',
        armed && !shown && 'translate-y-7 opacity-0',
        armed && shown && 'translate-y-0 opacity-100',
        className
      )}
    >
      {children}
    </div>
  );
}
