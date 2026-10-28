import { useMemo } from "react";
import { Link, useOutletContext } from "react-router";
import { RotateCcw } from "lucide-react";
import CourseGoal from "./CourseGoal";
import CourseRebuildPreview from "./CourseRebuildPreview";
import SourcesList from "./SourcesList";
import TopicCard from "./TopicCard";

function topicTitles(topics, titles = {}) {
  for (const topic of topics) {
    titles[topic.id] = topic.title;
    topicTitles(topic.children, titles);
  }
  return titles;
}

function CourseView() {
  const { course, courseRebuild, refreshCourse } = useOutletContext();
  const { topics_total, topics_completed } = course.progress;
  const titles = useMemo(() => topicTitles(course.topics), [course.topics]);
  const percent =
    topics_total > 0 ? Math.round((topics_completed / topics_total) * 100) : 0;

  return (
    <div className="max-w-3xl mx-auto w-full">
      <h1 className="type-title text-ink">{course.title}</h1>
      <CourseGoal course={course} onSaved={refreshCourse} />

      <div className="mt-3">
        <div className="h-2 rounded-full bg-line overflow-hidden">
          <div
            className="h-full bg-accent transition-all"
            style={{ width: `${percent}%` }}
          />
        </div>
        <p className="type-caption text-faint mt-1">
          {topics_completed} / {topics_total} topics completed
        </p>
      </div>

      {course.progress.reviews_due > 0 && (
        <Link to={`/courses/${course.id}/review`} className="btn-primary mt-4">
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
          <TopicCard key={topic.id} topic={topic} titles={titles} />
        ))}
      </div>

      <SourcesList sources={course.sources} />
    </div>
  );
}

export default CourseView;
