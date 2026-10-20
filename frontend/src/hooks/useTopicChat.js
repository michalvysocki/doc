import { useEffect, useMemo, useState } from "react";
import { fetchJson } from "../utils/api";

function toViewMessage(message) {
  return {
    role: message.role,
    text: message.content,
    documents: message.attachments.map((attachment) => ({
      file_uuid: attachment.file_uuid,
      filename: attachment.filename,
    })),
    images: message.images ?? [],
  };
}

export default function useTopicChat(topicId, fileUpload) {
  const [userInput, setUserInput] = useState("");
  const [chat, setChat] = useState({
    topicId: null,
    messages: [],
    error: null,
  });
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (!topicId) return;
    let ignore = false;

    fetchJson(`/topics/${topicId}/messages`)
      .then((messages) => {
        if (!ignore) setChat({ topicId, messages, error: null });
      })
      .catch((error) => {
        console.error("Error while loading messages: ", error);
        if (!ignore) setChat({ topicId, messages: [], error: error.message });
      });

    return () => {
      ignore = true;
    };
  }, [topicId]);

  function updateChat(forTopicId, update) {
    setChat((prev) => (prev.topicId === forTopicId ? update(prev) : prev));
  }

  async function handleSend() {
    const sendingTopicId = topicId;
    const { documents, images } = fileUpload;
    const pending = {
      role: "user",
      content: userInput,
      attachments: documents.map(({ file_uuid, filename }) => ({
        file_uuid,
        filename,
      })),
      images,
    };

    setUserInput("");
    fileUpload.setDocuments([]);
    fileUpload.setImages([]);
    updateChat(sendingTopicId, (prev) => ({
      ...prev,
      messages: [...prev.messages, pending],
      error: null,
    }));
    setIsLoading(true);

    try {
      const reply = await fetchJson(`/topics/${sendingTopicId}/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          content: pending.content,
          file_uuids: documents.map((document) => document.file_uuid),
          images: images.map(({ filename, data }) => ({ filename, data })),
        }),
      });
      updateChat(sendingTopicId, (prev) => ({
        ...prev,
        messages: [
          ...prev.messages.filter((message) => message !== pending),
          reply.user_message,
          reply.assistant_message,
        ],
      }));
    } catch (error) {
      console.error("Error while sending message: ", error);
      const saved = await fetchJson(`/topics/${sendingTopicId}/messages`).catch(
        () => null,
      );
      updateChat(sendingTopicId, (prev) => ({
        ...prev,
        messages: saved ?? prev.messages,
        error: error.message,
      }));
    } finally {
      setIsLoading(false);
    }
  }

  const isCurrent = chat.topicId === topicId;
  const messageHistory = useMemo(
    () => (isCurrent ? chat.messages.map(toViewMessage) : []),
    [isCurrent, chat.messages],
  );

  return {
    userInput,
    setUserInput,
    messageHistory,
    handleSend,
    isLoading,
    error: isCurrent ? chat.error : null,
  };
}
