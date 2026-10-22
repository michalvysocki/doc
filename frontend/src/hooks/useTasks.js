import { useEffect, useState } from "react";
import { fetchJson } from "../utils/api";

export default function useTasks(topicId, hasLesson, refreshKey = 0) {
  const [result, setResult] = useState({
    topicId: null,
    status: "loading",
    tasks: null,
    error: null,
  });

  useEffect(() => {
    if (!hasLesson) return;
    let ignore = false;

    async function load() {
      try {
        let tasks = await fetchJson(`/topics/${topicId}/tasks`);
        if (ignore) return;

        if (tasks.length === 0) {
          setResult({
            topicId,
            status: "generating",
            tasks: null,
            error: null,
          });
          tasks = await fetchJson(`/topics/${topicId}/tasks`, {
            method: "POST",
          });
          if (ignore) return;
        }

        setResult({ topicId, status: "ready", tasks, error: null });
      } catch (error) {
        console.error("Error while loading tasks: ", error);
        if (!ignore) {
          setResult({
            topicId,
            status: "error",
            tasks: null,
            error: error.message,
          });
        }
      }
    }

    load();

    return () => {
      ignore = true;
    };
  }, [topicId, hasLesson]);

  useEffect(() => {
    if (refreshKey === 0) return;
    let ignore = false;

    fetchJson(`/topics/${topicId}/tasks`)
      .then((tasks) => {
        if (ignore) return;
        setResult((prev) =>
          prev.topicId === topicId && prev.status === "ready"
            ? { ...prev, tasks }
            : prev,
        );
      })
      .catch((error) => console.error("Error while refreshing tasks: ", error));

    return () => {
      ignore = true;
    };
  }, [topicId, refreshKey]);

  function updateTask(forTopicId, taskId, update) {
    setResult((prev) =>
      prev.topicId === forTopicId && prev.tasks
        ? {
            ...prev,
            tasks: prev.tasks.map((task) =>
              task.id === taskId ? update(task) : task,
            ),
          }
        : prev,
    );
  }

  async function submitAttempt(taskId, answer) {
    const forTopicId = topicId;
    const previousCount =
      result.tasks?.find((task) => task.id === taskId)?.attempts.length ?? 0;

    try {
      const attempt = await fetchJson(`/tasks/${taskId}/attempts`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ answer }),
      });
      updateTask(forTopicId, taskId, (task) => ({
        ...task,
        attempts: [...task.attempts, attempt],
      }));
    } catch (error) {
      console.error("Error while submitting answer: ", error);
      const tasks = await fetchJson(`/topics/${forTopicId}/tasks`).catch(
        () => null,
      );
      if (tasks) {
        setResult((prev) =>
          prev.topicId === forTopicId ? { ...prev, tasks } : prev,
        );
      }

      const refreshed = tasks?.find((task) => task.id === taskId);
      error.attemptSaved = refreshed
        ? refreshed.attempts.length > previousCount
        : false;
      throw error;
    }
  }

  async function regradeAttempt(taskId, attemptId) {
    const forTopicId = topicId;
    const attempt = await fetchJson(`/attempts/${attemptId}/grade`, {
      method: "POST",
    });
    updateTask(forTopicId, taskId, (task) => ({
      ...task,
      attempts: task.attempts.map((a) => (a.id === attemptId ? attempt : a)),
    }));
  }

  const isCurrent = result.topicId === topicId;

  return {
    status: isCurrent ? result.status : "loading",
    tasks: isCurrent ? result.tasks : null,
    error: isCurrent ? result.error : null,
    submitAttempt,
    regradeAttempt,
  };
}
