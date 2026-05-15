import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/**
 * Shared markdown renderer. Used for LLM-produced prose throughout the app
 * (paper analyses, chat replies). Strips HTML for safety and applies our
 * design-system styling via the `.md-content` selector in globals.css.
 */
export function MarkdownContent({ children }: { children: string }) {
  return (
    <div className="md-content">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        // We disallow raw HTML on purpose: paper content is mostly trustworthy
        // (it came from our own LLM call) but defence-in-depth keeps the chat
        // bubble from ever rendering a stray <script>.
        skipHtml
        components={{
          // Open external links in a new tab; internal anchors stay in-page.
          a: ({ href, children: kids, ...rest }) => {
            const external = href?.startsWith("http");
            return (
              <a
                href={href}
                target={external ? "_blank" : undefined}
                rel={external ? "noopener noreferrer" : undefined}
                {...rest}
              >
                {kids}
              </a>
            );
          },
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}

export default MarkdownContent;
