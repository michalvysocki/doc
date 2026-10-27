import { useState } from "react";
import { fetchJson } from "../utils/api";

export const MAX_ABOUT_CHARS = 2000;

export default function useLearnerSettings() {
  const [about, setAbout] = useState(null); // null: not loaded yet
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState(null);

  async function load() {
    setError(null);
    try {
      const settings = await fetchJson("/learner-settings");
      setAbout(settings.about);
      return settings.about;
    } catch (error) {
      console.error("Error while loading learner settings: ", error);
      setError(error.message);
      return null;
    }
  }

  async function save(text) {
    setError(null);
    setIsSaving(true);
    try {
      const settings = await fetchJson("/learner-settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ about: text }),
      });
      setAbout(settings.about);
      return settings.about;
    } catch (error) {
      console.error("Error while saving learner settings: ", error);
      setError(error.message);
      return null;
    } finally {
      setIsSaving(false);
    }
  }

  return { about, load, save, isSaving, error };
}
