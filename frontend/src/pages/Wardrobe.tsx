import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { WardrobeCard } from '../components/WardrobeCard';
import { ErrorAlert } from '../components/ErrorAlert';
import { LoadingSkeleton } from '../components/LoadingSkeleton';
import { deleteWardrobeItem, listWardrobe } from '../services/wardrobeService';
import { extractErrorMessage } from '../services/api';
import { CLOTHING_CATEGORIES, CLOTHING_PATTERNS, CLOTHING_STYLES } from '../constants/clothing';
import type { WardrobeItem } from '../types';

export function Wardrobe() {
  const [items, setItems] = useState<WardrobeItem[]>([]);
  const [category, setCategory] = useState('');
  const [colour, setColour] = useState('');
  const [style, setStyle] = useState('');
  const [pattern, setPattern] = useState('');
  const [search, setSearch] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await listWardrobe({
        category: category || undefined,
        colour: colour.trim() || undefined,
        style: style || undefined,
        pattern: pattern || undefined,
      });
      setItems(data);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [category, colour, style, pattern]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return items;
    return items.filter((i) =>
      `${i.type} ${i.colour} ${i.category} ${i.style} ${i.pattern} ${i.material || ''} ${i.wardrobe_code}`
        .toLowerCase()
        .includes(q)
    );
  }, [items, search]);

  const onDelete = async (id: number) => {
    if (!confirm('Delete this wardrobe item?')) return;
    try {
      await deleteWardrobeItem(id);
      setItems((prev) => prev.filter((i) => i.id !== id));
    } catch (err) {
      setError(extractErrorMessage(err));
    }
  };

  return (
    <div className="page">
      <div className="page-header row" style={{ justifyContent: 'space-between' }}>
        <div>
          <h1>Wardrobe</h1>
          <p>Browse owned clothing with AI attributes you can edit and confirm.</p>
        </div>
        <Link className="btn btn-primary" to="/wardrobe/add">
          Add Clothing
        </Link>
      </div>

      <ErrorAlert message={error} />

      <div className="panel" style={{ marginBottom: '1rem' }}>
        <div className="row">
          <div className="field">
            <label>Search</label>
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="blouse, checked, beige…"
            />
          </div>
          <div className="field">
            <label>Category</label>
            <select value={category} onChange={(e) => setCategory(e.target.value)}>
              <option value="">All</option>
              {CLOTHING_CATEGORIES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label>Colour</label>
            <input value={colour} onChange={(e) => setColour(e.target.value)} placeholder="black" />
          </div>
          <div className="field">
            <label>Style</label>
            <select value={style} onChange={(e) => setStyle(e.target.value)}>
              <option value="">All</option>
              {CLOTHING_STYLES.map((s) => (
                <option key={s} value={s}>
                  {s.replace(/_/g, ' ')}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label>Pattern</label>
            <select value={pattern} onChange={(e) => setPattern(e.target.value)}>
              <option value="">All</option>
              {CLOTHING_PATTERNS.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {loading ? (
        <LoadingSkeleton rows={5} />
      ) : filtered.length === 0 ? (
        <div className="panel">
          <p className="meta">No wardrobe items match these filters.</p>
        </div>
      ) : (
        <div className="wardrobe-grid">
          {filtered.map((item) => (
            <WardrobeCard key={item.id} item={item} onDelete={onDelete} />
          ))}
        </div>
      )}
    </div>
  );
}
