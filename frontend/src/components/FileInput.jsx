import { Paperclip } from "lucide-react";

function FileInput({ inputRef, onChange, accept }) {
  return (
    <div>
      <input
        type="file"
        ref={inputRef}
        onChange={onChange}
        multiple
        accept={accept}
        className="hidden"
      />
      <button
        type="button"
        onClick={() => inputRef.current.click()}
        aria-label="Attach files"
        className="p-2 rounded-md text-faint hover:text-ink hover:bg-line"
      >
        <Paperclip size={18} />
      </button>
    </div>
  );
}

export default FileInput;
