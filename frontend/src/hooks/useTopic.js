import { useEffect, useState } from "react";
import { fetchJson } from "../utils/api";

export default function useTopic(topicId, refreshKey = 0) {
  const [result, setResult] = useState({
    topicId: null,
    topic: null,
    error: null,
  });
  const [isRegenerating, setIsRegenerating] = useState(false);

  useEffect(() => {
    let ignore = false;

    async function load() {
      try {
        const topic = await fetchJson(`/topics/${topicId}`);
        if (ignore) return;
        setResult({ topicId, topic, error: null });

        if (topic.explanation === null) {
          const withExplanation = await fetchJson(
            `/topics/${topicId}/explanation`,
            { method: "POST" },
          );
          if (!ignore) {
            setResult({ topicId, topic: withExplanation, error: null });
          }
        }
      } catch (error) {
        console.error("Error while loading topic: ", error);
        if (!ignore) {
          setResult((prev) => ({
            topicId,
            topic: prev.topicId === topicId ? prev.topic : null,
            error: error.message,
          }));
        }
      }
    }

    load();

    return () => {
      ignore = true;
    };
  }, [topicId]);

  useEffect(() => {
    if (refreshKey === 0) return;
    let ignore = false;

    fetchJson(`/topics/${topicId}`)
      .then((fresh) => {
        if (ignore) return;
        setResult((prev) =>
          prev.topicId === topicId && prev.topic
            ? { ...prev, topic: { ...prev.topic, subtopics: fresh.subtopics } }
            : prev,
        );
      })
      .catch((error) => console.error("Error while refreshing topic: ", error));

    return () => {
      ignore = true;
    };
  }, [topicId, refreshKey]);

  async function regenerate(options = {}) {
    const forTopicId = topicId;
    setIsRegenerating(true);

    try {
      const topic = await fetchJson(
        `/topics/${forTopicId}/explanation?regenerate=true`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(options),
        },
      );
      setResult((prev) =>
        prev.topicId === forTopicId
          ? { topicId: forTopicId, topic, error: null }
          : prev,
      );
      return true;
    } catch (error) {
      console.error("Error while regenerating lesson: ", error);
      setResult((prev) =>
        prev.topicId === forTopicId ? { ...prev, error: error.message } : prev,
      );
      return false;
    } finally {
      setIsRegenerating(false);
    }
  }

  const isCurrent = result.topicId === topicId;

  return {
    topic: isCurrent ? result.topic : null,
    error: isCurrent ? result.error : null,
    isRegenerating,
    regenerate,
  };
}
