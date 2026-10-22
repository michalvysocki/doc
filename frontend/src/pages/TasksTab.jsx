import { useOutletContext } from "react-router";
import useTasks from "../hooks/useTasks";
import RegenerateForm from "../components/RegenerateForm";
import TaskCard from "../components/TaskCard";

function TasksTab() {
  const { topic, courseVersion } = useOutletContext();
  const hasLesson = topic.explanation !== null;
  const {
    status,
    tasks,
    error,
    isRegenerating,
    regenerate,
    submitAttempt,
    regradeAttempt,
  } = useTasks(topic.id, hasLesson, courseVersion);

  if (!hasLesson) {
    return (
      <p className="text-sm text-ink/60">
        Tasks will be created as soon as the lesson is ready...
      </p>
    );
  }
  if (status === "loading") {
    return <p className="text-sm text-ink/60">Loading tasks...</p>;
  }
  if (status === "generating") {
    return (
      <p className="text-sm text-ink/60">
        Creating tasks, this can take a few minutes...
      </p>
    );
  }
  if (status === "error") {
    return <p className="text-sm text-warn">{error}</p>;
  }

  const solvedCount = tasks.filter((task) =>
    task.attempts.some((attempt) => attempt.verdict === "correct"),
  ).length;

  return (
    <section>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-ink/60">
          {solvedCount} / {tasks.length} solved
        </p>
        <RegenerateForm
          key={topic.id}
          label="Regenerate tasks"
          confirmMessage="Regenerate tasks? The current tasks and your attempts will be archived."
          isRegenerating={isRegenerating}
          regenerate={regenerate}
        />
      </div>

      {error && <p className="text-sm text-warn mt-2">{error}</p>}

      <ol className="mt-4 flex flex-col gap-3">
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
