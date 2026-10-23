function EmptyState({ icon: Icon, title, text, compact = false }) {
  return (
    <div
      className={`flex flex-col items-center text-center ${compact ? "gap-1 py-3" : "gap-2 py-10"}`}
    >
      {Icon && (
        <span
          className={`flex items-center justify-center rounded-full bg-accent/10 text-accent ${compact ? "h-8 w-8" : "h-12 w-12"}`}
        >
          <Icon size={compact ? 16 : 22} />
        </span>
      )}
      <p className={`font-medium text-ink ${compact ? "text-sm" : ""}`}>
        {title}
      </p>
      {text && (
        <p
          className={`text-ink/60 ${compact ? "text-xs" : "text-sm"} max-w-xs`}
        >
          {text}
        </p>
      )}
    </div>
  );
}

export default EmptyState;
