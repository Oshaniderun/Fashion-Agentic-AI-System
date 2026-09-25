import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { FashionRequestForm } from '../components/FashionRequestForm';
import { ErrorAlert } from '../components/ErrorAlert';
import { analyzeRequest } from '../services/analysisService';
import { extractErrorMessage } from '../services/api';
import type { FashionRequestInput } from '../types';

export function FashionRequest() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const onSubmit = async (payload: FashionRequestInput) => {
    setLoading(true);
    setError('');
    try {
      const result = await analyzeRequest(payload);
      sessionStorage.setItem(`analysis:${result.request_id}`, JSON.stringify(result));
      navigate(`/analysis/${result.request_id}`);
    } catch (err) {
      setError(extractErrorMessage(err, 'Analysis failed'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page">
      <div className="page-header">
        <h1>Fashion Request</h1>
        <p>Describe the outfit you need in natural language.</p>
      </div>
      <ErrorAlert message={error} />
      <div className="panel" style={{ maxWidth: 820 }}>
        <FashionRequestForm onSubmit={onSubmit} loading={loading} />
      </div>
    </div>
  );
}
