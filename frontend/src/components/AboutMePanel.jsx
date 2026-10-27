import { useEffect, useRef, useState } from "react";
import { UserRound } from "lucide-react";
import useLearnerSettings, {
  MAX_ABOUT_CHARS,
} from "../hooks/useLearnerSettings";

function AboutMePanel({ isOpen, onToggle }) {
  const settings = useLearnerSettings();
  const [draft, setDraft] = useState("");
  const { about, load } = settings;
  const loadStarted = useRef(false);

  // The text is loaded once, the first time the panel opens.
  useEffect(() => {
    if (!isOpen || loadStarted.current) return;
    loadStarted.current = true;
    load().then((text) => {
      if (text !== null) setDraft(text);
      else loadStarted.current = false; // try again next time it opens
    });
  }, [isOpen, load]);

  async function handleSave() {
    const saved = await settings.save(draft);
    if (saved !== null) setDraft(saved);
  }

  return (
    <div className="border-t border-line p-3">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={isOpen}
        className="w-full flex items-center gap-2 rounded-md px-3 py-2 type-label text-ink hover:bg-line"
      >
        <UserRound size={16} className="text-accent" />
        About me
      </button>

      <div
        className={`grid transition-[grid-template-rows] duration-200 ease-out motion-reduce:transition-none ${
          isOpen ? "grid-rows-[1fr]" : "grid-rows-[0fr]"
        }`}
        inert={!isOpen}
      >
        <div className="overflow-hidden px-1">
          <p className="type-caption text-muted mt-2">
            Lessons, tasks and chats adapt to what you write here.
          </p>
          <textarea
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            maxLength={MAX_ABOUT_CHARS}
            rows={6}
            disabled={about === null}
            placeholder="Your background, experience and how you like to learn…"
            className="mt-2 w-full rounded-md bg-paper px-3 py-2 type-body text-ink outline-2 outline-transparent focus:outline-accent/40 resize-none"
          />
          <div className="flex items-center justify-between mt-1">
            <span className="type-caption text-faint">
              {draft.length} / {MAX_ABOUT_CHARS}
            </span>
            <button
              type="button"
              onClick={handleSave}
              disabled={
                about === null || settings.isSaving || draft.trim() === about
              }
              className="btn-primary"
            >
              {settings.isSaving ? "Saving..." : "Save"}
            </button>
          </div>
          {settings.error && (
            <p className="type-caption text-warn mt-1">{settings.error}</p>
          )}
        </div>
      </div>
    </div>
  );
}

export default AboutMePanel;
