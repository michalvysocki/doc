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
    <div className="border border-line rounded-md bg-surface shadow-sm max-w-2xl mx-auto w-full focus-within:border-accent">
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
        <p className="text-ink/60 text-xs px-4 pb-2">
          Uploading and indexing files...
        </p>
      )}

      {fileUpload.error && (
        <p className="text-warn text-xs px-4 pb-2 whitespace-pre-line">
          {fileUpload.error}
        </p>
      )}

      {chat.error && (
        <div className="flex items-center justify-between gap-2 px-4 pb-2">
          <p className="text-warn text-xs">{chat.error}</p>
          {chat.canRetry && (
            <button
              type="button"
              onClick={chat.handleRetry}
              disabled={chat.isLoading}
              className="btn-secondary shrink-0 px-2 py-1 text-xs"
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
