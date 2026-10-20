import { useState } from "react";
import { fetchJson } from "../utils/api";

export default function useCreateCourse() {
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState(null);

  async function createCourse(initialPrompt) {
    setError(null);
    setIsCreating(true);

    try {
      return await fetchJson("/courses", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ initial_prompt: initialPrompt }),
      });
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
