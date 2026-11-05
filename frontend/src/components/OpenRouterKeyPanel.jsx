import { useState } from "react";
import { KeyRound } from "lucide-react";
import useOpenRouterKey from "../hooks/useOpenRouterKey";

function OpenRouterKeyPanel({ isOpen, onToggle }) {
  const apiKey = useOpenRouterKey();
  const [draft, setDraft] = useState("");

  async function handleSubmit(event) {
    event.preventDefault();
    if (await apiKey.save(draft.trim())) setDraft("");
  }

  return (
    <div className="border-t border-line p-3">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={isOpen}
        className="w-full flex items-center gap-2 rounded-md px-3 py-2 type-label text-ink hover:bg-line"
      >
        <KeyRound size={16} className="text-accent" />
        OpenRouter key
        <span
          className={`ml-auto type-caption ${
            apiKey.hint === null ? "text-warn" : "text-faint"
          }`}
        >
          {apiKey.hint === null ? "Not set" : apiKey.hint}
        </span>
      </button>

      <div
        className={`grid transition-[grid-template-rows] duration-200 ease-out motion-reduce:transition-none ${
          isOpen ? "grid-rows-[1fr]" : "grid-rows-[0fr]"
        }`}
        inert={!isOpen}
      >
        <div className="overflow-hidden px-1">
          <p className="type-caption text-muted mt-2">
            Lessons, tasks and chats use your own key from{" "}
            <a
              href="https://openrouter.ai/settings/keys"
              target="_blank"
              rel="noreferrer"
              className="text-accent hover:underline"
            >
              openrouter.ai
            </a>
            . It is stored encrypted and never shown again.
          </p>
          <form onSubmit={handleSubmit} className="mt-2 flex gap-2">
            <input
              type="password"
              required
              autoComplete="off"
              spellCheck={false}
              pattern="sk-or-\S{10,200}"
              title="An OpenRouter key starts with sk-or-"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              placeholder={apiKey.hint ? "Replace key…" : "sk-or-…"}
              className="flex-1 min-w-0 rounded-md bg-paper px-3 py-2 type-body text-ink outline-2 outline-transparent focus:outline-accent/40"
            />
            <button
              type="submit"
              disabled={apiKey.isSaving || apiKey.hint === undefined}
              className="btn-primary"
            >
              {apiKey.isSaving ? "Saving..." : "Save"}
            </button>
          </form>
          {apiKey.hint && (
            <button
              type="button"
              onClick={apiKey.remove}
              disabled={apiKey.isSaving}
              className="mt-1 type-caption text-faint hover:text-warn"
            >
              Remove key {apiKey.hint}
            </button>
          )}
          {apiKey.error && (
            <p className="type-caption text-warn mt-1">{apiKey.error}</p>
          )}
        </div>
      </div>
    </div>
  );
}

export default OpenRouterKeyPanel;
