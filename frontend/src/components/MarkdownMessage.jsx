/*
 * Shared markdown + KaTeX renderer, used by every modality so the base
 * rendering logic (and its dependency set: react-markdown, remark-math,
 * rehype-katex -- all already in the recovered package.json) lives in
 * one place. react-markdown renders $$...$$ as display math out of the
 * box via remark-math, so the same $$ delimiters MathGuard parses on
 * the backend are what render as LaTeX here -- no separate convention
 * needed between the two.
 */

import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";

export default function MarkdownMessage({ text }) {
  return (
    <div className="markdown-message">
      <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
        {text}
      </ReactMarkdown>
    </div>
  );
}
