import { Link, useOutletContext } from "react-router";
import { RefreshCw } from "lucide-react";
import MarkdownContent from "../components/MarkdownContent";

function TheoryTab() {
  const { course, topic, error, isRegenerating, regenerate } =
    useOutletContext();

  function handleRegenerate() {
    const confirmed = window.confirm(
      "Regenerate the lesson? The current lesson will be replaced.",
    );
    if (confirmed) regenerate();
  }

  return (
    <>
      {topic.explanation !== null ? (
        <>
          <div className="flex justify-end">
            <button
              type="button"
              onClick={handleRegenerate}
              disabled={isRegenerating}
              className="inline-flex items-center gap-1 rounded-md border border-line px-3 py-1.5 text-sm text-ink hover:bg-line/50 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <RefreshCw
                size={14}
                className={isRegenerating ? "animate-spin" : ""}
              />
              {isRegenerating ? "Regenerating..." : "Regenerate lesson"}
            </button>
          </div>
          {error && <p className="text-sm text-warn mt-2">{error}</p>}
          <div className="prose max-w-none text-ink mt-4">
            <MarkdownContent>{topic.explanation}</MarkdownContent>
          </div>
        </>
      ) : error ? (
        <p className="text-sm text-warn">{error}</p>
      ) : (
        <p className="text-sm text-ink/60">
          Writing the lesson, this can take a few minutes...
        </p>
      )}

      {topic.subtopics.length > 0 && (
        <section className="mt-8">
          <h2 className="text-lg font-semibold text-ink">Subtopics</h2>
          <ul className="mt-2 flex flex-col gap-2">
            {topic.subtopics.map((subtopic) => (
              <li key={subtopic.id}>
                <Link
                  to={`/courses/${course.id}/topics/${subtopic.id}`}
                  className="block border border-line rounded-md px-4 py-3 text-ink hover:bg-line/50"
                >
                  {subtopic.title}
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}
    </>
  );
}

export default TheoryTab;
