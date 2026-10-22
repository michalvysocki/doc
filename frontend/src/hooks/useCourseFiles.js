import { useEffect, useState } from "react";
import { fetchJson } from "../utils/api";

export default function useCourseFiles(courseId, { onRemoved } = {}) {
  const [result, setResult] = useState({ courseId: null, files: [] });
  const [isOpen, setIsOpen] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!isOpen) return;
    let ignore = false;

    fetchJson(`/courses/${courseId}/files`)
      .then((files) => {
        if (!ignore) setResult({ courseId, files });
      })
      .catch((error) => {
        console.error("Error while loading course files: ", error);
        if (!ignore) setError(error.message);
      });

    return () => {
      ignore = true;
    };
  }, [courseId, isOpen]);

  async function remove(file) {
    const confirmed = window.confirm(
      `Delete "${file.filename}"? Chats, lessons and course rebuilds will no longer use it.`,
    );
    if (!confirmed) return;

    setError(null);
    try {
      await fetchJson(`/delete_file/${file.id}`, { method: "DELETE" });
      setResult((prev) => ({
        ...prev,
        files: prev.files.filter((item) => item.id !== file.id),
      }));
      onRemoved?.(file);
    } catch (error) {
      console.error("Error while deleting course file: ", error);
      setError(`Couldn't delete the file: ${error.message}`);
    }
  }

  return {
    files: result.courseId === courseId ? result.files : [],
    isOpen,
    toggle: () => setIsOpen((prev) => !prev),
    error,
    remove,
  };
}
