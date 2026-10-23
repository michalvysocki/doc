import { useState } from "react";
import MarkdownContent from "./MarkdownContent";

const VERDICTS = {
  correct: { label: "Correct", className: "bg-good/10 text-good" },
  partially_correct: {
    label: "Partially correct",
    className: "bg-partial/10 text-partial",
  },
  incorrect: { label: "Incorrect", className: "bg-warn/10 text-warn" },
};

function AttemptView({ attempt, onRegrade }) {
  const [isGrading, setIsGrading] = useState(false);
  const [error, setError] = useState(null);
  const verdict = VERDICTS[attempt.verdict];

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
    <div className="mt-3 rounded-md bg-shade p-3">
      <p className="text-sm text-ink whitespace-pre-wrap">{attempt.answer}</p>

      {verdict ? (
        <>
          <span
            className={`inline-block mt-2 rounded-full px-2 py-0.5 text-xs font-medium ${verdict.className}`}
          >
            {verdict.label}
          </span>
          <div className="prose prose-sm max-w-none text-ink mt-2">
            <MarkdownContent>{attempt.feedback}</MarkdownContent>
          </div>
        </>
      ) : (
        <div className="mt-2 flex items-center gap-2">
          <span className="text-xs text-ink/60">
            Your answer was saved, but grading failed.
          </span>
          <button
            type="button"
            onClick={handleRegrade}
            disabled={isGrading}
            className="text-xs text-accent hover:underline disabled:opacity-40"
          >
            {isGrading ? "Grading..." : "Grade again"}
          </button>
        </div>
      )}
      {error && <p className="text-xs text-warn mt-1">{error}</p>}
    </div>
  );
}

export default AttemptView;
