import { useEffect, useRef, useState } from "react";
import { fetchJson } from "../utils/api";
import { IMAGE_TYPES, MAX_UPLOAD_BYTES } from "../utils/uploadLimits";

export default function useFileUpload(courseId) {
  const fileInput = useRef(null);
  const [documents, setDocuments] = useState([]);
  const [error, setError] = useState(null);
  const [isUploading, setIsUploading] = useState(false);

  // A new course starts with no staged attachments.
  const [stagedFor, setStagedFor] = useState(courseId);
  if (courseId !== stagedFor) {
    setStagedFor(courseId);
    setDocuments([]);
    setError(null);
  }
  const courseIdRef = useRef(courseId);
  useEffect(() => {
    courseIdRef.current = courseId;
  });

  async function handleFile(file_data) {
    const forCourseId = courseId;
    if (file_data.size > MAX_UPLOAD_BYTES) {
      return `${file_data.name}: the file is too large (max 20 MB)`;
    }

    try {
      const formData = new FormData();
      formData.append("file", file_data);
      if (courseId) formData.append("course_id", courseId);

      const data = await fetchJson("/parse_file", {
        method: "POST",
        body: formData,
      });
      if (courseIdRef.current !== forCourseId) return null;

      const newDocument = {
        file_uuid: data.file_uuid,
        filename: data.filename,
        type: file_data.type,
        media_type: IMAGE_TYPES.includes(file_data.type)
          ? file_data.type
          : null,
      };

      setDocuments((prev) => [...prev, newDocument]);
    } catch (error) {
      console.error("Error while indexing file: ", error);
      return `${file_data.name}: ${error.message}`;
    }

    return null;
  }

  async function handleUpload() {
    const files_data = [...fileInput.current.files];
    fileInput.current.value = "";
    if (files_data.length === 0) return;

    setError(null);
    setIsUploading(true);
    const errors = [];
    try {
      for (const file_data of files_data) {
        const fileError = await handleFile(file_data);
        if (fileError) errors.push(fileError);
      }
    } finally {
      setIsUploading(false);
    }
    if (errors.length > 0) setError(errors.join("\n"));
  }

  async function removeDocument(file_uuid) {
    setError(null);
    try {
      await fetchJson(`/delete_file/${file_uuid}`, { method: "DELETE" });
      setDocuments((prev) => prev.filter((doc) => doc.file_uuid !== file_uuid));
    } catch (error) {
      console.error("Error while deleting document: ", error);
      setError(`Couldn't remove the file: ${error.message}`);
    }
  }

  return {
    fileInput,
    documents,
    setDocuments,
    handleUpload,
    removeDocument,
    error,
    isUploading,
  };
}
