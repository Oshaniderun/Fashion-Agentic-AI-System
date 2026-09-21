interface Props {
  label: string;
  score: number;
  qualitative?: string;
}

export function CompatibilityMeter({ label, score, qualitative }: Props) {
  const pct = Math.max(0, Math.min(100, Math.round(score * 100)));
  return (
    <div>
      <div className="row" style={{ justifyContent: 'space-between', marginBottom: 6 }}>
        <strong>{label}</strong>
        <span className="meta">
          {qualitative ? `${qualitative} · ` : ''}
          {pct}%
        </span>
      </div>
      <div className="meter">
        <span style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
