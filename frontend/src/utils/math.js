// Fenced code blocks and inline code are left untouched.
const CODE = /(```[\s\S]*?```|`[^`\n]*`)/g;

// remark-math understands only $...$ and $$...$$, models often write \(...\) and \[...\].
export function normalizeMath(text) {
  return text
    .split(CODE)
    .map((part, index) =>
      index % 2 === 1
        ? part
        : part
            .replace(
              /\\\[([\s\S]+?)\\\]/g,
              (_, math) => `\n$$\n${math.trim()}\n$$\n`,
            )
            .replace(/\\\(([\s\S]+?)\\\)/g, (_, math) => `$${math.trim()}$`),
    )
    .join("");
}
