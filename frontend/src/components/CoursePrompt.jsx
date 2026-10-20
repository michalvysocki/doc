import { useState } from "react";

function CoursePrompt({ onSubmit, isLoading, error }) {
  const [prompt, setPrompt] = useState("");
  const canSubmit = prompt.trim() !== "" && !isLoading;

  function handleSubmit(event) {
    event.preventDefault();
    if (!canSubmit) return;
    onSubmit(prompt.trim());
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="border border-line rounded-md bg-paper max-w-2xl mx-auto w-full"
    >
      <textarea
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
        placeholder="What do you want to learn?"
        rows={4}
        disabled={isLoading}
        className="w-full px-4 py-3 outline-none text-ink bg-transparent resize-none"
      />

      <div className="flex items-center justify-between px-3 pb-2">
        <span className="text-xs text-ink/60">
          {isLoading &&
            "Creating the topic map, this can take a few minutes..."}
        </span>
        <button
          type="submit"
          disabled={!canSubmit}
          className="bg-accent hover:bg-accent/90 text-paper rounded-md px-4 py-2 text-sm transition-colors disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-accent"
        >
          Create course
        </button>
      </div>

      {error && <p className="text-warn text-xs px-4 pb-2">{error}</p>}
    </form>
  );
}

export default CoursePrompt;
