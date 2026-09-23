export function ConfidenceBadge({ value, label = 'Confidence' }: { value: number; label?: string }) {
  const pct = Math.round(value * 100);
  const cls = pct >= 80 ? 'badge-ok' : pct >= 55 ? 'badge-warn' : 'badge-danger';
  return (
    <span className={`badge ${cls}`} title={`${label}: ${pct}%`}>
      {label} {pct}%
    </span>
  );
}
