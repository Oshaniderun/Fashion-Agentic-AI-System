import { useState } from 'react';
import type { FashionRequestInput } from '../types';

const SAMPLE_PROMPTS = [
  'I need something elegant but not too formal for my cousin\'s engagement. I don\'t want bright colours.',
  'I need something formal for an interview like a blouse and a bottom pant.',
];

interface Props {
  onSubmit: (payload: FashionRequestInput) => Promise<void> | void;
  loading?: boolean;
}

export function FashionRequestForm({ onSubmit, loading }: Props) {
  const [query, setQuery] = useState(SAMPLE_PROMPTS[0]);
  const [occasion, setOccasion] = useState('');
  const [style, setStyle] = useState('');
  const [colour, setColour] = useState('');
  const [budget, setBudget] = useState('');

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    await onSubmit({
      query_text: query.trim(),
      occasion: occasion || null,
      style: style || null,
      colour_preference: colour || null,
      budget: budget ? Number(budget) : null,
    });
  };

  return (
    <form className="stack" onSubmit={submit}>
      <div className="field">
        <label htmlFor="query">Describe what you want…</label>
        <textarea
          id="query"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          required
          minLength={3}
          placeholder="e.g. elegant but not too formal for an engagement"
        />
      </div>

      <div>
        <div className="meta" style={{ marginBottom: 8 }}>
          Sample prompts
        </div>
        <div className="chip-row">
          {SAMPLE_PROMPTS.map((p) => (
            <button
              key={p}
              type="button"
              className={`chip ${query === p ? 'active' : ''}`}
              onClick={() => setQuery(p)}
            >
              {p.length > 48 ? `${p.slice(0, 48)}…` : p}
            </button>
          ))}
        </div>
      </div>

      <div className="row">
        <div className="field">
          <label>Occasion (optional)</label>
          <select value={occasion} onChange={(e) => setOccasion(e.target.value)}>
            <option value="">From text</option>
            <option value="wedding">Wedding</option>
            <option value="engagement">Engagement</option>
            <option value="university">University</option>
            <option value="work">Work</option>
            <option value="casual">Casual</option>
            <option value="party">Party</option>
            <option value="interview">Interview</option>
            <option value="other">Other</option>
          </select>
        </div>
        <div className="field">
          <label>Preferred style (optional)</label>
          <select value={style} onChange={(e) => setStyle(e.target.value)}>
            <option value="">From text</option>
            <option value="casual">Casual</option>
            <option value="smart_casual">Smart Casual</option>
            <option value="formal">Formal</option>
            <option value="semi_formal">Semi-formal</option>
            <option value="elegant">Elegant</option>
            <option value="streetwear">Streetwear</option>
          </select>
        </div>
      </div>

      <div className="row">
        <div className="field">
          <label>Colour preference (optional)</label>
          <select value={colour} onChange={(e) => setColour(e.target.value)}>
            <option value="">From text</option>
            <option value="dark">Dark</option>
            <option value="neutral">Neutral</option>
            <option value="bright">Bright</option>
            <option value="pastel">Pastel</option>
            <option value="black">Black</option>
            <option value="navy">Navy</option>
          </select>
        </div>
        <div className="field">
          <label>Budget USD (optional)</label>
          <input
            type="number"
            min={1}
            value={budget}
            onChange={(e) => setBudget(e.target.value)}
            placeholder="Leave blank if not stated"
          />
        </div>
      </div>

      <button className="btn btn-primary" type="submit" disabled={loading || query.trim().length < 3}>
        {loading ? 'Analyzing…' : 'Analyze Request'}
      </button>
    </form>
  );
}
