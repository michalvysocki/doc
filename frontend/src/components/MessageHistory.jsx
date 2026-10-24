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
  status,
  isReady,
  hasError,
  emptyState,
}) {
  const containerRef = useRef(null);
  const isStreaming = Boolean(messageHistory.at(-1)?.streaming);
  const isNearBottom = useRef(true);
  const lastScrollTop = useRef(0);

  // Remembers whether the learner is reading the end of the chat. Only scrolling
  // up turns following off: our own scrolling to the end always goes down.
  function handleScroll() {
    const container = containerRef.current;
    const nearBottom =
      container.scrollHeight - container.scrollTop - container.clientHeight <
      80;
    if (container.scrollTop < lastScrollTop.current) {
      isNearBottom.current = nearBottom;
    } else if (nearBottom) {
      isNearBottom.current = true;
    }
    lastScrollTop.current = container.scrollTop;
  }

  // The wheel and touch events come at once, before the next streamed piece
  // could scroll the chat back down; the scroll event only comes with the next frame.
  function stopFollowing(event) {
    if (event.type === "touchmove" || event.deltaY < 0) {
      isNearBottom.current = false;
    }
  }

  useEffect(() => {
    const container = containerRef.current;
    // While an answer streams, follow it only if the learner has not scrolled up.
    if (isStreaming && !isNearBottom.current) return;
    // Smooth scrolling for every streamed piece would make the text jump around.
    container.scrollTo({
      top: container.scrollHeight,
      behavior: isStreaming ? "auto" : "smooth",
    });
  }, [messageHistory, isLoading, isStreaming]);

  return (
    <div
      ref={containerRef}
      onScroll={handleScroll}
      onWheel={stopFollowing}
      onTouchMove={stopFollowing}
      className="flex flex-col gap-4 p-4 max-w-2xl mx-auto w-full flex-1 overflow-y-auto [overflow-anchor:none]"
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

      {isLoading && !isStreaming && (
        <div className="flex items-center gap-2 py-2 type-body text-muted">
          <div className="flex gap-1">
            <span className="w-2 h-2 rounded-full bg-faint animate-bounce" />
            <span className="w-2 h-2 rounded-full bg-faint animate-bounce [animation-delay:150ms]" />
            <span className="w-2 h-2 rounded-full bg-faint animate-bounce [animation-delay:300ms]" />
          </div>
          {status ?? "Thinking…"}
        </div>
      )}
    </div>
  );
}

export default MessageHistory;
