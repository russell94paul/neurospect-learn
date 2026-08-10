/**
 * Rubric item text, with the wiki's markdown emphasis rendered AS emphasis.
 *
 * Extracted from `SelfCheck` at E4 so the AI second reader can render the same
 * strings the same way. It is deliberately ONE implementation: both surfaces
 * show the *same* wiki sentence, and a second copy of this parser would be free
 * to drift — which is the whole failure mode the rubric layer exists to avoid
 * (the wiki is canonical; nothing in the app authors or reshapes a bar).
 *
 * Why it is load-bearing rather than cosmetic: the corpus really does contain
 * `write your *actual* daily routine` and `implement **two** environment
 * changes`. Rendered raw, the user reads asterisks in the middle of their own
 * course notes. E3 verified the self-check for exactly this; E4's live
 * walkthrough caught the advisory panel reintroducing it, which is why the
 * renderer now lives here instead of inside one component.
 *
 * It renders emphasis only — it never rewrites, truncates or re-words the text.
 */
export function RubricText({ text }: { text: string }) {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`|\*[^*]+\*)/g).filter(Boolean);
  return (
    <>
      {parts.map((part, i) => {
        if (part.startsWith('**') && part.endsWith('**'))
          return <strong key={i}>{part.slice(2, -2)}</strong>;
        if (part.startsWith('`') && part.endsWith('`'))
          return (
            <code key={i} className="rounded bg-muted px-1 font-mono text-[0.9em]">
              {part.slice(1, -1)}
            </code>
          );
        if (part.startsWith('*') && part.endsWith('*')) return <em key={i}>{part.slice(1, -1)}</em>;
        return <span key={i}>{part}</span>;
      })}
    </>
  );
}
