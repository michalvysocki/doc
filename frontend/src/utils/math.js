// Fenced code blocks and inline code are left untouched.
const CODE = /(```[\s\S]*?```|`[^`\n]*`)/g;

// Structured (JSON) output sometimes doubles the backslash: \\( ... \\).
const DISPLAY = /\\{1,2}\[([\s\S]+?)\\{1,2}\]/g;
const INLINE = /\\{1,2}\(([\s\S]+?)\\{1,2}\)/g;

// remark-math understands only $...$ and $$...$$, models often write \(...\) and \[...\].
export function normalizeMath(text) {
  return text
    .split(CODE)
    .map((part, index) =>
      index % 2 === 1
        ? part
        : part
            .replace(DISPLAY, (_, math) => `\n$$\n${math.trim()}\n$$\n`)
            .replace(INLINE, (_, math) => `$${math.trim()}$`),
    )
    .join("");
}
