import { PanelRightClose, PanelRightOpen } from "lucide-react";
import MessageHistory from "./MessageHistory";
import MessageComposer from "./MessageComposer";

function ChatPanel({ chat, fileUpload, isOpen, onToggle }) {
  if (!isOpen) {
    return (
      <aside className="w-12 shrink-0 border-l border-line flex flex-col items-center py-3">
        <button
          type="button"
          onClick={onToggle}
          aria-label="Open chat"
          className="p-2 rounded-md text-ink/70 hover:bg-line/50"
        >
          <PanelRightOpen size={18} />
        </button>
      </aside>
    );
  }

  return (
    <aside className="w-96 shrink-0 border-l border-line flex flex-col">
      <div className="flex items-center justify-between px-3 py-3">
        <span className="text-sm font-semibold text-ink">Chat</span>
        <button
          type="button"
          onClick={onToggle}
          aria-label="Close chat"
          className="p-2 rounded-md text-ink/70 hover:bg-line/50"
        >
          <PanelRightClose size={18} />
        </button>
      </div>

      <MessageHistory
        messageHistory={chat.messageHistory}
        isLoading={chat.isLoading}
      />
      <div className="pb-4 px-4">
        <MessageComposer chat={chat} fileUpload={fileUpload} />
      </div>
    </aside>
  );
}

export default ChatPanel;
