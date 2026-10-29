import { useMemo } from "react";
import { Link, useOutletContext, useSearchParams } from "react-router";
import { List, Network, RotateCcw } from "lucide-react";
import CourseGoal from "./CourseGoal";
import CourseMap from "./CourseMap";
import CourseRebuildPreview from "./CourseRebuildPreview";
import SourcesList from "./SourcesList";
import TopicCard from "./TopicCard";

const VIEWS = [
  { value: "list", label: "List", icon: List },
  { value: "map", label: "Map", icon: Network },
];

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
  const [searchParams, setSearchParams] = useSearchParams();
  const view = searchParams.get("view") === "map" ? "map" : "list";
  const percent =
    topics_total > 0 ? Math.round((topics_completed / topics_total) * 100) : 0;

  return (
    <div
      className={`${view === "map" ? "max-w-6xl" : "max-w-3xl"} mx-auto w-full`}
    >
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

      <div className="mt-4 inline-flex rounded-md bg-card p-0.5">
        {VIEWS.map((option) => (
          <button
            key={option.value}
            type="button"
            aria-pressed={view === option.value}
            onClick={() =>
              setSearchParams(option.value === "map" ? { view: "map" } : {}, {
                replace: true,
              })
            }
            className={`inline-flex items-center gap-1 rounded-md px-3 py-1 type-caption ${
              view === option.value
                ? "bg-paper text-ink"
                : "text-faint hover:text-ink"
            }`}
          >
            <option.icon size={14} />
            {option.label}
          </button>
        ))}
      </div>

      {view === "map" ? (
        <div className="mt-2">
          <CourseMap course={course} />
        </div>
      ) : (
        <div className="flex flex-col gap-2 mt-2">
          {course.topics.map((topic) => (
            <TopicCard key={topic.id} topic={topic} titles={titles} />
          ))}
        </div>
      )}

      <SourcesList sources={course.sources} />
    </div>
  );
}

export default CourseView;
