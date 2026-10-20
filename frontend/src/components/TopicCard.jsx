import { useState } from "react";
import { Link, useParams } from "react-router";
import { ArrowRight, BookCheck, ChevronRight } from "lucide-react";

function TopicCard({ topic }) {
  const [isOpen, setIsOpen] = useState(false);
  const { courseId } = useParams();

  return (
    <div className="border border-line rounded-md bg-paper">
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
        <span className="font-medium">{topic.title}</span>
        {topic.has_explanation && (
          <BookCheck
            size={16}
            className="shrink-0 ml-auto text-accent"
            aria-label="Lesson ready"
          />
        )}
      </button>

      {isOpen && (
        <div className="pl-10 pr-4 pb-3">
          <p className="text-sm text-ink/70">{topic.description}</p>
          <Link
            to={`/courses/${courseId}/topics/${topic.id}`}
            className="inline-flex items-center gap-1 mt-2 text-sm text-accent hover:underline"
          >
            Open lesson
            <ArrowRight size={14} />
          </Link>

          {topic.children.length > 0 && (
            <div className="flex flex-col gap-2 mt-3">
              {topic.children.map((child) => (
                <TopicCard key={child.id} topic={child} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default TopicCard;
