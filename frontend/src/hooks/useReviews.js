import { useEffect, useState } from "react";
import { fetchJson } from "../utils/api";

export default function useReviews(courseId, { onReviewed } = {}) {
  const [result, setResult] = useState({
    courseId: null,
    status: "loading",
    tasks: null,
    error: null,
  });
  const [reviewedIds, setReviewedIds] = useState(() => new Set());

  useEffect(() => {
    let ignore = false;

    fetchJson(`/courses/${courseId}/reviews`)
      .then((tasks) => {
        if (!ignore) {
          setResult({ courseId, status: "ready", tasks, error: null });
          setReviewedIds(new Set());
        }
      })
      .catch((error) => {
        console.error("Error while loading reviews: ", error);
        if (!ignore) {
          setResult({
            courseId,
            status: "error",
            tasks: null,
            error: error.message,
          });
        }
      });

    return () => {
      ignore = true;
    };
  }, [courseId]);

  function updateTask(taskId, update) {
    setResult((prev) => ({
      ...prev,
      tasks: prev.tasks?.map((task) =>
        task.id === taskId ? update(task) : task,
      ),
    }));
  }

  function markReviewed(taskId, attempt) {
    if (!attempt.verdict) return;
    setReviewedIds((prev) => new Set(prev).add(taskId));
    onReviewed?.();
  }

  async function submitAttempt(taskId, answer) {
    const previousCount =
      result.tasks?.find((task) => task.id === taskId)?.attempts.length ?? 0;

    try {
      const attempt = await fetchJson(`/tasks/${taskId}/attempts`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ answer }),
      });
      updateTask(taskId, (task) => ({
        ...task,
        attempts: [...task.attempts, attempt],
      }));
      markReviewed(taskId, attempt);
    } catch (error) {
      console.error("Error while submitting review answer: ", error);
      const tasks = await fetchJson(`/courses/${courseId}/reviews`).catch(
        () => null,
      );
      const refreshed = tasks?.find((task) => task.id === taskId);
      if (refreshed) updateTask(taskId, () => refreshed);
      error.attemptSaved = refreshed
        ? refreshed.attempts.length > previousCount
        : false;
      throw error;
    }
  }

  async function regradeAttempt(taskId, attemptId) {
    const attempt = await fetchJson(`/attempts/${attemptId}/grade`, {
      method: "POST",
    });
    updateTask(taskId, (task) => ({
      ...task,
      attempts: task.attempts.map((a) => (a.id === attemptId ? attempt : a)),
    }));
    markReviewed(taskId, attempt);
  }

  const isCurrent = result.courseId === courseId;
  const tasks = isCurrent ? result.tasks : null;

  return {
    status: isCurrent ? result.status : "loading",
    tasks,
    error: isCurrent ? result.error : null,
    reviewedIds,
    remaining: tasks
      ? tasks.filter((task) => !reviewedIds.has(task.id)).length
      : 0,
    submitAttempt,
    regradeAttempt,
  };
}
