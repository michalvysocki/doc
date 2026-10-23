import { useState } from "react";
import { Link, useParams } from "react-router";
import { ArrowRight, BookCheck, ChevronRight, CircleCheck } from "lucide-react";

function TopicCard({ topic, depth = 0 }) {
  const [isOpen, setIsOpen] = useState(false);
  const { courseId } = useParams();
  const isCompleted =
    topic.tasks_total > 0 && topic.tasks_solved === topic.tasks_total;

  return (
    <div
      className={`rounded-md transition-colors has-[>button:hover]:bg-line ${
        depth === 0 ? "bg-card" : ""
      }`}
    >
      <button
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        aria-expanded={isOpen}
        className="w-full flex items-center gap-2 px-4 py-3 text-left text-ink"
      >
        <ChevronRight
          size={16}
          className={`shrink-0 transition-transform ${isOpen ? "rotate-90" : ""}`}
        />
        <span className="type-item">{topic.title}</span>
        <span className="ml-auto flex items-center gap-2 shrink-0">
          {topic.reviews_due > 0 && (
            <span className="rounded-full bg-accent/10 px-2 py-0.5 type-caption text-accent">
              {topic.reviews_due} to review
            </span>
          )}
          {topic.has_explanation && (
            <BookCheck
              size={16}
              className="text-accent"
              aria-label="Lesson ready"
            />
          )}
          {isCompleted ? (
            <CircleCheck
              size={16}
              className="text-good"
              aria-label="Topic completed"
            />
          ) : (
            topic.tasks_total > 0 && (
              <span className="type-caption text-faint">
                {topic.tasks_solved}/{topic.tasks_total}
              </span>
            )
          )}
        </span>
      </button>

      <div
        className={`grid transition-[grid-template-rows] duration-200 ease-out ${
          isOpen ? "grid-rows-[1fr]" : "grid-rows-[0fr]"
        }`}
        inert={!isOpen}
      >
        <div className="overflow-hidden">
          <div className="pl-10 pr-4 pb-3">
            <p className="type-body text-muted">{topic.description}</p>
            <Link
              to={`/courses/${courseId}/topics/${topic.id}`}
              className="inline-flex items-center gap-1 mt-2 type-body text-accent hover:underline"
            >
              Open lesson
              <ArrowRight size={14} />
            </Link>

            {topic.children.length > 0 && (
              <div className="flex flex-col gap-1 mt-3 border-l border-line pl-2">
                {topic.children.map((child) => (
                  <TopicCard key={child.id} topic={child} depth={depth + 1} />
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default TopicCard;
