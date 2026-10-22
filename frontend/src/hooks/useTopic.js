import { useEffect, useState } from "react";
import { fetchJson } from "../utils/api";

export default function useTopic(topicId, refreshKey = 0) {
  const [result, setResult] = useState({
    topicId: null,
    topic: null,
    error: null,
  });

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
            ? {
                ...prev,
                topic: {
                  ...prev.topic,
                  subtopics: fresh.subtopics,
                  explanation: fresh.explanation ?? prev.topic.explanation,
                },
              }
            : prev,
        );
      })
      .catch((error) => console.error("Error while refreshing topic: ", error));

    return () => {
      ignore = true;
    };
  }, [topicId, refreshKey]);

  const isCurrent = result.topicId === topicId;

  return {
    topic: isCurrent ? result.topic : null,
    error: isCurrent ? result.error : null,
  };
}
