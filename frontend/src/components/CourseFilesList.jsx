import { FileText, Trash2 } from "lucide-react";

function CourseFilesList({ courseFiles }) {
  const { files, error, remove } = courseFiles;

  return (
    <div className="mx-3 mb-2 rounded-md border border-line p-3 text-sm max-h-48 overflow-y-auto">
      <p className="font-medium text-ink">Course files</p>
      {files.length === 0 ? (
        <p className="mt-1 text-ink/60">
          No files uploaded yet. Attach files in a chat to use them in this
          course.
        </p>
      ) : (
        <ul className="mt-1 flex flex-col gap-1">
          {files.map((file) => (
            <li key={file.id} className="flex items-center gap-2">
              <FileText size={14} className="shrink-0 text-ink/50" />
              <span className="flex-1 truncate text-ink" title={file.filename}>
                {file.filename}
              </span>
              <span className="text-xs text-ink/50">
                {new Date(file.created_at).toLocaleDateString()}
              </span>
              <button
                type="button"
                onClick={() => remove(file)}
                aria-label={`Delete ${file.filename}`}
                className="p-1 rounded-md text-ink/50 hover:text-warn hover:bg-line/50"
              >
                <Trash2 size={14} />
              </button>
            </li>
          ))}
        </ul>
      )}
      {error && <p className="mt-1 text-warn">{error}</p>}
    </div>
  );
}

export default CourseFilesList;
