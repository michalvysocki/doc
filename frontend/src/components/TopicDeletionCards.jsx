function describeLoss({ subtopics, lessons, tasks, attempts }) {
  return (
    `This will also delete ${subtopics} subtopics, ${lessons} lessons, ` +
    `${tasks} tasks and ${attempts} attempts. This cannot be undone.`
  );
}

function TopicDeletionCards({ topicDeletions }) {
  const { deletions, busy, error, confirm, cancel } = topicDeletions;

  function isBusy(deletion, action) {
    return busy?.id === deletion.id && busy.action === action;
  }
  if (deletions.length === 0 && !error) return null;

  return (
    <div className="px-4 pb-2 flex flex-col gap-2">
      {deletions.map((deletion) => (
        <div key={deletion.id} className="rounded-md bg-warn/5 p-3 type-body">
          <p className="type-label text-ink">
            Delete “{deletion.topic_title}”?
          </p>
          <p className="mt-1 text-muted">{describeLoss(deletion)}</p>
          <div className="mt-2 flex gap-2">
            <button
              type="button"
              onClick={() => confirm(deletion)}
              disabled={busy !== null}
              className="btn-danger"
            >
              {isBusy(deletion, "confirm") ? "Deleting..." : "Delete"}
            </button>
            <button
              type="button"
              onClick={() => cancel(deletion)}
              disabled={busy !== null}
              className="btn-secondary"
            >
              {isBusy(deletion, "cancel") ? "Cancelling..." : "Cancel"}
            </button>
          </div>
        </div>
      ))}
      {error && <p className="type-body text-warn">{error}</p>}
    </div>
  );
}

export default TopicDeletionCards;
