const TEXTS = {
  lesson: {
    question: "Regenerate the lesson?",
    warning: "The current lesson will be replaced.",
  },
  tasks: {
    question: "Regenerate the tasks?",
    warning: "The current tasks and your attempts will be archived.",
  },
};

function RegenerationCards({ regenerations }) {
  const { proposals, busy, error, confirm, cancel } = regenerations;
  if (proposals.length === 0 && !error) return null;

  function isBusy(proposal, action) {
    return busy?.id === proposal.id && busy.action === action;
  }

  return (
    <div className="px-4 pb-2 flex flex-col gap-2">
      {proposals.map((proposal) => (
        <div
          key={proposal.id}
          className="rounded-md border border-accent/40 bg-accent/5 p-3 text-sm"
        >
          <p className="font-medium text-ink">
            {TEXTS[proposal.kind].question}
          </p>
          {proposal.instructions && (
            <p className="mt-1 text-ink/70">
              Instructions: “{proposal.instructions}”
            </p>
          )}
          {proposal.use_files && (
            <p className="mt-1 text-ink/70">
              Uses the course's uploaded files.
            </p>
          )}
          <p className="mt-1 text-ink/70">{TEXTS[proposal.kind].warning}</p>
          <div className="mt-2 flex gap-2">
            <button
              type="button"
              onClick={() => confirm(proposal)}
              disabled={busy !== null}
              className="rounded-md bg-accent px-3 py-1.5 text-paper hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {isBusy(proposal, "confirm") ? "Regenerating..." : "Regenerate"}
            </button>
            <button
              type="button"
              onClick={() => cancel(proposal)}
              disabled={busy !== null}
              className="rounded-md border border-line px-3 py-1.5 text-ink hover:bg-line/50 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {isBusy(proposal, "cancel") ? "Cancelling..." : "Cancel"}
            </button>
          </div>
        </div>
      ))}
      {error && <p className="text-sm text-warn">{error}</p>}
    </div>
  );
}

export default RegenerationCards;
