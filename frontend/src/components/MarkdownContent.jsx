import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import { PrismLight as SyntaxHighlighter } from "react-syntax-highlighter";
import bash from "react-syntax-highlighter/dist/esm/languages/prism/bash";
import c from "react-syntax-highlighter/dist/esm/languages/prism/c";
import cpp from "react-syntax-highlighter/dist/esm/languages/prism/cpp";
import css from "react-syntax-highlighter/dist/esm/languages/prism/css";
import go from "react-syntax-highlighter/dist/esm/languages/prism/go";
import java from "react-syntax-highlighter/dist/esm/languages/prism/java";
import javascript from "react-syntax-highlighter/dist/esm/languages/prism/javascript";
import json from "react-syntax-highlighter/dist/esm/languages/prism/json";
import jsx from "react-syntax-highlighter/dist/esm/languages/prism/jsx";
import markdown from "react-syntax-highlighter/dist/esm/languages/prism/markdown";
import markup from "react-syntax-highlighter/dist/esm/languages/prism/markup";
import python from "react-syntax-highlighter/dist/esm/languages/prism/python";
import rust from "react-syntax-highlighter/dist/esm/languages/prism/rust";
import sql from "react-syntax-highlighter/dist/esm/languages/prism/sql";
import toml from "react-syntax-highlighter/dist/esm/languages/prism/toml";
import tsx from "react-syntax-highlighter/dist/esm/languages/prism/tsx";
import typescript from "react-syntax-highlighter/dist/esm/languages/prism/typescript";
import yaml from "react-syntax-highlighter/dist/esm/languages/prism/yaml";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import { normalizeMath } from "../utils/math";

// PrismLight ships no languages; registering only these keeps the bundle small.
// Other languages are still shown, just without colouring.
const LANGUAGES = {
  bash: bash,
  sh: bash,
  shell: bash,
  c: c,
  cpp: cpp,
  css: css,
  go: go,
  java: java,
  javascript: javascript,
  js: javascript,
  json: json,
  jsx: jsx,
  markdown: markdown,
  md: markdown,
  html: markup,
  xml: markup,
  python: python,
  py: python,
  rust: rust,
  rs: rust,
  sql: sql,
  toml: toml,
  tsx: tsx,
  typescript: typescript,
  ts: typescript,
  yaml: yaml,
  yml: yaml,
};
for (const [name, language] of Object.entries(LANGUAGES)) {
  SyntaxHighlighter.registerLanguage(name, language);
}

function MarkdownContent({ children }) {
  return (
    <Markdown
      remarkPlugins={[remarkGfm, remarkMath]}
      rehypePlugins={[rehypeKatex]}
      components={{
        code(props) {
          const { children, className, node: _node, ...rest } = props;
          const match = /language-(\w+)/.exec(className || "");
          return match ? (
            <SyntaxHighlighter
              {...rest}
              language={match[1]}
              style={oneDark}
              PreTag="div"
              customStyle={{
                fontFamily: "var(--font-mono)",
                margin: 0,
                borderRadius: "var(--radius-md)",
              }}
              codeTagProps={{ style: { fontFamily: "var(--font-mono)" } }}
            >
              {String(children).replace(/\n$/, "")}
            </SyntaxHighlighter>
          ) : (
            <code {...rest} className={className}>
              {children}
            </code>
          );
        },
      }}
    >
      {normalizeMath(children ?? "")}
    </Markdown>
  );
}

export default MarkdownContent;
