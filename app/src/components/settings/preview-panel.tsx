import { CheckCircle2, Clock, Info, XCircle } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { LADDER_LABELS } from '@/lib/learning';

const LADDER = [1, 2, 3, 4] as const;
const LADDER_CLASS: Record<number, string> = {
  1: 'bg-ladder-1-muted text-ladder-1',
  2: 'bg-ladder-2-muted text-ladder-2',
  3: 'bg-ladder-3-muted text-ladder-3',
  4: 'bg-ladder-4-muted text-ladder-4',
};

/** Live sample of every token the Appearance tab can move. */
export function PreviewPanel() {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Preview</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap gap-2">
          <Button size="sm">Primary</Button>
          <Button size="sm" variant="secondary">
            Secondary
          </Button>
          <Button size="sm" variant="outline">
            Outline
          </Button>
          <Button size="sm" variant="ghost">
            Ghost
          </Button>
          <Button size="sm" variant="destructive">
            Destructive
          </Button>
        </div>

        <div className="flex flex-wrap gap-2">
          <Badge variant="success">Cleared</Badge>
          <Badge variant="warning">Pending</Badge>
          <Badge variant="info">Tracked</Badge>
          <Badge variant="outline">Untracked</Badge>
        </div>

        <div className="flex flex-wrap gap-3 text-sm">
          <span className="flex items-center gap-1.5 text-success">
            <CheckCircle2 className="h-4 w-4" /> Met
          </span>
          <span className="flex items-center gap-1.5 text-warning">
            <Clock className="h-4 w-4" /> Pending
          </span>
          <span className="flex items-center gap-1.5 text-destructive-ink">
            <XCircle className="h-4 w-4" /> Short
          </span>
          <span className="flex items-center gap-1.5 text-info">
            <Info className="h-4 w-4" /> Note
          </span>
        </div>

        <div className="flex flex-wrap gap-1.5">
          {LADDER.map((n) => (
            <span
              key={n}
              className={`rounded-md px-2 py-1 text-xs font-medium ${LADDER_CLASS[n]}`}
            >
              {n}. {LADDER_LABELS[n] ?? `Tier ${n}`}
            </span>
          ))}
        </div>

        <p className="text-sm text-muted-foreground">
          Muted body text, and a{' '}
          <a href="#preview" className="text-primary underline underline-offset-2">
            link in the accent colour
          </a>
          .
        </p>
      </CardContent>
    </Card>
  );
}
