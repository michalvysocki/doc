import { PanelRightClose, PanelRightOpen, Paperclip } from "lucide-react";
import MessageHistory from "./MessageHistory";
import CourseFilesList from "./CourseFilesList";
import MessageComposer from "./MessageComposer";
import RegenerationCards from "./RegenerationCards";
import TopicDeletionCards from "./TopicDeletionCards";

// Both states render the same <aside>, so React keeps the element and the width animates.
// Below lg the open panel overlays the content; a spacer keeps the collapsed width in the layout.
const ASIDE =
  "shrink-0 overflow-hidden border-l border-line bg-paper transition-[width] duration-200 ease-out motion-reduce:transition-none";

function ChatPanel({
  chat,
  title,
  fileUpload,
  isOpen,
  onToggle,
  topicDeletions,
  regenerations,
  placeholder,
  courseFiles,
  emptyState,
}) {
  const overlay = isOpen && (
    <>
      <div className="w-12 shrink-0 lg:hidden" />
      <div
        className="fixed inset-0 z-20 bg-ink/20 lg:hidden"
        onClick={onToggle}
      />
    </>
  );

  if (!isOpen) {
    return (
      <>
        {overlay}
        <aside className={`w-12 ${ASIDE}`}>
          <div className="w-12 flex flex-col items-center py-3">
            <button
              type="button"
              onClick={onToggle}
              aria-label="Open chat"
              className="p-2 rounded-md text-muted hover:text-ink hover:bg-line"
            >
              <PanelRightOpen size={18} />
            </button>
          </div>
        </aside>
      </>
    );
  }

  return (
    <>
      {overlay}
      <aside
        className={`w-80 xl:w-96 max-lg:fixed max-lg:inset-y-0 max-lg:right-0 max-lg:z-30 ${ASIDE}`}
      >
        <div className="w-80 xl:w-96 h-full flex flex-col">
          <div className="border-b border-line">
            <div className="flex items-center justify-between px-3 py-3">
              <span className="type-label text-ink">{title}</span>
              <div className="flex items-center gap-1">
                {courseFiles && (
                  <button
                    type="button"
                    onClick={courseFiles.toggle}
                    aria-label="Course files"
                    aria-expanded={courseFiles.isOpen}
                    className="flex items-center gap-1 p-2 rounded-md text-muted hover:text-ink hover:bg-line"
                  >
                    <Paperclip size={16} />
                    {courseFiles.files.length > 0 && (
                      <span className="type-caption">
                        {courseFiles.files.length}
                      </span>
                    )}
                  </button>
                )}
                <button
                  type="button"
                  onClick={onToggle}
                  aria-label="Close chat"
                  className="p-2 rounded-md text-muted hover:text-ink hover:bg-line"
                >
                  <PanelRightClose size={18} />
                </button>
              </div>
            </div>

            {courseFiles && (
              <div
                className={`grid transition-[grid-template-rows] duration-200 ease-out motion-reduce:transition-none ${
                  courseFiles.isOpen ? "grid-rows-[1fr]" : "grid-rows-[0fr]"
                }`}
                inert={!courseFiles.isOpen}
              >
                <div className="overflow-hidden">
                  <CourseFilesList courseFiles={courseFiles} />
                </div>
              </div>
            )}
          </div>

          <MessageHistory
            messageHistory={chat.messageHistory}
            isLoading={chat.isLoading}
            status={chat.status}
            isReady={chat.isHistoryReady}
            hasError={Boolean(chat.error)}
            emptyState={emptyState}
          />
          {regenerations && <RegenerationCards regenerations={regenerations} />}
          {topicDeletions && (
            <TopicDeletionCards topicDeletions={topicDeletions} />
          )}
          <div className="pb-4 px-4">
            <MessageComposer
              chat={chat}
              fileUpload={fileUpload}
              placeholder={placeholder}
            />
          </div>
        </div>
      </aside>
    </>
  );
}

export default ChatPanel;
