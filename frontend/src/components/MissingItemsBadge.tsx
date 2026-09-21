import type { OutfitRequirements } from '../types';

export function MissingItemsBadge({ outfit }: { outfit: OutfitRequirements }) {
  if (!outfit.missing_categories.length) {
    return <span className="badge badge-ok">No required categories missing</span>;
  }
  return (
    <div className="chip-row">
      {outfit.missing_categories.map((c) => (
        <span key={c} className="badge badge-warn">
          Possible missing: {c}
        </span>
      ))}
    </div>
  );
}
