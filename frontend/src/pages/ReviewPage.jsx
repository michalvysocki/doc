import { Link, useOutletContext } from "react-router";
import { ArrowLeft, CircleCheck, PartyPopper } from "lucide-react";
import EmptyState from "../components/EmptyState";
import Skeleton from "../components/Skeleton";
import useReviews from "../hooks/useReviews";
import TaskCard from "../components/TaskCard";

function ReviewPage() {
  const { course, refreshCourse } = useOutletContext();
  const {
    status,
    tasks,
    error,
    reviewedIds,
    remaining,
    submitAttempt,
    regradeAttempt,
  } = useReviews(course.id, { onReviewed: refreshCourse });

  return (
    <div className="max-w-3xl mx-auto w-full">
      <Link
        to={`/courses/${course.id}`}
        className="inline-flex items-center gap-1 type-body text-muted hover:text-ink"
      >
        <ArrowLeft size={14} />
        {course.title}
      </Link>
      <h1 className="type-title text-ink mt-2">Review</h1>

      {status === "loading" && <Skeleton lines={4} className="mt-6" />}
      {status === "error" && (
        <p className="type-body text-warn mt-4">{error}</p>
      )}

      {status === "ready" && (
        <>
          {tasks.length === 0 ? (
            <EmptyState
              icon={PartyPopper}
              title="All caught up"
              text="Nothing to review today. Tasks come back here a few days after you answer them."
            />
          ) : (
            <p className="type-body text-muted mt-1">
              {remaining > 0
                ? `${remaining} ${remaining === 1 ? "task" : "tasks"} left to review today`
                : "All done for today, nice work."}
            </p>
          )}

          <ol className="mt-4 flex flex-col gap-4">
            {tasks.map((task) => (
              <li key={task.id}>
                <div className="flex items-center gap-2 mb-1 type-body">
                  <Link
                    to={`/courses/${course.id}/topics/${task.topic_id}`}
                    className="text-muted hover:text-ink"
                  >
                    {task.topic_title}
                  </Link>
                  {reviewedIds.has(task.id) && (
                    <span className="inline-flex items-center gap-1 type-caption text-accent">
                      <CircleCheck size={14} />
                      Reviewed
                    </span>
                  )}
                </div>
                <ul>
                  <TaskCard
                    task={task}
                    index={task.position}
                    onSubmit={submitAttempt}
                    onRegrade={regradeAttempt}
                  />
                </ul>
              </li>
            ))}
          </ol>
        </>
      )}
    </div>
  );
}

export default ReviewPage;
