import { useEffect, useState } from "react";
import { fetchJson } from "../utils/api";

export default function useCourses() {
  const [courses, setCourses] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    fetchJson("/courses")
      .then(setCourses)
      .catch((error) => {
        console.error("Error while loading courses: ", error);
        setError(error.message);
      })
      .finally(() => setIsLoading(false));
  }, [refreshKey]);

  function refresh() {
    setRefreshKey((key) => key + 1);
  }

  function addCourse(course) {
    setCourses((prev) => [
      { id: course.id, title: course.title, created_at: course.created_at },
      ...prev,
    ]);
  }

  async function removeCourse(courseId) {
    setError(null);

    try {
      await fetchJson(`/courses/${courseId}`, { method: "DELETE" });
      setCourses((prev) => prev.filter((course) => course.id !== courseId));
      return true;
    } catch (error) {
      console.error("Error while deleting course: ", error);
      setError(error.message);
      return false;
    }
  }

  return { courses, isLoading, error, addCourse, removeCourse, refresh };
}
