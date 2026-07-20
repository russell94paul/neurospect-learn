import { useMemo } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { buildResolutionMaps, stripLeadingH1, useContentPage, useContentPages } from '@/lib/content';
import { useProgress } from '@/lib/learning';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Button } from '@/components/ui/button';
import { ConceptBadgeRow } from '@/components/content/badges';
import { MarkdownRenderer } from '@/components/content/markdown-renderer';
import { ConceptTrackPanel } from '@/components/progress/concept-track-panel';

export function ConceptReaderPage() {
  const { slug } = useParams<{ slug: string }>();
  const pageQuery = useContentPage(slug);
  const pagesQuery = useContentPages(); // for wikilink resolution maps
  const progressQuery = useProgress(); // concepts referencing this page → track panels

  const maps = useMemo(
    () => buildResolutionMaps(pagesQuery.data ?? []),
    [pagesQuery.data]
  );

  // A content page may be referenced by 0..N gradable concepts (via
  // concept.content_slug). Surface a "track this" panel for each.
  const trackedConcepts = useMemo(
    () => (progressQuery.data ?? []).filter((r) => r.content_slug === slug),
    [progressQuery.data, slug]
  );

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <Button variant="ghost" size="sm" asChild>
        <Link to="/library">
          <ArrowLeft className="mr-1 h-4 w-4" />
          Library
        </Link>
      </Button>

      {pageQuery.isLoading && (
        <div className="space-y-3">
          <Skeleton className="h-8 w-2/3" />
          <Skeleton className="h-64 w-full" />
        </div>
      )}

      {pageQuery.isError && (
        <Card>
          <CardContent className="py-10 text-center text-muted-foreground">
            <p>Page not found: <span className="font-mono">{slug}</span></p>
            <Button variant="link" asChild>
              <Link to="/library">Back to the library</Link>
            </Button>
          </CardContent>
        </Card>
      )}

      {pageQuery.data && (
        <Card>
          <CardHeader className="space-y-3">
            <h1 className="text-2xl font-bold leading-tight">{pageQuery.data.title}</h1>
            <ConceptBadgeRow badge={pageQuery.data.badge} />
            {pageQuery.data.category && (
              <p className="text-xs uppercase tracking-wide text-muted-foreground">
                {pageQuery.data.category}
              </p>
            )}
          </CardHeader>
          <CardContent>
            <MarkdownRenderer body={stripLeadingH1(pageQuery.data.body)} maps={maps} />
          </CardContent>
        </Card>
      )}

      {pageQuery.data && trackedConcepts.length > 0 && (
        <div className="space-y-3">
          <h2 className="text-sm font-semibold text-muted-foreground">
            {trackedConcepts.length > 1 ? 'Concepts on this page' : 'Track your progress'}
          </h2>
          {trackedConcepts.map((row) => (
            <ConceptTrackPanel key={row.concept_id} row={row} />
          ))}
        </div>
      )}
    </div>
  );
}
