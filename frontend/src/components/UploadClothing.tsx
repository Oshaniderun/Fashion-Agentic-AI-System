import { useRef, useState, type DragEvent, type ChangeEvent } from 'react';
import { Upload } from 'lucide-react';

interface Props {
  onFile: (file: File) => void;
  disabled?: boolean;
}

export function UploadClothing({ onFile, disabled }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [active, setActive] = useState(false);

  const accept = (file?: File | null) => {
    if (!file || disabled) return;
    onFile(file);
  };

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setActive(false);
    accept(e.dataTransfer.files?.[0]);
  };

  const onChange = (e: ChangeEvent<HTMLInputElement>) => {
    accept(e.target.files?.[0]);
  };

  return (
    <div
      className={`dropzone ${active ? 'active' : ''}`}
      onDragOver={(e) => {
        e.preventDefault();
        setActive(true);
      }}
      onDragLeave={() => setActive(false)}
      onDrop={onDrop}
      onClick={() => inputRef.current?.click()}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === 'Enter' && inputRef.current?.click()}
    >
      <Upload size={28} style={{ margin: '0 auto 0.6rem', color: 'var(--accent)' }} />
      <strong>Drop clothing image here</strong>
      <p className="meta">JPG, PNG, or WEBP · max 10MB</p>
      <input
        ref={inputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp,.jpg,.jpeg,.png,.webp"
        hidden
        onChange={onChange}
        disabled={disabled}
      />
    </div>
  );
}
