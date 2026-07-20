import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Search } from 'lucide-react';
import { useContentPages, useContentSearch } from '@/lib/content';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { LabelBadge, TierBadge } from '@/components/content/badges';
import type { ContentPageSummary } from '@/types/api';

// Display order + labels for the category groups (the top-level concepts/ dirs).
const CATEGORY_ORDER: { key: string; label: string }[] = [
  { key: 'course', label: 'Course' },
  { key: 'entry-models', label: 'Entry Models' },
  { key: 'mastery', label: 'Mastery' },
  { key: 'aura', label: 'Aura' },
  { key: 'business-logic', label: 'Business Logic' },
  { key: 'advanced', label: 'Frontier / Advanced' },
];

function PageRow({ page }: { page: ContentPageSummary }) {
  return (
    <li>
      <Link
        to={`/concepts/${page.slug}`}
        className="flex items-center justify-between gap-3 rounded-md px-3 py-2 text-sm hover:bg-accent hover:text-accent-foreground"
      >
        <span className="truncate">{page.title}</span>
        <span className="flex shrink-0 items-center gap-1.5">
          <TierBadge tier={page.tier} />
          <LabelBadge label={page.label} />
        </span>
      </Link>
    </li>
  );
}

export function LibraryPage() {
  const [q, setQ] = useState('');
  const query = q.trim();
  const searching = query.length >= 2;

  const pagesQuery = useContentPages();
  const searchQuery = useContentSearch(q);

  const grouped = useMemo(() => {
    const src = searching ? searchQuery.data : pagesQuery.data;
    const by = new Map<string, ContentPageSummary[]>();
    for (const p of src ?? []) {
      const cat = p.category ?? 'other';
      let arr = by.get(cat);
      if (!arr) {
        arr = [];
        by.set(cat, arr);
      }
      arr.push(p);
    }
    return by;
  }, [searching, searchQuery.data, pagesQuery.data]);

  const isLoading = searching ? searchQuery.isLoading : pagesQuery.isLoading;
  const total = searching ? searchQuery.data?.length ?? 0 : pagesQuery.data?.length ?? 0;
  const orderedCats = CATEGORY_ORDER.filter((c) => grouped.has(c.key));
  const extraCats = [...grouped.keys()].filter(
    (k) => !CATEGORY_ORDER.some((c) => c.key === k)
  );

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Library</h1>
        <p className="text-muted-foreground">The Neurospect course corpus — {total} pages.</p>
      </div>

      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search titles and content…"
          className="pl-9"
          aria-label="Search content"
        />
      </div>

      {isLoading && (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-32 w-full" />
          ))}
        </div>
      )}

      {!isLoading && searching && total === 0 && (
        <p className="text-sm text-muted-foreground">No pages match “{query}”.</p>
      )}

      {!isLoading &&
        [...orderedCats.map((c) => c.key), ...extraCats].map((catKey) => {
          const label = CATEGORY_ORDER.find((c) => c.key === catKey)?.label ?? catKey;
          const pages = grouped.get(catKey) ?? [];
          return (
            <Card key={catKey}>
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center justify-between text-base">
                  <span>{label}</span>
                  <span className="text-xs font-normal text-muted-foreground">{pages.length}</span>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="-mx-3 divide-y divide-border/50">
                  {pages.map((p) => (
                    <PageRow key={p.slug} page={p} />
                  ))}
                </ul>
              </CardContent>
            </Card>
          );
        })}
    </div>
  );
}
