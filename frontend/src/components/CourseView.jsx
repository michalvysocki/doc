import { Link, useOutletContext } from "react-router";
import { RotateCcw } from "lucide-react";
import CourseRebuildPreview from "./CourseRebuildPreview";
import SourcesList from "./SourcesList";
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

      {course.progress.reviews_due > 0 && (
        <Link
          to={`/courses/${course.id}/review`}
          className="inline-flex items-center gap-2 mt-4 rounded-md bg-accent px-3 py-1.5 text-sm text-paper hover:opacity-90"
        >
          <RotateCcw size={14} />
          {course.progress.reviews_due}{" "}
          {course.progress.reviews_due === 1 ? "task" : "tasks"} to review →
        </Link>
      )}

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

      <SourcesList sources={course.sources} />
    </div>
  );
}

export default CourseView;
