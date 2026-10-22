import { useEffect, useState } from "react";
import { fetchJson } from "../utils/api";

export default function useTopicDeletions(
  courseId,
  refreshKey,
  { onResolved } = {},
) {
  const [result, setResult] = useState({ courseId: null, deletions: [] });
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let ignore = false;

    fetchJson(`/courses/${courseId}/topic-deletions`)
      .then((deletions) => {
        if (!ignore) setResult({ courseId, deletions });
      })
      .catch((error) =>
        console.error("Error while loading topic deletions: ", error),
      );

    return () => {
      ignore = true;
    };
  }, [courseId, refreshKey]);

  async function resolve(deletion, action) {
    setBusy({ id: deletion.id, action });
    setError(null);

    try {
      const note = await fetchJson(
        `/topic-deletions/${deletion.id}/${action}`,
        { method: "POST" },
      );
      setResult((prev) => ({
        ...prev,
        deletions: prev.deletions.filter((item) => item.id !== deletion.id),
      }));
      onResolved?.(note, action);
    } catch (error) {
      console.error(`Error while trying to ${action} deletion: `, error);
      setError(error.message);
    } finally {
      setBusy(null);
    }
  }

  return {
    deletions: result.courseId === courseId ? result.deletions : [],
    busy,
    error,
    confirm: (deletion) => resolve(deletion, "confirm"),
    cancel: (deletion) => resolve(deletion, "cancel"),
  };
}
