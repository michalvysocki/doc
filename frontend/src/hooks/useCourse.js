import { useEffect, useState } from "react";
import { fetchJson } from "../utils/api";

function getCourseIdFromUrl() {
  return new URLSearchParams(window.location.search).get("course");
}

function setCourseIdInUrl(courseId) {
  const url = new URL(window.location.href);
  url.searchParams.set("course", courseId);
  window.history.pushState(null, "", url);
}

function clearCourseIdFromUrl() {
  const url = new URL(window.location.href);
  url.searchParams.delete("course");
  window.history.pushState(null, "", url);
}

export default function useCourse() {
  const [course, setCourse] = useState(null);
  const [isLoading, setIsLoading] = useState(
    () => getCourseIdFromUrl() !== null,
  );
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    const courseId = getCourseIdFromUrl();
    if (!courseId) return;

    fetchJson(`/courses/${courseId}`)
      .then(setCourse)
      .catch((error) => {
        console.error("Error while loading course: ", error);
        setError(error.message);
      })
      .finally(() => setIsLoading(false));
  }, []);

  async function createCourse(initialPrompt) {
    setError(null);
    setIsCreating(true);

    try {
      const data = await fetchJson("/courses", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ initial_prompt: initialPrompt }),
      });
      setCourse(data);
      setCourseIdInUrl(data.id);
      return data;
    } catch (error) {
      console.error("Error while creating course: ", error);
      setError(error.message);
      return null;
    } finally {
      setIsCreating(false);
    }
  }

  async function loadCourse(courseId) {
    if (course?.id === courseId) return;

    setError(null);
    setIsLoading(true);

    try {
      const data = await fetchJson(`/courses/${courseId}`);
      setCourse(data);
      setCourseIdInUrl(courseId);
    } catch (error) {
      console.error("Error while loading course: ", error);
      setError(error.message);
    } finally {
      setIsLoading(false);
    }
  }

  function startNewCourse() {
    setCourse(null);
    setError(null);
    clearCourseIdFromUrl();
  }

  return {
    course,
    isLoading,
    isCreating,
    error,
    createCourse,
    loadCourse,
    startNewCourse,
  };
}
