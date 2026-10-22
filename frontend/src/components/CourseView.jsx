import { useOutletContext } from "react-router";
import CourseRebuildPreview from "./CourseRebuildPreview";
import TopicCard from "./TopicCard";

function CourseView() {
  const { course, courseRebuild } = useOutletContext();
  const { topics_total, topics_completed } = course.progress;
  const percent =
    topics_total > 0 ? Math.round((topics_completed / topics_total) * 100) : 0;

  return (
    <div className="max-w-3xl mx-auto w-full">
      <h1 className="text-xl font-semibold text-ink">{course.title}</h1>

      <div className="mt-3">
        <div className="h-2 rounded-full bg-line overflow-hidden">
          <div
            className="h-full bg-accent transition-all"
            style={{ width: `${percent}%` }}
          />
        </div>
        <p className="text-xs text-ink/60 mt-1">
          {topics_completed} / {topics_total} topics completed
        </p>
      </div>

      {courseRebuild.rebuild && (
        <div className="mt-4">
          <CourseRebuildPreview courseRebuild={courseRebuild} />
        </div>
      )}

      <div className="flex flex-col gap-2 mt-4">
        {course.topics.map((topic) => (
          <TopicCard key={topic.id} topic={topic} />
        ))}
      </div>
    </div>
  );
}

export default CourseView;
