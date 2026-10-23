import { PanelRightClose, PanelRightOpen, Paperclip } from "lucide-react";
import MessageHistory from "./MessageHistory";
import CourseFilesList from "./CourseFilesList";
import MessageComposer from "./MessageComposer";
import RegenerationCards from "./RegenerationCards";
import TopicDeletionCards from "./TopicDeletionCards";

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
  if (!isOpen) {
    return (
      <aside className="w-12 shrink-0 border-l border-line flex flex-col items-center py-3">
        <button
          type="button"
          onClick={onToggle}
          aria-label="Open chat"
          className="p-2 rounded-md text-ink/70 hover:bg-hover"
        >
          <PanelRightOpen size={18} />
        </button>
      </aside>
    );
  }

  return (
    <aside className="w-80 xl:w-96 shrink-0 border-l border-line flex flex-col">
      <div className="border-b border-line">
        <div className="flex items-center justify-between px-3 py-3">
          <span className="text-sm font-semibold text-ink">{title}</span>
          <div className="flex items-center gap-1">
            {courseFiles && (
              <button
                type="button"
                onClick={courseFiles.toggle}
                aria-label="Course files"
                aria-expanded={courseFiles.isOpen}
                className="flex items-center gap-1 p-2 rounded-md text-ink/70 hover:bg-hover"
              >
                <Paperclip size={16} />
                {courseFiles.files.length > 0 && (
                  <span className="text-xs">{courseFiles.files.length}</span>
                )}
              </button>
            )}
            <button
              type="button"
              onClick={onToggle}
              aria-label="Close chat"
              className="p-2 rounded-md text-ink/70 hover:bg-hover"
            >
              <PanelRightClose size={18} />
            </button>
          </div>
        </div>

        {courseFiles?.isOpen && <CourseFilesList courseFiles={courseFiles} />}
      </div>

      <MessageHistory
        messageHistory={chat.messageHistory}
        isLoading={chat.isLoading}
        isReady={chat.isHistoryReady}
        emptyState={emptyState}
      />
      {regenerations && <RegenerationCards regenerations={regenerations} />}
      {topicDeletions && <TopicDeletionCards topicDeletions={topicDeletions} />}
      <div className="pb-4 px-4">
        <MessageComposer
          chat={chat}
          fileUpload={fileUpload}
          placeholder={placeholder}
        />
      </div>
    </aside>
  );
}

export default ChatPanel;
