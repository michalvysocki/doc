import { FileText, Globe } from "lucide-react";

function isWebLink(url) {
  return typeof url === "string" && /^https?:\/\//.test(url);
}

function SourcesList({
  sources,
  className = "mt-8 border-t border-line pt-4",
}) {
  if (!sources || sources.length === 0) return null;

  const pages = sources.filter((source) => source.kind === "web");
  const files = sources.filter((source) => source.kind === "file");

  return (
    <section className={className}>
      <h2 className="text-sm font-semibold text-ink">Sources</h2>
      <ul className="mt-2 flex flex-col gap-1 text-sm">
        {pages.map((source) => (
          <li key={source.url} className="flex items-start gap-2">
            <Globe size={14} className="mt-0.5 shrink-0 text-ink/50" />
            {isWebLink(source.url) ? (
              <a
                href={source.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-accent hover:underline break-words"
              >
                {source.title}
              </a>
            ) : (
              <span className="text-ink/80">{source.title}</span>
            )}
          </li>
        ))}
        {files.map((source) => (
          <li key={`file-${source.title}`} className="flex items-start gap-2">
            <FileText size={14} className="mt-0.5 shrink-0 text-ink/50" />
            <span className="text-ink/80">{source.title}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

export default SourcesList;
