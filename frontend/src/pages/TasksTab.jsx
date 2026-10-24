import { useOutletContext } from "react-router";
import useTasks from "../hooks/useTasks";
import TaskCard from "../components/TaskCard";
import Skeleton from "../components/Skeleton";
import { LoaderCircle } from "lucide-react";

function TasksTab() {
  const { topic, courseVersion } = useOutletContext();
  const hasLesson = topic.explanation !== null;
  const { status, tasks, error, submitAttempt, regradeAttempt } = useTasks(
    topic.id,
    hasLesson,
    courseVersion,
  );

  if (!hasLesson) {
    return (
      <p className="type-body text-muted">
        Tasks will be created as soon as the lesson is ready...
      </p>
    );
  }
  if (status === "loading") {
    return <Skeleton lines={4} />;
  }
  if (status === "generating") {
    return (
      <p className="flex items-center gap-2 type-body text-muted">
        <LoaderCircle size={16} className="animate-spin text-accent" />
        Creating and checking tasks, this can take a few minutes...
      </p>
    );
  }
  if (status === "error") {
    return <p className="type-body text-warn">{error}</p>;
  }

  const solvedCount = tasks.filter((task) =>
    task.attempts.some((attempt) => attempt.verdict === "correct"),
  ).length;

  return (
    <section>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="type-body text-muted">
          {solvedCount} / {tasks.length} solved
        </p>
      </div>

      {error && <p className="type-body text-warn mt-2">{error}</p>}

      <ol className="mt-4 flex flex-col gap-4">
        {tasks.map((task, index) => (
          <TaskCard
            key={task.id}
            task={task}
            index={index}
            onSubmit={submitAttempt}
            onRegrade={regradeAttempt}
          />
        ))}
      </ol>
    </section>
  );
}

export default TasksTab;
