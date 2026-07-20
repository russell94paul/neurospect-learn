import { Hand, Wrench } from 'lucide-react';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { useUpdateDrill } from '@/lib/learning';
import { RepCounter } from '@/components/progress/rep-counter';
import type { DrillOut } from '@/types/api';

const TRACK_LABELS: Record<string, string> = {
  aura: 'Aura',
  ict_course: 'ICT-course',
};

/**
 * One drill: the ✋ hand-marking / 🛠 tool-assisted variant marks + a rep
 * counter, mark-complete → PATCH /api/drills. Hand-marking first, tools second
 * (concepts/mastery/README) — the ✋ toggle leads.
 */
export function DrillCard({ drill }: { drill: DrillOut }) {
  const update = useUpdateDrill();

  const toggle = (variant: 'hand' | 'tool') =>
    update.mutate({
      drill_ref: drill.drill_ref,
      [variant === 'hand' ? 'hand_done' : 'tool_done']:
        variant === 'hand' ? !drill.hand_done : !drill.tool_done,
      last_practiced: new Date().toISOString().slice(0, 10),
    });

  const setReps = (reps: number) =>
    update.mutate({
      drill_ref: drill.drill_ref,
      reps,
      last_practiced: new Date().toISOString().slice(0, 10),
    });

  return (
    <Card data-testid="drill-card">
      <CardHeader className="pb-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="font-mono text-xs">
              {drill.drill_ref}
            </Badge>
            <span className="font-medium">{drill.title}</span>
          </div>
          <Badge variant="secondary">{TRACK_LABELS[drill.track] ?? drill.track}</Badge>
        </div>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
          {drill.advances_to && <span>advances to {drill.advances_to}</span>}
          {drill.rep_target && <span>· target: {drill.rep_target}</span>}
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <Button
            type="button"
            size="sm"
            variant={drill.hand_done ? 'default' : 'outline'}
            onClick={() => toggle('hand')}
            disabled={update.isPending}
            className="h-8"
          >
            <Hand className="mr-1.5 h-4 w-4" /> Hand-marked
          </Button>
          <Button
            type="button"
            size="sm"
            variant={drill.tool_done ? 'default' : 'outline'}
            onClick={() => toggle('tool')}
            disabled={update.isPending}
            className="h-8"
          >
            <Wrench className="mr-1.5 h-4 w-4" /> Tool-assisted
          </Button>
        </div>

        <RepCounter reps={drill.reps} target={drill.rep_target_count} onChange={setReps} />

        {drill.concept_slugs && drill.concept_slugs.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5 text-xs">
            <span className="text-muted-foreground">Advances:</span>
            {drill.concept_slugs.map((slug) => (
              <span
                key={slug}
                className="rounded bg-accent px-1.5 py-0.5 font-mono text-accent-foreground"
              >
                {slug}
              </span>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
