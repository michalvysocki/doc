import {
  Link,
  NavLink,
  Outlet,
  useOutletContext,
  useParams,
} from "react-router";
import { ChevronRight } from "lucide-react";
import useTopic from "../hooks/useTopic";
import Skeleton from "../components/Skeleton";

function tabClass({ isActive }) {
  return `px-3 py-2 border-b-2 -mb-px ${
    isActive
      ? "border-accent type-label text-accent"
      : "border-transparent type-body text-muted hover:text-ink"
  }`;
}

function TopicLayout() {
  const { topicId } = useParams();
  const { course, courseVersion } = useOutletContext();
  const { topic, error } = useTopic(topicId, courseVersion);

  if (topic === null) {
    return error ? (
      <p className="type-body text-warn">{error}</p>
    ) : (
      <div className="max-w-3xl mx-auto w-full">
        <Skeleton lines={2} className="w-2/3" />
        <Skeleton lines={8} className="mt-8" />
      </div>
    );
  }

  return (
    <article className="max-w-3xl mx-auto w-full">
      <nav className="flex flex-wrap items-center gap-1 type-body text-muted">
        <Link to={`/courses/${course.id}`} className="hover:text-ink">
          {course.title}
        </Link>
        {topic.path.map((link) => (
          <span key={link.id} className="flex items-center gap-1">
            <ChevronRight size={14} />
            <Link
              to={`/courses/${course.id}/topics/${link.id}`}
              className="hover:text-ink"
            >
              {link.title}
            </Link>
          </span>
        ))}
      </nav>

      <h1 className="type-title text-ink mt-2">{topic.title}</h1>
      <p className="type-body text-muted mt-1">{topic.description}</p>

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
