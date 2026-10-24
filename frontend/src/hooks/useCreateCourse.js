import { useState } from "react";
import { streamJson } from "../utils/api";

export default function useCreateCourse() {
  const [isCreating, setIsCreating] = useState(false);
  const [status, setStatus] = useState(null);
  const [error, setError] = useState(null);

  async function createCourse(initialPrompt, files = []) {
    setError(null);
    setIsCreating(true);

    try {
      const formData = new FormData();
      formData.append("initial_prompt", initialPrompt);
      for (const file of files) formData.append("files", file);

      let course = null;
      await streamJson(
        "/courses",
        { method: "POST", body: formData },
        (event) => {
          if (event.type === "status") setStatus(event.text);
          else if (event.type === "done") course = event.course;
          else if (event.type === "error") throw new Error(event.detail);
        },
      );
      if (!course) throw new Error("Creating the course was cut off");
      return course;
    } catch (error) {
      console.error("Error while creating course: ", error);
      setError(error.message);
      return null;
    } finally {
      setIsCreating(false);
      setStatus(null);
    }
  }

  return { createCourse, isCreating, status, error };
}
