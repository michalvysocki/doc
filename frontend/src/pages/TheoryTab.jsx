import { Link, useOutletContext } from "react-router";
import MarkdownContent from "../components/MarkdownContent";
import { LoaderCircle } from "lucide-react";
import SourcesList from "../components/SourcesList";

function TheoryTab() {
  const { course, topic, error } = useOutletContext();

  return (
    <>
      {topic.explanation !== null ? (
        <>
          {error && <p className="text-sm text-warn">{error}</p>}
          <div className="prose prose-lg max-w-[70ch] text-ink mt-4 prose-headings:text-accent prose-a:text-accent prose-strong:text-ink">
            <MarkdownContent>{topic.explanation}</MarkdownContent>
          </div>
        </>
      ) : error ? (
        <p className="text-sm text-warn">{error}</p>
      ) : (
        <p className="flex items-center gap-2 text-sm text-ink/60">
          <LoaderCircle size={16} className="animate-spin text-accent" />
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

      <SourcesList sources={topic.sources} />
    </>
  );
}

export default TheoryTab;
