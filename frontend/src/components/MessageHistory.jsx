import { useEffect, useRef } from "react";
import AttachmentCard from "./AttachmentCard";
import MarkdownContent from "./MarkdownContent";
import EmptyState from "./EmptyState";
import { MessagesSquare } from "lucide-react";
import getFileLabel, { getFileLabelFromName } from "../utils/fileLabel";
import { fileContentUrl } from "../utils/api";

function MessageHistory({ messageHistory, isLoading, isReady, emptyState }) {
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
      {isReady && emptyState && messageHistory.length === 0 && !isLoading && (
        <div className="my-auto">
          <EmptyState icon={MessagesSquare} {...emptyState} />
        </div>
      )}
      {messageHistory.map((message, index) =>
        message.role === "user" ? (
          <div
            key={index}
            className="self-end max-w-[75%] rounded-md px-4 py-2 bg-accent text-paper"
          >
            {message.text}
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
          </div>
        ) : (
          <div key={index} className="text-ink prose prose-sm max-w-none">
            <MarkdownContent>{message.text}</MarkdownContent>
          </div>
        ),
      )}

      {isLoading && (
        <div className="flex gap-1 py-2">
          <span className="w-2 h-2 rounded-full bg-ink/40 animate-bounce" />
          <span className="w-2 h-2 rounded-full bg-ink/40 animate-bounce [animation-delay:150ms]" />
          <span className="w-2 h-2 rounded-full bg-ink/40 animate-bounce [animation-delay:300ms]" />
        </div>
      )}
    </div>
  );
}

export default MessageHistory;
