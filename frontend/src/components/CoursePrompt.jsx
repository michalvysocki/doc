import { useRef, useState } from "react";
import AttachmentCard from "./AttachmentCard";
import FileInput from "./FileInput";
import getFileLabel from "../utils/fileLabel";
import {
  DOCUMENT_TYPES,
  MAX_COURSE_FILES,
  MAX_UPLOAD_BYTES,
} from "../utils/uploadLimits";

function CoursePrompt({ onSubmit, isLoading, error }) {
  const [prompt, setPrompt] = useState("");
  const [files, setFiles] = useState([]);
  const [fileError, setFileError] = useState(null);
  const fileInput = useRef(null);
  const canSubmit = prompt.trim() !== "" && !isLoading;

  function handlePick() {
    const picked = [...fileInput.current.files];
    fileInput.current.value = "";

    const errors = [];
    const accepted = [...files];
    for (const file of picked) {
      if (file.type.startsWith("image/")) {
        errors.push(`${file.name}: images are not supported here`);
      } else if (file.size > MAX_UPLOAD_BYTES) {
        errors.push(`${file.name}: the file is too large (max 20 MB)`);
      } else if (
        accepted.some((f) => f.name === file.name && f.size === file.size)
      ) {
        continue;
      } else if (accepted.length >= MAX_COURSE_FILES) {
        errors.push(
          `${file.name}: at most ${MAX_COURSE_FILES} files per course`,
        );
      } else {
        accepted.push(file);
      }
    }
    setFiles(accepted);
    setFileError(errors.length > 0 ? errors.join("\n") : null);
  }

  function removeFile(index) {
    setFiles((prev) => prev.filter((_, i) => i !== index));
    setFileError(null);
  }

  function handleSubmit(event) {
    event.preventDefault();
    if (!canSubmit) return;
    onSubmit(prompt.trim(), files);
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="border border-line rounded-md bg-paper max-w-2xl mx-auto w-full"
    >
      <textarea
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
        placeholder="What do you want to learn?"
        rows={4}
        disabled={isLoading}
        className="w-full px-4 py-3 outline-none text-ink bg-transparent resize-none"
      />

      {files.length > 0 && (
        <div className="flex flex-wrap gap-2 px-4 pb-2">
          {files.map((file, index) => (
            <AttachmentCard
              key={`${file.name}-${file.size}`}
              name={file.name}
              typeLabel={getFileLabel(file.type)}
              onRemove={isLoading ? null : () => removeFile(index)}
            />
          ))}
        </div>
      )}

      <div className="flex items-center justify-between px-3 pb-2">
        <div className="flex items-center gap-2">
          {!isLoading && (
            <FileInput
              inputRef={fileInput}
              onChange={handlePick}
              accept={DOCUMENT_TYPES}
            />
          )}
          <span className="text-xs text-ink/60">
            {isLoading &&
              (files.length > 0
                ? "Reading your files and creating the topic map, this can take a few minutes..."
                : "Creating the topic map, this can take a few minutes...")}
          </span>
        </div>
        <button
          type="submit"
          disabled={!canSubmit}
          className="bg-accent hover:bg-accent/90 text-paper rounded-md px-4 py-2 text-sm transition-colors disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-accent"
        >
          Create course
        </button>
      </div>

      {fileError && (
        <p className="text-warn text-xs px-4 pb-2 whitespace-pre-line">
          {fileError}
        </p>
      )}
      {error && <p className="text-warn text-xs px-4 pb-2">{error}</p>}
    </form>
  );
}

export default CoursePrompt;
