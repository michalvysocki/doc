import { FileText, X } from "lucide-react";

function AttachmentCard({ name, typeLabel, thumbnail, onRemove }) {
  return (
    <div className="flex items-center gap-2 bg-paper border border-line rounded-md px-3 py-2 shrink-0 max-w-45">
      {thumbnail ? (
        <img
          src={thumbnail}
          alt={name}
          className="w-8 h-8 object-cover rounded-sm shrink-0"
        />
      ) : (
        <FileText size={16} className="text-accent shrink-0" />
      )}

      <div className="flex flex-col min-w-0">
        <span className="text-xs text-ink truncate">{name}</span>
        {typeLabel && (
          <span className="text-[10px] text-ink/50">{typeLabel}</span>
        )}
      </div>

      {onRemove && (
        <button
          type="button"
          onClick={onRemove}
          className="text-ink/40 hover:text-warn shrink-0"
        >
          <X size={14} />
        </button>
      )}
    </div>
  );
}

export default AttachmentCard;
