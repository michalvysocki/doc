import { Link, useOutletContext, useParams } from "react-router";
import { ChevronRight } from "lucide-react";
import useTopic from "../hooks/useTopic";
import MarkdownContent from "../components/MarkdownContent";

function TopicPage() {
  const { topicId } = useParams();
  const { course } = useOutletContext();
  const { topic, error } = useTopic(topicId);

  if (topic === null) {
    return error ? (
      <p className="text-sm text-warn">{error}</p>
    ) : (
      <p className="text-sm text-ink/60">Loading topic...</p>
    );
  }

  return (
    <article className="max-w-3xl mx-auto w-full">
      <nav className="flex flex-wrap items-center gap-1 text-sm text-ink/60">
        <Link to={`/courses/${course.id}`} className="hover:text-accent">
          {course.title}
        </Link>
        {topic.path.map((link) => (
          <span key={link.id} className="flex items-center gap-1">
            <ChevronRight size={14} />
            <Link
              to={`/courses/${course.id}/topics/${link.id}`}
              className="hover:text-accent"
            >
              {link.title}
            </Link>
          </span>
        ))}
      </nav>

      <h1 className="text-2xl font-semibold text-ink mt-2">{topic.title}</h1>
      <p className="text-ink/70 mt-1">{topic.description}</p>

      <div className="mt-6">
        {topic.explanation !== null ? (
          <div className="prose max-w-none text-ink">
            <MarkdownContent>{topic.explanation}</MarkdownContent>
          </div>
        ) : error ? (
          <p className="text-sm text-warn">{error}</p>
        ) : (
          <p className="text-sm text-ink/60">
            Writing the lesson, this can take a few minutes...
          </p>
        )}
      </div>

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
    </article>
  );
}

export default TopicPage;
