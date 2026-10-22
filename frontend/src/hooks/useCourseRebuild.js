import { useEffect, useState } from "react";
import { fetchJson } from "../utils/api";

export default function useCourseRebuild(
  courseId,
  refreshKey,
  { onResolved } = {},
) {
  const [result, setResult] = useState({ courseId: null, rebuild: null });
  const [isProposing, setIsProposing] = useState(false);
  const [busyAction, setBusyAction] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let ignore = false;

    fetchJson(`/courses/${courseId}/rebuild`)
      .then((rebuild) => {
        if (!ignore) setResult({ courseId, rebuild });
      })
      .catch((error) =>
        console.error("Error while loading course rebuild: ", error),
      );

    return () => {
      ignore = true;
    };
  }, [courseId, refreshKey]);

  async function propose(options = {}) {
    const forCourseId = courseId;
    setIsProposing(true);
    setError(null);

    try {
      const rebuild = await fetchJson(`/courses/${forCourseId}/rebuild`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(options),
      });
      setResult((prev) =>
        prev.courseId === forCourseId
          ? { courseId: forCourseId, rebuild }
          : prev,
      );
      return true;
    } catch (error) {
      console.error("Error while proposing course rebuild: ", error);
      setError(error.message);
      return false;
    } finally {
      setIsProposing(false);
    }
  }

  async function resolve(action) {
    const rebuild = result.rebuild;
    setBusyAction(action);
    setError(null);

    try {
      const note = await fetchJson(`/course-rebuilds/${rebuild.id}/${action}`, {
        method: "POST",
      });
      setResult((prev) => ({ ...prev, rebuild: null }));
      onResolved?.(note, action);
    } catch (error) {
      console.error(`Error while trying to ${action} course rebuild: `, error);
      setError(error.message);
    } finally {
      setBusyAction(null);
    }
  }

  return {
    rebuild: result.courseId === courseId ? result.rebuild : null,
    isProposing,
    busyAction,
    error,
    propose,
    apply: () => resolve("apply"),
    discard: () => resolve("discard"),
  };
}
