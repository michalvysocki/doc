import { Link } from "react-router";

// "Requires: A · B" with links to the lessons of the required topics.
function RequiredTopics({ courseId, topics, className = "" }) {
  if (topics.length === 0) return null;

  return (
    <p
      className={`flex flex-wrap gap-x-1 type-caption text-muted ${className}`}
    >
      <span className="text-faint">Requires:</span>
      {topics.map((link, index) => (
        <span key={link.id}>
          <Link
            to={`/courses/${courseId}/topics/${link.id}`}
            className="hover:text-ink hover:underline"
          >
            {link.title}
          </Link>
          {index < topics.length - 1 && " ·"}
        </span>
      ))}
    </p>
  );
}

export default RequiredTopics;
