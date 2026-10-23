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
        <div key={proposal.id} className="rounded-md bg-accent/5 p-3 type-body">
          <p className="type-label text-ink">{TEXTS[proposal.kind].question}</p>
          {proposal.instructions && (
            <p className="mt-1 text-muted">
              Instructions: “{proposal.instructions}”
            </p>
          )}
          {proposal.use_files && (
            <p className="mt-1 text-muted">Uses the course's uploaded files.</p>
          )}
          <p className="mt-1 text-muted">{TEXTS[proposal.kind].warning}</p>
          <div className="mt-2 flex gap-2">
            <button
              type="button"
              onClick={() => confirm(proposal)}
              disabled={busy !== null}
              className="btn-primary"
            >
              {isBusy(proposal, "confirm") ? "Regenerating..." : "Regenerate"}
            </button>
            <button
              type="button"
              onClick={() => cancel(proposal)}
              disabled={busy !== null}
              className="btn-secondary"
            >
              {isBusy(proposal, "cancel") ? "Cancelling..." : "Cancel"}
            </button>
          </div>
        </div>
      ))}
      {error && <p className="type-body text-warn">{error}</p>}
    </div>
  );
}

export default RegenerationCards;
