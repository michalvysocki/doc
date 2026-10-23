function EmptyState({ icon: Icon, title, text, action, compact = false }) {
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
      <p className={`${compact ? "type-label" : "type-item"} text-ink`}>
        {title}
      </p>
      {text && (
        <p
          className={`${compact ? "type-caption" : "type-body"} text-muted max-w-xs`}
        >
          {text}
        </p>
      )}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}

export default EmptyState;
