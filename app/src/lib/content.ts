import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import type { ContentPageDetail, ContentPageSummary } from '@/types/api';

// ============================================================
// TanStack Query hooks — hierarchical keys under ['content'].
// ============================================================

export const contentKeys = {
  all: ['content'] as const,
  pages: () => [...contentKeys.all, 'pages'] as const,
  page: (slug: string) => [...contentKeys.all, 'page', slug] as const,
  search: (q: string) => [...contentKeys.all, 'search', q] as const,
};

export function useContentPages() {
  return useQuery({
    queryKey: contentKeys.pages(),
    queryFn: () => api.get('api/content/pages').json<ContentPageSummary[]>(),
    staleTime: 5 * 60_000, // content changes only on re-ingest
  });
}

export function useContentPage(slug: string | undefined) {
  return useQuery({
    queryKey: contentKeys.page(slug ?? ''),
    queryFn: () => api.get(`api/content/pages/${slug}`).json<ContentPageDetail>(),
    enabled: !!slug,
  });
}

export function useContentSearch(q: string) {
  const query = q.trim();
  return useQuery({
    queryKey: contentKeys.search(query),
    queryFn: () =>
      api.get('api/content/search', { searchParams: { q: query } }).json<ContentPageSummary[]>(),
    enabled: query.length >= 2,
    staleTime: 60_000,
  });
}

// ============================================================
// Wikilink resolution — LOOKUP-only mirror of the backend.
//
// The backend (scripts/ingest_content.py) owns the slug scheme. The frontend
// never re-derives it: it builds path/basename → slug maps from the page list
// (slug + source_path) and resolves each raw [[token]] by lookup. Only the
// token normalization (strip |display, #anchor, concepts/ prefix, .md) is
// shared, and that is trivial string handling, not the slug scheme.
// ============================================================

export interface ResolutionMaps {
  slugs: Set<string>;
  pathToSlug: Map<string, string>;
  basenameToSlug: Map<string, string>;
  titles: Map<string, string>; // slug → page title (for wikilink display text)
}

const NUM_PREFIX = /^\d+[-_]/;

export function buildResolutionMaps(pages: ContentPageSummary[]): ResolutionMaps {
  const slugs = new Set<string>();
  const pathToSlug = new Map<string, string>();
  const titles = new Map<string, string>();
  const basenameSeen = new Map<string, string>();
  const basenameDupes = new Set<string>();

  for (const p of pages) {
    slugs.add(p.slug);
    titles.set(p.slug, p.title);
    if (!p.source_path) continue;
    // source_path e.g. "concepts/aura/sequential-smt.md" → rel "aura/sequential-smt"
    const rel = p.source_path
      .replace(/^concepts\//, '')
      .replace(/\.md$/i, '')
      .toLowerCase();
    pathToSlug.set(rel, p.slug);

    const base = rel.split('/').pop()!.replace(NUM_PREFIX, '');
    if (base === 'readme') continue;
    if (basenameSeen.has(base) && basenameSeen.get(base) !== p.slug) {
      basenameDupes.add(base);
    }
    basenameSeen.set(base, p.slug);
  }
  for (const dup of basenameDupes) basenameSeen.delete(dup); // ambiguous → unresolvable

  return { slugs, pathToSlug, basenameToSlug: basenameSeen, titles };
}

/**
 * Strip the leading `# H1` from a page body — the reader's card header already
 * shows the title, so rendering the body's own title H1 duplicates it.
 */
export function stripLeadingH1(body: string): string {
  return body.replace(/^\s*#\s+.*(?:\r?\n)+/, '');
}

/** A parsed wikilink: the display text + the resolved target slug (or null). */
export interface ResolvedWikilink {
  display: string;
  slug: string | null; // null = anchor-only or out-of-corpus (render inert)
}

export function resolveWikilink(raw: string, maps: ResolutionMaps): ResolvedWikilink {
  const [targetPart, displayPart] = raw.split('|', 2);
  const target = targetPart.split('#', 1)[0].trim();
  const hasAlias = displayPart !== undefined && displayPart.trim() !== '';
  const fallbackDisplay = (displayPart ?? targetPart).trim();

  if (!target) return { display: fallbackDisplay, slug: null }; // anchor-only [[#Section]]

  let token = target.replace(/\.md$/i, '').replace(/^concepts\//i, '').replace(/^\/+|\/+$/g, '');
  token = token.toLowerCase();

  const slug = token.includes('/')
    ? maps.pathToSlug.get(token) ?? null
    : maps.basenameToSlug.get(token.replace(NUM_PREFIX, '')) ?? null;

  // Prefer an explicit |alias; otherwise show the resolved page's title rather
  // than the raw path token (Obsidian-style). Unresolved links keep the token.
  const display = hasAlias
    ? fallbackDisplay
    : (slug && maps.titles.get(slug)) || fallbackDisplay;

  return { display, slug };
}
