import { useState } from "react";
import { CircleCheck } from "lucide-react";
import MarkdownContent from "./MarkdownContent";
import AttemptView from "./AttemptView";

function TaskCard({ task, index, onSubmit, onRegrade }) {
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
    <li className="border border-line rounded-md bg-surface p-4">
      <div className="flex items-center justify-between">
        <p className="text-xs text-ink/50">Task {index + 1}</p>
        {isSolved && (
          <span className="inline-flex items-center gap-1 text-xs text-good">
            <CircleCheck size={14} /> Solved
          </span>
        )}
      </div>

      <div className="prose prose-sm max-w-none text-ink mt-1">
        <MarkdownContent>{task.question}</MarkdownContent>
      </div>

      {earlier.length > 0 && (
        <button
          type="button"
          onClick={() => setShowEarlier((prev) => !prev)}
          className="mt-3 text-xs text-ink/60 hover:text-ink"
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
          />
        ))}
      {latest && (
        <AttemptView
          attempt={latest}
          onRegrade={() => onRegrade(task.id, latest.id)}
        />
      )}

      <form onSubmit={handleSubmit} className="mt-3">
        <textarea
          value={answer}
          onChange={(e) => setAnswer(e.target.value)}
          placeholder={latest ? "Try again..." : "Write your answer..."}
          rows={5}
          disabled={isSubmitting}
          className="w-full rounded-md border border-line bg-paper px-3 py-2 text-sm text-ink outline-none focus:border-accent"
        />
        <div className="flex items-center justify-between mt-2">
          <span className="text-xs text-ink/60">
            {isSubmitting && "Grading your answer..."}
          </span>
          <button
            type="submit"
            disabled={!canSubmit}
            className="btn-primary px-4 py-1.5"
          >
            Submit
          </button>
        </div>
        {error && <p className="text-xs text-warn mt-1">{error}</p>}
      </form>
    </li>
  );
}

export default TaskCard;
