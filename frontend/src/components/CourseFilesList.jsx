import { FileText, Paperclip, Trash2 } from "lucide-react";
import EmptyState from "./EmptyState";
import { fileContentUrl } from "../utils/api";

function CourseFilesList({ courseFiles }) {
  const { files, error, remove } = courseFiles;

  return (
    <div className="mx-3 mb-3 rounded-md bg-card p-3 type-body max-h-48 overflow-y-auto">
      <p className="type-label text-ink">Course files</p>
      {files.length === 0 ? (
        <EmptyState
          compact
          icon={Paperclip}
          title="No files yet"
          text="Attach files in a chat to use them in this course."
        />
      ) : (
        <ul className="mt-1 flex flex-col gap-1">
          {files.map((file) => (
            <li key={file.id}>
              <div className="flex items-center gap-2">
                {file.media_type ? (
                  <a
                    href={fileContentUrl(file.id)}
                    target="_blank"
                    rel="noopener noreferrer"
                    title="Open full size"
                    className="shrink-0"
                  >
                    <img
                      src={fileContentUrl(file.id)}
                      alt=""
                      className="w-6 h-6 rounded-sm object-cover"
                    />
                  </a>
                ) : (
                  <FileText size={14} className="shrink-0 text-faint" />
                )}
                <span
                  className="flex-1 truncate text-ink"
                  title={file.filename}
                >
                  {file.filename}
                </span>
                <span className="type-caption text-faint">
                  {new Date(file.created_at).toLocaleDateString()}
                </span>
                <button
                  type="button"
                  onClick={() => remove(file)}
                  aria-label={`Delete ${file.filename}`}
                  className="p-1 rounded-md text-faint hover:text-warn hover:bg-line"
                >
                  <Trash2 size={14} />
                </button>
              </div>
              {file.summary && (
                <p
                  className="ml-8 mt-0.5 type-caption text-muted line-clamp-2"
                  title={file.summary}
                >
                  {file.summary}
                </p>
              )}
            </li>
          ))}
        </ul>
      )}
      {error && <p className="mt-1 text-warn">{error}</p>}
    </div>
  );
}

export default CourseFilesList;
