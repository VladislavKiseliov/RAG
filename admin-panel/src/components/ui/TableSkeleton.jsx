export default function TableSkeleton({ rows = 6, cols = 5 }) {
  return (
    <div className="animate-pulse space-y-2">
      {Array.from({ length: rows }).map((_, rowIdx) => (
        <div key={rowIdx} className="grid gap-2" style={{ gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))` }}>
          {Array.from({ length: cols }).map((__, colIdx) => (
            <div key={colIdx} className="h-8 rounded bg-slate-200" />
          ))}
        </div>
      ))}
    </div>
  );
}
