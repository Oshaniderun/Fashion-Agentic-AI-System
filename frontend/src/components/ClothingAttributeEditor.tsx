import type { ClothingAttributes } from '../types';
import { CLOTHING_CATEGORIES, CLOTHING_PATTERNS, CLOTHING_STYLES } from '../constants/clothing';

interface Props {
  value: ClothingAttributes;
  onChange: (next: ClothingAttributes) => void;
  aiDetected?: boolean;
}

export function ClothingAttributeEditor({ value, onChange, aiDetected }: Props) {
  const set = <K extends keyof ClothingAttributes>(key: K, v: ClothingAttributes[K]) =>
    onChange({ ...value, [key]: v });

  return (
    <div className="stack">
      {aiDetected && (
        <div className="alert alert-info">
          AI-detected attributes — review and edit before saving. Predictions are not facts.
        </div>
      )}
      <div className="row">
        <div className="field">
          <label>Category</label>
          <select value={value.category} onChange={(e) => set('category', e.target.value)}>
            {CLOTHING_CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label>Type</label>
          <input value={value.type} onChange={(e) => set('type', e.target.value)} />
        </div>
      </div>
      <div className="row">
        <div className="field">
          <label>Colour</label>
          <input value={value.colour} onChange={(e) => set('colour', e.target.value)} />
        </div>
        <div className="field">
          <label>Secondary colour</label>
          <input
            value={value.secondary_colour || ''}
            onChange={(e) => set('secondary_colour', e.target.value || null)}
          />
        </div>
      </div>
      <div className="row">
        <div className="field">
          <label>Pattern</label>
          <select value={value.pattern} onChange={(e) => set('pattern', e.target.value)}>
            {CLOTHING_PATTERNS.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label>Style</label>
          <select value={value.style} onChange={(e) => set('style', e.target.value)}>
            {CLOTHING_STYLES.map((s) => (
              <option key={s} value={s}>
                {s.replace(/_/g, ' ')}
              </option>
            ))}
          </select>
        </div>
      </div>
      <div className="row">
        <div className="field">
          <label>Sleeve type</label>
          <input
            value={value.sleeve_type || ''}
            onChange={(e) => set('sleeve_type', e.target.value || null)}
          />
        </div>
        <div className="field">
          <label>Material</label>
          <input
            value={value.material || ''}
            onChange={(e) => set('material', e.target.value || null)}
          />
        </div>
        <div className="field">
          <label>Formality (0–1)</label>
          <input
            type="number"
            min={0}
            max={1}
            step={0.05}
            value={value.formality}
            onChange={(e) => set('formality', Number(e.target.value))}
          />
        </div>
      </div>
    </div>
  );
}
