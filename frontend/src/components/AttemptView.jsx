import { useState } from "react";
import { Target } from "lucide-react";
import MarkdownContent from "./MarkdownContent";
import { scrollToTask } from "../utils/scroll";

const VERDICTS = {
  correct: { label: "Correct", className: "bg-good/10 text-good" },
  partially_correct: {
    label: "Partially correct",
    className: "bg-partial/10 text-partial",
  },
  incorrect: { label: "Incorrect", className: "bg-warn/10 text-warn" },
};

function AttemptView({ attempt, onRegrade, onFollowUp, followUpTask }) {
  const [isGrading, setIsGrading] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState(null);
  const verdict = VERDICTS[attempt.verdict];
  const canPractice =
    onFollowUp &&
    (attempt.verdict === "partially_correct" ||
      attempt.verdict === "incorrect");

  async function handleFollowUp() {
    setIsCreating(true);
    setError(null);
    try {
      await onFollowUp();
    } catch (error) {
      setError(error.message);
    } finally {
      setIsCreating(false);
    }
  }

  async function handleRegrade() {
    setIsGrading(true);
    setError(null);
    try {
      await onRegrade();
    } catch (error) {
      setError(error.message);
    } finally {
      setIsGrading(false);
    }
  }

  return (
    <div className="mt-3 rounded-md bg-paper p-3">
      <p className="type-body text-ink whitespace-pre-wrap">{attempt.answer}</p>

      {verdict ? (
        <>
          <span
            className={`inline-block mt-2 rounded-full px-2 py-0.5 type-caption ${verdict.className}`}
          >
            {verdict.label}
          </span>
          <div className="prose prose-sm max-w-none mt-2">
            <MarkdownContent>{attempt.feedback}</MarkdownContent>
          </div>
          {canPractice &&
            (followUpTask ? (
              <button
                type="button"
                onClick={() => scrollToTask(followUpTask.id)}
                className="mt-2 type-caption text-accent hover:underline"
              >
                Practice task added: task {followUpTask.number} →
              </button>
            ) : (
              <button
                type="button"
                onClick={handleFollowUp}
                disabled={isCreating}
                className="btn-secondary btn-sm mt-2"
              >
                <Target size={12} />
                {isCreating ? "Creating a task..." : "Practice this"}
              </button>
            ))}
        </>
      ) : (
        <div className="mt-2 flex items-center gap-2">
          <span className="type-caption text-faint">
            Your answer was saved, but grading failed.
          </span>
          <button
            type="button"
            onClick={handleRegrade}
            disabled={isGrading}
            className="type-caption text-accent hover:underline disabled:opacity-40"
          >
            {isGrading ? "Grading..." : "Grade again"}
          </button>
        </div>
      )}
      {error && <p className="type-caption text-warn mt-1">{error}</p>}
    </div>
  );
}

export default AttemptView;
