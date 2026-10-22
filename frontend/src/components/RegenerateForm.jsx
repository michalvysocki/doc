import { useId, useState } from "react";
import { RefreshCw } from "lucide-react";

function RegenerateForm({ label, confirmMessage, isRegenerating, regenerate }) {
  const instructionsId = useId();
  const [isOpen, setIsOpen] = useState(false);
  const [instructions, setInstructions] = useState("");
  const [useFiles, setUseFiles] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    if (!window.confirm(confirmMessage)) return;

    setIsOpen(false);
    const succeeded = await regenerate({ instructions, use_files: useFiles });
    if (succeeded) {
      setInstructions("");
      setUseFiles(false);
    }
  }

  if (!isOpen) {
    return (
      <button
        type="button"
        onClick={() => setIsOpen(true)}
        disabled={isRegenerating}
        className="inline-flex items-center gap-1 rounded-md border border-line px-3 py-1.5 text-sm text-ink hover:bg-line/50 disabled:opacity-40 disabled:cursor-not-allowed"
      >
        <RefreshCw size={14} className={isRegenerating ? "animate-spin" : ""} />
        {isRegenerating ? "Regenerating..." : label}
      </button>
    );
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="w-full flex flex-col gap-2 rounded-md border border-line p-3"
    >
      <label htmlFor={instructionsId} className="text-sm text-ink">
        Instructions (optional)
      </label>
      <textarea
        id={instructionsId}
        value={instructions}
        onChange={(event) => setInstructions(event.target.value)}
        maxLength={2000}
        rows={3}
        placeholder="e.g. simpler, more code examples"
        className="rounded-md border border-line px-3 py-2 text-sm text-ink"
      />
      <label className="flex items-center gap-2 text-sm text-ink">
        <input
          type="checkbox"
          checked={useFiles}
          onChange={(event) => setUseFiles(event.target.checked)}
        />
        Use the course's uploaded files
      </label>
      <div className="flex justify-end gap-2">
        <button
          type="button"
          onClick={() => setIsOpen(false)}
          className="rounded-md border border-line px-3 py-1.5 text-sm text-ink hover:bg-line/50"
        >
          Cancel
        </button>
        <button
          type="submit"
          className="rounded-md bg-accent px-3 py-1.5 text-sm text-paper hover:opacity-90"
        >
          Regenerate
        </button>
      </div>
    </form>
  );
}

export default RegenerateForm;
