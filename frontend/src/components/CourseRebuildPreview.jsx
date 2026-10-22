import { Check, Plus } from "lucide-react";

function describeProgress({ has_explanation, tasks_total, tasks_solved }) {
  const parts = [];
  if (has_explanation) parts.push("lesson");
  if (tasks_total > 0) parts.push(`${tasks_solved}/${tasks_total} tasks`);
  return parts.join(" · ");
}

function describeLoss({ has_explanation, tasks, attempts }) {
  const parts = [
    has_explanation && "lesson",
    tasks > 0 && `${tasks} tasks`,
    attempts > 0 && `${attempts} attempts`,
  ].filter(Boolean);
  return parts.length > 0 ? ` (${parts.join(", ")})` : "";
}

function PreviewTree({ nodes }) {
  return (
    <ul className="flex flex-col gap-1">
      {nodes.map((node, index) => (
        <li key={node.topic_id ?? `new-${index}`}>
          <div className="flex flex-wrap items-center gap-x-2 text-sm">
            {node.topic_id ? (
              <Check size={14} className="text-accent shrink-0" />
            ) : (
              <Plus size={14} className="text-ink/60 shrink-0" />
            )}
            <span className="text-ink">{node.title}</span>
            {node.old_title && (
              <span className="text-xs text-ink/50">
                renamed from “{node.old_title}”
              </span>
            )}
            <span className="text-xs text-ink/50">
              {node.topic_id ? describeProgress(node) : "new"}
            </span>
          </div>
          {node.children.length > 0 && (
            <div className="ml-5 mt-1">
              <PreviewTree nodes={node.children} />
            </div>
          )}
        </li>
      ))}
    </ul>
  );
}

function CourseRebuildPreview({ courseRebuild }) {
  const { rebuild, busyAction, error, apply, discard } = courseRebuild;
  const isBusy = busyAction !== null;

  return (
    <section className="rounded-md border border-accent/40 bg-accent/5 p-4">
      <h2 className="font-semibold text-ink">Proposed new course map</h2>
      <p className="text-sm text-ink/70 mt-1">
        Keeps {rebuild.kept_count} topics, adds {rebuild.new_count}, deletes{" "}
        {rebuild.deleted.length}.
      </p>

      <div className="mt-3">
        <PreviewTree nodes={rebuild.topics} />
      </div>

      {rebuild.deleted.length > 0 && (
        <div className="mt-4 rounded-md border border-warn/40 bg-warn/5 p-3 text-sm">
          <p className="font-medium text-ink">Will be deleted</p>
          <ul className="mt-1 text-ink/70">
            {rebuild.deleted.map((topic) => (
              <li key={topic.topic_id}>
                {topic.title}
                {describeLoss(topic)}
              </li>
            ))}
          </ul>
          <p className="mt-1 text-ink/70">This cannot be undone.</p>
        </div>
      )}

      <div className="mt-4 flex gap-2">
        <button
          type="button"
          onClick={apply}
          disabled={isBusy}
          className="rounded-md bg-accent px-3 py-1.5 text-sm text-paper hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {busyAction === "apply" ? "Applying..." : "Apply"}
        </button>
        <button
          type="button"
          onClick={discard}
          disabled={isBusy}
          className="rounded-md border border-line px-3 py-1.5 text-sm text-ink hover:bg-line/50 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {busyAction === "discard" ? "Discarding..." : "Discard"}
        </button>
      </div>
      {error && <p className="text-sm text-warn mt-2">{error}</p>}
    </section>
  );
}

export default CourseRebuildPreview;
