import AttachmentList from "./AttachmentList";
import FileInput from "./FileInput";
import SendButton from "./SendButton";

function MessageComposer({ chat, fileUpload }) {
  const hasAttachments =
    fileUpload.documents.length > 0 || fileUpload.images.length > 0;
  const canSend = chat.userInput.trim() !== "" && !chat.isLoading;

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
        </div>

        <SendButton onClick={chat.handleSend} disabled={!canSend} />
      </div>

      {fileUpload.error && (
        <p className="text-warn text-xs px-4 pb-2">{fileUpload.error}</p>
      )}

      {chat.error && (
        <p className="text-warn text-xs px-4 pb-2">{chat.error}</p>
      )}
    </div>
  );
}

export default MessageComposer;
