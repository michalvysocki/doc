import { useState, useRef } from "react";

const readFile = (file) => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();

    reader.onload = () => resolve(reader.result);
    reader.onerror = (error) => reject(error);

    reader.readAsDataURL(file);
  });
};

export default function useFileUpload() {
  const fileInput = useRef(null);
  const [documents, setDocuments] = useState([]);
  const [images, setImages] = useState([]);
  const [error, setError] = useState(null);

  async function handleFile(file_data) {
    const isImage = file_data.type.startsWith("image/");

    if (isImage) {
      try {
        const base64data = await readFile(file_data);

        const newImage = {
          id: crypto.randomUUID(),
          filename: file_data.name,
          type: file_data.type,
          data: base64data,
        };

        setImages((prev) => [...prev, newImage]);
      } catch (error) {
        console.error("Error while processing image: ", error);
        setError("Couldn't process file. Try Again.");
      }
    } else {
      try {
        const formData = new FormData();
        formData.append("file", file_data);

        const response = await fetch("http://localhost:8000/parse_file", {
          method: "POST",
          body: formData,
        });

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          throw new Error(
            errorData.detail || `Error while parsing file: ${response.status}`,
          );
        }

        const data = await response.json();

        const newDocument = {
          file_uuid: data.file_uuid,
          filename: data.filename,
          type: file_data.type,
        };

        setDocuments((prev) => [...prev, newDocument]);
      } catch (error) {
        console.error("Error while indexing file: ", error);
        setError("Couldn't process file. Try Again.");
      }
    }
  }

  async function handleUpload() {
    const files_data = fileInput.current.files;

    if (files_data.length === 0) {
      console.error("No file selected");
      return;
    }

    for (const file_data of files_data) {
      await handleFile(file_data);
    }
  }

  async function removeDocument(file_uuid) {
    try {
      const response = await fetch(
        `http://localhost:8000/delete_file/${file_uuid}`,
        { method: "DELETE" },
      );
      if (response.ok) {
        setDocuments((prev) =>
          prev.filter((doc) => doc.file_uuid !== file_uuid),
        );
      } else {
        console.error(`Couldn't delete file. Code: ${response.status}`);
      }
    } catch (error) {
      console.error("Network error while deleting document: ", error);
      setError("Couldn't process file. Try Again.");
    }
  }

  async function removeImage(id) {
    setImages((prev) => prev.filter((img) => img.id !== id));
  }

  return {
    fileInput,
    documents,
    setDocuments,
    images,
    setImages,
    handleUpload,
    removeDocument,
    removeImage,
    error,
  };
}
