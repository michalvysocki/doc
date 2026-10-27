import { useState } from "react";
import { CircleCheck } from "lucide-react";
import MarkdownContent from "./MarkdownContent";
import AttemptView from "./AttemptView";

function TaskCard({
  task,
  index,
  onSubmit,
  onRegrade,
  onFollowUp,
  followUpOf,
  followUpTask,
}) {
  const [answer, setAnswer] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [showEarlier, setShowEarlier] = useState(false);

  const latest = task.attempts.at(-1);
  const earlier = task.attempts.slice(0, -1);
  const isSolved = task.attempts.some(
    (attempt) => attempt.verdict === "correct",
  );
  const canSubmit = answer.trim() !== "" && !isSubmitting;

  async function handleSubmit(event) {
    event.preventDefault();
    if (!canSubmit) return;

    setIsSubmitting(true);
    setError(null);
    try {
      await onSubmit(task.id, answer.trim());
      setAnswer("");
    } catch (error) {
      if (error.attemptSaved) {
        setAnswer("");
      } else {
        setError(error.message);
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <li id={`task-${task.id}`} className="rounded-md bg-card p-4 scroll-mt-4">
      <div className="flex items-center justify-between">
        <p className="flex items-center gap-2 type-caption text-faint">
          Task {index + 1}
          {followUpOf && (
            <span className="rounded-full bg-accent/10 px-2 py-0.5 type-caption text-accent">
              Follow-up to task {followUpOf}
            </span>
          )}
        </p>
        {isSolved && (
          <span className="inline-flex items-center gap-1 type-caption text-good">
            <CircleCheck size={14} /> Solved
          </span>
        )}
      </div>

      <div className="prose prose-sm max-w-none mt-1">
        <MarkdownContent>{task.question}</MarkdownContent>
      </div>

      {earlier.length > 0 && (
        <button
          type="button"
          onClick={() => setShowEarlier((prev) => !prev)}
          className="mt-3 type-caption text-muted hover:text-ink"
        >
          {showEarlier ? "Hide" : "Show"} {earlier.length} earlier attempt
          {earlier.length > 1 ? "s" : ""}
        </button>
      )}
      {showEarlier &&
        earlier.map((attempt) => (
          <AttemptView
            key={attempt.id}
            attempt={attempt}
            onRegrade={() => onRegrade(task.id, attempt.id)}
            onFollowUp={onFollowUp && (() => onFollowUp(attempt.id))}
            followUpTask={followUpTask?.(attempt.id)}
          />
        ))}
      {latest && (
        <AttemptView
          attempt={latest}
          onRegrade={() => onRegrade(task.id, latest.id)}
          onFollowUp={onFollowUp && (() => onFollowUp(latest.id))}
          followUpTask={followUpTask?.(latest.id)}
        />
      )}

      <form onSubmit={handleSubmit} className="mt-3">
        <textarea
          value={answer}
          onChange={(e) => setAnswer(e.target.value)}
          placeholder={latest ? "Try again..." : "Write your answer..."}
          rows={5}
          disabled={isSubmitting}
          className="w-full rounded-md bg-paper px-3 py-2 type-body text-ink outline-2 outline-transparent focus:outline-accent/40"
        />
        <div className="flex items-center justify-between mt-2">
          <span className="type-caption text-faint">
            {isSubmitting && "Grading your answer..."}
          </span>
          <button type="submit" disabled={!canSubmit} className="btn-primary">
            Submit
          </button>
        </div>
        {error && <p className="type-caption text-warn mt-1">{error}</p>}
      </form>
    </li>
  );
}

export default TaskCard;
