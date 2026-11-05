import { useEffect, useState } from "react";
import { fetchJson } from "../utils/api";

const PATH = "/settings/openrouter-key";

export default function useOpenRouterKey() {
  const [hint, setHint] = useState(undefined); // undefined: loading, null: no key saved
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchJson(PATH)
      .then((settings) => setHint(settings.key_hint))
      .catch((error) => setError(error.message));
  }, []);

  async function request(options) {
    setError(null);
    setIsSaving(true);
    try {
      const settings = await fetchJson(PATH, options);
      setHint(settings?.key_hint ?? null); // DELETE returns no body
      return true;
    } catch (error) {
      setError(error.message);
      return false;
    } finally {
      setIsSaving(false);
    }
  }

  const save = (key) =>
    request({
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ key }),
    });
  const remove = () => request({ method: "DELETE" });

  return { hint, save, remove, isSaving, error };
}
