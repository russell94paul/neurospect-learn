import { useMemo } from 'react';
import Markdown, { defaultUrlTransform } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Link } from 'react-router-dom';
import { cn } from '@/lib/utils';
import { resolveWikilink, type ResolutionMaps } from '@/lib/content';

// Encode [[wikilink]] tokens into a private URL scheme react-markdown can carry
// through to the custom <a> renderer. We rewrite each [[target|display]] to a
// markdown link `[display](wikilink:<base64(raw)>)`; the anchor component then
// resolves the raw token against the page maps → internal <Link> or inert span.
const WIKILINK = /\[\[([^\]]+)\]\]/g;
const SCHEME = 'wikilink:';

function encodeWikilinks(body: string): string {
  return body.replace(WIKILINK, (_m, raw: string) => {
    // The link text is a placeholder; the real display is resolved from `raw`
    // in the <a> renderer. btoa on UTF-8: escape first so non-ASCII survives.
    const enc = btoa(unescape(encodeURIComponent(raw)));
    return `[wikilink](${SCHEME}${enc})`;
  });
}

// react-markdown v10 sanitizes hrefs and would strip our custom scheme to "".
// Preserve wikilink: URLs; defer everything else to the default (safe) transform.
function urlTransform(url: string): string {
  return url.startsWith(SCHEME) ? url : defaultUrlTransform(url);
}

function decodeWikilink(href: string): string | null {
  if (!href.startsWith(SCHEME)) return null;
  try {
    return decodeURIComponent(escape(atob(href.slice(SCHEME.length))));
  } catch {
    return null;
  }
}

interface Props {
  body: string;
  maps: ResolutionMaps;
  className?: string;
}

/**
 * Renders a content page's markdown (GFM) with [[wikilinks]] resolved to
 * internal /concepts/:slug routes. Unresolved links (anchor-only, or targets
 * outside the ingested corpus) render inert/disabled — never as dead <a>s.
 */
export function MarkdownRenderer({ body, maps, className }: Props) {
  const processed = useMemo(() => encodeWikilinks(body), [body]);

  return (
    <div
      className={cn(
        // Bind prose colours to the shadcn tokens (which follow the real
        // `.dark` class theme) rather than prose's own grays + the media-based
        // `dark:prose-invert`, which mismatches the class-based theme.
        'prose prose-sm max-w-none',
        '[--tw-prose-body:hsl(var(--foreground))] [--tw-prose-headings:hsl(var(--foreground))]',
        '[--tw-prose-bold:hsl(var(--foreground))] [--tw-prose-code:hsl(var(--foreground))]',
        '[--tw-prose-links:hsl(var(--primary))] [--tw-prose-quotes:hsl(var(--muted-foreground))]',
        '[--tw-prose-quote-borders:hsl(var(--border))] [--tw-prose-hr:hsl(var(--border))]',
        '[--tw-prose-bullets:hsl(var(--muted-foreground))] [--tw-prose-counters:hsl(var(--muted-foreground))]',
        '[--tw-prose-captions:hsl(var(--muted-foreground))] [--tw-prose-th-borders:hsl(var(--border))]',
        '[--tw-prose-td-borders:hsl(var(--border))] [--tw-prose-pre-bg:hsl(var(--muted))]',
        '[--tw-prose-pre-code:hsl(var(--foreground))]',
        '[&_h1]:scroll-mt-20 [&_a]:underline-offset-4',
        className
      )}
    >
      <Markdown
        remarkPlugins={[remarkGfm]}
        urlTransform={urlTransform}
        components={{
          a({ href, children, ...props }) {
            const raw = href ? decodeWikilink(href) : null;
            if (raw === null) {
              // Ordinary markdown link — open external in a new tab.
              const external = href?.startsWith('http');
              return (
                <a
                  href={href}
                  {...(external ? { target: '_blank', rel: 'noreferrer' } : {})}
                  {...props}
                >
                  {children}
                </a>
              );
            }
            const { display, slug } = resolveWikilink(raw, maps);
            if (slug) {
              return (
                <Link to={`/concepts/${slug}`} className="text-primary underline underline-offset-4">
                  {display}
                </Link>
              );
            }
            // Unresolved wikilink — inert.
            return (
              <span
                className="cursor-not-allowed text-muted-foreground underline decoration-dotted"
                title="Not in the ingested course corpus"
              >
                {display}
              </span>
            );
          },
        }}
      >
        {processed}
      </Markdown>
    </div>
  );
}
