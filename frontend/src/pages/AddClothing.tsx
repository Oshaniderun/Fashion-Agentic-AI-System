import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { UploadClothing } from '../components/UploadClothing';
import { ClothingAttributeEditor } from '../components/ClothingAttributeEditor';
import { ConfidenceBadge } from '../components/ConfidenceBadge';
import { ErrorAlert } from '../components/ErrorAlert';
import { createWardrobeItem, uploadAndAnalyze } from '../services/wardrobeService';
import { extractErrorMessage, imageUrl } from '../services/api';
import type { ClothingAttributes, ImageAnalysisDraft } from '../types';

export function AddClothing() {
  const navigate = useNavigate();
  const [draft, setDraft] = useState<ImageAnalysisDraft | null>(null);
  const [attrs, setAttrs] = useState<ClothingAttributes | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  const onFile = async (file: File) => {
    setError('');
    setLoading(true);
    setPreviewUrl(URL.createObjectURL(file));
    try {
      const result = await uploadAndAnalyze(file);
      setDraft(result);
      setAttrs(result.detected_attributes);
    } catch (err) {
      setError(extractErrorMessage(err, 'Image analysis failed'));
      setDraft(null);
      setAttrs(null);
    } finally {
      setLoading(false);
    }
  };

  const onSave = async () => {
    if (!draft || !attrs) return;
    setSaving(true);
    setError('');
    try {
      const item = await createWardrobeItem({
        image_path: draft.image_url,
        category: attrs.category,
        type: attrs.type,
        colour: attrs.colour,
        secondary_colour: attrs.secondary_colour,
        pattern: attrs.pattern,
        style: attrs.style,
        sleeve_type: attrs.sleeve_type,
        formality: attrs.formality,
        material: attrs.material,
        confidence: attrs.confidence,
        attributes_confirmed: true,
      });
      navigate(`/wardrobe/${item.id}`);
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not save wardrobe item'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="page">
      <div className="page-header">
        <h1>Add Clothing</h1>
        <p>Upload → AI detects attributes → you confirm or edit → save to wardrobe.</p>
      </div>

      <ErrorAlert message={error} />

      <div className="split-2">
        <div className="panel stack">
          <h2>1. Upload image</h2>
          <UploadClothing onFile={onFile} disabled={loading} />
          {(previewUrl || draft) && (
            <img
              src={previewUrl || imageUrl(draft?.image_url)}
              alt="Upload preview"
              style={{ borderRadius: 12, maxHeight: 320, objectFit: 'cover', width: '100%' }}
            />
          )}
          {loading && <p className="meta">Analyzing image…</p>}
        </div>

        <div className="panel stack">
          <div className="row" style={{ justifyContent: 'space-between' }}>
            <h2 style={{ margin: 0 }}>2. Review attributes</h2>
            {attrs && <ConfidenceBadge value={attrs.confidence} />}
          </div>
          {attrs ? (
            <>
              <ClothingAttributeEditor value={attrs} onChange={setAttrs} aiDetected />
              <button className="btn btn-primary" type="button" onClick={onSave} disabled={saving}>
                {saving ? 'Saving…' : 'Save to Wardrobe'}
              </button>
            </>
          ) : (
            <p className="meta">Upload an image to see AI-detected attributes here.</p>
          )}
        </div>
      </div>
    </div>
  );
}
