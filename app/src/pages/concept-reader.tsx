import { useMemo } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { buildResolutionMaps, stripLeadingH1, useContentPage, useContentPages } from '@/lib/content';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Button } from '@/components/ui/button';
import { ConceptBadgeRow } from '@/components/content/badges';
import { MarkdownRenderer } from '@/components/content/markdown-renderer';

export function ConceptReaderPage() {
  const { slug } = useParams<{ slug: string }>();
  const pageQuery = useContentPage(slug);
  const pagesQuery = useContentPages(); // for wikilink resolution maps

  const maps = useMemo(
    () => buildResolutionMaps(pagesQuery.data ?? []),
    [pagesQuery.data]
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
    </div>
  );
}
