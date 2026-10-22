import {
  Link,
  NavLink,
  Outlet,
  useOutletContext,
  useParams,
} from "react-router";
import { ChevronRight } from "lucide-react";
import useTopic from "../hooks/useTopic";

function tabClass({ isActive }) {
  return `px-3 py-2 text-sm border-b-2 -mb-px ${
    isActive
      ? "border-accent text-accent font-medium"
      : "border-transparent text-ink/60 hover:text-ink"
  }`;
}

function TopicLayout() {
  const { topicId } = useParams();
  const { course, courseVersion } = useOutletContext();
  const { topic, error } = useTopic(topicId, courseVersion);

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

      <nav className="flex gap-2 mt-4 border-b border-line">
        <NavLink to="." end className={tabClass}>
          Theory
        </NavLink>
        <NavLink to="tasks" className={tabClass}>
          Tasks
        </NavLink>
      </nav>

      <div className="mt-6">
        <Outlet
          context={{
            course,
            courseVersion,
            topic,
            error,
          }}
        />
      </div>
    </article>
  );
}

export default TopicLayout;
