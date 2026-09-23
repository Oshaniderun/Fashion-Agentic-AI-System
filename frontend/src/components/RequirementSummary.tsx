import type { UserRequirements } from '../types';

export function RequirementSummary({ requirements }: { requirements: UserRequirements }) {
  const rows = [
    { label: 'Occasion', value: requirements.occasion || 'Not specified' },
    { label: 'Style', value: requirements.style.length ? requirements.style.join(', ') : 'Not specified' },
    {
      label: 'Requested item',
      value: (() => {
        if (requirements.identified_items && requirements.identified_items.length > 0) {
          const reqItems = requirements.identified_items.filter((i) => i.role === 'requested');
          if (reqItems.length > 0) {
            return reqItems.map((i) => i.type || i.category).join(', ');
          }
        }
        return requirements.requested_types?.length
          ? requirements.requested_types.join(', ')
          : requirements.requested_categories?.length
            ? requirements.requested_categories.join(', ')
            : 'Not specified';
      })(),
    },
    {
      label: 'Pattern',
      value: requirements.pattern_preferences?.length
        ? requirements.pattern_preferences.join(', ')
        : 'Not specified',
    },
    {
      label: 'Colour preferences',
      value: requirements.colour_preferences.length
        ? requirements.colour_preferences.join(', ')
        : 'Not specified',
    },
    {
      label: 'Excluded colours',
      value: requirements.excluded_colours.length
        ? requirements.excluded_colours.join(', ')
        : 'None',
    },
    {
      label: 'Budget',
      value: requirements.budget != null ? `LKR ${requirements.budget.toLocaleString()}` : 'Not specified',
    },
  ];

  return (
    <div className="stack" style={{ gap: '0.65rem' }}>
      {rows.map((r) => (
        <div key={r.label} className="row" style={{ justifyContent: 'space-between' }}>
          <span className="meta">{r.label}</span>
          <strong style={{ textTransform: 'capitalize' }}>{r.value}</strong>
        </div>
      ))}
    </div>
  );
}
