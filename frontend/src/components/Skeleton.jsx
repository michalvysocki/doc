function Skeleton({ lines = 3, className = "" }) {
  return (
    <div
      className={`flex flex-col gap-3 animate-pulse ${className}`}
      aria-busy="true"
    >
      {Array.from({ length: lines }, (_, index) => (
        <div
          key={index}
          className="h-4 rounded-md bg-line"
          style={{ width: `${index === lines - 1 ? 60 : 100 - index * 8}%` }}
        />
      ))}
    </div>
  );
}

export default Skeleton;
