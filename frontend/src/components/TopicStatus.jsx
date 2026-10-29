import { BookCheck, CircleCheck } from "lucide-react";
import { isTopicCompleted } from "../utils/moduleGraph";

function TopicStatus({ topic }) {
  return (
    <span className="ml-auto flex items-center gap-1 shrink-0">
      {topic.reviews_due > 0 && (
        <span className="rounded-full bg-accent/10 px-1.5 type-caption text-accent">
          {topic.reviews_due}
        </span>
      )}
      {topic.has_explanation && (
        <BookCheck
          size={14}
          className="text-accent"
          aria-label="Lesson ready"
        />
      )}
      {isTopicCompleted(topic) && (
        <CircleCheck
          size={14}
          className="text-good"
          aria-label="Topic completed"
        />
      )}
    </span>
  );
}

export default TopicStatus;
