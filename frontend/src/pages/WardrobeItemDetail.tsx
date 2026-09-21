import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ClothingAttributeEditor } from '../components/ClothingAttributeEditor';
import { ConfidenceBadge } from '../components/ConfidenceBadge';
import { ErrorAlert } from '../components/ErrorAlert';
import { LoadingSkeleton } from '../components/LoadingSkeleton';
import {
  deleteWardrobeItem,
  getWardrobeItem,
  updateWardrobeItem,
} from '../services/wardrobeService';
import { extractErrorMessage, imageUrl } from '../services/api';
import type { ClothingAttributes, WardrobeItem } from '../types';

export function WardrobeItemDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [item, setItem] = useState<WardrobeItem | null>(null);
  const [attrs, setAttrs] = useState<ClothingAttributes | null>(null);
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!id) return;
    getWardrobeItem(Number(id))
      .then((data) => {
        setItem(data);
        setAttrs({
          category: data.category,
          type: data.type,
          colour: data.colour,
          secondary_colour: data.secondary_colour,
          pattern: data.pattern,
          style: data.style,
          sleeve_type: data.sleeve_type,
          formality: data.formality,
          material: data.material,
          confidence: data.confidence,
        });
      })
      .catch((err) => setError(extractErrorMessage(err)))
      .finally(() => setLoading(false));
  }, [id]);

  const onSave = async () => {
    if (!item || !attrs) return;
    setSaving(true);
    setError('');
    try {
      const updated = await updateWardrobeItem(item.id, attrs);
      setItem(updated);
      setEditing(false);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  const onDelete = async () => {
    if (!item || !confirm('Delete this item permanently?')) return;
    await deleteWardrobeItem(item.id);
    navigate('/wardrobe');
  };

  if (loading) {
    return (
      <div className="page">
        <LoadingSkeleton rows={6} />
      </div>
    );
  }

  if (!item || !attrs) {
    return (
      <div className="page">
        <ErrorAlert message={error || 'Item not found'} />
        <Link to="/wardrobe" className="btn btn-secondary">
          Back to wardrobe
        </Link>
      </div>
    );
  }

  return (
    <div className="page">
      <div className="page-header row" style={{ justifyContent: 'space-between' }}>
        <div>
          <h1 style={{ textTransform: 'capitalize' }}>
            {item.colour} {item.type}
          </h1>
          <p>
            {item.wardrobe_code} ·{' '}
            {item.attributes_confirmed ? 'User-confirmed attributes' : 'AI-detected only'}
          </p>
        </div>
        <ConfidenceBadge value={item.confidence} />
      </div>

      <ErrorAlert message={error} />

      <div className="split-2">
        <div className="panel">
          <img
            src={imageUrl(item.image_url)}
            alt={`${item.colour} ${item.type}`}
            style={{ width: '100%', borderRadius: 12, objectFit: 'cover' }}
          />
        </div>
        <div className="panel stack">
          {editing ? (
            <>
              <ClothingAttributeEditor value={attrs} onChange={setAttrs} />
              <div className="row">
                <button className="btn btn-primary" type="button" onClick={onSave} disabled={saving}>
                  {saving ? 'Saving…' : 'Save changes'}
                </button>
                <button className="btn btn-ghost" type="button" onClick={() => setEditing(false)}>
                  Cancel
                </button>
              </div>
            </>
          ) : (
            <>
              <div className="stack" style={{ gap: 8 }}>
                {[
                  ['Category', item.category],
                  ['Type', item.type],
                  ['Colour', item.colour],
                  ['Pattern', item.pattern],
                  ['Style', item.style.replace(/_/g, ' ')],
                  ['Sleeve', item.sleeve_type || '—'],
                  ['Material', item.material || '—'],
                  ['Formality', item.formality.toFixed(2)],
                ].map(([k, v]) => (
                  <div key={k} className="row" style={{ justifyContent: 'space-between' }}>
                    <span className="meta">{k}</span>
                    <strong style={{ textTransform: 'capitalize' }}>{v}</strong>
                  </div>
                ))}
              </div>
              <div className="row">
                <button className="btn btn-primary" type="button" onClick={() => setEditing(true)}>
                  Edit
                </button>
                <button className="btn btn-danger" type="button" onClick={onDelete}>
                  Delete
                </button>
                <Link className="btn btn-ghost" to="/wardrobe">
                  Back
                </Link>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
