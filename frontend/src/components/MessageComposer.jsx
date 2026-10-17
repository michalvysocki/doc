import AttachmentList from "./AttachmentList";
import FileInput from "./FileInput";
import SendButton from "./SendButton";

function MessageComposer({ chat, fileUpload }) {
  const hasAttachments =
    fileUpload.documents.length > 0 || fileUpload.images.length > 0;
  const canSend = chat.userInput.trim() !== "";

  return (
    <div className="border border-line rounded-md bg-paper max-w-2xl mx-auto w-full">
      {hasAttachments && (
        <AttachmentList
          documents={fileUpload.documents}
          removeDocument={fileUpload.removeDocument}
          images={fileUpload.images}
          removeImage={fileUpload.removeImage}
        />
      )}

      <input
        value={chat.userInput}
        onChange={(e) => chat.setUserInput(e.target.value)}
        placeholder="Write a message..."
        className="w-full px-4 py-3 outline-none text-ink bg-transparent"
      />

      <div className="flex items-center justify-between px-3 pb-2">
        <div className="flex items-center gap-2">
          <FileInput
            inputRef={fileUpload.fileInput}
            onChange={fileUpload.handleUpload}
          />

          <label className="flex items-center gap-2 cursor-pointer">
            <div className="relative">
              <input
                type="checkbox"
                checked={fileUpload.useRag}
                onChange={(e) => fileUpload.setUseRag(e.target.checked)}
                className="sr-only peer"
              />
              <div className="w-9 h-5 bg-line rounded-full peer-checked:bg-accent transition-colors" />
              <div className="absolute top-0.5 left-0.5 w-4 h-4 bg-paper rounded-full transition-transform peer-checked:translate-x-4" />
            </div>
            <span className="text-xs text-ink/60">RAG</span>
          </label>
        </div>

        <SendButton onClick={chat.handleSend} disabled={!canSend} />
      </div>

      {fileUpload.error && (
        <p className="text-warn text-xs px-4 pb-2">{fileUpload.error}</p>
      )}
    </div>
  );
}

export default MessageComposer;
