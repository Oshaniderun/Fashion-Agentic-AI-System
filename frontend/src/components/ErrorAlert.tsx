import { AlertCircle } from 'lucide-react';

export function ErrorAlert({ message }: { message: string }) {
  if (!message) return null;
  return (
    <div className="alert alert-error" role="alert">
      <strong style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
        <AlertCircle size={16} /> Error
      </strong>
      <div style={{ marginTop: 4 }}>{message}</div>
    </div>
  );
}
