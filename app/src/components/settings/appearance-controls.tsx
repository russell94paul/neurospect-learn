import { AlertTriangle } from 'lucide-react';
import {
  BRANDS,
  RADII,
  osPrefersReducedMotion,
  useSettings,
  type Density,
  type FontId,
  type MotionPref,
  type ThemeMode,
} from '@/lib/settings';
import { cn } from '@/lib/utils';
import { Label } from '@/components/ui/label';

/** A small segmented control. Radio semantics, so it is keyboard- and SR-usable. */
function Segmented<T extends string | number>({
  label,
  value,
  options,
  onChange,
  name,
}: {
  label: string;
  value: T;
  options: { value: T; label: string }[];
  onChange: (v: T) => void;
  name: string;
}) {
  return (
    <fieldset className="space-y-2">
      <legend className="text-sm font-medium">{label}</legend>
      <div role="radiogroup" aria-label={label} className="flex flex-wrap gap-1.5">
        {options.map((o) => (
          <button
            key={String(o.value)}
            type="button"
            role="radio"
            aria-checked={value === o.value}
            name={name}
            onClick={() => onChange(o.value)}
            className={cn(
              'rounded-md border px-3 py-1.5 text-sm transition-colors',
              value === o.value
                ? 'border-primary bg-primary text-primary-foreground'
                : 'border-input bg-background text-muted-foreground hover:bg-accent hover:text-accent-foreground'
            )}
          >
            {o.label}
          </button>
        ))}
      </div>
    </fieldset>
  );
}

export function AppearanceControls() {
  const { settings, set } = useSettings();

  return (
    <div className="space-y-6">
      <Segmented<ThemeMode>
        name="mode"
        label="Theme"
        value={settings.mode}
        onChange={(v) => set({ mode: v })}
        options={[
          { value: 'light', label: 'Light' },
          { value: 'dark', label: 'Dark' },
          { value: 'system', label: 'System' },
        ]}
      />

      <fieldset className="space-y-2">
        <legend className="text-sm font-medium">Accent</legend>
        <div role="radiogroup" aria-label="Accent" className="flex flex-wrap gap-2">
          {BRANDS.map((b) => (
            <button
              key={b.id}
              type="button"
              role="radio"
              aria-checked={settings.brand === b.id}
              aria-label={b.label}
              onClick={() => set({ brand: b.id })}
              data-brand={b.id}
              className={cn(
                'flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm transition-colors',
                settings.brand === b.id
                  ? 'border-primary'
                  : 'border-input text-muted-foreground hover:bg-accent'
              )}
            >
              <span
                aria-hidden
                className="h-3.5 w-3.5 rounded-full"
                style={{ background: 'oklch(var(--brand-l) var(--brand-c) var(--brand-h))' }}
              />
              {b.label}
            </button>
          ))}
        </div>
      </fieldset>

      <Segmented<number>
        name="radius"
        label="Corners"
        value={settings.radius}
        onChange={(v) => set({ radius: v })}
        options={RADII.map((r) => ({ value: r.value, label: r.label }))}
      />

      <Segmented<Density>
        name="density"
        label="Density"
        value={settings.density}
        onChange={(v) => set({ density: v })}
        options={[
          { value: 'comfortable', label: 'Comfortable' },
          { value: 'compact', label: 'Compact' },
        ]}
      />

      <Segmented<FontId>
        name="font"
        label="Typeface"
        value={settings.font}
        onChange={(v) => set({ font: v })}
        options={[
          { value: 'inter', label: 'Inter' },
          { value: 'system', label: 'System' },
          { value: 'serif', label: 'Serif' },
        ]}
      />
    </div>
  );
}

export function MotionControls() {
  const { settings, set } = useSettings();
  const osReduce = osPrefersReducedMotion();
  const overriding = osReduce && (settings.motion === 'full' || settings.motion === 'subtle');

  return (
    <div className="space-y-4">
      <Segmented<MotionPref>
        name="motion"
        label="Animation"
        value={settings.motion}
        onChange={(v) => set({ motion: v })}
        options={[
          { value: 'system', label: 'System' },
          { value: 'full', label: 'Full' },
          { value: 'subtle', label: 'Subtle' },
          { value: 'none', label: 'None' },
        ]}
      />
      <p className="text-sm text-muted-foreground">
        <span className="font-medium text-foreground">System</span> follows your
        operating system&rsquo;s reduced-motion setting
        {osReduce ? ' — which currently asks for reduced motion.' : '.'}
      </p>

      {overriding && (
        <div className="flex gap-2 rounded-md border border-warning-emphasis/40 bg-warning-muted p-3">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warning" />
          <p className="text-sm text-warning">
            Your system requests reduced motion. This setting overrides it.
          </p>
        </div>
      )}

      <div className="space-y-1.5">
        <Label className="text-muted-foreground">What each level does</Label>
        <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">
          <li>
            <span className="font-medium text-foreground">Full</span> — all transitions,
            reveals and overlay animations.
          </li>
          <li>
            <span className="font-medium text-foreground">Subtle</span> — fades kept,
            movement and scaling removed.
          </li>
          <li>
            <span className="font-medium text-foreground">None</span> — everything
            resolves instantly.
          </li>
        </ul>
      </div>
    </div>
  );
}
