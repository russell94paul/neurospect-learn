import { useState } from 'react';
import { Controller, useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Loader2, Plus, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { WEEKDAYS } from '@/lib/planner';
import { TRACKS } from '@/lib/learning';
import type { PreferencesIn, PreferencesOut } from '@/types/api';

const minutes = z.number().int().min(0).max(1440);

const schema = z.object({
  timezone: z.string().min(1, 'Timezone is required'),
  mon_minutes: minutes,
  tue_minutes: minutes,
  wed_minutes: minutes,
  thu_minutes: minutes,
  fri_minutes: minutes,
  sat_minutes: minutes,
  sun_minutes: minutes,
  max_session_minutes: z.number().int().min(1).max(1440),
  active_track: z.enum(['aura', 'ict_course', 'unified']),
  target_go_live_date: z.string().optional(),
});

type FormValues = z.infer<typeof schema>;

function localTimezone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
  } catch {
    return 'UTC';
  }
}

function toDefaults(prefs?: PreferencesOut): FormValues {
  if (prefs?.is_configured) {
    return {
      timezone: prefs.timezone,
      mon_minutes: prefs.mon_minutes,
      tue_minutes: prefs.tue_minutes,
      wed_minutes: prefs.wed_minutes,
      thu_minutes: prefs.thu_minutes,
      fri_minutes: prefs.fri_minutes,
      sat_minutes: prefs.sat_minutes,
      sun_minutes: prefs.sun_minutes,
      max_session_minutes: prefs.max_session_minutes,
      active_track: (prefs.active_track as FormValues['active_track']) ?? 'aura',
      target_go_live_date: prefs.target_go_live_date ?? '',
    };
  }
  return {
    timezone: localTimezone(),
    mon_minutes: 30,
    tue_minutes: 30,
    wed_minutes: 30,
    thu_minutes: 30,
    fri_minutes: 30,
    sat_minutes: 45,
    sun_minutes: 0,
    max_session_minutes: 45,
    active_track: 'aura',
    target_go_live_date: '',
  };
}

/**
 * Availability & preferences — per-weekday minute budget, max single session,
 * timezone, blackout dates, and an optional (PACING-ONLY) target go-live date.
 * RHF + Zod. On save the whole schedule recomputes.
 */
export function AvailabilityForm({
  defaults,
  onSaved,
  isSaving,
  saveError,
}: {
  defaults?: PreferencesOut;
  onSaved: (body: PreferencesIn) => void;
  isSaving?: boolean;
  saveError?: string | null;
}) {
  const {
    register,
    handleSubmit,
    control,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: toDefaults(defaults),
  });

  const [blackouts, setBlackouts] = useState<string[]>(defaults?.blackout_dates ?? []);
  const [newBlackout, setNewBlackout] = useState('');

  function addBlackout() {
    if (newBlackout && !blackouts.includes(newBlackout)) {
      setBlackouts((b) => [...b, newBlackout].sort());
      setNewBlackout('');
    }
  }

  function submit(values: FormValues) {
    onSaved({
      timezone: values.timezone,
      mon_minutes: values.mon_minutes,
      tue_minutes: values.tue_minutes,
      wed_minutes: values.wed_minutes,
      thu_minutes: values.thu_minutes,
      fri_minutes: values.fri_minutes,
      sat_minutes: values.sat_minutes,
      sun_minutes: values.sun_minutes,
      max_session_minutes: values.max_session_minutes,
      blackout_dates: blackouts,
      target_go_live_date: values.target_go_live_date ? values.target_go_live_date : null,
      active_track: values.active_track,
    });
  }

  return (
    <form onSubmit={handleSubmit(submit)} className="space-y-6">
      {/* Track */}
      <section className="space-y-2">
        <Label>Active track</Label>
        <p className="text-xs text-muted-foreground">The planner schedules one track at a time.</p>
        <Controller
          control={control}
          name="active_track"
          render={({ field }) => (
            <Select value={field.value} onValueChange={field.onChange}>
              <SelectTrigger className="max-w-xs" aria-label="Active track">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {TRACKS.map((t) => (
                  <SelectItem key={t.key} value={t.key}>
                    {t.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        />
      </section>

      {/* Weekday minutes */}
      <section className="space-y-2">
        <Label>Minutes per weekday</Label>
        <p className="text-xs text-muted-foreground">0 = a day off. Weekends can run longer.</p>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 md:grid-cols-7">
          {WEEKDAYS.map((d) => (
            <div key={d.key} className="space-y-1">
              <Label htmlFor={d.key} className="text-xs text-muted-foreground">
                {d.label}
              </Label>
              <Input
                id={d.key}
                type="number"
                min={0}
                max={1440}
                className="tabular-nums"
                {...register(d.key as keyof FormValues, { valueAsNumber: true })}
              />
            </div>
          ))}
        </div>
      </section>

      {/* Max session + timezone */}
      <section className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1">
          <Label htmlFor="max_session_minutes">Max single session (min)</Label>
          <Input
            id="max_session_minutes"
            type="number"
            min={1}
            max={1440}
            className="max-w-[10rem] tabular-nums"
            {...register('max_session_minutes', { valueAsNumber: true })}
          />
          {errors.max_session_minutes && (
            <p className="text-xs text-destructive">{errors.max_session_minutes.message}</p>
          )}
        </div>
        <div className="space-y-1">
          <Label htmlFor="timezone">Timezone (IANA)</Label>
          <Input id="timezone" {...register('timezone')} placeholder="America/Chicago" />
          {errors.timezone && <p className="text-xs text-destructive">{errors.timezone.message}</p>}
        </div>
      </section>

      {/* Blackout dates */}
      <section className="space-y-2">
        <Label>Blackout dates</Label>
        <p className="text-xs text-muted-foreground">Days the planner skips (travel, breaks).</p>
        <div className="flex items-center gap-2">
          <Input
            type="date"
            value={newBlackout}
            onChange={(e) => setNewBlackout(e.target.value)}
            className="max-w-[12rem]"
            aria-label="Add blackout date"
          />
          <Button type="button" variant="outline" size="sm" onClick={addBlackout} disabled={!newBlackout}>
            <Plus className="mr-1 h-3.5 w-3.5" /> Add
          </Button>
        </div>
        {blackouts.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {blackouts.map((d) => (
              <span
                key={d}
                className="inline-flex items-center gap-1 rounded-md border bg-muted px-2 py-0.5 text-xs tabular-nums"
              >
                {d}
                <button
                  type="button"
                  onClick={() => setBlackouts((b) => b.filter((x) => x !== d))}
                  aria-label={`Remove ${d}`}
                  className="text-muted-foreground hover:text-destructive"
                >
                  <X className="h-3 w-3" />
                </button>
              </span>
            ))}
          </div>
        )}
      </section>

      {/* Target go-live date (pacing only) */}
      <section className="space-y-1">
        <Label htmlFor="target_go_live_date">Target go-live date (optional)</Label>
        <Input
          id="target_go_live_date"
          type="date"
          className="max-w-[12rem]"
          {...register('target_go_live_date')}
        />
        <p className="text-xs text-muted-foreground">
          Pacing only — this drives an ETA and on-pace flag. It never unlocks a stage or advances the
          Readiness-to-Live Gate.
        </p>
      </section>

      {saveError && <p className="text-sm text-destructive">{saveError}</p>}

      <Button type="submit" disabled={isSaving}>
        {isSaving && <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />}
        Save & generate plan
      </Button>
    </form>
  );
}
