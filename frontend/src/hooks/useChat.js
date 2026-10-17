import { useState } from "react";

export default function useChat(fileUpload) {
  const [userInput, setUserInput] = useState("");
  const [messageHistory, updateMessageHistory] = useState([]);
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(false);

  function formatMessagesForBackend(history) {
    return history.map((message) => {
      if (message.role === "assistant") {
        return { role: "assistant", content: message.text };
      }

      const contentBlocks = [{ type: "text", text: message.text }];

      for (const image of message.images) {
        contentBlocks.push({
          type: "file",
          file: {
            filename: image.filename,
            file_data: image.data,
          },
        });
      }

      return { role: "user", content: contentBlocks };
    });
  }

  async function handleSend() {
    const newUserMessage = {
      role: "user",
      text: userInput,
      images: fileUpload.images,
      documents: fileUpload.documents,
    };
    updateMessageHistory((prev) => [...prev, newUserMessage]);
    setUserInput("")
    fileUpload.setDocuments([])
    fileUpload.setImages([])
    

    const fullHistory = [...messageHistory, newUserMessage];

    const fileUuids = fullHistory
      .flatMap((message) => message.documents ?? [])
      .map((document) => document.file_uuid);

    const messages = formatMessagesForBackend(fullHistory);

    setError(null);
    setIsLoading(true);

    try {
      const response = await fetch("http://localhost:8000/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages, file_uuids: fileUuids }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(
          typeof errorData.detail === "string"
            ? errorData.detail
            : `Error while sending message: ${response.status}`,
        );
      }

      const data = await response.json();

      updateMessageHistory((prev) => [
        ...prev,
        { role: "assistant", text: data },
      ]);
    } catch (error) {
      console.error("Error while sending message: ", error);
      setError(error.message);
    } finally {
      setIsLoading(false);
    }
  }

  return {
    userInput,
    setUserInput,
    messageHistory,
    handleSend,
    error,
    isLoading,
  };
}
