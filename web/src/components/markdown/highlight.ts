import type { Options } from 'react-markdown'
import rehypeHighlight from 'rehype-highlight'

type RehypePlugin = NonNullable<Options['rehypePlugins']>[number]

/**
 * The syntax highlighter, in its own module so it is only ever loaded through
 * `import()`: highlight.js and its grammars are about half of the Markdown
 * bundle, and most answers contain no code. Same languages and auto-detection
 * as before; rehype-highlight v7 already skips unknown fence languages instead
 * of throwing.
 */
export const rehypeHighlightPlugin: RehypePlugin = [rehypeHighlight, { detect: true }]
