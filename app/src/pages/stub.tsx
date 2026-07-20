import { useParams } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

/**
 * Generic placeholder page used for every route until its real feature lands
 * in a later phase (5c–5g). Renders the page title + the phase it arrives in,
 * plus any route params so dynamic routes are visibly distinct.
 */
export function StubPage({ title, phase }: { title: string; phase: string }) {
  const params = useParams();
  const paramEntries = Object.entries(params);

  return (
    <div className="mx-auto max-w-2xl">
      <Card>
        <CardHeader>
          <CardTitle className="text-2xl">{title}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-muted-foreground">
          <p>{phase} — coming soon.</p>
          {paramEntries.length > 0 && (
            <ul className="text-sm">
              {paramEntries.map(([key, value]) => (
                <li key={key}>
                  <span className="font-mono">{key}</span>: {value}
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
