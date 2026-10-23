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
          {error && <p className="type-body text-warn">{error}</p>}
          <div className="prose prose-base sm:prose-lg max-w-[70ch] mt-4 prose-h1:text-xl prose-h2:text-xl prose-h3:text-lg">
            <MarkdownContent>{topic.explanation}</MarkdownContent>
          </div>
        </>
      ) : error ? (
        <p className="type-body text-warn">{error}</p>
      ) : (
        <p className="flex items-center gap-2 type-body text-muted">
          <LoaderCircle size={16} className="animate-spin text-accent" />
          Writing the lesson, this can take a few minutes...
        </p>
      )}

      {topic.subtopics.length > 0 && (
        <section className="mt-8">
          <h2 className="type-caption uppercase tracking-wide text-faint">
            Subtopics
          </h2>
          <ul className="mt-2 flex flex-col gap-2">
            {topic.subtopics.map((subtopic) => (
              <li key={subtopic.id}>
                <Link
                  to={`/courses/${course.id}/topics/${subtopic.id}`}
                  className="block rounded-md bg-card px-4 py-3 type-item text-ink hover:bg-line"
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
