import { cn } from '@/lib/utils';

/**
 * The NeuroSpect Learn mark.
 *
 * Four ascending bars crossed by a scan line: the bars are the four-tier mastery
 * ladder this app is built around (Learned → Can-mark → Backtested → Live-ready),
 * the sweep across them is the "-spect" half of the name. Drawn from the brand
 * tokens, so it re-hues with the accent setting instead of being a fixed asset.
 */
export function Logo({
  className,
  size = 'md',
}: {
  className?: string;
  size?: 'sm' | 'md' | 'lg';
}) {
  const px = size === 'sm' ? 22 : size === 'lg' ? 40 : 28;

  return (
    <svg
      width={px}
      height={px}
      viewBox="0 0 32 32"
      fill="none"
      aria-hidden
      className={cn('shrink-0', className)}
    >
      <defs>
        <linearGradient id="ns-mark" x1="4" y1="28" x2="28" y2="4" gradientUnits="userSpaceOnUse">
          <stop stopColor="var(--primary)" />
          <stop offset="1" stopColor="var(--brand-2)" />
        </linearGradient>
      </defs>
      {/* The ladder: four rungs, each taller than the last. */}
      <rect x="3" y="20" width="4.5" height="8" rx="1.25" fill="url(#ns-mark)" opacity="0.45" />
      <rect x="10" y="15" width="4.5" height="13" rx="1.25" fill="url(#ns-mark)" opacity="0.65" />
      <rect x="17" y="9" width="4.5" height="19" rx="1.25" fill="url(#ns-mark)" opacity="0.82" />
      <rect x="24" y="3" width="4.5" height="25" rx="1.25" fill="url(#ns-mark)" />
      {/* The scan. */}
      <path
        d="M2 23.5 L30 6.5"
        stroke="var(--brand-2)"
        strokeWidth="1.75"
        strokeLinecap="round"
        opacity="0.9"
      />
    </svg>
  );
}
