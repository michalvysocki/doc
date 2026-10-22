import { useState } from "react";
import { fetchJson } from "../utils/api";

export default function useCreateCourse() {
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState(null);

  async function createCourse(initialPrompt, files = []) {
    setError(null);
    setIsCreating(true);

    try {
      const formData = new FormData();
      formData.append("initial_prompt", initialPrompt);
      for (const file of files) formData.append("files", file);

      return await fetchJson("/courses", { method: "POST", body: formData });
    } catch (error) {
      console.error("Error while creating course: ", error);
      setError(error.message);
      return null;
    } finally {
      setIsCreating(false);
    }
  }

  return { createCourse, isCreating, error };
}
