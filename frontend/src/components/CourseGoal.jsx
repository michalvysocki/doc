import { useState } from "react";
import { Pencil } from "lucide-react";
import { fetchJson } from "../utils/api";

const MAX_GOAL_CHARS = 4000;

function CourseGoal({ course, onSaved }) {
  const [isEditing, setIsEditing] = useState(false);
  const [draft, setDraft] = useState(course.initial_prompt);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState(null);

  function startEditing() {
    setDraft(course.initial_prompt);
    setError(null);
    setIsEditing(true);
  }

  async function save() {
    setIsSaving(true);
    setError(null);
    try {
      await fetchJson(`/courses/${course.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ initial_prompt: draft }),
      });
      setIsEditing(false);
      onSaved();
    } catch (error) {
      console.error("Error while saving the course goal: ", error);
      setError(error.message);
    } finally {
      setIsSaving(false);
    }
  }

  if (!isEditing) {
    return (
      <div className="mt-1 flex items-start gap-1">
        <p className="type-body text-muted">
          <span className="type-label text-ink">Goal: </span>
          {course.initial_prompt}
        </p>
        <button
          type="button"
          onClick={startEditing}
          aria-label="Edit course goal"
          className="p-1 rounded-md text-faint hover:text-ink hover:bg-line shrink-0"
        >
          <Pencil size={14} />
        </button>
      </div>
    );
  }

  return (
    <div className="mt-2">
      <textarea
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
        maxLength={MAX_GOAL_CHARS}
        rows={3}
        className="w-full rounded-md bg-card px-3 py-2 type-body text-ink outline-2 outline-transparent focus:outline-accent/40 resize-none"
      />
      <div className="flex items-center gap-2 mt-1">
        <button
          type="button"
          onClick={save}
          disabled={isSaving || !draft.trim()}
          className="btn-primary"
        >
          {isSaving ? "Saving..." : "Save"}
        </button>
        <button
          type="button"
          onClick={() => setIsEditing(false)}
          className="btn-secondary"
        >
          Cancel
        </button>
        <span className="type-caption text-faint ml-auto">
          New lessons and tasks follow the new goal.
        </span>
      </div>
      {error && <p className="type-caption text-warn mt-1">{error}</p>}
    </div>
  );
}

export default CourseGoal;
