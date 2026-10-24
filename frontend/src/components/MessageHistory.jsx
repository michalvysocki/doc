import { useEffect, useRef } from "react";
import AttachmentCard from "./AttachmentCard";
import MarkdownContent from "./MarkdownContent";
import EmptyState from "./EmptyState";
import { Info, MessagesSquare } from "lucide-react";
import getFileLabel, { getFileLabelFromName } from "../utils/fileLabel";
import { fileContentUrl } from "../utils/api";

// Notes the backend adds after a confirmation card, e.g. "[Deleted topic: X]".
const NOTE = /^\[([^\]\n]+)\]$/;

function MessageHistory({
  messageHistory,
  isLoading,
  isReady,
  hasError,
  emptyState,
}) {
  const containerRef = useRef(null);

  useEffect(() => {
    const container = containerRef.current;
    container.scrollTo({ top: container.scrollHeight, behavior: "smooth" });
  }, [messageHistory, isLoading]);

  return (
    <div
      ref={containerRef}
      className="flex flex-col gap-4 p-4 max-w-2xl mx-auto w-full flex-1 overflow-y-auto"
    >
      {isReady &&
        emptyState &&
        messageHistory.length === 0 &&
        !isLoading &&
        !hasError && (
          <div className="my-auto">
            <EmptyState icon={MessagesSquare} {...emptyState} />
          </div>
        )}
      {messageHistory.map((message, index) => {
        const note = message.role === "user" && NOTE.exec(message.text);
        if (note) {
          return (
            <p
              key={index}
              className="self-center flex items-center gap-1.5 type-caption text-faint"
            >
              <Info size={12} />
              {note[1]}
            </p>
          );
        }
        return message.role === "user" ? (
          <div
            key={index}
            className="self-end max-w-[75%] rounded-md px-4 py-2 bg-card type-body text-ink"
          >
            {message.text}
            {message.documents.length > 0 && (
              <div className="flex flex-wrap gap-2 mt-2">
                {message.documents.map((doc) => (
                  <AttachmentCard
                    key={doc.file_uuid}
                    name={doc.filename}
                    thumbnail={
                      doc.media_type ? fileContentUrl(doc.file_uuid) : null
                    }
                    typeLabel={
                      doc.type
                        ? getFileLabel(doc.type)
                        : getFileLabelFromName(doc.filename)
                    }
                  />
                ))}
              </div>
            )}
          </div>
        ) : (
          <div
            key={index}
            className="prose prose-sm max-w-none prose-h1:text-base prose-h2:text-base prose-h3:text-sm"
          >
            <MarkdownContent>{message.text}</MarkdownContent>
          </div>
        );
      })}

      {isLoading && (
        <div className="flex items-center gap-2 py-2 type-body text-muted">
          <div className="flex gap-1">
            <span className="w-2 h-2 rounded-full bg-faint animate-bounce" />
            <span className="w-2 h-2 rounded-full bg-faint animate-bounce [animation-delay:150ms]" />
            <span className="w-2 h-2 rounded-full bg-faint animate-bounce [animation-delay:300ms]" />
          </div>
          Thinking…
        </div>
      )}
    </div>
  );
}

export default MessageHistory;
