import { useEffect, useMemo, useState } from "react";
import { fetchJson, streamJson } from "../utils/api";

function toViewMessage(message) {
  return {
    role: message.role,
    text: message.content,
    streaming: Boolean(message.streaming),
    documents: message.attachments.map((attachment) => ({
      file_uuid: attachment.file_uuid,
      filename: attachment.filename,
      media_type: attachment.media_type,
    })),
  };
}

// Adds a piece of a streamed answer to the temporary message at the end.
function withDelta(messages, text) {
  const last = messages.at(-1);
  if (last?.streaming) {
    return [
      ...messages.slice(0, -1),
      { ...last, content: last.content + text },
    ];
  }
  return [
    ...messages,
    { role: "assistant", content: text, attachments: [], streaming: true },
  ];
}

const withoutStreaming = (messages) =>
  messages.filter((message) => !message.streaming);

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
  const [status, setStatus] = useState(null);

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

  // Reads the chat events of one answer and resolves with the final reply.
  async function readAnswer(forPath, url, options, onUserMessage) {
    let reply = null;
    await streamJson(url, options, (event) => {
      if (event.type === "user_message") {
        onUserMessage?.(event.message);
      } else if (event.type === "status") {
        setStatus(event.text);
      } else if (event.type === "delta") {
        setStatus(null);
        updateChat(forPath, (prev) => ({
          ...prev,
          messages: withDelta(prev.messages, event.text),
        }));
      } else if (event.type === "reset") {
        updateChat(forPath, (prev) => ({
          ...prev,
          messages: withoutStreaming(prev.messages),
        }));
      } else if (event.type === "done") {
        reply = event.reply;
      } else if (event.type === "error") {
        throw new Error(event.detail);
      }
    });
    if (!reply) throw new Error("The answer was cut off");
    return reply;
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
      const reply = await readAnswer(
        sendingPath,
        sendingPath,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            content: pending.content,
            file_uuids: documents.map((document) => document.file_uuid),
          }),
        },
        (saved) =>
          updateChat(sendingPath, (prev) => ({
            ...prev,
            messages: prev.messages.map((message) =>
              message === pending ? saved : message,
            ),
          })),
      );
      updateChat(sendingPath, (prev) => ({
        ...prev,
        messages: [
          ...withoutStreaming(prev.messages).filter(
            (message) =>
              message !== pending && message.id !== reply.user_message.id,
          ),
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
        messages: saved ?? withoutStreaming(prev.messages),
        error: error.message,
      }));
    } finally {
      setIsLoading(false);
      setStatus(null);
    }
  }

  async function handleRetry() {
    const retryPath = path;
    updateChat(retryPath, (prev) => ({ ...prev, error: null }));
    setIsLoading(true);

    try {
      const reply = await readAnswer(retryPath, `${retryPath}/retry`, {
        method: "POST",
      });
      updateChat(retryPath, (prev) => ({
        ...prev,
        messages: [...withoutStreaming(prev.messages), reply.assistant_message],
      }));
      if (reply.course_changed) onCourseChanged?.();
    } catch (error) {
      console.error("Error while retrying message: ", error);
      updateChat(retryPath, (prev) => ({
        ...prev,
        messages: withoutStreaming(prev.messages),
        error: error.message,
      }));
    } finally {
      setIsLoading(false);
      setStatus(null);
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
    status,
    error: isCurrent ? chat.error : null,
    isHistoryReady: isCurrent,
  };
}
