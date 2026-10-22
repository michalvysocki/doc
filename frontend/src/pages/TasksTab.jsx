import { useOutletContext } from "react-router";
import { RefreshCw } from "lucide-react";
import useTasks from "../hooks/useTasks";
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

  function handleRegenerate() {
    const confirmed = window.confirm(
      "Regenerate tasks? The current tasks and your attempts will be archived.",
    );
    if (confirmed) regenerate();
  }

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
      <div className="flex items-center justify-between">
        <p className="text-sm text-ink/60">
          {solvedCount} / {tasks.length} solved
        </p>
        <button
          type="button"
          onClick={handleRegenerate}
          disabled={isRegenerating}
          className="inline-flex items-center gap-1 rounded-md border border-line px-3 py-1.5 text-sm text-ink hover:bg-line/50 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          <RefreshCw
            size={14}
            className={isRegenerating ? "animate-spin" : ""}
          />
          {isRegenerating ? "Regenerating..." : "Regenerate tasks"}
        </button>
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
