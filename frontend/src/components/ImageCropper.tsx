import { useEffect, useRef, useState } from 'react';

interface Props {
  /** Object URL or data URL of the selected image */
  src: string;
  disabled?: boolean;
  onCancel: () => void;
  /** Called with a cropped JPEG File ready for upload/analyze */
  onCropped: (file: File) => void;
}

/**
 * Lightweight crop tool (no extra npm deps).
 * Drag the box to move; drag corners to resize; then Crop & Analyze.
 */
export function ImageCropper({ src, disabled, onCancel, onCropped }: Props) {
  const imgRef = useRef<HTMLImageElement>(null);
  const [natural, setNatural] = useState({ w: 0, h: 0 });
  // Crop box in natural image pixels
  const [box, setBox] = useState({ x: 0, y: 0, w: 0, h: 0 });
  const drag = useRef<{
    mode: 'move' | 'se' | 'sw' | 'ne' | 'nw';
    startX: number;
    startY: number;
    orig: { x: number; y: number; w: number; h: number };
  } | null>(null);

  useEffect(() => {
    const img = new Image();
    img.onload = () => {
      const w = img.naturalWidth;
      const h = img.naturalHeight;
      setNatural({ w, h });
      // Default: centered 80% crop
      const cw = Math.round(w * 0.8);
      const ch = Math.round(h * 0.8);
      setBox({
        x: Math.round((w - cw) / 2),
        y: Math.round((h - ch) / 2),
        w: cw,
        h: ch,
      });
    };
    img.src = src;
  }, [src]);

  const displayWidth = 360;
  const scale = natural.w > 0 ? displayWidth / natural.w : 1;
  const displayHeight = natural.h * scale;

  const clampBox = (next: { x: number; y: number; w: number; h: number }) => {
    const minSize = Math.max(40, Math.round(Math.min(natural.w, natural.h) * 0.15));
    let { x, y, w, h } = next;
    w = Math.max(minSize, Math.min(w, natural.w));
    h = Math.max(minSize, Math.min(h, natural.h));
    x = Math.max(0, Math.min(x, natural.w - w));
    y = Math.max(0, Math.min(y, natural.h - h));
    return { x, y, w, h };
  };

  const onPointerDown = (
    e: React.PointerEvent,
    mode: 'move' | 'se' | 'sw' | 'ne' | 'nw'
  ) => {
    if (disabled) return;
    e.preventDefault();
    e.stopPropagation();
    (e.target as HTMLElement).setPointerCapture?.(e.pointerId);
    drag.current = {
      mode,
      startX: e.clientX,
      startY: e.clientY,
      orig: { ...box },
    };
  };

  const onPointerMove = (e: React.PointerEvent) => {
    if (!drag.current) return;
    const dx = (e.clientX - drag.current.startX) / scale;
    const dy = (e.clientY - drag.current.startY) / scale;
    const o = drag.current.orig;
    let next = { ...o };

    if (drag.current.mode === 'move') {
      next = { x: o.x + dx, y: o.y + dy, w: o.w, h: o.h };
    } else if (drag.current.mode === 'se') {
      next = { x: o.x, y: o.y, w: o.w + dx, h: o.h + dy };
    } else if (drag.current.mode === 'sw') {
      next = { x: o.x + dx, y: o.y, w: o.w - dx, h: o.h + dy };
    } else if (drag.current.mode === 'ne') {
      next = { x: o.x, y: o.y + dy, w: o.w + dx, h: o.h - dy };
    } else if (drag.current.mode === 'nw') {
      next = { x: o.x + dx, y: o.y + dy, w: o.w - dx, h: o.h - dy };
    }
    setBox(clampBox(next));
  };

  const onPointerUp = () => {
    drag.current = null;
  };

  const applyCrop = async () => {
    const img = imgRef.current;
    if (!img || !box.w || !box.h) return;
    const canvas = document.createElement('canvas');
    canvas.width = box.w;
    canvas.height = box.h;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.drawImage(img, box.x, box.y, box.w, box.h, 0, 0, box.w, box.h);
    const blob = await new Promise<Blob | null>((resolve) =>
      canvas.toBlob((b) => resolve(b), 'image/jpeg', 0.92)
    );
    if (!blob) return;
    onCropped(new File([blob], 'cropped-clothing.jpg', { type: 'image/jpeg' }));
  };

  const useFull = async () => {
    const img = imgRef.current;
    if (!img) return;
    const canvas = document.createElement('canvas');
    canvas.width = natural.w;
    canvas.height = natural.h;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.drawImage(img, 0, 0);
    const blob = await new Promise<Blob | null>((resolve) =>
      canvas.toBlob((b) => resolve(b), 'image/jpeg', 0.92)
    );
    if (!blob) return;
    onCropped(new File([blob], 'clothing.jpg', { type: 'image/jpeg' }));
  };

  if (!natural.w) {
    return <p className="meta">Loading image for crop…</p>;
  }

  return (
    <div className="stack">
      <p className="meta">
        Drag the box to frame the garment. Cropping out background improves colour/category detection.
      </p>
      <div
        style={{
          position: 'relative',
          width: displayWidth,
          height: displayHeight,
          maxWidth: '100%',
          userSelect: 'none',
          touchAction: 'none',
        }}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerLeave={onPointerUp}
      >
        <img
          ref={imgRef}
          src={src}
          alt="Crop source"
          width={displayWidth}
          height={displayHeight}
          draggable={false}
          style={{ display: 'block', borderRadius: 8 }}
        />
        <div
          style={{
            position: 'absolute',
            left: box.x * scale,
            top: box.y * scale,
            width: box.w * scale,
            height: box.h * scale,
            border: '2px solid var(--accent)',
            boxShadow: '0 0 0 9999px rgba(18, 24, 31, 0.45)',
            cursor: 'move',
            borderRadius: 4,
          }}
          onPointerDown={(e) => onPointerDown(e, 'move')}
        >
          {(['nw', 'ne', 'sw', 'se'] as const).map((corner) => (
            <span
              key={corner}
              onPointerDown={(e) => onPointerDown(e, corner)}
              style={{
                position: 'absolute',
                width: 14,
                height: 14,
                background: '#fff',
                border: '2px solid var(--accent)',
                borderRadius: 2,
                ...(corner === 'nw' ? { left: -7, top: -7, cursor: 'nwse-resize' } : {}),
                ...(corner === 'ne' ? { right: -7, top: -7, cursor: 'nesw-resize' } : {}),
                ...(corner === 'sw' ? { left: -7, bottom: -7, cursor: 'nesw-resize' } : {}),
                ...(corner === 'se' ? { right: -7, bottom: -7, cursor: 'nwse-resize' } : {}),
              }}
            />
          ))}
        </div>
      </div>
      <div className="row">
        <button type="button" className="btn btn-primary" disabled={disabled} onClick={applyCrop}>
          Crop & Analyze
        </button>
        <button type="button" className="btn btn-secondary" disabled={disabled} onClick={useFull}>
          Use full image
        </button>
        <button type="button" className="btn btn-ghost" disabled={disabled} onClick={onCancel}>
          Cancel
        </button>
      </div>
    </div>
  );
}
