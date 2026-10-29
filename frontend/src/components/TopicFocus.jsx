import { Link } from "react-router";
import { ArrowLeft, ArrowRight } from "lucide-react";
import TopicStatus from "./TopicStatus";

function TopicColumn({ label, topics, empty, onFocus }) {
  return (
    <section>
      <h3 className="type-caption uppercase tracking-wide text-faint">
        {label}
      </h3>
      {topics.length === 0 ? (
        <p className="type-caption text-faint mt-2">{empty}</p>
      ) : (
        <ul className="mt-2 flex flex-col gap-1">
          {topics.map((topic) => (
            <li key={topic.id}>
              <button
                type="button"
                onClick={() => onFocus(topic.id)}
                className="w-full rounded-md bg-card px-3 py-2 text-left hover:bg-line"
              >
                <span className="block type-caption text-faint truncate">
                  {topic.moduleTitle}
                </span>
                <span className="flex items-center gap-2">
                  <span className="type-body text-ink">{topic.title}</span>
                  <TopicStatus topic={topic} />
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function TopicFocus({ courseId, focus, onFocus, onBack }) {
  const { topic, requires, requiredBy } = focus;

  return (
    <div className="@container rounded-md border border-line bg-paper p-4">
      <button
        type="button"
        onClick={onBack}
        className="inline-flex items-center gap-1 type-caption text-faint hover:text-ink"
      >
        <ArrowLeft size={14} />
        All modules
      </button>

      <div className="mt-3 grid gap-4 @2xl:grid-cols-3 @2xl:items-center">
        <TopicColumn
          label="Requires"
          topics={requires}
          empty="No prerequisites besides the course order"
          onFocus={onFocus}
        />

        <section className="rounded-md border border-accent bg-accent/5 p-4">
          <p className="type-caption text-faint">{topic.moduleTitle}</p>
          <div className="flex items-center gap-2 mt-1">
            <h2 className="type-item text-ink">{topic.title}</h2>
            <TopicStatus topic={topic} />
          </div>
          <p className="type-body text-muted mt-2">{topic.description}</p>
          <Link
            to={`/courses/${courseId}/topics/${topic.id}`}
            className="inline-flex items-center gap-1 mt-3 type-body text-accent hover:underline"
          >
            {topic.has_explanation ? "Open lesson" : "Write lesson"}
            <ArrowRight size={14} />
          </Link>
        </section>

        <TopicColumn
          label="Required by"
          topics={requiredBy}
          empty="No topic builds on it directly"
          onFocus={onFocus}
        />
      </div>
    </div>
  );
}

export default TopicFocus;
