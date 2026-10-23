import { useEffect, useMemo, useState } from "react";
import { fetchJson } from "../utils/api";

function toViewMessage(message) {
  return {
    role: message.role,
    text: message.content,
    documents: message.attachments.map((attachment) => ({
      file_uuid: attachment.file_uuid,
      filename: attachment.filename,
      media_type: attachment.media_type,
    })),
  };
}

export default function usePersistentChat(
  path,
  fileUpload,
  { onCourseChanged } = {},
) {
  const [userInput, setUserInput] = useState("");
  const [chat, setChat] = useState({
    path: null,
    messages: [],
    error: null,
  });
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (!path) return;
    let ignore = false;

    fetchJson(path)
      .then((messages) => {
        if (!ignore) setChat({ path, messages, error: null });
      })
      .catch((error) => {
        console.error("Error while loading messages: ", error);
        if (!ignore) setChat({ path, messages: [], error: error.message });
      });

    return () => {
      ignore = true;
    };
  }, [path]);

  function updateChat(forPath, update) {
    setChat((prev) => (prev.path === forPath ? update(prev) : prev));
  }

  function appendMessage(forPath, message) {
    updateChat(forPath, (prev) => ({
      ...prev,
      messages: [...prev.messages, message],
    }));
  }

  async function handleSend() {
    const sendingPath = path;
    const { documents } = fileUpload;
    const pending = {
      role: "user",
      content: userInput,
      attachments: documents.map(({ file_uuid, filename, media_type }) => ({
        file_uuid,
        filename,
        media_type,
      })),
    };

    setUserInput("");
    fileUpload.setDocuments([]);
    updateChat(sendingPath, (prev) => ({
      ...prev,
      messages: [...prev.messages, pending],
      error: null,
    }));
    setIsLoading(true);

    try {
      const reply = await fetchJson(sendingPath, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          content: pending.content,
          file_uuids: documents.map((document) => document.file_uuid),
        }),
      });
      updateChat(sendingPath, (prev) => ({
        ...prev,
        messages: [
          ...prev.messages.filter((message) => message !== pending),
          reply.user_message,
          reply.assistant_message,
        ],
      }));
      if (reply.course_changed) onCourseChanged?.();
    } catch (error) {
      console.error("Error while sending message: ", error);
      const saved = await fetchJson(sendingPath).catch(() => null);
      const wasSaved =
        saved?.at(-1)?.role === "user" &&
        saved.at(-1).content === pending.content.trim();
      if (!wasSaved) {
        setUserInput(pending.content);
        fileUpload.setDocuments(documents);
      }
      updateChat(sendingPath, (prev) => ({
        ...prev,
        messages: saved ?? prev.messages,
        error: error.message,
      }));
    } finally {
      setIsLoading(false);
    }
  }

  async function handleRetry() {
    const retryPath = path;
    updateChat(retryPath, (prev) => ({ ...prev, error: null }));
    setIsLoading(true);

    try {
      const reply = await fetchJson(`${retryPath}/retry`, { method: "POST" });
      updateChat(retryPath, (prev) => ({
        ...prev,
        messages: [...prev.messages, reply.assistant_message],
      }));
      if (reply.course_changed) onCourseChanged?.();
    } catch (error) {
      console.error("Error while retrying message: ", error);
      updateChat(retryPath, (prev) => ({ ...prev, error: error.message }));
    } finally {
      setIsLoading(false);
    }
  }

  const isCurrent = chat.path === path;
  const lastMessage = isCurrent ? chat.messages.at(-1) : null;
  const canRetry = Boolean(
    isCurrent && chat.error && lastMessage?.role === "user",
  );
  const messageHistory = useMemo(
    () => (isCurrent ? chat.messages.map(toViewMessage) : []),
    [isCurrent, chat.messages],
  );

  return {
    userInput,
    setUserInput,
    messageHistory,
    handleSend,
    handleRetry,
    canRetry,
    appendMessage,
    isLoading,
    error: isCurrent ? chat.error : null,
    isHistoryReady: isCurrent,
  };
}
