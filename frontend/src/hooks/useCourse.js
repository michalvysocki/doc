import { useEffect, useState } from "react";
import { fetchJson } from "../utils/api";

export default function useCourse(courseId) {
  const [result, setResult] = useState({
    courseId: null,
    course: null,
    error: null,
  });

  useEffect(() => {
    let ignore = false;

    fetchJson(`/courses/${courseId}`)
      .then((course) => {
        if (!ignore) setResult({ courseId, course, error: null });
      })
      .catch((error) => {
        console.error("Error while loading course: ", error);
        if (!ignore)
          setResult({ courseId, course: null, error: error.message });
      });

    return () => {
      ignore = true;
    };
  }, [courseId]);

  const isCurrent = result.courseId === courseId;

  return { course: result.course, error: isCurrent ? result.error : null };
}
