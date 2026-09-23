export function LoadingSkeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="stack">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="skeleton" style={{ height: i === 0 ? 28 : 14, width: i === 0 ? '40%' : '100%' }} />
      ))}
    </div>
  );
}
