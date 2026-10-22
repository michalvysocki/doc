import { useEffect, useState } from "react";
import { fetchJson } from "../utils/api";

export default function useRegenerations(
  topicId,
  refreshKey,
  { onResolved } = {},
) {
  const [result, setResult] = useState({ topicId: null, proposals: [] });
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!topicId) return;
    let ignore = false;

    fetchJson(`/topics/${topicId}/regenerations`)
      .then((proposals) => {
        if (!ignore) setResult({ topicId, proposals });
      })
      .catch((error) =>
        console.error("Error while loading regenerations: ", error),
      );

    return () => {
      ignore = true;
    };
  }, [topicId, refreshKey]);

  async function resolve(proposal, action) {
    setBusy({ id: proposal.id, action });
    setError(null);

    try {
      const note = await fetchJson(`/regenerations/${proposal.id}/${action}`, {
        method: "POST",
      });
      setResult((prev) => ({
        ...prev,
        proposals: prev.proposals.filter((item) => item.id !== proposal.id),
      }));
      onResolved?.(note, proposal, action);
    } catch (error) {
      console.error(`Error while trying to ${action} regeneration: `, error);
      setError(error.message);
    } finally {
      setBusy(null);
    }
  }

  return {
    proposals: result.topicId === topicId ? result.proposals : [],
    busy,
    error,
    confirm: (proposal) => resolve(proposal, "confirm"),
    cancel: (proposal) => resolve(proposal, "cancel"),
  };
}
