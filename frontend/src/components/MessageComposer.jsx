import AttachmentList from "./AttachmentList";
import FileInput from "./FileInput";
import SendButton from "./SendButton";
import { ACCEPTED_TYPES } from "../utils/uploadLimits";

function MessageComposer({ chat, fileUpload, placeholder }) {
  const hasAttachments = fileUpload.documents.length > 0;
  const canSend =
    chat.userInput.trim() !== "" && !chat.isLoading && !fileUpload.isUploading;

  function handleKeyDown(event) {
    if (event.key !== "Enter" || event.nativeEvent.isComposing) return;
    event.preventDefault();
    if (canSend) chat.handleSend();
  }

  return (
    <div className="rounded-md bg-card max-w-2xl mx-auto w-full outline-2 outline-transparent focus-within:outline-accent/40">
      {hasAttachments && (
        <AttachmentList
          documents={fileUpload.documents}
          removeDocument={fileUpload.removeDocument}
        />
      )}

      <input
        value={chat.userInput}
        onChange={(e) => chat.setUserInput(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        className="w-full px-4 py-3 outline-none text-ink bg-transparent"
      />

      <div className="flex items-center justify-between px-3 pb-2">
        <div className="flex items-center gap-2">
          <FileInput
            inputRef={fileUpload.fileInput}
            onChange={fileUpload.handleUpload}
            accept={ACCEPTED_TYPES}
          />
        </div>

        <SendButton onClick={chat.handleSend} disabled={!canSend} />
      </div>

      {fileUpload.isUploading && (
        <p className="type-caption text-faint px-4 pb-2">
          Uploading and indexing files...
        </p>
      )}

      {fileUpload.error && (
        <p className="type-caption text-warn px-4 pb-2 whitespace-pre-line">
          {fileUpload.error}
        </p>
      )}

      {chat.error && (
        <div className="flex items-center justify-between gap-2 px-4 pb-2">
          <p className="type-caption text-warn">{chat.error}</p>
          {chat.canRetry && (
            <button
              type="button"
              onClick={chat.handleRetry}
              disabled={chat.isLoading}
              className="btn-secondary btn-sm shrink-0"
            >
              Retry
            </button>
          )}
        </div>
      )}
    </div>
  );
}

export default MessageComposer;
